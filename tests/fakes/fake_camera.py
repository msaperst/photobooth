# tests/fakes/fake_camera.py (or similar)

from datetime import datetime
from pathlib import Path

from controller.camera import Camera


class FakeCamera(Camera):
    def __init__(self, image_root: Path):
        self.image_root = image_root
        self.captured_images = []

    def health_check(self) -> bool:
        return True

    def start_live_view(self) -> None:
        pass

    def stop_live_view(self) -> None:
        pass

    def capture(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"fake_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        path = output_dir / filename
        path.write_bytes(b"fake image data")

        self.captured_images.append(path)
        return path
