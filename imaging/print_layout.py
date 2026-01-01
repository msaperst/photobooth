from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PrintLayout:
    """Layout settings for the print artifact (separate from strip creation)."""

    canvas_size: Tuple[int, int]  # (width, height)
    dpi: int
    strip_size: Tuple[int, int]  # expected (width, height) of strip images
    background_color: Tuple[int, int, int]

    # Strip-internal padding (used to align text with strip content)
    strip_inner_padding: int  # e.g. 12

    # Print-only text region per strip (same size, drawn twice)
    text_box_size: Tuple[int, int]  # (width, height) -> (576, 192)
    text_top_y: int  # y coordinate where text region begins -> 1596
    text_color: Tuple[int, int, int]

    # Typography (best-effort; font loading falls back to PIL default)
    font_path: str | None = None
    font_size_info: int = 32
    font_size_link: int = 34
    font_size_code: int = 32
    line_spacing: int = 4
