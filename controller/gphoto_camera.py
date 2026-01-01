import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from controller.camera_base import Camera, CameraError


class GPhotoCamera(Camera):
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._io_lock = threading.Lock()

    # ---------- Required interface ----------

    def health_check(self) -> bool:
        """
        Verify that the camera is connected and responsive.
        """
        try:
            subprocess.run(
                ["gphoto2", "--summary"],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def capture(self, output_dir: Path) -> Path:
        """
        Capture a photo and download the resulting file(s) into output_dir.

        We intentionally do not hardcode an output extension here.
        Depending on camera settings, a capture may produce JPEG, RAW (NEF), or both.
        Using gphoto2 filename tokens ensures each file is saved with its correct extension.

        Contract for this project:
        - We return the downloaded JPEG Path (used for strip creation).
        - If the camera is configured RAW-only and no JPEG is produced, raise CameraError.
        - Any RAW file(s) that are downloaded remain in output_dir for later editing.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_template = str(output_dir / f"photo_{ts}_%n.%C")

        cmd = [
            "gphoto2",
            "--capture-image-and-download",
            "--force-overwrite",
            "--filename",
            filename_template,
        ]

        try:
            with self._io_lock:
                result = subprocess.run(
                    cmd,
                    check=True,
                    timeout=self.timeout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
        except subprocess.TimeoutExpired as e:
            raise CameraError("Camera capture timed out") from e
        except subprocess.CalledProcessError as e:
            raise CameraError(
                f"Camera capture failed: {e.stderr.decode(errors='ignore')}"
            ) from e

        downloaded = _parse_gphoto_saved_paths(result.stdout, result.stderr)
        if not downloaded:
            raise CameraError("Camera reported success but no files were downloaded")

        jpeg_path = _select_jpeg(downloaded)
        if jpeg_path is None:
            raise CameraError(
                "No JPEG file was downloaded. Configure the camera to shoot JPEG or RAW+JPEG."
            )

        if not jpeg_path.exists():
            raise CameraError("Camera reported success but JPEG file was not created")

        return jpeg_path


def _parse_gphoto_saved_paths(stdout: bytes, stderr: bytes) -> List[Path]:
    """Extract local paths from gphoto2 output.

    We look for lines like:
      'Saving file as /path/to/file'
    and return all parsed paths.

    This avoids depending on camera-side filenames and ensures we track what was actually written.
    """
    text = (stdout or b"") + b"\n" + (stderr or b"")
    lines = text.decode(errors="ignore").splitlines()
    out: List[Path] = []
    prefix = "Saving file as "
    for line in lines:
        line = line.strip()
        if line.startswith(prefix):
            path_str = line[len(prefix):].strip()
            if path_str:
                out.append(Path(path_str))
    return out


def _is_jpeg_file(path: Path) -> bool:
    """Best-effort check for JPEG magic bytes."""
    try:
        with path.open("rb") as f:
            sig = f.read(2)
        return sig == b"\xff\xd8"
    except Exception:
        return False


def _select_jpeg(paths: List[Path]) -> Optional[Path]:
    """Select the JPEG among downloaded files.

    Preference order:
    1) Any file with .jpg/.jpeg extension that is actually a JPEG.
    2) Any file that is actually a JPEG regardless of extension.
    """
    for p in paths:
        if p.suffix.lower() in {".jpg", ".jpeg"} and _is_jpeg_file(p):
            return p

    for p in paths:
        if _is_jpeg_file(p):
            return p

    return None
