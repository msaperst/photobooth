from pathlib import Path

import pytest
from PIL import Image

from imaging.print_layout import PrintLayout
from imaging.print_renderer import render_print_sheet
from imaging.strip_errors import StripCreationError


def test_print_sheet_is_exact_size():
    strip = Image.new("RGB", (600, 1596), (255, 0, 0))

    layout = PrintLayout(
        canvas_size=(1200, 1800),
        dpi=300,
        strip_size=(600, 1596),
        background_color=(255, 255, 255),
        strip_inner_padding=12,
        text_box_size=(576, 192),
        text_top_y=1596,
        text_color=(0, 0, 0),
    )

    sheet = render_print_sheet(strip=strip, layout=layout, album_code="CODE123")
    assert sheet.size == (1200, 1800)


def test_print_rejects_wrong_strip_size():
    bad_strip = Image.new("RGB", (600, 1597), (255, 0, 0))
    layout = PrintLayout(
        canvas_size=(1200, 1800),
        dpi=300,
        strip_size=(600, 1596),
        background_color=(255, 255, 255),
        strip_inner_padding=12,
        text_box_size=(576, 192),
        text_top_y=1596,
        text_color=(0, 0, 0),
    )

    with pytest.raises(StripCreationError, match="Strip must be exactly"):
        render_print_sheet(strip=bad_strip, layout=layout, album_code="CODE123")


def test_print_dpi_is_300_when_saved(tmp_path: Path):
    strip = Image.new("RGB", (600, 1596), (255, 0, 0))
    layout = PrintLayout(
        canvas_size=(1200, 1800),
        dpi=300,
        strip_size=(600, 1596),
        background_color=(255, 255, 255),
        strip_inner_padding=12,
        text_box_size=(576, 192),
        text_top_y=1596,
        text_color=(0, 0, 0),
    )

    sheet = render_print_sheet(strip=strip, layout=layout, album_code="CODE123")
    out_path = tmp_path / "print.jpg"
    sheet.save(out_path, dpi=(layout.dpi, layout.dpi))

    reloaded = Image.open(out_path)
    dpi = reloaded.info.get("dpi")
    assert dpi is not None
    assert int(round(dpi[0])) == 300
    assert int(round(dpi[1])) == 300


def _has_nonwhite_pixels(img, box_origin, box_size, white):
    x0, y0 = box_origin
    w, h = box_size
    for y in range(y0 + 10, y0 + h - 10, 12):
        for x in range(x0 + 10, x0 + w - 10, 12):
            if img.getpixel((x, y)) != white:
                return True
    return False


def test_print_contains_text_pixels_in_both_halves():
    strip = Image.new("RGB", (600, 1596), (255, 0, 0))

    layout = PrintLayout(
        canvas_size=(1200, 1800),
        dpi=300,
        strip_size=(600, 1596),
        background_color=(255, 255, 255),
        strip_inner_padding=12,
        text_box_size=(576, 192),
        text_top_y=1596,
        text_color=(0, 0, 0),
    )

    sheet = render_print_sheet(strip=strip, layout=layout, album_code="CODE123")
    white = layout.background_color

    left_origin = (12, 1596)
    right_origin = (612, 1596)

    assert _has_nonwhite_pixels(sheet, left_origin, layout.text_box_size, white)
    assert _has_nonwhite_pixels(sheet, right_origin, layout.text_box_size, white)
