"""Create synthetic capture fixtures, never training data or real defects."""

import argparse
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_test_media(output_dir: Path, frames: int = 30) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "sample.png"
    video_path = output_dir / "sample.avi"
    image = np.full((240, 320, 3), 180, dtype=np.uint8)
    cv2.rectangle(image, (70, 70), (250, 190), (90, 90, 90), -1)
    cv2.putText(image, "SYNTHETIC CAPTURE TEST", (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 0, 0), 1)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode test image.")
    image_path.write_bytes(encoded.tobytes())

    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
    try:
        if not writer.isOpened():
            raise RuntimeError("MJPG/AVI codec unavailable; use your own local video instead.")
        for index in range(frames):
            frame = image.copy()
            cv2.circle(frame, (80 + index % 160, 130), 10, (0, 180, 255), -1)
            writer.write(frame)
    finally:
        writer.release()
    return image_path, video_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "outputs" / "demo")
    args = parser.parse_args()
    for path in create_test_media(args.out):
        print(path)


if __name__ == "__main__":
    main()
