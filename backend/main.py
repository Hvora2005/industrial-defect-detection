"""
FastAPI backend for the AI Industrial Defect Detection system.

Run from inside the backend/ folder:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
    GET  /health       -> server + model status
    POST /detect        -> for live camera frames / capture-and-inspect (phone)
    POST /upload         -> for gallery image uploads (phone)
    GET  /monitor       -> laptop console page (live feed + results)
    WS   /ws/monitor     -> pushes every detection result to connected laptop consoles
"""

from pathlib import Path
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID
import re
import time

import numpy as np
import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from detector import DefectDetector
from config import CONF_THRESHOLD, DEMO_VIDEO, INFERENCE_DEVICE, MODEL_PATH, PROJECT_ROOT
from camera import CameraSession
from capture import CaptureError, list_cameras
from runtime import resolve_device, runtime_status
from database import save_inspection, get_recent_inspections, get_stats, get_trend
from reports import build_csv, build_pdf

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
detector = DefectDetector() if MODEL_PATH.is_file() else None
CAPTURE_DIR = PROJECT_ROOT / "outputs" / "captures"


def camera_predict(frame, conf, device):
    if detector is None:
        raise RuntimeError("Defect weights are missing. Configure ACERO_MODEL_PATH and restart.")
    return detector.predict(frame, conf=conf, device=device)


camera = CameraSession(camera_predict, CAPTURE_DIR)


@asynccontextmanager
async def lifespan(app):
    yield
    await run_in_threadpool(camera.stop)

app = FastAPI(title="AI Industrial Defect Detection API", lifespan=lifespan)

# Permissive CORS: the phone browser may load the frontend from the same
# origin, but keeping this open avoids cross-origin surprises during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Laptop "monitor" consoles currently connected. Every /detect and /upload
# result gets pushed to all of them, so the laptop shows the phone's feed
# and detection result live, without the laptop running any AI itself.
monitor_clients: list[WebSocket] = []


async def broadcast_to_monitors(result: dict):
    dead_clients = []
    for client in monitor_clients:
        try:
            await client.send_json(result)
        except Exception:
            dead_clients.append(client)
    for client in dead_clients:
        monitor_clients.remove(client)


async def _read_image_from_upload(file: UploadFile) -> np.ndarray:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    np_array = np.frombuffer(contents, dtype=np.uint8)
    image_bgr = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode image. Is it a valid JPEG/PNG?")
    return image_bgr


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/monitor")
def serve_monitor():
    return FileResponse(str(FRONTEND_DIR / "monitor.html"))


@app.get("/dashboard")
def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": detector is not None,
        "classes": list(detector.class_names.values()) if detector is not None else [],
    }


async def _inspect(image_bgr: np.ndarray, conf: float = CONF_THRESHOLD,
                   device: str = INFERENCE_DEVICE, record: bool = True) -> dict:
    if detector is None:
        raise HTTPException(
            status_code=503,
            detail=f"Defect model missing: {MODEL_PATH}. Supply existing trained weights and "
                   "restart the server. Use capture.py --preview-only for capture tests.",
        )
    try:
        result = await run_in_threadpool(detector.predict, image_bgr, conf=conf, device=device)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if record:
        save_inspection(result)
        await broadcast_to_monitors(result)
    return result


@app.post("/detect")
async def detect(file: UploadFile = File(...), conf: float = Query(CONF_THRESHOLD, ge=0, le=1),
                 device: Literal["auto", "cpu", "cuda"] = INFERENCE_DEVICE):
    """Used for phone frames and the OpenCV capture client."""
    return await _inspect(await _read_image_from_upload(file), conf, device)


@app.post("/upload")
async def upload(file: UploadFile = File(...), conf: float = Query(CONF_THRESHOLD, ge=0, le=1),
                 device: Literal["auto", "cpu", "cuda"] = INFERENCE_DEVICE):
    """Used for gallery image uploads. Same processing as /detect."""
    return await _inspect(await _read_image_from_upload(file), conf, device)


@app.post("/preview")
async def preview(file: UploadFile = File(...), conf: float = Query(CONF_THRESHOLD, ge=0, le=1),
                  device: Literal["auto", "cpu", "cuda"] = INFERENCE_DEVICE):
    """Live frames are predictions, not additional pieces or inspection records."""
    return await _inspect(await _read_image_from_upload(file), conf, device, record=False)


