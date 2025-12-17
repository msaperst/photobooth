from pathlib import Path

from PIL import Image

from controller.strip_layout import StripLayout
from controller.strip_renderer import render_strip


def make_image(path: Path, color):
    img = Image.new("RGB", (100, 100), color)
    img.save(path)


def test_strip_renders_images_vertically(tmp_path):
    img1 = tmp_path / "1.jpg"
    img2 = tmp_path / "2.jpg"
    make_image(img1, (255, 0, 0))
    make_image(img2, (0, 255, 0))

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
    )

    strip = render_strip([img1, img2], layout)

    assert strip.size[0] == 70  # 50 + 2*10
