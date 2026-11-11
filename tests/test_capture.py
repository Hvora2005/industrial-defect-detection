import base64
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import cv2
import numpy as np
import pytest

from backend import capture
from tools.create_test_media import create_test_media


@pytest.fixture
def frame():
    return np.full((24, 32, 3), 120, dtype=np.uint8)


@pytest.fixture
def media(tmp_path):
    return create_test_media(tmp_path / "medios con acentos á", frames=4)


def fake_camera(monkeypatch, reads=(), opened=True):
    device = Mock()
    device.open.return_value = opened
    device.read.side_effect = reads
    monkeypatch.setattr(capture.cv2, "VideoCapture", lambda: device)
    return device


def test_real_local_image_and_video(media):
    image, video = media
    assert [frame.shape for frame in capture.read_frames(image)] == [(240, 320, 3)]
    frames = list(capture.read_frames(video))
    assert len(frames) == 4
    assert all(frame.shape == (240, 320, 3) for frame in frames)
    assert not np.array_equal(frames[0], frames[-1])


def test_preview_never_contacts_api(media, monkeypatch, capsys):
    monkeypatch.setattr(capture, "inspect_frame", Mock(side_effect=AssertionError("Unexpected inference")))
    assert capture.main(["--source", str(media[1]), "--preview-only", "--headless",
                         "--interval", "0"]) == 0
    output = capsys.readouterr().out
    assert "no inference" in output
    assert "Finished: 4 frame(s)" in output
    assert "PASS" not in output and "FAIL" not in output


def test_max_frames_releases_capture(media, monkeypatch):
    real_factory = cv2.VideoCapture
    devices = []

    def factory():
        device = real_factory()
        devices.append(device)
        return device

    monkeypatch.setattr(capture.cv2, "VideoCapture", factory)
    assert capture.main(["--source", str(media[1]), "--preview-only", "--headless",
                         "--max-frames", "2", "--interval", "0"]) == 0
    assert devices and all(not device.isOpened() for device in devices)


def test_camera_selection_and_disconnection_release(monkeypatch, frame):
    device = fake_camera(monkeypatch, [(True, frame), (False, None)])
    frames = capture.read_frames(2, "dshow")
    assert next(frames) is frame
    with pytest.raises(capture.CaptureError, match="stopped returning frames"):
        next(frames)
    device.open.assert_called_once_with(2, cv2.CAP_DSHOW)
    device.release.assert_called_once()


def test_camera_open_failure_is_actionable_and_releases(monkeypatch):
    device = fake_camera(monkeypatch, opened=False)
    with pytest.raises(capture.CaptureError, match="Windows camera privacy"):
        next(capture.read_frames(7))
    device.release.assert_called_once()


def test_camera_discovery_requires_a_frame_and_releases(monkeypatch, frame):
    devices = [Mock(), Mock(), Mock()]
    devices[0].open.return_value = False
    devices[1].open.return_value = True
    devices[1].read.return_value = (False, None)
    devices[2].open.return_value = True
    devices[2].read.return_value = (True, frame)
    monkeypatch.setattr(capture.cv2, "VideoCapture", Mock(side_effect=devices))
    assert capture.list_cameras(max_index=2, backend="msmf") == [2]
    for device in devices:
        device.release.assert_called_once()


def test_no_cameras_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(capture, "list_cameras", lambda *args: [])
    assert capture.main(["--list-cameras"]) == 1
    assert "No readable cameras" in capsys.readouterr().out


def test_video_does_not_use_windows_camera_backend(tmp_path, monkeypatch, frame):
    video = tmp_path / "test.avi"
    video.touch()
    device = fake_camera(monkeypatch, [(True, frame), (False, None)])
    assert len(list(capture.read_frames(video, "dshow"))) == 1
    device.open.assert_called_once_with(str(video), cv2.CAP_ANY)


@pytest.mark.parametrize("name,content", [("missing.png", None), ("bad.jpg", b"not an image"),
                                         ("empty.avi", b"no video")])
def test_invalid_local_files_fail(tmp_path, name, content, capsys):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    assert capture.main(["--source", str(path), "--preview-only", "--headless"]) == 1
    assert "ERROR:" in capsys.readouterr().err


def test_video_with_no_frames_is_error(tmp_path, monkeypatch):
    path = tmp_path / "empty.avi"
    path.touch()
    device = fake_camera(monkeypatch, [(False, None)])
    with pytest.raises(capture.CaptureError, match="no readable frames"):
        next(capture.read_frames(path))
    device.release.assert_called_once()


