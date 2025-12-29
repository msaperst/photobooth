import subprocess
import threading
from datetime import datetime
from pathlib import Path

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
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = datetime.now().strftime("photo_%Y%m%d_%H%M%S.jpg")
        output_path = output_dir / filename

        cmd = [
            "gphoto2",
            "--capture-image-and-download",
            "--force-overwrite",
            "--filename",
            str(output_path),
        ]

        try:
            with self._io_lock:
                subprocess.run(
                    cmd,
                    check=True,
                    timeout=self.timeout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
        except subprocess.TimeoutExpired as e:
            raise CameraError("Camera capture timed out") from e
        except subprocess.CalledProcessError as e:
            raise CameraError(
                f"Camera capture failed: {e.stderr.decode(errors='ignore')}"
            ) from e

        if not output_path.exists():
            raise CameraError("Camera reported success but no file was created")

        return output_path
