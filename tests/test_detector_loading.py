from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest

import detector


def test_missing_weights_explain_capture_only_option(tmp_path, monkeypatch):
    monkeypatch.setattr(detector, "MODEL_PATH", tmp_path / "missing.pt")
    with pytest.raises(FileNotFoundError, match="preview-only"):
        detector.DefectDetector()


def test_existing_weights_are_loaded_without_training(tmp_path, monkeypatch):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fixture, not real model weights")
    model = SimpleNamespace(names={0: "scratches"})
    load = Mock(return_value=model)
    monkeypatch.setattr(detector, "MODEL_PATH", weights)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=load))
    loaded = detector.DefectDetector()
    load.assert_called_once_with(str(weights))
    assert loaded.model is model and loaded.class_names == {0: "scratches"}
