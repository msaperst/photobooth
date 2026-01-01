from pathlib import Path

import pytest
from PIL import Image

from imaging.strip_errors import StripCreationError
from imaging.strip_layout import StripLayout
from imaging.strip_renderer import render_strip


def make_image(path: Path, size=(300, 200), color=(255, 0, 0)):
    img = Image.new("RGB", size, color)
    img.save(path)


def test_render_strip_requires_exactly_three_photos(tmp_path):
    logo = tmp_path / "logo.png"
    make_image(logo, size=(900, 600), color=(0, 0, 255))

    layout = StripLayout(
        photo_size=(576, 384),
        padding=12,
        background_color=(255, 255, 255),
        logo_path=logo,
        logo_size=(576, 384),
    )

    img1 = tmp_path / "1.jpg"
    make_image(img1)

    with pytest.raises(StripCreationError, match="exactly 3 photos"):
        render_strip([img1], layout)


def test_render_strip_requires_logo(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"{i}.jpg"
        make_image(p)
        imgs.append(p)

    layout = StripLayout(
        photo_size=(576, 384),
        padding=12,
        background_color=(255, 255, 255),
        logo_path=None,
        logo_size=(576, 384),
    )

    with pytest.raises(StripCreationError, match="Logo is required"):
        render_strip(imgs, layout)


def test_render_strip_output_size_matches_spec(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"{i}.jpg"
        make_image(p, size=(6016, 4016), color=(255, 0, 0))
        imgs.append(p)

    logo = tmp_path / "logo.png"
    make_image(logo, size=(900, 600), color=(0, 0, 255))

    layout = StripLayout(
        photo_size=(576, 384),
        padding=12,
        background_color=(255, 255, 255),
        logo_path=logo,
        logo_size=(576, 384),
    )

    strip = render_strip(imgs, layout)
    assert strip.size == (600, 1596)


def test_render_strip_preserves_aspect_ratio_letterboxes(tmp_path):
    """A square input should be letterboxed into the 3:2 tile."""
    imgs = []
    for i in range(3):
        p = tmp_path / f"{i}.jpg"
        # Square image to force letterboxing
        make_image(p, size=(500, 500), color=(10, 200, 10))
        imgs.append(p)

    logo = tmp_path / "logo.png"
    make_image(logo, size=(900, 600), color=(0, 0, 255))

    bg = (255, 255, 255)
    layout = StripLayout(
        photo_size=(576, 384),
        padding=12,
        background_color=bg,
        logo_path=logo,
        logo_size=(576, 384),
    )

    strip = render_strip(imgs, layout)

    # Sample within the first photo tile.
    tile_x0 = 12
    tile_y0 = 12

    # Square -> fit-to-height (384), width becomes 384, leaving side padding.
    # So left edge inside tile should be background.
    assert strip.getpixel((tile_x0 + 1, tile_y0 + 10)) == bg
    assert strip.getpixel((tile_x0 + 574, tile_y0 + 10)) == bg

    # Center should be the image color (not background).
    center = strip.getpixel((tile_x0 + 288, tile_y0 + 192))
    assert center != bg
