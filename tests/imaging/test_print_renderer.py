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
        text_box_origin=((1200 - 576) // 2, 1596),
        text_box_size=(576, 192),
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
        text_box_origin=((1200 - 576) // 2, 1596),
        text_box_size=(576, 192),
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
        text_box_origin=((1200 - 576) // 2, 1596),
        text_box_size=(576, 192),
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


def test_print_contains_text_pixels(tmp_path: Path):
    """We don't assert exact typography, but we do ensure something non-white exists in the text box."""
    strip = Image.new("RGB", (600, 1596), (255, 0, 0))

    layout = PrintLayout(
        canvas_size=(1200, 1800),
        dpi=300,
        strip_size=(600, 1596),
        background_color=(255, 255, 255),
        text_box_origin=((1200 - 576) // 2, 1596),
        text_box_size=(576, 192),
        text_color=(0, 0, 0),
    )

    sheet = render_print_sheet(strip=strip, layout=layout, album_code="CODE123")

    x0, y0 = layout.text_box_origin
    w, h = layout.text_box_size

    white = layout.background_color
    found_non_white = False
    for y in range(y0 + 10, y0 + h - 10, 12):
        for x in range(x0 + 10, x0 + w - 10, 12):
            if sheet.getpixel((x, y)) != white:
                found_non_white = True
                break
        if found_non_white:
            break

    assert found_non_white, "Expected to find non-white pixels in the text region"
