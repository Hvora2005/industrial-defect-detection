"""Warm CPU/GPU comparison of one unchanged checkpoint and image. No training or database writes."""

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from capture import read_frames
from detector import DefectDetector
from runtime import runtime_status, synchronize


def summary(values):
    mean = statistics.mean(values)
    return {"mean_ms": round(mean, 3), "median_ms": round(statistics.median(values), 3),
            "approx_fps": round(1000 / mean, 2)}


def benchmark(model, frame, *, device, warmup=5, runs=30, conf=0.4):
    for _ in range(warmup):
        model.predict(frame, conf=conf, device=device)
    selected = "cuda:0" if device == "cuda" else "cpu"
    inference, end_to_end = [], []
    for _ in range(runs):
        synchronize(selected)
        started = perf_counter()
        result = model.predict(frame, conf=conf, device=device)
        synchronize(selected)
        end_to_end.append((perf_counter() - started) * 1000)
        inference.append(result["inference_ms"])
    parameters = next(model.model.model.parameters())
    return {"device": result["inference_device"], "parameter_device": str(parameters.device),
            "parameter_dtype": str(parameters.dtype), "runs": runs, "warmup": warmup,
            "inference": summary(inference), "end_to_end": summary(end_to_end),
            "detections_last_run": result["defects_found"], "inference_samples_ms": inference,
            "end_to_end_samples_ms": end_to_end}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.4)
    parser.add_argument("--iou", type=float, default=0.6)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "benchmark" / "cpu_gpu.json")
    args = parser.parse_args()
    if args.warmup < 1 or args.runs < 1:
        parser.error("warmup and runs must be positive")
    frames = read_frames(args.image)
    try:
        frame = next(frames)
    finally:
        frames.close()
    model = DefectDetector(args.model, imgsz=args.imgsz, grayscale=True, iou=args.iou, device="cpu")
    hardware = runtime_status()
    devices = ["cpu", "cuda"] if hardware["cuda_available"] else ["cpu"]
    report = {"runtime": hardware, "weights": str(args.model), "weights_sha256": model.weights_sha256,
              "image": str(args.image), "imgsz": args.imgsz, "grayscale": True,
              "conf": args.conf, "iou": args.iou,
              "timing": "inference includes YOLO preprocessing, forward and NMS; end_to_end also includes drawing/JPEG. CUDA synchronized. No capture, HTTP, model load or warmup in samples.",
              "results": [benchmark(model, frame, device=device, warmup=args.warmup, runs=args.runs, conf=args.conf)
                          for device in devices]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for result in report["results"]:
        print(result["device"], "YOLO:", result["inference"], "full pipeline:", result["end_to_end"])
    print("Saved:", args.out)


if __name__ == "__main__":
    main()
