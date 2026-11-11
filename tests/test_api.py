"""Exercise existing routes and the OpenCV protocol without real YOLO weights."""

import base64
from io import BytesIO

import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
import main
from backend import capture


class FakeDetector:
    """A protocol fixture, not evidence of real model accuracy."""

    class_names = {0: "scratches"}

    def predict(self, frame, conf=0.4, device="auto"):
        assert frame.shape == (24, 32, 3)
        ok, encoded = cv2.imencode(".jpg", frame)
        assert ok
        return {"status": "FAIL", "defects_found": 1, "severity": "MINOR", "confidence_threshold": conf,
                "defects": [{"class_name": "scratches", "confidence": 45.0, "severity": "MINOR",
                             "bbox": {"x1": 1, "y1": 2, "x2": 10, "y2": 12}}],
                "annotated_image": base64.b64encode(encoded).decode("ascii")}


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(main, "detector", FakeDetector())
    with TestClient(main.app) as client:
        yield client
    engine.dispose()


@pytest.fixture
def jpeg():
    ok, image = cv2.imencode(".jpg", np.zeros((24, 32, 3), dtype=np.uint8))
    assert ok
    return image.tobytes()


def test_health_without_weights_and_detection_503(client, monkeypatch, jpeg):
    monkeypatch.setattr(main, "detector", None)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "model_loaded": False, "classes": []}
    for endpoint in ("/detect", "/upload"):
        response = client.post(endpoint, files={"file": ("sample.jpg", jpeg, "image/jpeg")})
        assert response.status_code == 503
        assert "preview-only" in response.json()["detail"]
    assert client.get("/stats").json()["total_inspected"] == 0


@pytest.mark.parametrize("endpoint", ["/detect", "/upload"])
def test_existing_upload_routes_persist_and_broadcast(client, jpeg, endpoint):
    assert client.get("/health").json()["model_loaded"] is True
    with client.websocket_connect("/ws/monitor") as monitor:
        response = client.post(endpoint, files={"file": ("frame.jpg", jpeg, "image/jpeg")})
        assert response.status_code == 200
        assert monitor.receive_json() == response.json()
    assert response.json()["status"] == "FAIL"
    rows = client.get("/history").json()["inspections"]
    assert len(rows) == 1 and rows[0]["primary_defect"] == "scratches"
    assert client.get("/stats").json()["fail_count"] == 1


@pytest.mark.parametrize("endpoint", ["/detect", "/upload"])
@pytest.mark.parametrize("body", [b"", b"not an image"])
def test_bad_uploads_do_not_log_inspections(client, endpoint, body):
    assert client.post(endpoint, files={"file": ("bad.jpg", body)}).status_code == 400
    assert client.get("/stats").json()["total_inspected"] == 0


def test_capture_client_protocol_against_real_api_routes(client, monkeypatch):
    def bridge(request, timeout):
        response = client.post("/detect", content=request.data, headers=dict(request.header_items()))
        assert response.status_code == 200
        return BytesIO(response.content)

    monkeypatch.setattr(capture, "urlopen", bridge)
    result = capture.inspect_frame(np.zeros((24, 32, 3), dtype=np.uint8), "http://testserver")
    assert result["status"] == "FAIL"
    assert capture.annotated_frame(result).shape == (24, 32, 3)
    assert client.get("/stats").json()["total_inspected"] == 1


