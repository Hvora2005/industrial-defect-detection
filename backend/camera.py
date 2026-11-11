"""One server-owned OpenCV source. Preview frames never create inspections."""

from collections import deque
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from time import monotonic
from uuid import UUID

import cv2

try:
    from .capture import CaptureError, annotated_frame, configure_capture, open_capture
except ImportError:
    from capture import CaptureError, annotated_frame, configure_capture, open_capture


class CameraSession:
    def __init__(self, predict, capture_dir: Path):
        self.predict = predict
        self.capture_dir = capture_dir
        self._lock = RLock()
        self._lifecycle = Lock()
        self._inspection = Lock()
        self._stop = Event()
        self._thread = None
        self._raw = None
        self._jpeg = None
        self._conf = 0.4
        self._device = "auto"
        self._records = {}
        self._state = {"state": "stopped", "running": False, "error": None,
                       "frames_processed": 0, "inspections_recorded": 0}

    def status(self) -> dict:
        with self._lock:
            return {**self._state, "confidence": self._conf, "requested_device": self._device}

    def start(self, source: int | Path, *, backend="auto", width=640, height=480, fps=30,
              conf=0.4, device="auto", loop=False) -> dict:
        with self._lifecycle:
            if self._thread is not None and self._thread.is_alive():
                raise CaptureError("Capture is already active. Stop it before changing source.")
            self._stop.clear()
            with self._lock:
                self._raw = self._jpeg = None
                self._conf, self._device = conf, device
                self._state = {"state": "starting", "running": True, "error": None,
                               "source": str(source), "source_type": "camera" if isinstance(source, int) else "video",
                               "frames_processed": 0, "inspections_recorded": 0,
                               "requested": {"width": width, "height": height, "fps": fps}}
            self._thread = Thread(target=self._run, args=(source, backend, width, height, fps, loop), daemon=True)
            self._thread.start()
            return self.status()

    def _run(self, source, backend, width, height, fps, loop):
        samples = deque(maxlen=30)
        try:
            target = source if isinstance(source, int) else str(source)
            with open_capture(target, backend) as reader:
                settings = configure_capture(reader, width, height, fps) if isinstance(source, int) else configure_capture(reader)
                period = 1 / (settings["effective"]["fps"] or fps)
                with self._lock:
                    self._state.update(settings)
                while not self._stop.is_set():
                    started = monotonic()
                    ok, frame = reader.read()
                    if not ok or frame is None or not frame.size:
                        if not isinstance(source, int) and loop:
                            reader.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ok, frame = reader.read()
                        if not ok or frame is None or not frame.size:
                            raise CaptureError("Camera disconnected, busy, or no readable frames remain. Reconnect and start again.")
                    with self._lock:
                        conf, device = self._conf, self._device
                    result = self.predict(frame, conf=conf, device=device)
                    annotated = annotated_frame(result)
                    ok, encoded = cv2.imencode(".jpg", annotated)
                    if not ok:
                        raise CaptureError("Cannot encode camera preview.")
                    samples.append((monotonic() - started) * 1000)
                    with self._lock:
                        self._raw, self._jpeg = frame.copy(), encoded.tobytes()
                        self._state.update(state="running", frames_processed=self._state["frames_processed"] + 1,
                                           frame_width=frame.shape[1], frame_height=frame.shape[0],
                                           inference_device=result.get("inference_device"),
                                           inference_ms=result.get("inference_ms"),
                                           processing_fps=round(1000 / (sum(samples) / len(samples)), 2))
                    self._stop.wait(max(0, period - (monotonic() - started)))
        except Exception as exc:
            with self._lock:
                self._state.update(state="error", error=str(exc))
        finally:
            with self._lock:
                self._state["running"] = False
                if self._state["state"] != "error":
                    self._state["state"] = "stopped"

    def stop(self) -> dict:
        with self._lifecycle:
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=5)
                if self._thread.is_alive():
                    raise CaptureError("Camera driver is still blocked in a read. Capture is stopping; wait before restarting.")
            with self._lock:
                self._state.update(state="stopped", running=False)
                self._raw = None
            return self.status()

    def set_confidence(self, conf: float) -> dict:
        if not 0 <= conf <= 1:
            raise ValueError("Confidence must be between 0 and 1.")
        with self._lock:
            self._conf = conf
        return self.status()

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def capture(self, request_id: str, record) -> tuple[dict, bool]:
        """One explicit operator event; retries with the same UUID reuse the result."""
        request_id = str(UUID(request_id))
        with self._inspection:
            if request_id in self._records:
                return self._records[request_id], True
            with self._lock:
                if not self._state["running"] or self._raw is None:
                    raise CaptureError("No active camera frame. Start capture and wait for the preview.")
                frame, conf, device = self._raw.copy(), self._conf, self._device
            result = self.predict(frame, conf=conf, device=device)
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            original = self.capture_dir / f"{request_id}_original.jpg"
            annotated = self.capture_dir / f"{request_id}_annotated.jpg"
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise CaptureError("Cannot encode original capture.")
            # Exclusive creation protects previous files, including after a restart.
            created = []
            try:
                for path, data in ((original, encoded.tobytes()),
                                   (annotated, self._annotation_bytes(result))):
                    with path.open("xb") as handle:
                        created.append(path)
                        handle.write(data)
                result = {**result, "capture_id": request_id,
                          "captures": {"original_url": f"/captures/{original.name}",
                                       "annotated_url": f"/captures/{annotated.name}"}}
                record(result)
            except Exception:
                for path in created:
                    path.unlink(missing_ok=True)
                raise
            self._records[request_id] = result
            if len(self._records) > 64:
                del self._records[next(iter(self._records))]
            with self._lock:
                self._state["inspections_recorded"] += 1
            return result, False

    @staticmethod
    def _annotation_bytes(result):
        import base64
        return base64.b64decode(result["annotated_image"], validate=True)
