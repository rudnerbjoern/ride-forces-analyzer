"""App identity and native Windows caption colors; standard window controls remain.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap pixmap COLORREF BBGGRR dwmapi

import ctypes
from ctypes import wintypes
import sys

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QIcon, QKeyEvent, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QMainWindow,
    QProxyStyle,
    QStyle,
    QStyleHintReturn,
    QStyleOption,
    QWidget,
)

from ride_forces_analyzer.ui.presentation.icons import ICON_SIZES, render_icon


class AccessKeyStyle(QProxyStyle):
    """Toggle native access-key underlines with bare Alt on Windows.

    Attributes:
        visible: Whether access-key underlines are currently displayed.
    """

    def __init__(self) -> None:
        """Retain native styling and start with hidden access-key underlines."""
        super().__init__()
        self.visible = False
        self._alt_only = False

    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
        returnData: QStyleHintReturn | None = None,
    ) -> int:
        """Override underline visibility and delegate every other native style hint.

        Args:
            hint: Requested Qt style behavior.
            option: Drawing options supplied by Qt.
            widget: Widget being styled, if available.
            returnData: Optional extended result supplied by Qt.

        Returns:
            The toggle state for underlines, otherwise the native style result.
        """
        if hint == QStyle.StyleHint.SH_UnderlineShortcut:
            return int(self.visible)
        return super().styleHint(hint, option, widget, returnData)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Toggle on bare Alt release without consuming keyboard events.

        Args:
            watched: Object receiving the original event.
            event: Qt event delivered to the application.

        Returns:
            False so native keyboard navigation and shortcuts remain active.
        """
        if isinstance(event, QKeyEvent) and not event.isAutoRepeat():
            if event.type() == QEvent.Type.KeyPress:
                self._alt_only = event.key() == Qt.Key.Key_Alt and event.modifiers() in (
                    Qt.KeyboardModifier.NoModifier,
                    Qt.KeyboardModifier.AltModifier,
                )
            elif event.type() == QEvent.Type.ShortcutOverride and event.key() != Qt.Key.Key_Alt:
                self._alt_only = False
            elif event.type() == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Alt:
                if self._alt_only:
                    self.visible = not self.visible
                    for button in QApplication.allWidgets():
                        if isinstance(button, QAbstractButton) and button.isVisible():
                            button.update()
                self._alt_only = False
        return False


def install_access_key_cues(application: QApplication) -> None:
    """Install the Windows Alt toggle once, preserving native styling elsewhere.

    Args:
        application: Application owning the style and keyboard event filter.
    """
    if sys.platform == "win32" and application.findChild(AccessKeyStyle) is None:
        style = AccessKeyStyle()
        style.setParent(application)
        application.setStyle(style)
        application.installEventFilter(style)


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
