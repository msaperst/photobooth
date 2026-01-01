from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PrintLayout:
    """Layout settings for the print artifact.

    This layout is intentionally separate from strip creation.
    """

    canvas_size: Tuple[int, int]  # (width, height)
    dpi: int
    strip_size: Tuple[int, int]  # expected (width, height) of strip images
    background_color: Tuple[int, int, int]

    # Text region (print-only). Coordinates are in print-canvas pixels.
    text_box_origin: Tuple[int, int]  # (x, y)
    text_box_size: Tuple[int, int]  # (width, height)
    text_color: Tuple[int, int, int]

    # Typography (best-effort; font loading falls back to PIL default)
    font_path: str | None = None
    font_size_info: int = 36
    font_size_link: int = 44
    font_size_code: int = 36
    line_spacing: int = 4
