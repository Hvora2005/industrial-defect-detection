"""Run defect inference, estimate severity, and annotate the result.
Absence of boxes is not a product quality approval.
"""

import base64
import hashlib
import math
from pathlib import Path
from threading import RLock
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

try:
    from .config import CONF_THRESHOLD, DEFECT_CLASSES, GRAYSCALE, IMG_SIZE, INFERENCE_DEVICE, IOU_THRESHOLD, MODEL_PATH
    from .runtime import resolve_device, synchronize
except ImportError:  # Direct execution/import from backend/.
    from config import CONF_THRESHOLD, DEFECT_CLASSES, GRAYSCALE, IMG_SIZE, INFERENCE_DEVICE, IOU_THRESHOLD, MODEL_PATH
    from runtime import resolve_device, synchronize

# Severity thresholds. A defect is scored on two independent signals -
# how confident the model is, and how much of the product surface it covers.
# Confident detections that also cover a large area are the ones worth
# flagging as CRITICAL; either signal alone at a moderate level is MAJOR;
# everything else is MINOR. Thresholds are deliberately simple/explainable
# rather than a second trained model, since severity here is a business
# rule on top of detection, not a new CV task.
SEVERITY_ORDER = ["MINOR", "MAJOR", "CRITICAL"]
CRITICAL_CONFIDENCE = 85.0
CRITICAL_AREA_RATIO = 0.08
MAJOR_CONFIDENCE = 60.0
MAJOR_AREA_RATIO = 0.05


def classify_severity(confidence_pct: float, area_ratio: float) -> str:
    if confidence_pct >= CRITICAL_CONFIDENCE and area_ratio >= CRITICAL_AREA_RATIO:
        return "CRITICAL"
    if confidence_pct >= MAJOR_CONFIDENCE or area_ratio >= MAJOR_AREA_RATIO:
        return "MAJOR"
    return "MINOR"


class DefectDetector:
    def __init__(self, model_path: str | Path | None = None, *, imgsz: int = IMG_SIZE,
                 grayscale: bool = GRAYSCALE, iou: float = IOU_THRESHOLD, device: str = INFERENCE_DEVICE):
        if imgsz <= 0 or not math.isfinite(iou) or not 0 <= iou <= 1:
            raise ValueError("Image size must be positive and IoU must be between 0 and 1.")
        self.imgsz, self.grayscale, self.iou = imgsz, grayscale, iou
        self.requested_device = device
        self._device = None
        self._lock = RLock()
        self.model_path = Path(model_path) if model_path is not None else MODEL_PATH
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. Supply existing trained defect weights, "
                "or use backend/capture.py --preview-only to test capture without a model."
            )
        if self.model_path.suffix.lower() != ".pt":
            raise ValueError("Expected trained .pt weights; YAML creates an untrained model and is not accepted.")
        from ultralytics import YOLO

        self.model = YOLO(str(self.model_path))
        self.class_names = self.model.names  # {id: name}
        names = list(self.class_names.values())
        if self.model.task != "detect" or len(names) != len(DEFECT_CLASSES) or set(names) != set(DEFECT_CLASSES):
            raise ValueError(
                "Incompatible model: expected a detection model with the six NEU-DET classes "
                f"{DEFECT_CLASSES}; got task={self.model.task}, classes={names}. "
                "Generic COCO weights are not a defect detector."
            )
        self.weights_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()

    def predict(self, image_bgr: np.ndarray, conf: float = CONF_THRESHOLD, device: str | None = None) -> dict:
        # Ultralytics caches its predictor. model.to() resets it when switching
        # device; serialize phone/camera requests so a move cannot race inference.
        selected = resolve_device(device or self.requested_device)
        with self._lock:
            if selected != self._device:
                self.model.to(selected)
                self._device = selected
            synchronize(selected)
            started = perf_counter()
            result = self._predict(image_bgr, conf, selected)
            processing_ms = (perf_counter() - started) * 1000
            result.update(inference_device=selected, processing_ms=round(processing_ms, 3),
                          processing_fps=round(1000 / processing_ms, 2) if processing_ms else 0)
            return result

    def _predict(self, image_bgr: np.ndarray, conf: float, device: str) -> dict:
        """Runs detection on one BGR image (as loaded by cv2.imdecode).
        Returns a JSON-serializable dict with the decision, defects (each
        with a severity rating), overall severity, and an annotated image
        encoded as a base64 JPEG string."""
        if not math.isfinite(conf) or not 0 <= conf <= 1:
            raise ValueError("Confidence must be finite and between 0 and 1.")
        img_h, img_w = image_bgr.shape[:2]
        image_area = float(img_w * img_h)

        model_input = image_bgr
        if self.grayscale:
            gray = np.asarray(Image.fromarray(image_bgr[:, :, ::-1]).convert("L"))
            model_input = np.repeat(gray[:, :, None], 3, axis=2)
        started = perf_counter()
        results = self.model.predict(
            source=model_input,
            imgsz=self.imgsz,
            conf=conf,
            iou=self.iou,
            device=0 if device.startswith("cuda") else "cpu",
            verbose=False,
        )
        synchronize(device)
        inference_ms = (perf_counter() - started) * 1000
        result = results[0]

        defects = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            confidence = round(float(box.conf[0]) * 100, 2)
            area_ratio = ((x2 - x1) * (y2 - y1)) / image_area if image_area > 0 else 0.0
            severity = classify_severity(confidence, area_ratio)

            defects.append({
                "class_name": self.class_names[cls_id],
                "confidence": confidence,
                "severity": severity,
                "bbox": {
                    "x1": round(x1, 1), "y1": round(y1, 1),
                    "x2": round(x2, 1), "y2": round(y2, 1),
                },
            })

        # Sort strongest detection first so the frontend can headline it
        defects.sort(key=lambda d: d["confidence"], reverse=True)

        overall_severity = None
        if defects:
            overall_severity = max(defects, key=lambda d: SEVERITY_ORDER.index(d["severity"]))["severity"]

        annotated_bgr = result.plot(labels=True, conf=True)
        if not defects:
            cv2.putText(annotated_bgr, "NO DETECTIONS - quality unverified", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 255), 1, cv2.LINE_AA)
        annotated_base64 = self._encode_image_base64(annotated_bgr)

        status = "FAIL" if defects else "NO_DETECTIONS"

        return {
            "status": status,
            "message": "Defects detected" if defects else "No detections at this threshold; product quality is unverified.",
            "confidence_threshold": conf,
            "inference_ms": round(inference_ms, 3),
            "defects_found": len(defects),
            "severity": overall_severity,
            "defects": defects,
            "annotated_image": annotated_base64,
        }

    @staticmethod
    def _encode_image_base64(image_bgr: np.ndarray) -> str:
        success, buffer = cv2.imencode(".jpg", image_bgr)
        if not success:
            raise RuntimeError("Failed to encode annotated image to JPEG")
        return base64.b64encode(buffer).decode("utf-8")
