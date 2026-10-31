"""Optional Windows taskbar presentation of the existing export progress.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words ole32 CLSCTX HRESULT hwnd CoInitializeEx CoUninitialize CoCreateInstance
# cspell:words ITaskbarList HrInit TaskbarButtonCreated RegisterWindowMessageW
# cspell:words COINIT APARTMENTTHREADED clsid vtable WINFUNCTYPE ulonglong TBPF NOPROGRESS

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
from uuid import UUID

from PySide6.QtCore import QByteArray, QAbstractNativeEventFilter, QCoreApplication, QObject
from PySide6.QtWidgets import QWidget


def _check(result: int) -> None:
    """Reject a failed signed Windows HRESULT.

    Args:
        result: HRESULT returned by a native COM operation.

    Raises:
        OSError: Windows rejected the operation.
    """
    if result < 0:
        raise OSError(f"Taskbar operation failed: 0x{result & 0xFFFFFFFF:08X}")


class WindowsTaskbar:
    """Own one initialized ITaskbarList3 interface on the calling GUI thread.

    Raises:
        OSError: COM initialization, shell activation or HrInit fails.
    """

    def __init__(self, window_id: int) -> None:
        """Initialize the native shell interface after taskbar-button creation.

        Args:
            window_id: HWND of the owning explorer window.

        Raises:
            OSError: The shell interface cannot be initialized.
        """
        self._window_id = window_id
        self._pointer = ctypes.c_void_p()
        self._interface_ready = False
        self._ole = ctypes.WinDLL("ole32")
        self._ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        self._ole.CoInitializeEx.restype = ctypes.c_long
        self._ole.CoUninitialize.argtypes = []
        self._ole.CoUninitialize.restype = None
        self._ole.CoCreateInstance.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._ole.CoCreateInstance.restype = ctypes.c_long
        result = self._ole.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
        # Qt may already own COM in a different apartment; do not uninitialize it.
        if result != -2147417850:  # RPC_E_CHANGED_MODE
            _check(result)
        self._initialized = result >= 0
        try:
            clsid = (ctypes.c_byte * 16).from_buffer_copy(
                UUID("56FDF344-FD6D-11D0-958A-006097C9A090").bytes_le,
            )
            iid = (ctypes.c_byte * 16).from_buffer_copy(
                UUID("EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF").bytes_le,
            )
            _check(self._ole.CoCreateInstance(clsid, None, 1, iid, ctypes.byref(self._pointer)))
            vtable = ctypes.cast(
                self._pointer,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
            ).contents
            # IUnknown (0..2), ITaskbarList (3..7), ITaskbarList2 (8), then progress.
            self._release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])
            initialize = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
            self._set_value = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                wintypes.HWND,
                ctypes.c_ulonglong,
                ctypes.c_ulonglong,
            )(vtable[9])
            self._set_state = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                wintypes.HWND,
                wintypes.DWORD,
            )(vtable[10])
            _check(initialize(self._pointer))
            self._interface_ready = True
        except OSError:
            self.close()
            raise

    def show(self, percent: int | None) -> None:
        """Show indeterminate activity or a percentage for the owning window.

        Args:
            percent: Percentage, or None while preparing an export.

        Raises:
            OSError: The shell rejected the update.
        """
        if percent is None:
            _check(self._set_state(self._pointer, self._window_id, 1))  # TBPF_INDETERMINATE
        else:
            _check(self._set_value(self._pointer, self._window_id, percent, 100))

    def close(self) -> None:
        """Remove progress, release the COM interface and balance initialization.

        Raises:
            OSError: Removing shell progress failed; COM resources are still released.
        """
        try:
            if self._pointer.value:
                try:
                    if self._interface_ready:
                        # TBPF_NOPROGRESS
                        _check(self._set_state(self._pointer, self._window_id, 0))
                finally:
                    self._release(self._pointer)
                    self._pointer = ctypes.c_void_p()
        finally:
            if self._initialized:
                self._ole.CoUninitialize()
                self._initialized = False


class _TaskbarButtonFilter(QAbstractNativeEventFilter):
    """Wait for the shell's taskbar button before issuing progress updates."""

    def __init__(self, progress: TaskbarProgress, message_id: int) -> None:
        super().__init__()
        self._progress = progress
        self._message_id = message_id

    def nativeEventFilter(
        self,
        eventType: QByteArray | bytes | bytearray | memoryview,
        message: int,
    ) -> bool:
        """Observe button creation, including recreation after Explorer restarts.

        Args:
            eventType: Qt native message category.
            message: Pointer to the native Windows MSG.

        Returns:
            A false handled flag so normal Qt message processing continues.
        """
        # Qt pointer wrappers can be false despite holding a nonzero address.
        if eventType == b"windows_generic_MSG" and int(message):
            native = wintypes.MSG.from_address(int(message))
            window_id = int(self._progress.window.effectiveWinId())
            if native.message == self._message_id and native.hWnd == window_id:
                self._progress.button_created()
        return False


