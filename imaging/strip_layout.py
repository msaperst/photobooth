from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class StripLayout:
    photo_size: Tuple[int, int]  # (width, height)
    padding: int
    background_color: Tuple[int, int, int]

    logo_path: Optional[Path] = None
    logo_size: Optional[Tuple[int, int]] = None
