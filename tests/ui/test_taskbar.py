"""Windows shell progress, resource ownership and graceful platform fallbacks."""

# cspell:words qapp ole32 CoInitializeEx CoUninitialize CoCreateInstance hwnd

import ctypes
from ctypes import wintypes
import sys
from typing import cast
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QAbstractNativeEventFilter, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from ride_forces_analyzer.ui.presentation import taskbar
from tests.ui.helpers import wait_until


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shell message contract")
def test_queued_progress_targets_root_and_survives_taskbar_recreation(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = QWidget()
    child = QDialog(root)
    nested = QDialog(child)
    native = Mock()
    create = Mock(return_value=native)
    monkeypatch.setattr(taskbar, "WindowsTaskbar", create)
    install = Mock(wraps=qapp.installNativeEventFilter)
    remove = Mock(wraps=qapp.removeNativeEventFilter)
    monkeypatch.setattr(qapp, "installNativeEventFilter", install)
    monkeypatch.setattr(qapp, "removeNativeEventFilter", remove)
    progress = taskbar.taskbar_progress(root)
    native_filter = cast(QAbstractNativeEventFilter, install.call_args.args[0])
    disposed = False
    try:
        assert taskbar.taskbar_progress(nested) is progress
        progress.start()
        progress.set_value(25)
        create.assert_not_called()  # Wait for TaskbarButtonCreated, not just a Qt show.
        message = wintypes.MSG()
        register = ctypes.WinDLL("user32").RegisterWindowMessageW
        register.argtypes = [wintypes.LPCWSTR]
        register.restype = wintypes.UINT
        message.message = register("TaskbarButtonCreated")
        message.hWnd = int(child.winId())
        native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
        create.assert_not_called()  # An owned dialog is not the explorer's taskbar button.
        message.hWnd = int(root.winId())
        assert native_filter.nativeEventFilter(b"other", ctypes.addressof(message)) is False
        create.assert_not_called()
        assert native_filter.nativeEventFilter(b"windows_generic_MSG", 0) is False
        native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
        create.assert_called_once_with(int(root.winId()))
        native.show.assert_called_once_with(25)
        progress.set_value(25)
        native.show.assert_called_once_with(25)  # Repeated frame percentages do not hit COM.
        progress.set_value(1000)
        native.show.assert_called_with(100)
        progress.set_value(-5)
        native.show.assert_called_with(0)
        native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
        assert native.show.call_count == 4  # Reapply after a shell/button restart.
        progress.clear()
        native.close.assert_called_once()
        progress.clear()
        native.close.assert_called_once()
        progress.start()
        native.show.assert_called_with(None)
        root.deleteLater()
        qapp.sendPostedEvents(root, QEvent.Type.DeferredDelete)
        assert native.close.call_count == 2
        remove.assert_called_once_with(native_filter)
        disposed = True
    finally:
        if not disposed:
            root.deleteLater()
            qapp.sendPostedEvents(root, QEvent.Type.DeferredDelete)


def test_non_windows_never_loads_shell_libraries(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(taskbar.sys, "platform", "linux")
    load = Mock(side_effect=AssertionError("No Windows library on another platform"))
    monkeypatch.setattr(taskbar.ctypes, "WinDLL", load, raising=False)
    root = QWidget()
    progress = taskbar.taskbar_progress(root)
    try:
        progress.start()
        progress.set_value(50)
        progress.button_created()
        progress.clear()
        load.assert_not_called()
    finally:
        root.deleteLater()
        qapp.sendPostedEvents(root, QEvent.Type.DeferredDelete)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows shell fallback contract")
def test_shell_failure_is_nonfatal_and_next_export_can_retry(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = QWidget()
    native = Mock()
    create = Mock(side_effect=[OSError("Shell unavailable"), native])
    monkeypatch.setattr(taskbar, "WindowsTaskbar", create)
    progress = taskbar.taskbar_progress(root)
    try:
        progress.button_created()
        progress.start()
        progress.set_value(20)
        assert create.call_count == 1
        progress.start()
        native.show.assert_called_once_with(None)
        native.show.side_effect = OSError("Shell disconnected")
        native.close.side_effect = OSError("Shell cleanup unavailable")
        progress.set_value(30)
        progress.set_value(40)
        assert native.show.call_count == 2
        native.close.assert_called_once()
    finally:
        root.deleteLater()
        qapp.sendPostedEvents(root, QEvent.Type.DeferredDelete)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM lifetime contract")
@pytest.mark.parametrize("initialized", [0, 1, -2147417850])
def test_failed_com_creation_balances_only_owned_initialization(
    initialized: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ole = Mock()
    ole.CoInitializeEx.return_value = initialized
    ole.CoCreateInstance.return_value = -2147467259
    monkeypatch.setattr(taskbar.ctypes, "WinDLL", Mock(return_value=ole))
    with pytest.raises(OSError, match="Taskbar operation failed"):
        taskbar.WindowsTaskbar(123)
    assert ole.CoUninitialize.call_count == (0 if initialized < 0 else 1)


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows taskbar integration")
def test_real_shell_accepts_progress_for_visible_and_minimized_window(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = QMainWindow()
    progress = taskbar.taskbar_progress(root)
    constructor = taskbar.WindowsTaskbar
    interfaces: list[taskbar.WindowsTaskbar] = []

    def create(window_id: int) -> taskbar.WindowsTaskbar:
        native = constructor(window_id)
        interfaces.append(native)
        return native

    monkeypatch.setattr(taskbar, "WindowsTaskbar", create)
    root.setWindowTitle("Ride Forces Analyzer · taskbar verification")
    try:
        root.show()
        progress.start()
        wait_until(lambda: bool(interfaces))
        native = interfaces[0]
        show = Mock(wraps=native.show)
        close = Mock(wraps=native.close)
        monkeypatch.setattr(native, "show", show)
        monkeypatch.setattr(native, "close", close)
        progress.set_value(25)
        root.showMinimized()
        wait_until(root.isMinimized)
        progress.set_value(75)
        progress.set_value(76)
        assert [call.args[0] for call in show.call_args_list] == [25, 75, 76]
        progress.clear()
        close.assert_called_once()
        native.close()  # Cleanup remains idempotent.
    finally:
        progress.clear()
        root.close()
        root.deleteLater()
        qapp.sendPostedEvents(root, QEvent.Type.DeferredDelete)
