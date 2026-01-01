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


def test_health_check_success(monkeypatch):
    def fake_run(*args, **kwargs):
        return None  # subprocess.run succeeds

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera()
    assert cam.health_check() is True


def test_health_check_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        raise Exception("no camera")

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera()
    assert cam.health_check() is False


def test_capture_timeout(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="gphoto2", timeout=1)

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera(timeout=1)
    with pytest.raises(CameraError, match="Camera capture timed out"):
        cam.capture(tmp_path)


def test_capture_called_process_error(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd="gphoto2",
            stderr=b"camera busy",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera()
    with pytest.raises(CameraError, match="camera busy"):
        cam.capture(tmp_path)


def test_capture_no_files_downloaded(monkeypatch, tmp_path):
    class Result:
        stdout = b""
        stderr = b""

    def fake_run(*args, **kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera()
    with pytest.raises(CameraError, match="no files were downloaded"):
        cam.capture(tmp_path)


def test_capture_jpeg_path_missing(monkeypatch, tmp_path):
    class Result:
        stdout = b"Saving file as /tmp/missing.jpg\n"
        stderr = b""

    def fake_run(*args, **kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    cam = GPhotoCamera()
    with pytest.raises(CameraError, match="No JPEG file was downloaded"):
        cam.capture(tmp_path)


import subprocess
from pathlib import Path

import pytest

from controller.camera_base import CameraError
from controller.gphoto_camera import GPhotoCamera


def test_capture_jpeg_selected_but_exists_false(monkeypatch, tmp_path):
    out_dir = tmp_path / "photos"
    out_dir.mkdir()

    jpeg = out_dir / "photo_20260101_000000_1.jpg"
    jpeg.write_bytes(b"\xff\xd8" + b"fakejpeg")  # enough for _is_jpeg_file

    class Result:
        stdout = f"Saving file as {jpeg}\n".encode()
        stderr = b""

    def fake_run(*args, **kwargs):
        return Result()

    monkeypatch.setattr("subprocess.run", fake_run)

    # Monkeypatch Path.exists so only our jpeg path appears missing
    orig_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if str(self) == str(jpeg):
            return False
        return orig_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)

    cam = GPhotoCamera()
    with pytest.raises(CameraError, match="JPEG file was not created"):
        cam.capture(out_dir)


def test_is_jpeg_file_missing_path(tmp_path):
    from controller.gphoto_camera import _is_jpeg_file

    missing = tmp_path / "does_not_exist.jpg"
    assert _is_jpeg_file(missing) is False


def test_select_jpeg_fallback_magic_bytes(tmp_path):
    from controller.gphoto_camera import _select_jpeg

    fake = tmp_path / "image.weird"
    fake.write_bytes(b"\xff\xd8" + b"rest")

    assert _select_jpeg([fake]) == fake
