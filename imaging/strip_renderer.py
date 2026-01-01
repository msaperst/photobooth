from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image

from imaging.strip_errors import StripCreationError
from imaging.strip_layout import StripLayout


def _fit_preserve_aspect(
        img: Image.Image,
        target_size: Tuple[int, int],
        background_color: Tuple[int, int, int],
) -> Image.Image:
    """Resize `img` to fit within `target_size` without cropping or distortion.

    If aspect ratios differ, the image is letterboxed/pillarboxed using
    `background_color`.
    """
    target_w, target_h = target_size
    src_w, src_h = img.size

    if src_w <= 0 or src_h <= 0:
        raise StripCreationError("Invalid image dimensions")

    # Compute uniform scale to fit within target.
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    resized = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), background_color)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(resized, (x, y))
    return canvas


def render_strip(
        image_paths: List[Path],
        layout: StripLayout,
) -> Image.Image:
    """Render a photostrip.

    Contract for this project phase:
    - Exactly 3 photos are required.
    - A logo is required and is treated as a 4th tile.
    - No cropping or distortion: sources are fit to tiles preserving aspect ratio.
    """
    if not image_paths:
        raise StripCreationError("No images provided for strip")
    if len(image_paths) != 3:
        raise StripCreationError("Strip requires exactly 3 photos")

    if layout.logo_path is None:
        raise StripCreationError("Logo is required for strip")
    if layout.logo_size is None:
        raise StripCreationError("Logo size is required for strip")
    if not layout.logo_path.exists():
        raise StripCreationError("Configured logo file does not exist")

    images: List[Image.Image] = []
    for path in image_paths:
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            raise StripCreationError(f"Failed to load image: {path}") from e
        images.append(_fit_preserve_aspect(img, layout.photo_size, layout.background_color))

    try:
        logo_src = Image.open(layout.logo_path).convert("RGB")
    except Exception as e:
        raise StripCreationError("Failed to load logo image") from e

    logo_img = _fit_preserve_aspect(logo_src, layout.logo_size, layout.background_color)

    total_tiles = 4  # 3 photos + logo
    width = layout.photo_size[0] + 2 * layout.padding
    height = total_tiles * layout.photo_size[1] + (total_tiles + 1) * layout.padding

    strip = Image.new("RGB", (width, height), layout.background_color)

    y = layout.padding
    for img in images:
        strip.paste(img, (layout.padding, y))
        y += layout.photo_size[1] + layout.padding

    strip.paste(logo_img, (layout.padding, y))
    return strip
