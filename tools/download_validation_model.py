"""Fetch a pinned third-party NEU-DET YOLO11n checkpoint, never the original author's weights."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = "0d3d93d0ec8754d8dacc0585298fab32c4aea940"
URL = f"https://huggingface.co/hazemaaa/steel-defect-yolo11n/resolve/{REVISION}/production/best.pt"
SHA256 = "621c742492ffe5137d214893499e47d59066685c53c400810de71cd26e4f8bac"
DESTINATION = Path(__file__).resolve().parent.parent / "model" / "steel-defect-yolo11n.pt"


def download_model(destination: Path = DESTINATION) -> Path:
    print("Third-party model: hazemaaa/steel-defect-yolo11n (AGPL-3.0). Not Hvora2005's model.")
    if destination.exists():
        data = destination.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise ValueError(f"Checkpoint SHA-256 mismatch: {digest}; no file was written.")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(data)
    print(f"Verified SHA-256: {digest}\nWeights: {destination}")
    return destination


if __name__ == "__main__":
    download_model()
