"""Native caption appearance across application windows and Qt dialog families."""

# cspell:words dwmapi

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsView,
    QMessageBox,
    QProgressDialog,
    QWidget,
)

from ride_forces_analyzer.gps_overview import GpsOverview
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.about import AboutDialog
from ride_forces_analyzer.ui.batches import BatchDialog
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.gps import gps_dialog
from ride_forces_analyzer.ui.preferences import SettingsDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows caption contract")
@pytest.mark.usefixtures("small_preview_frames")
def test_native_captions_follow_theme_for_all_application_windows(
    explorer_window: ExplorerWindow,
    export_directory: Path,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    store = ExportStore(export_directory / "exports.sqlite3")
    files = QFileDialog(window)
    files.setOption(QFileDialog.Option.DontUseNativeDialog)
    progress = QProgressDialog(window)
    progress.setAutoClose(False)
    export = ExportDialog(window.data, 0, 10, window, store=store)
    batches = BatchDialog(store, window)
    route = gps_dialog(GpsOverview((((0, 0), (1, 1)),), 2, 2), "GPS", window)
    view = route.findChild(QGraphicsView)
    assert view is not None
    dialogs = (
        SettingsDialog(window.preferences, window, language=window.ui_language),
        AboutDialog(window, window.updates),
        export,
        batches,
        route,
        QMessageBox(window),
        progress,
        files,
    )
    getter = ctypes.WinDLL("dwmapi").DwmGetWindowAttribute
    getter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    getter.restype = ctypes.c_long

    def is_dark(widget: QWidget) -> bool:
        value = wintypes.DWORD()
        assert getter(int(widget.winId()), 20, ctypes.byref(value), ctypes.sizeof(value)) == 0
        return bool(value.value)

    def assert_shared_palette() -> None:
        assert view is not None
        assert view.palette().base().color() == QColor(window.theme.panel)
        assert export.seconds.palette().base().color() == window.position.palette().base().color()
        assert batches.table.palette().base().color() == window.position.palette().base().color()
        assert export.preview_result is preview
        scene = view.scene()
        assert scene is not None and scene.backgroundBrush().style().value == 0

    try:
        window.set_appearance(0)
        for dialog in dialogs:
            dialog.show()
        wait_until(lambda: export.preview_result is not None and export.preview_worker is None)
        preview = export.preview_result
        QApplication.processEvents()
        for widget in (window, *dialogs):
            assert is_dark(widget), type(widget).__name__
        assert_shared_palette()
        window.set_appearance(1)
        QApplication.processEvents()
        for widget in (window, *dialogs):
            assert not is_dark(widget), type(widget).__name__
        assert_shared_palette()
        window.set_appearance(0)
        QApplication.processEvents()
        for dialog in dialogs:
            assert is_dark(dialog), type(dialog).__name__
        assert_shared_palette()
        for widget in (window, *dialogs):
            caption = wintypes.DWORD()
            # Custom caption colors require Windows 11; dark captions also work on Windows 10.
            if getter(int(widget.winId()), 35, ctypes.byref(caption), ctypes.sizeof(caption)) == 0:
                color = widget.palette().window().color()
                assert caption.value == color.red() | color.green() << 8 | color.blue() << 16
        for dialog in dialogs:
            dialog.hide()
            dialog.show()
        QApplication.processEvents()
        for dialog in dialogs:
            assert is_dark(dialog) == window.theme.is_dark, type(dialog).__name__
        # A queued caption update must not outlive its dialog.
        transient = QMessageBox(window)
        transient.show()
        transient.deleteLater()
        QApplication.processEvents()
    finally:
        for dialog in reversed(dialogs):
            dialog.close()
