# tests/fakes/fake_camera.py

from datetime import datetime
from pathlib import Path

from controller.camera_base import Camera

CAMERA_NOT_CONNECTED = "Camera not connected"


class FakeCamera(Camera):
    def __init__(self, image_root: Path):
        self.image_root = image_root
        self.captured_images = []
        self.live_view_active = False
        self.connected = True

    def health_check(self) -> bool:
        return self.connected

    def start_live_view(self) -> None:
        if not self.connected:
            raise RuntimeError(CAMERA_NOT_CONNECTED)
        self.live_view_active = True

    def stop_live_view(self) -> None:
        self.live_view_active = False

    def get_live_view_frame(self) -> bytes:
        if not self.connected:
            raise RuntimeError(CAMERA_NOT_CONNECTED)
        if not self.live_view_active:
            raise RuntimeError("Live view not active")
        return b"\xff\xd8\xff"

    def capture(self, output_dir: Path) -> Path:
        if not self.connected:
            raise RuntimeError(CAMERA_NOT_CONNECTED)

        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"fake_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        path = output_dir / filename
        path.write_bytes(b"fake image data")

        self.captured_images.append(path)
        return path
