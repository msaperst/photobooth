import subprocess
from datetime import datetime
from pathlib import Path

from controller.camera import Camera, CameraError


class GPhotoCamera(Camera):
    def __init__(self, timeout: int = 10):
        self._live_view_active = False
        self.timeout = timeout

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

    def start_live_view(self) -> None:
        subprocess.run(
            ["gphoto2", "--set-config", "/main/actions/viewfinder=1"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._live_view_active = True

    def stop_live_view(self) -> None:
        subprocess.run(
            ["gphoto2", "--set-config", "/main/actions/viewfinder=0"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._live_view_active = False

    def get_live_view_frame(self) -> bytes:
        if not self._live_view_active:
            raise CameraError("Live view not started")

        try:
            result = subprocess.run(
                ["gphoto2", "--capture-preview", "--stdout"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=1.0,
                check=True,
            )
            return result.stdout

        except subprocess.CalledProcessError:
            # Camera busy, frame dropped — normal
            raise CameraError("Live view frame unavailable")

        except subprocess.TimeoutExpired:
            raise CameraError("Live view frame timeout")

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
