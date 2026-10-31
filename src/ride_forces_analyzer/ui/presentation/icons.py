"""Shared application artwork and custom UI icons.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from math import cos, pi, sin

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_SOURCE = Path(__file__).with_name("app-icon.svg")
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)


def data_export_icon() -> QIcon:
    """Create a document with an outgoing arrow using an active QApplication.

    Returns:
        A transparent 20-pixel export icon rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    document = QPainterPath()
    document.moveTo(12, 7)
    document.lineTo(12, 5)
    document.lineTo(9, 2)
    document.lineTo(2, 2)
    document.lineTo(2, 18)
    document.lineTo(12, 18)
    document.lineTo(12, 15)
    painter.setPen(QPen(QColor("#354052"), 1.5))
    painter.setBrush(QColor("#e5eaf0"))
    painter.drawPath(document)
    painter.drawLine(9, 2, 9, 5)
    painter.drawLine(9, 5, 12, 5)
    _paint_export_arrow(painter)
    painter.end()
    return QIcon(pixmap)


def video_export_icon() -> QIcon:
    """Create a film frame with an outgoing arrow using an active QApplication.

    Returns:
        A transparent 20-pixel video export icon rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#354052"), 1))
    painter.setBrush(QColor("#e5eaf0"))
    painter.drawRoundedRect(1, 2, 14, 16, 1, 1)
    painter.setBrush(QColor("#354052"))
    painter.drawRect(5, 4, 6, 12)
    for y in (4, 8, 12, 16):
        painter.drawRect(2, y, 1, 1)
        painter.drawRect(13, y, 1, 1)
    _paint_export_arrow(painter)
    painter.end()
    return QIcon(pixmap)


def _paint_export_arrow(painter: QPainter) -> None:
    """Draw the common outgoing arrow onto an active icon painter."""
    arrow = QPainterPath()
    arrow.moveTo(6, 9)
    arrow.lineTo(14, 9)
    arrow.lineTo(14, 6)
    arrow.lineTo(19, 11)
    arrow.lineTo(14, 16)
    arrow.lineTo(14, 13)
    arrow.lineTo(6, 13)
    arrow.closeSubpath()
    painter.setPen(QPen(QColor("#203020"), 1))
    painter.setBrush(QColor("#70d43b"))
    painter.drawPath(arrow)


def zoom_selection_icon() -> QIcon:
    """Create a magnifier over a selected interval using an active QApplication.

    Returns:
        A transparent 20-pixel zoom icon rendered at double pixel density.
    """
    return _magnifier_icon(reset=False)


def reset_view_icon() -> QIcon:
    """Create a magnifier with a small red X using an active QApplication.

    Returns:
        A transparent 20-pixel reset icon rendered at double pixel density.
    """
    return _magnifier_icon(reset=True)


def _magnifier_icon(*, reset: bool) -> QIcon:
    """Draw the shared magnifier with a reset or selection marker.

    Args:
        reset: Whether to draw a red X instead of the selected interval.

    Returns:
        The decorated magnifier icon.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#354052"), 2))
    painter.setBrush(QColor("#e5eaf0"))
    painter.drawEllipse(2, 2, 11, 11)
    handle_pen = QPen(QColor("#354052"), 3)
    handle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(handle_pen)
    painter.drawLine(12, 12, 18, 18)
    if reset:
        painter.setPen(QPen(QColor("#dc2626"), 2))
        painter.drawLine(5, 5, 10, 10)
        painter.drawLine(5, 10, 10, 5)
    else:
        painter.setPen(QPen(QColor("#2563eb"), 1))
        painter.setBrush(QColor("#8cb8f2"))
        painter.drawRect(5, 5, 5, 5)
    painter.end()
    return QIcon(pixmap)


def select_visible_icon() -> QIcon:
    """Create visible-range selection brackets using an active QApplication.

    Returns:
        A transparent 20-pixel range icon rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(4, 5, 12, 10, QColor("#8cb8f2"))
    painter.setPen(QPen(QColor("#354052"), 2))
    for x, inside in ((2, 5), (18, 15)):
        painter.drawLine(x, 3, x, 17)
        painter.drawLine(x, 3, inside, 3)
        painter.drawLine(x, 17, inside, 17)
    painter.end()
    return QIcon(pixmap)


def gps_overview_icon() -> QIcon:
    """Create a map with a location marker using an active QApplication.

    Returns:
        A transparent 20-pixel GPS icon rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline = QPen(QColor("#354052"), 1)
    painter.setPen(outline)
    painter.setBrush(QColor("#d5e6d1"))
    map_path = QPainterPath()
    map_path.moveTo(1, 6)
    map_path.lineTo(6, 3)
    map_path.lineTo(12, 6)
    map_path.lineTo(18, 3)
    map_path.lineTo(18, 16)
    map_path.lineTo(12, 19)
    map_path.lineTo(6, 16)
    map_path.lineTo(1, 19)
    map_path.closeSubpath()
    painter.drawPath(map_path)
    painter.drawLine(6, 3, 6, 16)
    painter.drawLine(12, 6, 12, 19)
    marker = QPainterPath()
    marker.moveTo(13, 14)
    marker.cubicTo(11, 11, 8, 8, 8, 6)
    marker.cubicTo(8, 0, 18, 0, 18, 6)
    marker.cubicTo(18, 8, 15, 11, 13, 14)
    marker.closeSubpath()
    painter.setBrush(QColor("#dc5347"))
    painter.drawPath(marker)
    painter.setBrush(QColor("#f5f7fa"))
    painter.drawEllipse(11, 4, 4, 4)
    painter.end()
    return QIcon(pixmap)


def clipboard_icon() -> QIcon:
    """Create a clipboard symbol using an active QApplication.

    Returns:
        A transparent 20-pixel clipboard rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#354052"), 1.2))
    painter.setBrush(QColor("#aab4bf"))
    painter.drawRoundedRect(3, 3, 14, 16, 2, 2)
    painter.setBrush(QColor("#f5f7fa"))
    painter.drawRect(5, 5, 10, 12)
    painter.setBrush(QColor("#aab4bf"))
    painter.drawRoundedRect(7, 1, 6, 5, 1, 1)
    for y in (9, 12, 15):
        painter.drawLine(7, y, 13, y)
    painter.end()
    return QIcon(pixmap)


def settings_icon() -> QIcon:
    """Create the shared gear icon with an active QApplication.

    Returns:
        A transparent 20-pixel gear rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    gear = QPainterPath()
    for index in range(32):
        angle = index * pi / 16
        radius = (7, 9, 9, 7)[index % 4]
        x, y = 10 + radius * cos(angle), 10 + radius * sin(angle)
        if index == 0:
            gear.moveTo(x, y)
        else:
            gear.lineTo(x, y)
    gear.closeSubpath()
    gear.addEllipse(7, 7, 6, 6)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#354052"), 1))
    painter.setBrush(QColor("#aab4bf"))
    painter.drawPath(gear)
    painter.end()
    return QIcon(pixmap)


def icon_with_plus(base: QIcon) -> QIcon:
    """Add the shared green plus badge to a UI icon.

    Args:
        base: Icon to decorate; requires an active QApplication.

    Returns:
        A transparent 20-pixel icon rendered at double pixel density.
    """
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    base.paint(painter, 0, 0, 20, 20)
    for color, width in ((QColor("#203020"), 5), (QColor("#70d43b"), 3)):
        painter.setPen(QPen(color, width))
        painter.drawLine(12, 15, 17, 15)
        painter.drawLine(15, 12, 15, 17)
    painter.end()
    return QIcon(pixmap)


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
