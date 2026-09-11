"""Central configuration for the backend server."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "model" / "best.pt"

# Inference settings
CONF_THRESHOLD = 0.4   # matches the threshold used in Phase 4 testing
IMG_SIZE = 256         # matches training image size

# Server settings
HOST = "0.0.0.0"       # bind to all interfaces so the phone can reach it over LAN
PORT = 8000
