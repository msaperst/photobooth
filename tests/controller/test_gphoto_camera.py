import pytest

from controller.camera_base import CameraError
from controller.gphoto_camera import GPhotoCamera


class _Result:
    def __init__(self, stdout: bytes, stderr: bytes):
        self.stdout = stdout
        self.stderr = stderr


def test_capture_returns_downloaded_jpeg_and_keeps_raw(tmp_path, monkeypatch):
    out_dir = tmp_path / "photos"
    out_dir.mkdir()

    jpeg = out_dir / "photo_20260101_000000_1.jpg"
    raw = out_dir / "photo_20260101_000000_2.nef"

    # Create files as if gphoto2 wrote them.
    jpeg.write_bytes(b"\xff\xd8" + b"fakejpeg")
    raw.write_bytes(b"II" + b"fakeraw")

    def fake_run(cmd, check, timeout, stdout, stderr):
        # Ensure we're using a filename template (not hardcoded .jpg).
        assert "--filename" in cmd
        return _Result(
            stdout=(f"Saving file as {jpeg}\nSaving file as {raw}\n").encode(),
            stderr=b"",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera(timeout=1)
    got = cam.capture(out_dir)
    assert got == jpeg
    assert raw.exists()


def test_capture_errors_if_no_jpeg_downloaded(tmp_path, monkeypatch):
    out_dir = tmp_path / "photos"
    out_dir.mkdir()

    raw = out_dir / "photo_20260101_000000_1.nef"
    raw.write_bytes(b"II" + b"fakeraw")

    def fake_run(cmd, check, timeout, stdout, stderr):
        return _Result(stdout=f"Saving file as {raw}\n".encode(), stderr=b"")

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera(timeout=1)
    with pytest.raises(CameraError, match="No JPEG file was downloaded"):
        cam.capture(out_dir)
