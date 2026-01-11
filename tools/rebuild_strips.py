#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from imaging.layout_presets import default_strip_layout
from imaging.strip_renderer import render_strip

RASTER_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _gather_images(folder: Path) -> List[Path]:
    # Only gather raster images Pillow can open reliably
    paths: List[Path] = []
    for ext in RASTER_EXTS:
        paths.extend(folder.glob(f"*{ext}"))
        paths.extend(folder.glob(f"*{ext.upper()}"))

    # Deterministic ordering
    paths = sorted(set(paths), key=lambda p: p.name.lower())
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild photobooth strips from edited images (3 at a time)."
    )
    parser.add_argument(
        "images_folder",
        type=Path,
        help="Folder containing edited raster images (JPG/PNG/TIF).",
    )
    parser.add_argument(
        "--logo",
        required=True,
        type=Path,
        help="Path to the logo image used in the strip (same as booth).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="Starting strip number for output files (default: 1).",
    )
    args = parser.parse_args()

    folder: Path = args.images_folder.expanduser().resolve()
    logo_path: Path = args.logo.expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Images folder does not exist or is not a directory: {folder}")
    if not logo_path.exists() or not logo_path.is_file():
        raise SystemExit(f"Logo path does not exist or is not a file: {logo_path}")

    images = _gather_images(folder)

    if not images:
        # Provide a helpful hint if they only have NEFs
        nef_count = len(list(folder.glob("*.nef"))) + len(list(folder.glob("*.NEF")))
        if nef_count > 0:
            raise SystemExit(
                "No JPG/PNG/TIF files found. This script does not read .NEF directly.\n"
                "Export your Lightroom edits as JPG (recommended) or TIF into this folder and re-run."
            )
        raise SystemExit("No supported images found (expected JPG/PNG/TIF).")

    if len(images) % 3 != 0:
        raise SystemExit(
            f"Image count must be divisible by 3. Found {len(images)} supported images."
        )

    layout = default_strip_layout(logo_path=logo_path)

    strip_num = args.start_index
    for i in range(0, len(images), 3):
        chunk = images[i: i + 3]
        strip = render_strip(image_paths=chunk, layout=layout)

        out_path = folder / f"strip{strip_num}.jpg"
        strip.save(out_path, format="JPEG", quality=95, subsampling=0, optimize=True)
        print(f"Wrote {out_path.name} from: {[p.name for p in chunk]}")
        strip_num += 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
