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

    def predict(self, frame):
        assert frame.shape == (24, 32, 3)
        ok, encoded = cv2.imencode(".jpg", frame)
        assert ok
        return {"status": "FAIL", "defects_found": 1, "severity": "MINOR",
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
