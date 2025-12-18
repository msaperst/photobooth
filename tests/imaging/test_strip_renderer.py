from pathlib import Path

import pytest
from PIL import Image

from imaging.strip_errors import StripCreationError
from imaging.strip_layout import StripLayout
from imaging.strip_renderer import render_strip


def make_image(path: Path, size=(50, 50), color=(255, 0, 0)):
    img = Image.new("RGB", size, color)
    img.save(path)


def test_strip_renders_images_vertically(tmp_path):
    img1 = tmp_path / "1.jpg"
    img2 = tmp_path / "2.jpg"
    make_image(img1, size=(50, 50), color=(255, 0, 0))
    make_image(img2, size=(50, 50), color=(0, 255, 0))

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
    )

    strip = render_strip([img1, img2], layout)

    assert strip.size[0] == 70  # 50 + 2*10


def test_render_strip_raises_when_no_images():
    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
    )

    with pytest.raises(StripCreationError, match="No images provided"):
        render_strip([], layout)


def test_render_strip_raises_when_image_cannot_be_loaded(tmp_path):
    bad_path = tmp_path / "does_not_exist.jpg"

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
    )

    with pytest.raises(StripCreationError, match="Failed to load image"):
        render_strip([bad_path], layout)


def test_render_strip_raises_when_logo_path_missing(tmp_path):
    img = tmp_path / "photo.jpg"
    make_image(img)

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
        logo_path=tmp_path / "missing_logo.jpg",
        logo_size=(30, 30),
    )

    with pytest.raises(StripCreationError, match="logo file does not exist"):
        render_strip([img], layout)


def test_render_strip_raises_when_logo_cannot_be_loaded(tmp_path):
    img = tmp_path / "photo.jpg"
    make_image(img)

    logo = tmp_path / "logo.jpg"
    logo.write_bytes(b"not an image")

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
        logo_path=logo,
        logo_size=(30, 30),
    )

    with pytest.raises(StripCreationError, match="Failed to load logo image"):
        render_strip([img], layout)


def test_render_strip_pastes_logo_at_bottom(tmp_path):
    photo = tmp_path / "photo.jpg"
    logo = tmp_path / "logo.jpg"

    make_image(photo, color=(255, 0, 0))
    make_image(logo, size=(50, 50), color=(0, 0, 255))

    layout = StripLayout(
        photo_size=(50, 50),
        padding=10,
        background_color=(255, 255, 255),
        logo_path=logo,
        logo_size=(50, 50),
    )

    strip = render_strip([photo], layout)

    # Sample a pixel well inside the logo area
    x = layout.padding + 10
    y = layout.padding + layout.photo_size[1] + layout.padding + 10

    r, g, b = strip.getpixel((x, y))
    assert b > 250
    assert r < 5
    assert g < 5