def test_preview_window_quit_releases_device(monkeypatch, frame):
    device = fake_camera(monkeypatch, [(True, frame)])
    show = Mock()
    destroy = Mock()
    monkeypatch.setattr(capture.cv2, "imshow", show)
    monkeypatch.setattr(capture.cv2, "waitKey", lambda delay: ord("q"))
    monkeypatch.setattr(capture.cv2, "destroyAllWindows", destroy)
    assert capture.main(["--camera", "0", "--preview-only"]) == 0
    show.assert_called_once()
    destroy.assert_called_once()
    device.release.assert_called_once()


def test_server_failure_releases_device(monkeypatch, frame, capsys):
    device = fake_camera(monkeypatch, [(True, frame)])
    monkeypatch.setattr(capture, "inspect_frame", Mock(side_effect=capture.CaptureError("server offline")))
    assert capture.main(["--camera", "0", "--headless"]) == 1
    device.release.assert_called_once()
    assert "server offline" in capsys.readouterr().err


def test_keyboard_interrupt_releases_device(monkeypatch):
    device = fake_camera(monkeypatch, [KeyboardInterrupt])
    assert capture.main(["--camera", "0", "--preview-only", "--headless"]) == 130
    device.release.assert_called_once()


def test_gui_failure_reports_error_and_releases_camera(monkeypatch, frame, capsys):
    device = fake_camera(monkeypatch, [(True, frame)])
    monkeypatch.setattr(capture.cv2, "imshow", Mock(side_effect=cv2.error("GUI unavailable")))
    monkeypatch.setattr(capture.cv2, "destroyAllWindows", Mock(side_effect=cv2.error("GUI unavailable")))
    assert capture.main(["--camera", "0", "--preview-only"]) == 1
    device.release.assert_called_once()
    assert "GUI unavailable" in capsys.readouterr().err


@pytest.mark.parametrize("args", [[], ["--camera", "-1"], ["--source", "x", "--camera", "0"],
                                 ["--camera", "0", "--interval", "nan"],
                                 ["--camera", "0", "--interval", "-1"],
                                 ["--camera", "0", "--max-frames", "-1"],
                                 ["--camera", "0", "--api-url", "localhost:8000"],
                                 ["--camera", "0", "--api-url", "http://localhost:bad"]])
def test_cli_rejects_invalid_arguments(args):
    with pytest.raises(SystemExit) as exc:
        capture.parse_args(args)
    assert exc.value.code == 2


def test_http_client_sends_decodable_jpeg_multipart(monkeypatch, frame):
    def respond(request, timeout):
        assert request.full_url == "http://localhost:8000/detect"
        assert request.method == "POST" and timeout == 30
        assert b'name="file"; filename="frame.jpg"' in request.data
        assert "multipart/form-data; boundary=" in request.get_header("Content-type")
        jpeg = request.data.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
        decoded = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape == frame.shape
        return BytesIO(b'{"status": "PASS", "defects_found": 0}')

    monkeypatch.setattr(capture, "urlopen", respond)
    assert capture.inspect_frame(frame, "http://localhost:8000/")["status"] == "PASS"


@pytest.mark.parametrize("error,match", [
    (URLError("connection refused"), "Cannot reach inspection server"),
    (TimeoutError("timed out"), "Cannot reach inspection server"),
    (HTTPError("http://localhost", 503, "missing model", {}, BytesIO(b"Model missing")), "HTTP 503"),
])
def test_http_errors_are_actionable(monkeypatch, frame, error, match):
    monkeypatch.setattr(capture, "urlopen", Mock(side_effect=error))
    with pytest.raises(capture.CaptureError, match=match):
        capture.inspect_frame(frame, "http://localhost")


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"status":"unknown"}', b'{"status": []}'])
def test_invalid_server_result(monkeypatch, frame, body):
    monkeypatch.setattr(capture, "urlopen", lambda *a, **kw: BytesIO(body))
    with pytest.raises(capture.CaptureError):
        capture.inspect_frame(frame, "http://localhost")


def test_annotated_image_roundtrip(frame):
    ok, encoded = cv2.imencode(".jpg", frame)
    assert ok
    result = {"annotated_image": base64.b64encode(encoded).decode("ascii")}
    assert capture.annotated_frame(result).shape == frame.shape


@pytest.mark.parametrize("result", [{}, {"annotated_image": "invalid"}, {"annotated_image": ""}])
def test_invalid_annotated_image(result):
    with pytest.raises(capture.CaptureError):
        capture.annotated_frame(result)
