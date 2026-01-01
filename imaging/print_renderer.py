from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from imaging.print_layout import PrintLayout
from imaging.strip_errors import StripCreationError

DEFAULT_RETRIEVAL_INFO_LINE = "Find your photos online"
DEFAULT_RETRIEVAL_LINK_LINE = "saperstonestudios.com#album"


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass

    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _draw_centered_lines_in_box(
        *,
        draw: ImageDraw.ImageDraw,
        box_origin: Tuple[int, int],
        box_size: Tuple[int, int],
        lines: list[tuple[str, ImageFont.ImageFont]],
        fill: Tuple[int, int, int],
        line_spacing: int,
) -> None:
    x0, y0 = box_origin
    box_w, box_h = box_size

    # Measure total height
    metrics: list[tuple[str, ImageFont.ImageFont, tuple[int, int, int, int]]] = []
    total_h = 0
    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        metrics.append((text, font, bbox))
        total_h += (bbox[3] - bbox[1])
    total_h += line_spacing * (len(lines) - 1)

    y = y0 + max(0, (box_h - total_h) // 2)
    for text, font, bbox in metrics:
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = x0 + max(0, (box_w - text_w) // 2)
        draw.text((x, y), text, fill=fill, font=font)
        y += text_h + line_spacing


def render_print_sheet(
        *,
        strip: Image.Image,
        layout: PrintLayout,
        album_code: str,
        info_line: str = DEFAULT_RETRIEVAL_INFO_LINE,
        link_line: str = DEFAULT_RETRIEVAL_LINK_LINE,
) -> Image.Image:
    if strip.size != layout.strip_size:
        raise StripCreationError(
            f"Strip must be exactly {layout.strip_size[0]}x{layout.strip_size[1]} for printing"
        )

    canvas_w, canvas_h = layout.canvas_size
    sheet = Image.new("RGB", (canvas_w, canvas_h), layout.background_color)

    strip_w, _strip_h = layout.strip_size
    sheet.paste(strip, (0, 0))
    sheet.paste(strip, (strip_w, 0))

    # Prepare fonts + lines
    draw = ImageDraw.Draw(sheet)
    font_info = _load_font(layout.font_path, layout.font_size_info)
    font_link = _load_font(layout.font_path, layout.font_size_link)
    font_code = _load_font(layout.font_path, layout.font_size_code)

    lines = [
        (info_line, font_info),
        (link_line, font_link),
        (album_code, font_code),
    ]

    # Draw one text block under EACH strip, aligned to strip content (not the outer border)
    box_w, box_h = layout.text_box_size
    y0 = layout.text_top_y

    left_origin = (layout.strip_inner_padding, y0)
    right_origin = (strip_w + layout.strip_inner_padding, y0)

    _draw_centered_lines_in_box(
        draw=draw,
        box_origin=left_origin,
        box_size=(box_w, box_h),
        lines=lines,
        fill=layout.text_color,
        line_spacing=layout.line_spacing,
    )
    _draw_centered_lines_in_box(
        draw=draw,
        box_origin=right_origin,
        box_size=(box_w, box_h),
        lines=lines,
        fill=layout.text_color,
        line_spacing=layout.line_spacing,
    )

    return sheet
