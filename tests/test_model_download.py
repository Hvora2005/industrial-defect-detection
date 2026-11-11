import hashlib
from io import BytesIO
from unittest.mock import Mock

import pytest

from tools import download_validation_model as download


def test_pinned_download_verifies_before_writing(tmp_path, monkeypatch):
    data = b"test checkpoint"
    monkeypatch.setattr(download, "SHA256", hashlib.sha256(data).hexdigest())
    request = Mock(return_value=BytesIO(data))
    monkeypatch.setattr(download, "urlopen", request)
    path = tmp_path / "model.pt"
    assert download.download_model(path) == path
    assert path.read_bytes() == data
    assert download.REVISION in request.call_args.args[0]


def test_bad_download_is_not_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "urlopen", lambda *a, **kw: BytesIO(b"wrong data"))
    path = tmp_path / "model.pt"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        download.download_model(path)
    assert not path.exists()


def test_existing_checkpoint_is_not_silently_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "model.pt"
    path.write_bytes(b"existing weights")
    monkeypatch.setattr(download, "urlopen", Mock(side_effect=AssertionError("Unexpected network")))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        download.download_model(path)
    assert path.read_bytes() == b"existing weights"
