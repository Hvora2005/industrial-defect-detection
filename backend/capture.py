"""OpenCV capture client for Acero Cifrado; reuses the existing /detect API.

Run from the repository root: python backend/capture.py --help
Preview mode never runs inference, sends requests, or records inspections.
"""

import argparse
import base64
from contextlib import contextmanager
import json
import math
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import cv2
import numpy as np


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
BACKENDS = {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}
WINDOW_TITLE = "Acero Cifrado - q / Esc to stop"


class CaptureError(RuntimeError):
    """An actionable capture or server error for the command-line user."""


def configure_capture(capture, width=None, height=None, fps=None) -> dict:
    """Request settings, but report what the driver actually returns."""
    requested = {"width": width, "height": height, "fps": fps}
    properties = {"width": cv2.CAP_PROP_FRAME_WIDTH, "height": cv2.CAP_PROP_FRAME_HEIGHT,
                  "fps": cv2.CAP_PROP_FPS}
    for name, value in requested.items():
        if value is not None:
            capture.set(properties[name], value)
    effective = {}
    for name, prop in properties.items():
        value = capture.get(prop)
        effective[name] = float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None
    return {"requested": requested, "effective": effective}


@contextmanager
def open_capture(source: int | str, backend: str = "auto"):
    """Always release the device/file, including failed opens and reads."""
    capture = cv2.VideoCapture()
    try:
        # Windows camera backends must not be applied to video files.
        api = BACKENDS[backend] if isinstance(source, int) else cv2.CAP_ANY
        if not capture.open(source, api):
            if isinstance(source, int):
                raise CaptureError(
                    f"Cannot open camera {source}. Check the USB connection, Windows camera "
                    "privacy settings, and close other camera apps. Try --backend dshow "
                    "or --backend msmf."
                )
            raise CaptureError(f"Cannot open video: {source}. Check the file and its codec.")
        yield capture
    except cv2.error as exc:
        raise CaptureError(f"OpenCV capture failed: {exc}") from exc
    finally:
        capture.release()


def list_cameras(max_index: int = 5, backend: str = "auto") -> list[int]:
    """Probe indices 0..max_index; only advertise cameras returning a frame."""
    available = []
    for index in range(max_index + 1):
        try:
            with open_capture(index, backend) as capture:
                ok, frame = capture.read()
                if ok and frame is not None and frame.size:
                    available.append(index)
        except CaptureError:
            continue
    return available


