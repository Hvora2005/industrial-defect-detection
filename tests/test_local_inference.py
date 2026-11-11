"""Inference contract and media exports with deterministic model doubles."""

import base64
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import cv2
import numpy as np
import pytest

import detector
from backend import capture
from tools.create_test_media import create_test_media


@pytest.fixture
def model(tmp_path, monkeypatch):
    weights = tmp_path / "defects.pt"
    weights.write_bytes(b"mock checkpoint")
    box = SimpleNamespace(cls=np.array([2]), conf=np.array([0.875]),
                          xyxy=np.array([[2, 3, 18, 20]], dtype=float))
    plotted = np.full((24, 32, 3), 120, dtype=np.uint8)
    result = SimpleNamespace(boxes=[box], plot=Mock(return_value=plotted))
    yolo = SimpleNamespace(names=dict(enumerate(detector.DEFECT_CLASSES)), task="detect",
                           predict=Mock(return_value=[result]), to=Mock())
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=Mock(return_value=yolo)))
    loaded = detector.DefectDetector(weights, imgsz=640, grayscale=True, iou=0.6, device="cpu")
    return loaded, yolo, result


def test_real_detector_wrapper_boxes_confidence_and_preprocessing(model):
    loaded, yolo, raw = model
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    image[..., 0] = 255
    result = loaded.predict(image, conf=0.17)
    assert result["status"] == "FAIL"
    assert result["defects"][0]["class_name"] == "patches"
    assert result["defects"][0]["confidence"] == 87.5
    assert result["defects"][0]["bbox"] == {"x1": 2, "y1": 3, "x2": 18, "y2": 20}
    options = yolo.predict.call_args.kwargs
    assert (options["conf"], options["imgsz"], options["iou"]) == (0.17, 640, 0.6)
    assert np.array_equal(options["source"][..., 0], options["source"][..., 2])
    assert np.all(options["source"] == 29)  # Pillow luma for pure BGR blue.
    raw.plot.assert_called_once_with(labels=True, conf=True)
    assert capture.annotated_frame(result).shape == image.shape


def test_no_boxes_is_explicit_and_never_a_quality_approval(model):
    loaded, _, raw = model
    raw.boxes = []
    result = loaded.predict(np.zeros((24, 32, 3), dtype=np.uint8))
    assert result["status"] == "NO_DETECTIONS"
    assert result["defects_found"] == 0 and result["severity"] is None
    assert "unverified" in result["message"]
    assert capture.annotated_frame(result).size


@pytest.mark.parametrize("conf", [-0.1, 1.1, float("nan"), float("inf")])
def test_detector_rejects_invalid_threshold(model, conf):
    loaded, yolo, _ = model
    with pytest.raises(ValueError, match="Confidence"):
        loaded.predict(np.zeros((24, 32, 3), dtype=np.uint8), conf=conf)
    yolo.predict.assert_not_called()


def test_switching_device_moves_and_rebuilds_the_cached_predictor(model, monkeypatch):
    loaded, yolo, _ = model
    monkeypatch.setattr(detector, "resolve_device", lambda requested: "cuda:0" if requested == "cuda" else "cpu")
    monkeypatch.setattr(detector, "synchronize", Mock())
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    loaded.predict(frame, device="cpu")
    loaded.predict(frame, device="cpu")
    assert yolo.to.call_count == 1
    result = loaded.predict(frame, device="cuda")
    assert result["inference_device"] == "cuda:0"
    assert yolo.predict.call_args.kwargs["device"] == 0
    loaded.predict(frame, device="cpu")
    assert [call.args[0] for call in yolo.to.call_args_list] == ["cpu", "cuda:0", "cpu"]


@pytest.mark.parametrize("names,task", [({0: "person"}, "detect"),
                                      (dict(enumerate(detector.DEFECT_CLASSES)), "classify")])
def test_rejects_generic_or_wrong_task_weights(tmp_path, monkeypatch, names, task):
    weights = tmp_path / "wrong.pt"
    weights.write_bytes(b"mock")
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda path: SimpleNamespace(names=names, task=task)))
    with pytest.raises(ValueError, match="Incompatible model"):
        detector.DefectDetector(weights)


