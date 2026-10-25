"""App identity and native Windows caption colors; standard window controls remain.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap pixmap COLORREF BBGGRR dwmapi

import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from .icons import ICON_SIZES, render_icon


class NativeCaptionFilter(QObject):
    """Apply native colors after Qt finishes showing or restyling an app window."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Apply native caption styling when the observed widget changes.

        Args:
            watched: Qt object whose event is being observed.
            event: Qt event delivered to this handler.

        Returns:
            True when the requested check succeeds or the event is handled; otherwise False.
        """
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
    """Install one Windows caption observer for Qt-managed application windows.

    Args:
        application: Native Qt application whose event loop owns the widgets.

    Returns:
        None.
    """
    if sys.platform == "win32" and application.findChild(NativeCaptionFilter) is None:
        observer = NativeCaptionFilter(application)
        application.installEventFilter(observer)


def app_icon() -> QIcon:
    """Draw a lightly raised force trace over a blue gradient at native icon sizes.

    Returns:
        Application icon containing the generated native-size variants.
    """
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon(size)))
    return icon


def style_native_caption(window_id: int, *, palette: QPalette) -> None:
    """Use supported DWM attributes, allowing older Windows to retain defaults.

    Args:
        window_id: Identifier of the owning application window.
        palette: Palette to apply to the view.

    Returns:
        None.
    """
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
