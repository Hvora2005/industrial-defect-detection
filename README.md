# AI-Based Industrial Defect Detection Using Phone Camera

A real-time industrial quality-control system that uses a smartphone as a wireless inspection
camera. The phone captures product images over the local Wi-Fi network and sends them to a
laptop, which runs a YOLO object-detection model to classify the product as **PASS** or **FAIL**,
identify the defect type, draw a bounding box, and report a confidence score — all without the
phone doing any AI processing and without any cloud service or internet dependency.

## Table of Contents
- [Project Overview](#project-overview)
- [Problem Statement](#problem-statement)
- [Proposed Solution](#proposed-solution)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Dataset](#dataset)
- [Model & Training](#model--training)
- [Results](#results)
- [Installation](#installation)
- [Usage](#usage)
- [Phone Connection Setup](#phone-connection-setup)
- [API Documentation](#api-documentation)
- [Applications](#applications)
- [Limitations](#limitations)
- [Future Scope](#future-scope)
- [Author](#author)
- [License](#license)

---

## Project Overview

Manual visual inspection on production lines is slow, inconsistent, and expensive to scale.
This project builds an end-to-end computer-vision inspection pipeline that runs entirely on
commodity hardware a student already owns — a phone and a laptop — proving the same
architecture (camera → CV/YOLO → PASS/FAIL decision) that industrial vision-inspection stations
use in production, without requiring an industrial camera, PLC, or conveyor hardware for the MVP.

## Problem Statement

Small manufacturers and student/hobbyist production setups often cannot justify the cost of a
dedicated machine-vision camera and industrial PC for quality control. A system that reuses a
standard smartphone as the camera and a normal laptop as the inference engine removes that
capital barrier while still demonstrating a real, working automated-inspection pipeline.

## Proposed Solution

- The phone opens a web page (no app install) and streams/captures product images.
- Images are sent over the local Wi-Fi network (HTTPS) to a FastAPI server on the laptop.
- The laptop runs a YOLO11 object-detection model trained on real industrial defect imagery.
- The result (PASS/FAIL, defect type, confidence, bounding box) is sent back and displayed on
  the phone, on a separate laptop "monitor" console in real time, and logged to a local database
  for history and statistics.

## Features

- Live phone-camera capture, single-shot "Capture & Inspect", and gallery image upload
- Real YOLO object detection (not just classification) — bounding box + class + confidence
- PASS/FAIL decision logic
- Laptop-side live monitor console (mirrors whatever the phone is inspecting, in real time)
- Inspection history logged to SQLite (timestamp, result, defect type, confidence)
- Statistics dashboard: total inspected, pass/fail counts, defect rate, most common defect,
  defect-type distribution chart
- CSV and PDF report export
- Local HTTPS (self-signed certificate) so phone camera permission works over Wi-Fi
- 100% local network — no cloud service, no internet dependency for inference

## System Architecture

```
Phone Camera
     |
Mobile Web Interface (HTML/CSS/JS, served by the laptop)
     |
Wi-Fi / Local Network (HTTPS)
     |
FastAPI Server (laptop)
     |
Image Decode (OpenCV)
     |
YOLO11 Inference (Ultralytics)
     |
PASS / FAIL Decision + Bounding Boxes
     |
      +------------------------+------------------------+
      |                        |                         |
Annotated JSON result   WebSocket broadcast        SQLite (history)
back to phone            to laptop Monitor page     for /stats, /history
```

**Component roles**
| Component | Responsibility |
|---|---|
| Phone browser | Camera capture only — zero AI processing on-device |
| FastAPI backend (`backend/main.py`) | Receives images, orchestrates detection, serves all pages |
| `backend/detector.py` | Loads the trained YOLO model once, runs inference, draws boxes |
| `backend/database.py` | Persists every inspection to SQLite |
| `backend/reports.py` | Builds CSV/PDF exports from the stored history |
| Laptop Monitor page (`/monitor`) | Live read-only view of whatever the phone just inspected, via WebSocket |
| Dashboard page (`/dashboard`) | Aggregate statistics and history, auto-refreshing |

## Technology Stack

| Layer | Technology |
|---|---|
| Object detection | Ultralytics YOLO11 (nano) |
| Computer vision / image I/O | OpenCV |
| Backend API | FastAPI + Uvicorn |
| Realtime updates | WebSockets |
| Database | SQLite via SQLAlchemy |
| PDF generation | fpdf2 |
| Frontend | Plain HTML / CSS / JavaScript (no build step, no framework) |
| Local HTTPS | Self-signed certificate via `cryptography` |
| Training | PyTorch (CPU), Ultralytics training pipeline |

## Dataset

**NEU-DET Steel Surface Defect Database** — hot-rolled steel strip surface defects.

| | |
|---|---|
| Classes (6) | `crazing`, `inclusion`, `patches`, `pitted_surface`, `rolled-in_scale`, `scratches` |
| Images | 1,800 total (300/class), 200×200 grayscale, plus a 30-image held-out test set |
| Original annotation format | PASCAL VOC (XML bounding boxes) |
| Converted to | YOLO format via `training/convert_voc_to_yolo.py` |
| Split | 1,416 train / 354 val / 30 test |

## Model & Training

- Base model: `yolo11n.pt` (nano — fastest CPU inference, appropriate given no GPU was available)
- Image size: 256px, batch size 16, 60 epochs, CPU-only training
- Training script: `training/train.py` (epochs/imgsz/batch/confidence/device all CLI-configurable)
- Total training time: ~1 hour on an AMD Ryzen 3 7320U (no dedicated GPU)

## Results

All numbers below come directly from `model.val()` on the held-out validation split after
training — see `training/runs/neu_det_run/` for the full training curves and confusion matrix.

| Metric | Value |
|---|---|
| Precision | 0.701 |
| Recall | 0.710 |
| mAP@50 | 0.749 |
| mAP@50-95 | 0.418 |

**Per-class mAP@50**
| Class | mAP@50 |
|---|---|
| patches | 0.937 |
| scratches | 0.883 |
| pitted_surface | 0.859 |
| inclusion | 0.781 |
| rolled-in_scale | 0.625 |
| crazing | 0.408 |

**Inference speed** (measured on the test set, CPU only): ~1.2ms preprocess, ~30ms inference,
~1.5ms postprocess per image (256×256) — roughly 30 FPS of raw model throughput, well within
what's needed for the phone's periodic-capture workflow.

`crazing` is the weakest class — it's a low-contrast, subtle defect type, which is a known
difficulty for this dataset and worth noting explicitly rather than hiding.

## Installation

```powershell
# 1. Clone/open the project, then create a virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (First time only) Train the model, or place a trained model/best.pt
python training/convert_voc_to_yolo.py
python training/train.py --epochs 60 --imgsz 256 --batch 16 --device cpu
```

## Usage

```powershell
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile certs\key.pem --ssl-certfile certs\cert.pem
```

Then open:
- `https://<laptop-ip>:8000/` — phone inspection page
- `https://<laptop-ip>:8000/monitor` — laptop live console
- `https://<laptop-ip>:8000/dashboard` — statistics dashboard, CSV/PDF export

## Phone Connection Setup

1. Connect the phone and laptop to the **same Wi-Fi network** (or use the phone's hotspot).
2. Find the laptop's IPv4 address: `ipconfig` (look under the Wi-Fi adapter).
3. Generate a local HTTPS certificate (once, or whenever the IP changes):
   `python backend/generate_cert.py`
4. Start the server (see Usage above).
5. Allow the app through Windows Firewall if prompted (or add a rule manually — see
   `backend/generate_cert.py` docstring / project notes).
6. On the phone, open `https://<laptop-ip>:8000`, accept the self-signed certificate warning,
   grant camera permission, and start inspecting.

**Troubleshooting**
| Symptom | Likely cause | Fix |
|---|---|---|
| "This site can't be reached" | Firewall blocking the port, or Wi-Fi profile set to Public | Add a firewall rule for the port; check `Get-NetConnectionProfile` |
| Camera permission denied | Page loaded over plain HTTP | Must use HTTPS (self-signed is fine) — phone browsers block camera on non-secure origins |
| Connection refused | Wrong IP, or phone/laptop on different networks | Re-check `ipconfig`, confirm both devices show the same subnet |
| Live feed is laggy | Phone camera capturing at full native resolution | Already mitigated: capture is capped to 640px longest side client-side |

## API Documentation

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Server + model status |
| `/detect` | POST | Run detection on a camera frame/capture (multipart `file`) |
| `/upload` | POST | Run detection on a gallery-uploaded image (multipart `file`) |
| `/history` | GET | Recent inspections (`?limit=N`) |
| `/stats` | GET | Aggregate statistics |
| `/export/csv` | GET | Download full inspection history as CSV |
| `/export/pdf` | GET | Download a formatted PDF report |
| `/ws/monitor` | WebSocket | Live push of every detection result to the laptop console |

## Applications

The same phone-camera-as-sensor concept scales toward real production use by swapping the
phone for a fixed industrial camera, and adding:
- A conveyor belt with a trigger sensor for automatic capture
- A PLC or Arduino/ESP32 interface to actuate a servo-based reject mechanism
- Integration into an existing production-line control system

## Limitations

- CPU-only inference (no GPU on the development laptop) — a GPU would allow larger models and
  higher-resolution training for better accuracy, especially on the weaker `crazing` class
- Single-camera, single-station setup — no multi-camera or multi-line support yet
- No authentication on the API — acceptable for a local-network student project, not production
- Self-signed certificate requires a manual "proceed anyway" on first connection

## Future Scope

- Defect severity scoring, batch inspection mode, video inspection
- Email/Telegram alerts on FAIL
- Product/batch tracking
- Conveyor-belt + Arduino/ESP32 reject-arm prototype
- Edge deployment (e.g. exporting to ONNX/TensorRT for a dedicated inspection PC)

## Author

**Hemin Vora**

## License

This project is licensed under the [MIT License](LICENSE).