@pytest.mark.parametrize("path", ["/", "/monitor", "/dashboard", "/static/app.js"])
def test_existing_pages_still_served(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("endpoint", ["/detect", "/upload"])
def test_api_forwards_configurable_confidence(client, jpeg, endpoint):
    response = client.post(endpoint + "?conf=0.17", files={"file": ("frame.jpg", jpeg)})
    assert response.status_code == 200
    assert response.json()["confidence_threshold"] == 0.17


@pytest.mark.parametrize("conf", ["-0.1", "1.1", "nan", "inf", "invalid"])
def test_api_rejects_invalid_confidence_without_logging(client, jpeg, conf):
    response = client.post("/detect?conf=" + conf, files={"file": ("frame.jpg", jpeg)})
    assert response.status_code == 422
    assert client.get("/stats").json()["total_inspected"] == 0


def test_no_detections_are_neither_pass_nor_fail_in_history_stats_trends_and_reports(client, monkeypatch, jpeg):
    fake = FakeDetector()
    result = fake.predict(np.zeros((24, 32, 3), dtype=np.uint8))
    result.update(status="NO_DETECTIONS", defects_found=0, defects=[], severity=None)
    fake.predict = lambda frame, conf, device="auto": result
    monkeypatch.setattr(main, "detector", fake)
    with client.websocket_connect("/ws/monitor") as monitor:
        response = client.post("/detect", files={"file": ("frame.jpg", jpeg)})
        assert response.status_code == 200
        assert monitor.receive_json()["status"] == "NO_DETECTIONS"
    stats = client.get("/stats").json()
    assert stats["no_detections_count"] == 1
    assert stats["pass_count"] == stats["fail_count"] == stats["defect_rate"] == 0
    assert client.get("/history").json()["inspections"][0]["status"] == "NO_DETECTIONS"
    bucket = client.get("/trend").json()["buckets"][0]
    assert bucket["no_detections"] == 1 and bucket["pass"] == bucket["fail"] == 0
    assert "NO_DETECTIONS" in client.get("/export/csv").text
    pdf = client.get("/export/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_historical_pass_records_are_preserved_and_not_counted_as_detections(client):
    database.save_inspection({"status": "PASS", "defects_found": 0, "defects": []})
    stats = client.get("/stats").json()
    assert stats["pass_count"] == 1 and stats["fail_count"] == stats["no_detections_count"] == 0


def test_live_preview_does_not_register_each_frame(client, jpeg):
    for _ in range(5):
        assert client.post("/preview?device=cpu", files={"file": ("frame.jpg", jpeg)}).status_code == 200
    assert client.get("/stats").json()["total_inspected"] == 0


def test_camera_listing_and_active_device_protection(client, monkeypatch):
    from unittest.mock import Mock
    probe = Mock(return_value=[0, 2])
    monkeypatch.setattr(main, "list_cameras", probe)
    response = client.get("/cameras?max_index=2&backend=dshow")
    assert [camera["index"] for camera in response.json()["cameras"]] == [0, 2]
    probe.assert_called_once_with(2, "dshow")


def test_explicit_cuda_error_does_not_open_a_camera(client, monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr(main, "resolve_device", Mock(side_effect=RuntimeError("CUDA unavailable")))
    start = Mock()
    monkeypatch.setattr(main.camera, "start", start)
    response = client.post("/camera/start", json={"device": "cuda"})
    assert response.status_code == 409 and "CUDA unavailable" in response.json()["detail"]
    start.assert_not_called()


def test_camera_manual_capture_is_idempotent_and_downloadable(client, tmp_path, monkeypatch):
    from uuid import uuid4
    from camera import CameraSession
    from tools.create_test_media import create_test_media
    from test_camera_session import wait_for
    _, video = create_test_media(tmp_path / "media", frames=4)
    def predict(frame, conf, device):
        result = FakeDetector().predict(np.zeros((24, 32, 3), dtype=np.uint8), conf)
        ok, encoded = cv2.imencode(".jpg", frame)
        assert ok
        result["annotated_image"] = base64.b64encode(encoded).decode("ascii")
        result.update(inference_device="cpu", inference_ms=1)
        return result
    folder = tmp_path / "captures"
    session = CameraSession(predict, folder)
    monkeypatch.setattr(main, "camera", session)
    monkeypatch.setattr(main, "DEMO_VIDEO", video)
    monkeypatch.setattr(main, "CAPTURE_DIR", folder)
    try:
        response = client.post("/camera/start", json={"source_type": "demo", "device": "cpu"})
        assert response.status_code == 200
        wait_for(session, lambda s: s["frames_processed"] >= 2)
        assert client.get("/stats").json()["total_inspected"] == 0
        token = str(uuid4())
        with client.websocket_connect("/ws/monitor") as monitor:
            first = client.post("/camera/capture", json={"request_id": token})
            assert first.status_code == 200
            assert monitor.receive_json()["capture_id"] == token
        second = client.post("/camera/capture", json={"request_id": token})
        assert second.json()["duplicate"] is True
        assert client.get("/stats").json()["total_inspected"] == 1
        for url in first.json()["captures"].values():
            assert client.get(url).headers["content-type"] == "image/jpeg"
        assert client.post("/camera/stop").json()["running"] is False
        assert client.post("/camera/capture", json={"request_id": str(uuid4())}).status_code == 409
    finally:
        session.stop()
