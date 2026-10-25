"""Shared SVG identity for window icons and native package artwork.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON_SOURCE = Path(__file__).with_name("app-icon.svg")
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)


def render_icon(size: int) -> QImage:
    """Rasterize the canonical SVG without creating a window or QApplication.

    Returns:
        An RGBA image with transparent corners at the requested pixel size.

    Raises:
        ValueError: The bundled SVG cannot be loaded.

    Args:
        size: Required dimensions or capacity.
    """
    renderer = QSvgRenderer(str(ICON_SOURCE))
    if not renderer.isValid():
        raise ValueError("Application SVG icon is invalid")
    image = QImage(size, size, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image