class TaskbarProgress(QObject):
    """Mirror export progress to one explorer window's Windows taskbar button.

    Create before showing the explorer so TaskbarButtonCreated is observed. Calls
    belong to the GUI thread. Non-Windows platforms and unavailable shell services
    are harmless no-ops; progress never controls or interrupts the export itself.

    Attributes:
        window: Root application window owning the taskbar button and this object.
    """

    def __init__(self, window: QWidget) -> None:
        """Bind optional native integration to the root window lifetime.

        Args:
            window: Root window, before its first show.
        """
        super().__init__(window)
        self.window = window
        self._active = False
        self._ready = False
        self._failed = False
        self._percent: int | None = None
        self._native: WindowsTaskbar | None = None
        self._filter: _TaskbarButtonFilter | None = None
        self._application = QCoreApplication.instance()
        if sys.platform == "win32" and self._application is not None:
            try:
                register = ctypes.WinDLL("user32").RegisterWindowMessageW
                register.argtypes = [wintypes.LPCWSTR]
                register.restype = wintypes.UINT
                message_id = register("TaskbarButtonCreated")
                if message_id:
                    self._filter = _TaskbarButtonFilter(self, message_id)
                    self._application.installNativeEventFilter(self._filter)
            except OSError:
                pass
        window.destroyed.connect(self._dispose)

    def button_created(self) -> None:
        """Apply any queued state after the shell creates or recreates the button."""
        self._ready = True
        self._apply()

    def start(self) -> None:
        """Show indeterminate preparation for a newly started export or batch."""
        self.clear()
        self._failed = False
        self._active = True
        self._percent = None
        self._apply()

    def set_value(self, percent: int) -> None:
        """Mirror an already calculated percentage without recalculating progress.

        Args:
            percent: Existing video or overall batch percentage, clamped to 0–100.
        """
        value = min(100, max(0, percent))
        if self._active and self._percent == value:
            return
        self._active = True
        self._percent = value
        self._apply()

    def clear(self) -> None:
        """Remove progress on success, failure, cancellation or window disposal."""
        self._active = False
        if self._native is not None:
            native, self._native = self._native, None
            try:
                native.close()
            except OSError:
                pass

    def _apply(self) -> None:
        if not self._ready or not self._active or self._failed or self._filter is None:
            return
        try:
            if self._native is None:
                self._native = WindowsTaskbar(int(self.window.winId()))
            self._native.show(self._percent)
        except OSError:
            self._failed = True
            self.clear()

    def _dispose(self) -> None:
        self.clear()
        if self._application is not None and self._filter is not None:
            self._application.removeNativeEventFilter(self._filter)
            self._filter = None


def taskbar_progress(owner: QWidget) -> TaskbarProgress:
    """Return the shared controller for the root window, including nested dialogs.

    Args:
        owner: Explorer window or a dialog belonging to it.

    Returns:
        Existing root controller, or a new controller for an unbound root window.
    """
    root = owner
    while (parent := root.parentWidget()) is not None:
        root = parent
    for child in root.children():
        if isinstance(child, TaskbarProgress):
            return child
    return TaskbarProgress(root)
