"""Wraps the trained YOLO model: runs inference, applies the PASS/FAIL rule,
classifies defect severity, and draws bounding boxes on the image."""

import base64

import cv2
import numpy as np
from ultralytics import YOLO

from config import CONF_THRESHOLD, IMG_SIZE, MODEL_PATH

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
    def __init__(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. Run training/train.py first (Phase 3)."
            )
        self.model = YOLO(str(MODEL_PATH))
        self.class_names = self.model.names  # {id: name}

    def predict(self, image_bgr: np.ndarray, conf: float = CONF_THRESHOLD) -> dict:
        """Runs detection on one BGR image (as loaded by cv2.imdecode).
        Returns a JSON-serializable dict with the decision, defects (each
        with a severity rating), overall severity, and an annotated image
        encoded as a base64 JPEG string."""
        img_h, img_w = image_bgr.shape[:2]
        image_area = float(img_w * img_h)

        results = self.model.predict(
            source=image_bgr,
            imgsz=IMG_SIZE,
            conf=conf,
            verbose=False,
        )
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

        annotated_bgr = result.plot()  # numpy array with boxes/labels drawn
        annotated_base64 = self._encode_image_base64(annotated_bgr)

        status = "FAIL" if len(defects) > 0 else "PASS"

        return {
            "status": status,
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


# Loaded once at import time so every request reuses the same in-memory model
detector = DefectDetector()
