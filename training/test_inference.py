"""
Phase 4: Run the trained YOLO model on sample images, draw bounding boxes,
apply the PASS/FAIL decision rule, and save annotated results.

Usage:
    python training/test_inference.py
    python training/test_inference.py --source dataset/images/test --conf 0.4
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(description="Test the trained defect detector on sample images")
    parser.add_argument("--model", type=str, default=str(PROJECT_ROOT / "model" / "best.pt"))
    parser.add_argument("--source", type=str, default=str(PROJECT_ROOT / "dataset" / "images" / "test"),
                         help="Folder or single image path to run inference on")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=256)
    parser.add_argument("--out", type=str, default=str(PROJECT_ROOT / "outputs"))
    return parser.parse_args()


def main():
    args = parse_args()
    model = YOLO(args.model)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = model.predict(
        source=args.source,
        imgsz=args.imgsz,
        conf=args.conf,
        save=False,  # we draw and save manually so we control filenames/output dir
    )

    print(f"\n{'File':<20} {'Result':<10} {'Defects':<40} {'Count'}")
    print("-" * 90)

    total_images = 0
    total_fail = 0

    for r in results:
        total_images += 1
        image_name = Path(r.path).name
        num_boxes = len(r.boxes)

        defect_summary = []
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            defect_summary.append(f"{cls_name} ({conf * 100:.1f}%)")

        status = "FAIL" if num_boxes > 0 else "PASS"
        if status == "FAIL":
            total_fail += 1

        print(f"{image_name:<20} {status:<10} {', '.join(defect_summary):<40} {num_boxes}")

        # Save annotated image (bounding boxes + labels drawn on it)
        annotated = r.plot()  # BGR numpy array with boxes/labels drawn
        out_path = out_dir / f"annotated_{image_name}"
        import cv2
        cv2.imwrite(str(out_path), annotated)

    print("-" * 90)
    print(f"Total images: {total_images} | PASS: {total_images - total_fail} | FAIL: {total_fail}")
    print(f"\nAnnotated images saved to: {out_dir}")


if __name__ == "__main__":
    main()
