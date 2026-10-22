"""App identity and native Windows caption colors; standard window controls remain.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap pixmap COLORREF BBGGRR dwmapi

import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget


class NativeCaptionFilter(QObject):
    """Apply native colors after Qt finishes showing or restyling an app window."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, (QDialog, QMainWindow)) and event.type() in (
            QEvent.Type.Show,
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        ):
            # The widget context cancels delivery if the window is destroyed first.
            QTimer.singleShot(0, watched, lambda: self._apply(watched))
        return False

    @staticmethod
    def _apply(window: QWidget) -> None:
        if window.isVisible():
            style_native_caption(
                int(window.winId()),
                palette=window.palette(),
            )


def install_native_captions(application: QApplication) -> None:
    """Install one Windows caption observer for Qt-managed application windows."""
    if sys.platform == "win32" and application.findChild(NativeCaptionFilter) is None:
        observer = NativeCaptionFilter(application)
        application.installEventFilter(observer)


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


def style_native_caption(window_id: int, *, palette: QPalette) -> None:
    """Use supported DWM attributes, allowing older Windows to retain defaults."""
    if sys.platform != "win32":
        return
    try:
        setter = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        # COLORREF uses 0x00BBGGRR. Unsupported attributes leave native defaults.
        attributes = [(20, int(palette.window().color().lightness() < 128))]
        for attribute, role in (
            (34, QPalette.ColorRole.Mid),
            (35, QPalette.ColorRole.Window),
            (36, QPalette.ColorRole.WindowText),
        ):
            color = palette.color(role)
            attributes.append((attribute, color.red() | color.green() << 8 | color.blue() << 16))
        for attribute, value in attributes:
            setting = wintypes.DWORD(value)
            setter(window_id, attribute, ctypes.byref(setting), ctypes.sizeof(setting))
    except OSError:
        # Cosmetic integration must never prevent opening a recording.
        return
