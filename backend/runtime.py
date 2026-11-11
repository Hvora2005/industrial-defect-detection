"""Explicit CPU/CUDA selection shared by API, CLI, camera and benchmarks."""

import warnings

import torch


def resolve_device(requested: str = "auto") -> str:
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu, or cuda.")
    if requested == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda:0"
    message = "CUDA is unavailable. Check the official CUDA-enabled PyTorch installation and NVIDIA driver."
    if requested == "cuda":
        raise RuntimeError(message + " Explicit CUDA requests never fall back to CPU.")
    warnings.warn(message + " auto is using CPU.", RuntimeWarning, stacklevel=2)
    return "cpu"


def synchronize(device: str):
    if device.startswith("cuda"):
        torch.cuda.synchronize(0)


def runtime_status() -> dict:
    available = torch.cuda.is_available()
    return {
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": available,
        "gpus": [{"index": index, "name": torch.cuda.get_device_name(index),
                  "memory_mb": round(torch.cuda.get_device_properties(index).total_memory / 1024**2)}
                 for index in range(torch.cuda.device_count())] if available else [],
    }
