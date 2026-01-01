from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from imaging.print_layout import PrintLayout
from imaging.strip_errors import StripCreationError

# --- Print-only text defaults ---
# Keep these as module-level constants so changing copy later is easy.
DEFAULT_RETRIEVAL_INFO_LINE = "Find your photos online"
DEFAULT_RETRIEVAL_LINK_LINE = "saperstonestudios.com#album"


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TTF font if available; fall back to a PIL default font.

    We avoid hard failures on systems without the expected font installed.
    """
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass

    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def render_print_sheet(
        *,
        strip: Image.Image,
        layout: PrintLayout,
        album_code: str,
        info_line: str = DEFAULT_RETRIEVAL_INFO_LINE,
        link_line: str = DEFAULT_RETRIEVAL_LINK_LINE,
) -> Image.Image:
    """Create a print-ready image.

    Contract:
    - Output canvas is layout.canvas_size.
    - Two strips are placed side-by-side (same strip duplicated).
    - Print-only text is rendered in the reserved text box area.
    """
    if strip.size != layout.strip_size:
        raise StripCreationError(
            f"Strip must be exactly {layout.strip_size[0]}x{layout.strip_size[1]} for printing"
        )

    canvas_w, canvas_h = layout.canvas_size
    sheet = Image.new("RGB", (canvas_w, canvas_h), layout.background_color)

    # Place strips at top: left at x=0, right at x=strip_width
    strip_w, _strip_h = layout.strip_size
    sheet.paste(strip, (0, 0))
    sheet.paste(strip, (strip_w, 0))

    # Render the 3-line retrieval text centered in the text box.
    x0, y0 = layout.text_box_origin
    box_w, box_h = layout.text_box_size

    draw = ImageDraw.Draw(sheet)

    font_info = _load_font(layout.font_path, layout.font_size_info)
    font_link = _load_font(layout.font_path, layout.font_size_link)
    font_code = _load_font(layout.font_path, layout.font_size_code)

    lines = [
        (info_line, font_info),
        (link_line, font_link),
        (album_code, font_code),
    ]

    # Measure total height to vertically center within the box.
    line_metrics: list[Tuple[str, ImageFont.ImageFont, Tuple[int, int, int, int]]] = []
    total_h = 0
    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        line_metrics.append((text, font, bbox))
        total_h += (bbox[3] - bbox[1])
    total_h += layout.line_spacing * (len(lines) - 1)

    start_y = y0 + max(0, (box_h - total_h) // 2)

    y = start_y
    for text, font, bbox in line_metrics:
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = x0 + max(0, (box_w - text_w) // 2)
        draw.text((x, y), text, fill=layout.text_color, font=font)
        y += text_h + layout.line_spacing

    return sheet
