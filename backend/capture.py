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


def read_frames(source: int | Path, backend: str = "auto"):
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


def inspect_frame(frame: np.ndarray, api_url: str, timeout: float = 30.0) -> dict:
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
        api_url.rstrip("/") + "/detect",
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
    if not isinstance(result, dict) or result.get("status") not in ("PASS", "FAIL"):
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
    parser.add_argument("--api-url", type=http_url, default="http://127.0.0.1:8000", help="Existing inspection API base URL")
    parser.add_argument("--headless", action="store_true", help="Do not open an OpenCV window")
    parser.add_argument("--max-frames", type=nonnegative_int, default=0, help="Stop after N frames; 0 means until EOF/q/Ctrl+C")
    parser.add_argument("--interval", type=nonnegative_float, default=0.1, help="Delay between frames in seconds (not real-time playback)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    frames = None
    try:
        if args.list_cameras:
            cameras = list_cameras(args.max_index, args.backend)
            print("Readable camera indices: " + ", ".join(map(str, cameras)) if cameras else
                  f"No readable cameras in indices 0..{args.max_index}. Check connection and camera permissions.")
            return 0 if cameras else 1

        mode = "PREVIEW ONLY - no inference or inspection logging" if args.preview_only else "Inspection via " + args.api_url
        print(mode)
        source = args.camera if args.camera is not None else args.source
        frames = read_frames(source, args.backend)
        count = 0
        for frame in frames:
            count += 1
            if args.preview_only:
                print(f"Frame {count}: {frame.shape[1]}x{frame.shape[0]}")
            else:
                result = inspect_frame(frame, args.api_url)
                print(f"Frame {count}: {result['status']} - defects: {result.get('defects_found', '?')}")
                if not args.headless:
                    frame = annotated_frame(result)
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
        return 0
    except KeyboardInterrupt:
        print("Capture stopped.")
        return 130
    except (CaptureError, cv2.error, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if frames is not None:
            frames.close()
        if not args.headless and not args.list_cameras:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                # A build without GUI support may also reject cleanup after
                # imshow failed; preserve the actionable error reported above.
                pass


if __name__ == "__main__":
    raise SystemExit(main())
