"""App identity and native Windows caption colors; standard window controls remain."""

# cspell:words Pixmap pixmap COLORREF BBGGRR dwmapi

import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def app_icon() -> QIcon:
    """Draw a compact force trace, legible in the caption and taskbar."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 64, size / 64)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#245fe5"))
        painter.drawRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
        trace = QPainterPath(QPointF(8, 35))
        for x, y in ((19, 35), (26, 16), (35, 49), (43, 29), (56, 29)):
            trace.lineTo(x, y)
        painter.setPen(
            QPen(
                QColor("#ffffff"),
                5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            ),
        )
        painter.drawPath(trace)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def style_native_caption(window_id: int, *, dark: bool = True) -> None:
    """Use supported DWM attributes, allowing older Windows to retain defaults."""
    if sys.platform != "win32":
        return
    try:
        setter = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        # COLORREF uses 0x00BBGGRR. Unsupported attributes leave native defaults.
        attributes = (
            ((20, 1), (34, 0x4A392B), (35, 0x2B1F15), (36, 0xF5EBE3))
            if dark
            else ((20, 0), (34, 0xE2D3C6), (35, 0xF6EFE9), (36, 0x422B17))
        )
        for attribute, value in attributes:
            setting = wintypes.DWORD(value)
            setter(window_id, attribute, ctypes.byref(setting), ctypes.sizeof(setting))
    except OSError:
        # Cosmetic integration must never prevent opening a recording.
        return
