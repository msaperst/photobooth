# imaging/layout_presets.py
from __future__ import annotations

from pathlib import Path

from imaging.print_layout import PrintLayout
from imaging.strip_layout import StripLayout

# Keep these values identical to the booth strip layout.
# If you ever change the booth strip layout, change them here.
DEFAULT_STRIP_PHOTO_SIZE = (558, 372)
DEFAULT_STRIP_PADDING = 16
DEFAULT_STRIP_BG = (255, 255, 255)
DEFAULT_STRIP_LOGO_SIZE = (558, 372)


def default_strip_layout(*, logo_path: Path) -> StripLayout:
    return StripLayout(
        photo_size=DEFAULT_STRIP_PHOTO_SIZE,
        padding=DEFAULT_STRIP_PADDING,
        background_color=DEFAULT_STRIP_BG,
        logo_path=logo_path,
        logo_size=DEFAULT_STRIP_LOGO_SIZE,
    )


def default_print_layout() -> PrintLayout:
    return PrintLayout(
        canvas_size=(1181, 1748),
        dpi=300,
        strip_size=(558, 1536),
        background_color=(255, 255, 255),
        strip_inner_padding=0,
        text_box_size=(558, 196),
        text_top_y=1552,
        text_color=(0, 0, 0),
        cut_line_size=65,
    )
