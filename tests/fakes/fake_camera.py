from pathlib import Path
from typing import List

from controller.camera import Camera


class FakeCamera(Camera):
    def __init__(self, image_dir: Path):
        self.image_dir = image_dir
        self.live_view_active = False

    def health_check(self) -> bool:
        return True

    def start_live_view(self) -> None:
        self.live_view_active = True

    def stop_live_view(self) -> None:
        self.live_view_active = False

    def capture_images(self, count: int) -> List[Path]:
        images = []
        for i in range(count):
            path = self.image_dir / f"fake_image_{i}.jpg"
            path.write_text("fake image data")
            images.append(path)
        return images