@pytest.fixture
def offline_model(monkeypatch):
    def predict(frame, conf):
        annotated = frame.copy()
        cv2.rectangle(annotated, (10, 10), (100, 100), (0, 0, 255), 3)
        ok, encoded = cv2.imencode(".jpg", annotated)
        assert ok
        return {"status": "FAIL", "defects_found": 1,
                "defects": [{"class_name": "patches", "confidence": 87.5}],
                "annotated_image": base64.b64encode(encoded).decode("ascii")}
    fake = SimpleNamespace(predict=Mock(side_effect=predict))
    monkeypatch.setattr(capture, "load_detector", lambda args: fake)
    monkeypatch.setattr(capture, "inspect_frame", Mock(side_effect=AssertionError("Offline mode contacted API")))
    return fake


def test_offline_image_saves_annotations_and_forwards_threshold(tmp_path, offline_model):
    image, _ = create_test_media(tmp_path / "input", frames=4)
    output = tmp_path / "out á" / "annotated.png"
    assert capture.main(["--model", "mock.pt", "--source", str(image), "--headless",
                         "--conf", "0.23", "--output", str(output)]) == 0
    assert offline_model.predict.call_args.kwargs["conf"] == 0.23
    saved = list(capture.read_frames(output))[0]
    assert saved[10, 10, 2] > saved[10, 10, 0] + 50


def test_offline_video_saves_every_frame_with_source_fps(tmp_path, offline_model):
    _, video = create_test_media(tmp_path / "input", frames=4)
    output = tmp_path / "annotated.avi"
    assert capture.main(["--model", "mock.pt", "--source", str(video), "--headless",
                         "--interval", "0", "--output", str(output)]) == 0
    frames = list(capture.read_frames(output))
    assert len(frames) == 4 and offline_model.predict.call_count == 4
    with capture.open_capture(str(output)) as reader:
        assert reader.get(cv2.CAP_PROP_FPS) == pytest.approx(10)


def test_missing_weights_fail_without_output_or_download(tmp_path, capsys):
    image, _ = create_test_media(tmp_path, frames=1)
    output = tmp_path / "not-written.png"
    assert capture.main(["--model", str(tmp_path / "missing.pt"), "--source", str(image),
                         "--headless", "--output", str(output)]) == 1
    assert "Model not found" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("extra", [["--conf", "nan"], ["--conf", "1.1"], ["--imgsz", "0"],
                                  ["--iou", "-0.1"], ["--preview-only", "--model", "x.pt"],
                                  ["--output", "x.png"]])
def test_invalid_inference_options(extra):
    with pytest.raises(SystemExit) as exc:
        capture.parse_args(["--source", "input.avi", *extra])
    assert exc.value.code == 2


def test_output_cannot_replace_input_even_with_overwrite(tmp_path):
    image, _ = create_test_media(tmp_path, frames=1)
    original = image.read_bytes()
    with pytest.raises(SystemExit):
        capture.parse_args(["--source", str(image), "--output", str(image), "--overwrite"])
    assert image.read_bytes() == original


def test_existing_output_requires_explicit_overwrite(tmp_path):
    output = tmp_path / "existing.png"
    output.write_bytes(b"keep")
    with pytest.raises(SystemExit):
        capture.parse_args(["--source", "input.png", "--output", str(output)])
    assert output.read_bytes() == b"keep"


def test_yaml_cannot_silently_create_an_untrained_model(tmp_path):
    yaml = tmp_path / "model.yaml"
    yaml.write_text("nc: 6", encoding="utf-8")
    with pytest.raises(ValueError, match="untrained"):
        detector.DefectDetector(yaml)


def test_export_codec_failure_is_reported_and_released(tmp_path, offline_model, monkeypatch, capsys):
    _, video = create_test_media(tmp_path / "input", frames=1)
    writer = Mock()
    writer.isOpened.return_value = False
    monkeypatch.setattr(capture.cv2, "VideoWriter", Mock(return_value=writer))
    assert capture.main(["--model", "mock.pt", "--source", str(video), "--headless",
                         "--output", str(tmp_path / "out.avi")]) == 1
    assert "Cannot create video" in capsys.readouterr().err
    writer.release.assert_called_once()