def read_frames(source: int | Path, backend: str = "auto", metadata: dict | None = None,
                *, width=None, height=None, fps=None):
    """Yield BGR images. Video EOF is normal; a lost webcam is an error."""
    if isinstance(source, Path):
        if not source.is_file():
            raise CaptureError(f"Local file not found: {source}")
        if source.suffix.lower() in IMAGE_SUFFIXES:
            # imread has path-encoding issues on some Windows builds.
            frame = cv2.imdecode(np.frombuffer(source.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise CaptureError(f"Cannot decode image: {source}")
            yield frame
            return
        source = str(source)

    with open_capture(source, backend) as capture:
        settings = configure_capture(capture, width, height, fps) if isinstance(source, int) else configure_capture(capture)
        if metadata is not None:
            metadata.update(settings)
            metadata["fps"] = settings["effective"]["fps"] or 10.0
        count = 0
        while True:
            ok, frame = capture.read()
            if not ok or frame is None or not frame.size:
                if isinstance(source, int):
                    raise CaptureError(
                        f"Camera {source} stopped returning frames. Reconnect it, close other "
                        "camera apps, then run the command again."
                    )
                if count == 0:
                    raise CaptureError(f"Video contains no readable frames: {source}")
                return
            count += 1
            yield frame


def inspect_frame(frame: np.ndarray, api_url: str, timeout: float = 30.0, conf: float | None = None,
                  device: str | None = None, endpoint: str = "/detect") -> dict:
    """Send a JPEG as the same multipart field used by the phone browser."""
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise CaptureError("Cannot encode captured frame as JPEG.")
    boundary = uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        'filename="frame.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'
    ).encode("ascii") + encoded.tobytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(
        api_url.rstrip("/") + endpoint + (f"?conf={conf}" if conf is not None else "")
        + (("&" if conf is not None else "?") + f"device={device}" if device is not None else ""),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CaptureError(f"Inspection server returned HTTP {exc.code}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise CaptureError(
            f"Cannot reach inspection server at {api_url}: {exc}. Start the API and "
            "check --api-url, or use --preview-only."
        ) from exc
    except (ValueError, UnicodeError) as exc:
        raise CaptureError("Inspection server did not return valid JSON.") from exc
    if not isinstance(result, dict) or result.get("status") not in ("PASS", "FAIL", "NO_DETECTIONS"):
        raise CaptureError("Inspection server returned an invalid inspection result.")
    return result


def annotated_frame(result: dict) -> np.ndarray:
    try:
        data = base64.b64decode(result["annotated_image"], validate=True)
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (KeyError, TypeError, ValueError, cv2.error) as exc:
        raise CaptureError("Inspection server returned an invalid annotated image.") from exc
    if frame is None:
        raise CaptureError("Inspection server returned an unreadable annotated image.")
    return frame


def load_detector(args):
    if __package__:
        from .detector import DefectDetector
    else:
        from detector import DefectDetector
    model = DefectDetector(args.model, imgsz=args.imgsz, grayscale=args.grayscale, iou=args.iou, device=args.device)
    print(f"Model: {model.model_path}\nSHA-256: {model.weights_sha256}\nClasses: {model.class_names}")
    return model


class AnnotatedOutput:
    """Write one annotated image or a video; release the encoder on every exit."""

    def __init__(self, path: Path, *, image: bool, fps: float):
        self.path, self.image, self.fps = path, image, fps
        self.writer = None
        self.size = None

    def write(self, frame: np.ndarray):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.image:
            ok, encoded = cv2.imencode(self.path.suffix, frame)
            if not ok:
                raise CaptureError(f"Cannot encode output image: {self.path}")
            self.path.write_bytes(encoded.tobytes())
            return
        size = (frame.shape[1], frame.shape[0])
        if self.writer is None:
            codec = "MJPG" if self.path.suffix.lower() == ".avi" else "mp4v"
            self.writer = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*codec), self.fps, size)
            self.size = size
            if not self.writer.isOpened():
                raise CaptureError(f"Cannot create video: {self.path}. Try AVI/MJPG or another codec.")
        if size != self.size:
            raise CaptureError("Annotated frame size changed during video export.")
        self.writer.write(frame)

    def close(self):
        if self.writer is not None:
            self.writer.release()


