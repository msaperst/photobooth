import subprocess
import threading
from datetime import datetime
from pathlib import Path

from controller.camera import Camera, CameraError


class GPhotoCamera(Camera):
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._io_lock = threading.Lock()
        self._live_view_active = False

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
        # Nikon live view via viewfinder toggle
        with self._io_lock:
            subprocess.run(
                ["gphoto2", "--set-config", "/main/actions/viewfinder=1"],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._live_view_active = True

    def stop_live_view(self) -> None:
        with self._io_lock:
            subprocess.run(
                ["gphoto2", "--set-config", "/main/actions/viewfinder=0"],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._live_view_active = False

    def get_live_view_frame(self) -> bytes:
        # Caller may “ensure start”, but if we got here without it:
        if not self._live_view_active:
            raise CameraError("Live view not started")

        # Serialize access to gphoto2 to avoid “device busy”
        with self._io_lock:
            try:
                result = subprocess.run(
                    ["gphoto2", "--capture-preview", "--stdout"],
                    check=True,
                    timeout=2,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if not result.stdout:
                    raise CameraError("Empty live view frame")
                return result.stdout
            except subprocess.TimeoutExpired as e:
                raise CameraError("Live view frame timeout") from e
            except subprocess.CalledProcessError as e:
                # Typical when camera is busy; treat as “frame unavailable”
                msg = e.stderr.decode(errors="ignore") if e.stderr else ""
                raise CameraError(f"Live view frame unavailable: {msg}") from e

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
