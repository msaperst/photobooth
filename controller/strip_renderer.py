from pathlib import Path
from typing import List

from PIL import Image

from controller.strip_errors import StripCreationError
from controller.strip_layout import StripLayout


def render_strip(
        image_paths: List[Path],
        layout: StripLayout,
) -> Image.Image:
    if not image_paths:
        raise StripCreationError("No images provided for strip")

    images = []
    for path in image_paths:
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            raise StripCreationError(f"Failed to load image: {path}") from e
        images.append(img.resize(layout.photo_size))

    logo_img = None
    if layout.logo_path:
        if not layout.logo_path.exists():
            raise StripCreationError("Configured logo file does not exist")
        try:
            logo_img = (
                Image.open(layout.logo_path)
                .convert("RGB")
                .resize(layout.logo_size)
            )
        except Exception as e:
            raise StripCreationError("Failed to load logo image") from e

    total_tiles = len(images) + (1 if logo_img else 0)
    width = layout.photo_size[0] + 2 * layout.padding
    height = (
            total_tiles * layout.photo_size[1]
            + (total_tiles + 1) * layout.padding
    )

    strip = Image.new("RGB", (width, height), layout.background_color)

    y = layout.padding
    for img in images:
        strip.paste(img, (layout.padding, y))
        y += layout.photo_size[1] + layout.padding

    if logo_img:
        strip.paste(logo_img, (layout.padding, y))

    return strip
