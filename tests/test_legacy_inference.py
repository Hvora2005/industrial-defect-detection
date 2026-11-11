from types import SimpleNamespace
from unittest.mock import Mock

from training import test_inference as legacy


def test_legacy_image_directory_reuses_one_model_and_preserves_options(tmp_path, monkeypatch):
    for name in ("one.png", "two.jpg"):
        (tmp_path / name).write_bytes(b"fixture")
    args = SimpleNamespace(source=str(tmp_path), model="weights.pt", out=str(tmp_path / "out"),
                           conf=0.23, imgsz=640, iou=0.6, grayscale=True, overwrite=False)
    monkeypatch.setattr(legacy, "parse_args", lambda: args)
    model = object()
    loader = Mock(return_value=model)
    run = Mock(return_value=0)
    monkeypatch.setattr(legacy, "load_detector", loader)
    monkeypatch.setattr(legacy, "capture_main", run)
    assert legacy.main() == 0
    assert loader.call_count == 1 and run.call_count == 2
    assert all(call.kwargs["local_detector"] is model for call in run.call_args_list)
    assert all("--grayscale" in call.args[0] for call in run.call_args_list)


def test_empty_legacy_directory_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "parse_args", lambda: SimpleNamespace(source=str(tmp_path), out="out"))
    assert legacy.main() == 1
