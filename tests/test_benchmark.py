from types import SimpleNamespace
from unittest.mock import Mock

from tools import benchmark_inference as bench


def test_warmup_is_excluded_from_reported_samples(monkeypatch):
    values = iter([1000, 1000, 10, 20])
    predict = Mock(side_effect=lambda *args, **kwargs: {
        "inference_ms": next(values), "inference_device": "cpu", "defects_found": 3})
    model = SimpleNamespace(predict=predict, model=SimpleNamespace(model=SimpleNamespace(
        parameters=lambda: iter([SimpleNamespace(device="cpu", dtype="torch.float32")]))))
    clock = iter([0, 0.01, 0.02, 0.04])
    monkeypatch.setattr(bench, "perf_counter", lambda: next(clock))
    synchronize = Mock()
    monkeypatch.setattr(bench, "synchronize", synchronize)
    result = bench.benchmark(model, object(), device="cpu", warmup=2, runs=2)
    assert result["inference_samples_ms"] == [10, 20]
    assert result["inference"]["mean_ms"] == result["inference"]["median_ms"] == 15
    assert result["parameter_device"] == "cpu" and result["parameter_dtype"] == "torch.float32"
    assert predict.call_count == 4 and synchronize.call_count == 4
