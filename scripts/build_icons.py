"""Generate native icon formats from the application's shared SVG.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words icns frombytes

import argparse
from pathlib import Path

from PIL import Image

from ride_forces_analyzer.ui.icons import ICON_SIZES, render_icon


def build_icons(destination: Path) -> Path:
    """Write multi-resolution ICO/ICNS and a 512-pixel PNG using existing Qt/Pillow.

    Args:
        destination: Requested output path; replacement follows the explicit overwrite
            policy.

    Returns:
        Path to the generated Windows icon.

    Raises:
        OSError: If the required filesystem operation fails.
    """
    destination.mkdir(parents=True, exist_ok=True)
    images: dict[int, Image.Image] = {}
    for size in ICON_SIZES:
        image = render_icon(size)
        images[size] = Image.frombytes("RGBA", (size, size), bytes(image.constBits()))
    images[1024].save(
        destination / "app-icon.ico",
        sizes=[(size, size) for size in ICON_SIZES if size <= 256],
        append_images=list(images.values()),
    )
    images[1024].save(destination / "app-icon.icns", append_images=list(images.values()))
    images[512].save(destination / "app-icon.png")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".tmp/app-icons"))
    args = parser.parse_args()
    build_icons(args.output)
    print(f"Generated native icons in {args.output}", flush=True)