def confidence(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be finite and between 0 and 1")
    return number


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def nonnegative_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be finite and zero or greater")
    return number


def http_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("expected http:// or https:// and a host")
        # Accessing port also validates malformed/non-numeric port numbers.
        parsed.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid API URL: {exc}") from exc
    return value.rstrip("/")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--camera", type=nonnegative_int, help="OpenCV camera index, e.g. 0 or 1")
    sources.add_argument("--source", type=Path, help="Local image or video path (quote paths with spaces)")
    sources.add_argument("--list-cameras", action="store_true", help="Probe for readable cameras")
    parser.add_argument("--max-index", type=nonnegative_int, default=5, help="Last index to probe (inclusive)")
    parser.add_argument("--backend", choices=BACKENDS, default="auto", help="Camera backend; dshow/msmf are Windows-only")
    parser.add_argument("--preview-only", action="store_true", help="Capture only: no model, API, or PASS/FAIL")
    parser.add_argument("--model", type=Path, help="Existing local NEU-DET weights; run directly without the API")
    parser.add_argument("--conf", type=confidence, default=0.4, help="Detection confidence threshold (0..1)")
    parser.add_argument("--imgsz", type=positive_int, default=256, help="Local model input size")
    parser.add_argument("--grayscale", action="store_true", help="Replicate grayscale into three channels before local inference")
    parser.add_argument("--iou", type=confidence, default=0.7, help="Local model NMS IoU threshold")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--width", type=positive_int, help="Requested camera width")
    parser.add_argument("--height", type=positive_int, help="Requested camera height")
    parser.add_argument("--fps", type=positive_int, help="Requested camera FPS")
    parser.add_argument("--output", type=Path, help="Save annotated image or .avi/.mp4 video (inference only)")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output; never replaces the input")
    parser.add_argument("--api-url", type=http_url, default="http://127.0.0.1:8000", help="Existing inspection API base URL")
    parser.add_argument("--headless", action="store_true", help="Do not open an OpenCV window")
    parser.add_argument("--max-frames", type=nonnegative_int, default=0, help="Stop after N frames; 0 means until EOF/q/Ctrl+C")
    parser.add_argument("--interval", type=nonnegative_float, default=0.1, help="Delay between frames in seconds (not real-time playback)")
    args = parser.parse_args(argv)
    if args.preview_only and (args.model or args.output):
        parser.error("--model and --output require inference; remove --preview-only")
    if args.list_cameras and (args.model or args.output):
        parser.error("--model and --output require a capture source")
    if args.output:
        if args.source and args.output.resolve() == args.source.resolve():
            parser.error("output must differ from the input source")
        if args.output.exists() and not args.overwrite:
            parser.error("output exists; choose another path or add --overwrite")
        image = args.source is not None and args.source.suffix.lower() in IMAGE_SUFFIXES
        suffixes = IMAGE_SUFFIXES if image else {".avi", ".mp4"}
        if args.output.suffix.lower() not in suffixes:
            parser.error("output must be an image for image input, or .avi/.mp4 for video/webcam")
    return args


def main(argv=None, *, local_detector=None) -> int:
    args = parse_args(argv)
    frames = None
    output = None
    try:
        if args.list_cameras:
            cameras = list_cameras(args.max_index, args.backend)
            print("Readable camera indices: " + ", ".join(map(str, cameras)) if cameras else
                  f"No readable cameras in indices 0..{args.max_index}. Check connection and camera permissions.")
            return 0 if cameras else 1

        model = local_detector
        if args.model is not None and model is None:
            model = load_detector(args)
        mode = "PREVIEW ONLY - no inference or inspection logging" if args.preview_only else (
            "Local model inference (no database logging)" if model is not None else "Inspection via " + args.api_url)
        print(mode)
        source = args.camera if args.camera is not None else args.source
        metadata = {}
        frames = read_frames(source, args.backend, metadata, width=args.width, height=args.height, fps=args.fps)
        count = 0
        for frame in frames:
            count += 1
            if count == 1 and isinstance(source, int):
                print(f"Camera settings: {metadata}")
            if args.preview_only:
                print(f"Frame {count}: {frame.shape[1]}x{frame.shape[0]}")
            else:
                endpoint = "/detect" if isinstance(source, Path) and source.suffix.lower() in IMAGE_SUFFIXES else "/preview"
                result = model.predict(frame, conf=args.conf) if model is not None else inspect_frame(
                    frame, args.api_url, conf=args.conf, device=args.device, endpoint=endpoint)
                label = "DEFECTS DETECTED" if result["defects_found"] else "NO DETECTIONS - product quality unverified"
                details = "; ".join(f"{d['class_name']} {d['confidence']:.2f}%" for d in result.get("defects", []))
                print(f"Frame {count}: {label} - defects: {result['defects_found']} {details}")
                if "inference_device" in result:
                    print(f"Device: {result['inference_device']} | inference {result['inference_ms']:.2f} ms | processing {result['processing_fps']:.2f} FPS")
                if not args.headless or args.output:
                    frame = annotated_frame(result)
                if args.output:
                    if output is None:
                        output = AnnotatedOutput(args.output, image=isinstance(source, Path) and source.suffix.lower() in IMAGE_SUFFIXES,
                                                 fps=metadata.get("fps", 10.0))
                    output.write(frame)
            if not args.headless:
                cv2.imshow(WINDOW_TITLE, frame)
                # Keep a still image visible until the user presses a key.
                still = isinstance(source, Path) and source.suffix.lower() in IMAGE_SUFFIXES
                key = cv2.waitKey(0 if still else 1) & 0xFF
                if key in (ord("q"), 27) or still or cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                    break
            if args.max_frames and count >= args.max_frames:
                break
            if args.interval:
                time.sleep(args.interval)
        print(f"Finished: {count} frame(s).")
        if output is not None:
            print(f"Annotated output: {args.output}")
        return 0
    except KeyboardInterrupt:
        print("Capture stopped.")
        return 130
    except (CaptureError, cv2.error, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if frames is not None:
            frames.close()
        if output is not None:
            output.close()
        if not args.headless and not args.list_cameras:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                # A build without GUI support may also reject cleanup after
                # imshow failed; preserve the actionable error reported above.
                pass


if __name__ == "__main__":
    raise SystemExit(main())
