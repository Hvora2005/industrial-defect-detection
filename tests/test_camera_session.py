import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import time
from unittest.mock import Mock
from uuid import uuid4

import cv2
import numpy as np
import pytest

import camera as camera_module
from camera import CameraSession
from capture import CaptureError


def wait_for(session, predicate, seconds=4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        status = session.status()
        if predicate(status):
            return status
        if status["state"] == "error":
            raise AssertionError(status)
        time.sleep(0.01)
    raise AssertionError(session.status())


@pytest.fixture
def session(tmp_path, monkeypatch):
    frame = np.full((48, 64, 3), 100, dtype=np.uint8)
    reader = Mock()
    reader.get.side_effect = lambda prop: {cv2.CAP_PROP_FRAME_WIDTH: 64, cv2.CAP_PROP_FRAME_HEIGHT: 48,
                                          cv2.CAP_PROP_FPS: 60}[prop]
    reader.read.return_value = (True, frame)

    @contextmanager
    def opened(source, backend):
        try:
            yield reader
        finally:
            reader.release()
    monkeypatch.setattr(camera_module, "open_capture", opened)

    def predict(image, conf, device):
        annotated = image.copy()
        cv2.rectangle(annotated, (2, 2), (30, 30), (0, 0, 255), 3)
        ok, encoded = cv2.imencode(".jpg", annotated)
        assert ok
        return {"status": "NO_DETECTIONS", "defects_found": 0, "defects": [], "severity": None,
                "inference_device": "cpu", "inference_ms": 2.5,
                "annotated_image": base64.b64encode(encoded).decode("ascii"), "confidence_threshold": conf}
    current = CameraSession(predict, tmp_path / "captures")
    yield current, reader
    current.stop()


def test_preview_does_not_record_and_manual_retry_records_once(session):
    current, reader = session
    current.start(2, backend="dshow", width=1280, height=720, fps=30, device="cpu")
    state = wait_for(current, lambda s: s["frames_processed"] >= 3)
    assert state["inspections_recorded"] == 0
    assert state["requested"]["width"] == 1280 and state["effective"]["width"] == 64
    assert state["inference_device"] == "cpu" and state["processing_fps"] > 0
    token = str(uuid4())
    record = Mock()
    result, duplicate = current.capture(token, record)
    again, duplicate_again = current.capture(token, record)
    assert not duplicate and duplicate_again and again == result
    record.assert_called_once()
    assert current.status()["inspections_recorded"] == 1
    saved = list(current.capture_dir.glob("*.jpg"))
    assert len(saved) == 2
    raw = cv2.imread(str(current.capture_dir / f"{token}_original.jpg"))
    drawn = cv2.imread(str(current.capture_dir / f"{token}_annotated.jpg"))
    assert raw.shape == drawn.shape and not np.array_equal(raw, drawn)
    current.stop()
    reader.release.assert_called_once()
    with pytest.raises(CaptureError, match="No active"):
        current.capture(str(uuid4()), record)


def test_concurrent_retries_cannot_duplicate_inspection(session):
    current, _ = session
    current.start(0, device="cpu")
    wait_for(current, lambda s: s["frames_processed"] > 0)
    record, token = Mock(), str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: current.capture(token, record), range(2)))
    assert sorted(result[1] for result in results) == [False, True]
    record.assert_called_once()


def test_restart_and_confidence_without_restarting_backend(session):
    current, reader = session
    current.start(0, device="cpu")
    wait_for(current, lambda s: s["frames_processed"] > 0)
    with pytest.raises(CaptureError, match="already active"):
        current.start(1)
    current.set_confidence(0.8)
    result, _ = current.capture(str(uuid4()), Mock())
    assert result["confidence_threshold"] == 0.8
    current.stop()
    current.start(1, device="cpu")
    wait_for(current, lambda s: s["frames_processed"] > 0)
    current.stop()
    assert reader.release.call_count == 2


def test_disconnection_is_reported_and_camera_released(session):
    current, reader = session
    reader.read.return_value = (False, None)
    current.start(0, device="cpu")
    current._thread.join(timeout=2)
    assert current.status()["state"] == "error"
    assert "disconnected" in current.status()["error"]
    assert not current.status()["running"]
    reader.release.assert_called_once()


def test_record_failure_leaves_no_partial_files_or_false_count(session):
    current, _ = session
    current.start(0, device="cpu")
    wait_for(current, lambda s: s["frames_processed"] > 0)
    with pytest.raises(RuntimeError, match="database offline"):
        current.capture(str(uuid4()), Mock(side_effect=RuntimeError("database offline")))
    assert not list(current.capture_dir.glob("*.jpg"))
    assert current.status()["inspections_recorded"] == 0
