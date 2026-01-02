from pathlib import Path

import pytest
from PIL import Image, ImageFont

from imaging.print_layout import PrintLayout
from imaging.print_renderer import render_print_sheet, _load_font
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



def test_print_qr_and_text_regions_have_pixels_in_both_halves():
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

    y0 = layout.text_top_y
    qr_size = layout.text_box_size[1]
    text_w = layout.text_box_size[0] - qr_size
    text_h = layout.text_box_size[1]

    # QR is a 192x192 square, left-aligned in each text box.
    left_qr_origin = (layout.strip_inner_padding, y0)
    right_qr_origin = (600 + layout.strip_inner_padding, y0)
    assert _has_nonwhite_pixels(sheet, left_qr_origin, (qr_size, qr_size), white)
    assert _has_nonwhite_pixels(sheet, right_qr_origin, (qr_size, qr_size), white)

    # Text is centered in the remaining width to the right of the QR.
    left_text_origin = (layout.strip_inner_padding + qr_size, y0)
    right_text_origin = (600 + layout.strip_inner_padding + qr_size, y0)
    assert _has_nonwhite_pixels(sheet, left_text_origin, (text_w, text_h), white)
    assert _has_nonwhite_pixels(sheet, right_text_origin, (text_w, text_h), white)

def test_print_seam_in_text_region_is_background():
    """
    The print is cut down the middle at x=600.
    To ensure each strip retains the full URL/code, the text region must not
    draw across the seam. If fonts/centering regress, this will catch it.
    """
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
        # If you set these in your layout defaults, you can omit them here.
        # font_size_link=38,
    )

    sheet = render_print_sheet(strip=strip, layout=layout, album_code="MaxMitzvah2026")

    bg = layout.background_color
    y0 = layout.text_top_y
    y1 = y0 + layout.text_box_size[1]

    # Check a thin band around the seam.
    seam_x = 600
    band_half_width = 2  # checks x in [598..602]
    non_bg = 0
    total = 0

    for y in range(y0, y1):
        for x in range(seam_x - band_half_width, seam_x + band_half_width + 1):
            total += 1
            if sheet.getpixel((x, y)) != bg:
                non_bg += 1

    # Strictest: require zero. If you ever see flaky failures due to antialiasing,
    # change to a tiny threshold like <= 5.
    assert non_bg == 0, f"Expected seam band to be background; found {non_bg}/{total} non-bg pixels"


def test_load_font_uses_explicit_font_path(monkeypatch):
    sentinel = object()

    def fake_truetype(path, size):
        # When a font_path is provided, we should load exactly that path
        assert path == "/tmp/custom.ttf"
        assert size == 12
        return sentinel

    monkeypatch.setattr(ImageFont, "truetype", fake_truetype)

    font = _load_font("/tmp/custom.ttf", 12)
    assert font is sentinel


def test_load_font_falls_back_to_default_when_dejavu_missing(monkeypatch):
    sentinel_default = object()

    def fake_truetype(path, size):
        # Simulate DejaVu load failure
        assert path == "DejaVuSans.ttf"
        raise OSError("no font available")

    def fake_load_default():
        return sentinel_default

    monkeypatch.setattr(ImageFont, "truetype", fake_truetype)
    monkeypatch.setattr(ImageFont, "load_default", fake_load_default)

    font = _load_font(None, 12)
    assert font is sentinel_default


def test_load_font_falls_back_when_explicit_font_path_fails(monkeypatch):
    sentinel = object()

    calls = []

    def fake_truetype(path, size):
        calls.append(path)
        if path == "/tmp/custom.ttf":
            raise OSError("bad font path")
        if path == "DejaVuSans.ttf":
            return sentinel
        raise AssertionError("Unexpected font path")

    monkeypatch.setattr(ImageFont, "truetype", fake_truetype)

    font = _load_font("/tmp/custom.ttf", 12)
    assert font is sentinel
    assert calls == ["/tmp/custom.ttf", "DejaVuSans.ttf"]
