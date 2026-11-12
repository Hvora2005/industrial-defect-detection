"""Serve the real API/model/frontend in a temporary project, never the user's DB.

This is a validation host, not an alternative backend implementation.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    model = args.model.resolve()
    if not model.is_file() or not (root / "frontend/dist/index.html").is_file():
        raise SystemExit("Supply existing defect weights and build frontend first.")
    os.environ["ACERO_MODEL_PATH"] = str(model)
    os.environ["ACERO_DEVICE"] = args.device
    os.environ["ACERO_DEMO_VIDEO"] = str(root / "outputs/demo/sample.avi")
    with tempfile.TemporaryDirectory(prefix="acero-frontend-validation-") as temporary:
        destination = Path(temporary)
        shutil.copytree(root / "backend", destination / "backend", ignore=shutil.ignore_patterns("__pycache__", "certs"))
        shutil.copytree(root / "frontend/dist", destination / "frontend/dist")
        sys.path.insert(0, str(destination / "backend"))
        import uvicorn
        import main as backend
        print(f"Isolated validation project: {destination}", flush=True)
        uvicorn.run(backend.app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
