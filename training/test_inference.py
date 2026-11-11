"""
Phase 4: Run the trained YOLO model on sample images, draw bounding boxes,
report detections or unverified absence of detections, and save annotated results.

Usage:
    python training/test_inference.py
    python training/test_inference.py --source dataset/images/test --conf 0.4
"""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from capture import IMAGE_SUFFIXES, load_detector, main as capture_main, parse_args as parse_capture_args


def parse_args():
    parser = argparse.ArgumentParser(description="Test the trained defect detector on sample images")
    parser.add_argument("--model", type=str, default=str(PROJECT_ROOT / "model" / "best.pt"))
    parser.add_argument("--source", type=str, default=str(PROJECT_ROOT / "dataset" / "images" / "test"),
                         help="Folder or single image path to run inference on")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=256)
    parser.add_argument("--out", type=str, default=str(PROJECT_ROOT / "outputs"))
    parser.add_argument("--grayscale", action="store_true")
    parser.add_argument("--iou", type=float, default=0.7)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out)
    source = Path(args.source)
    sources = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES) if source.is_dir() else [source]
    if not sources:
        print(f"ERROR: No images in {source}", file=sys.stderr)
        return 1
    model = None
    for item in sources:
        suffix = ".png" if item.suffix.lower() in IMAGE_SUFFIXES else ".avi"
        options = ["--model", args.model, "--source", str(item), "--conf", str(args.conf),
                   "--device", getattr(args, "device", "auto"),
                   "--imgsz", str(args.imgsz), "--iou", str(args.iou), "--headless",
                   "--output", str(out_dir / f"annotated_{item.name}{suffix}")]
        if args.grayscale:
            options.append("--grayscale")
        if args.overwrite:
            options.append("--overwrite")
        if model is None:
            try:
                model = load_detector(parse_capture_args(options))
            except (OSError, ValueError, RuntimeError) as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1
        code = capture_main(options, local_detector=model)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
