from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import runtime


@pytest.mark.parametrize("requested,available,selected", [("cpu", False, "cpu"), ("cpu", True, "cpu"),
                                                         ("auto", True, "cuda:0"), ("cuda", True, "cuda:0")])
def test_device_selection_is_explicit(monkeypatch, requested, available, selected):
    monkeypatch.setattr(runtime.torch.cuda, "is_available", lambda: available)
    assert runtime.resolve_device(requested) == selected


def test_auto_warns_on_cpu_and_explicit_cuda_never_falls_back(monkeypatch):
    monkeypatch.setattr(runtime.torch.cuda, "is_available", lambda: False)
    with pytest.warns(RuntimeWarning, match="auto is using CPU"):
        assert runtime.resolve_device("auto") == "cpu"
    with pytest.raises(RuntimeError, match="never fall back"):
        runtime.resolve_device("cuda")


def test_unknown_device_is_rejected():
    with pytest.raises(ValueError):
        runtime.resolve_device("gpu")


def test_gpu_status_uses_pytorch_properties(monkeypatch):
    cuda = SimpleNamespace(is_available=lambda: True, device_count=lambda: 1,
                           get_device_name=lambda index: "Mock NVIDIA GPU",
                           get_device_properties=lambda index: SimpleNamespace(total_memory=6 * 1024**3))
    monkeypatch.setattr(runtime, "torch", SimpleNamespace(__version__="test", version=SimpleNamespace(cuda="13.0"), cuda=cuda))
    status = runtime.runtime_status()
    assert status["gpus"] == [{"index": 0, "name": "Mock NVIDIA GPU", "memory_mb": 6144}]


def test_cuda_timing_synchronizes_but_cpu_does_not(monkeypatch):
    synchronize = Mock()
    monkeypatch.setattr(runtime.torch.cuda, "synchronize", synchronize)
    runtime.synchronize("cpu")
    synchronize.assert_not_called()
    runtime.synchronize("cuda:0")
    synchronize.assert_called_once_with(0)
