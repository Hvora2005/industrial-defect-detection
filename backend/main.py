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

import numpy as np
import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from detector import detector
from database import save_inspection, get_recent_inspections, get_stats, get_trend
from reports import build_csv, build_pdf

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="AI Industrial Defect Detection API")

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
        "model_loaded": True,
        "classes": list(detector.class_names.values()),
    }


@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    """Used for live camera frames and 'Capture & Inspect'."""
    image_bgr = await _read_image_from_upload(file)
    result = detector.predict(image_bgr)
    save_inspection(result)
    await broadcast_to_monitors(result)
    return result


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Used for gallery image uploads. Same processing as /detect."""
    image_bgr = await _read_image_from_upload(file)
    result = detector.predict(image_bgr)
    save_inspection(result)
    await broadcast_to_monitors(result)
    return result


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