@app.get("/runtime")
def runtime():
    return {**runtime_status(), "model_loaded": detector is not None,
            "requested_device": getattr(detector, "requested_device", INFERENCE_DEVICE),
            "active_device": getattr(detector, "_device", None)}


@app.get("/cameras")
def cameras(max_index: int = Query(5, ge=0, le=16), backend: Literal["auto", "dshow", "msmf"] = "auto"):
    if camera.status()["running"]:
        raise HTTPException(status_code=409, detail="Stop capture before probing cameras.")
    return {"cameras": [{"index": index, "name": f"OpenCV camera {index}"}
                        for index in list_cameras(max_index, backend)],
            "demo_available": DEMO_VIDEO.is_file()}


class CameraStart(BaseModel):
    source_type: Literal["camera", "demo"] = "camera"
    camera_index: int = Field(0, ge=0, le=32)
    backend: Literal["auto", "dshow", "msmf"] = "auto"
    width: int = Field(640, ge=64, le=4096)
    height: int = Field(480, ge=64, le=4096)
    fps: int = Field(30, ge=1, le=120)
    conf: float = Field(CONF_THRESHOLD, ge=0, le=1, allow_inf_nan=False)
    device: Literal["auto", "cpu", "cuda"] = INFERENCE_DEVICE


@app.post("/camera/start")
def start_camera(options: CameraStart):
    if detector is None:
        raise HTTPException(status_code=503, detail="Model missing. Configure ACERO_MODEL_PATH and restart.")
    try:
        resolve_device(options.device)  # Explicit CUDA must fail before opening a source.
        source = options.camera_index if options.source_type == "camera" else DEMO_VIDEO
        if isinstance(source, Path) and not source.is_file():
            raise CaptureError("Demo video missing. Run tools/create_test_media.py first.")
        return camera.start(source, backend=options.backend, width=options.width, height=options.height,
                            fps=options.fps, conf=options.conf, device=options.device,
                            loop=options.source_type == "demo")
    except (CaptureError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/camera/stop")
def stop_camera():
    try:
        return camera.stop()
    except CaptureError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/camera/status")
def camera_status():
    return camera.status()


class CameraSettings(BaseModel):
    conf: float = Field(ge=0, le=1, allow_inf_nan=False)


@app.post("/camera/settings")
def camera_settings(options: CameraSettings):
    return camera.set_confidence(options.conf)


@app.get("/camera/stream")
def camera_stream():
    def frames():
        previous = -1
        while camera.status()["running"]:
            current = camera.status()["frames_processed"]
            data = camera.jpeg()
            if data is not None and current != previous:
                previous = current
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            time.sleep(0.03)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


class ManualCapture(BaseModel):
    request_id: UUID


@app.post("/camera/capture")
async def capture_camera(options: ManualCapture):
    try:
        result, duplicate = await run_in_threadpool(camera.capture, str(options.request_id), save_inspection)
    except (CaptureError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not duplicate:
        await broadcast_to_monitors(result)
    return {**result, "duplicate": duplicate}


@app.get("/captures/{filename}")
def saved_capture(filename: str):
    if not re.fullmatch(r"[0-9a-f-]{36}_(original|annotated)\.jpg", filename):
        raise HTTPException(status_code=404, detail="Capture not found")
    path = CAPTURE_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Capture not found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/history")
def history(limit: int = 50):
    return {"inspections": get_recent_inspections(limit)}


@app.get("/stats")
def stats():
    return get_stats()


@app.get("/trend")
def trend(bucket_seconds: int = 60, limit_buckets: int = 15):
    return {"buckets": get_trend(bucket_seconds, limit_buckets)}


@app.get("/export/csv")
def export_csv():
    csv_text = build_csv()
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inspection_history.csv"},
    )


@app.get("/export/pdf")
def export_pdf():
    pdf_bytes = build_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=inspection_report.pdf"},
    )


@app.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    await websocket.accept()
    monitor_clients.append(websocket)
    try:
        while True:
            # We don't expect the monitor page to send anything, but we need
            # to await something so the connection stays open and we notice
            # a disconnect.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in monitor_clients:
            monitor_clients.remove(websocket)
