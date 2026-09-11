"""
Trains a YOLO object-detection model on the NEU-DET defect dataset.

Usage examples:
    python training/train.py
    python training/train.py --epochs 100 --imgsz 320 --batch 16 --device cpu
    python training/train.py --model yolo11s.pt --epochs 150 --device 0   (if you have a GPU)

After training, the best weights are copied to model/best.pt for the backend to use.
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = PROJECT_ROOT / "dataset" / "data.yaml"
MODEL_OUT_DIR = PROJECT_ROOT / "model"


def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLO on the industrial defect dataset")
    parser.add_argument("--model", type=str, default="yolo11n.pt",
                         help="Base model to fine-tune (yolo11n.pt = nano, fastest on CPU; "
                              "yolo11s.pt/yolo11m.pt = larger, need a GPU for reasonable speed)")
    parser.add_argument("--epochs", type=int, default=80, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=320, help="Training image size (pixels)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--conf", type=float, default=0.25,
                         help="Confidence threshold used later for validation/prediction display")
    parser.add_argument("--device", type=str, default="cpu",
                         help="'cpu', or GPU index e.g. '0' if you have an NVIDIA GPU with CUDA")
    parser.add_argument("--name", type=str, default="neu_det_run",
                         help="Name of this training run (used for the output folder)")
    parser.add_argument("--patience", type=int, default=20,
                         help="Early-stopping patience (epochs with no improvement)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not DATA_YAML.exists():
        raise SystemExit(
            f"ERROR: {DATA_YAML} not found. Run training/convert_voc_to_yolo.py first (Phase 2)."
        )

    print(f"Loading base model: {args.model}")
    model = YOLO(args.model)  # downloads pretrained COCO weights on first run (transfer learning)

    print(
        f"Starting training | epochs={args.epochs} imgsz={args.imgsz} "
        f"batch={args.batch} device={args.device}"
    )
    model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=args.patience,
        project=str(PROJECT_ROOT / "training" / "runs"),
        name=args.name,
        exist_ok=True,
        plots=True,
    )

    # --- Validate on the val split right after training ---
    print("\nRunning validation...")
    metrics = model.val(data=str(DATA_YAML), imgsz=args.imgsz, device=args.device, conf=args.conf)
    print(f"mAP50:    {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")

    # --- Copy best weights to model/best.pt for the backend ---
    run_dir = PROJECT_ROOT / "training" / "runs" / args.name
    best_weights = run_dir / "weights" / "best.pt"
    if best_weights.exists():
        MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = MODEL_OUT_DIR / "best.pt"
        shutil.copy2(best_weights, dest)
        print(f"\nBest weights copied to: {dest}")
    else:
        print(f"\nWARNING: expected weights not found at {best_weights}")

    print(f"\nFull training run (weights, plots, confusion matrix) saved in: {run_dir}")


if __name__ == "__main__":
    main()
