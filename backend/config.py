"""Central configuration for the backend server."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = Path(os.environ.get("ACERO_MODEL_PATH", str(PROJECT_ROOT / "model" / "best.pt")))
if not MODEL_PATH.is_absolute():
    MODEL_PATH = PROJECT_ROOT / MODEL_PATH
DEFECT_CLASSES = ("crazing", "inclusion", "patches", "pitted_surface", "rolled-in_scale", "scratches")

# Inference settings
CONF_THRESHOLD = 0.4   # matches the threshold used in Phase 4 testing
IMG_SIZE = int(os.environ.get("ACERO_IMG_SIZE", "256"))
GRAYSCALE = os.environ.get("ACERO_GRAYSCALE", "0") == "1"
IOU_THRESHOLD = float(os.environ.get("ACERO_IOU", "0.7"))
INFERENCE_DEVICE = os.environ.get("ACERO_DEVICE", "auto")
DEMO_VIDEO = PROJECT_ROOT / os.environ.get("ACERO_DEMO_VIDEO", "outputs/demo/sample.avi")

# Server settings
HOST = "0.0.0.0"       # bind to all interfaces so the phone can reach it over LAN
PORT = 8000
