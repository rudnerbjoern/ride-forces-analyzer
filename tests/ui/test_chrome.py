"""Native caption appearance across application windows and Qt dialog families."""

# cspell:words dwmapi

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog, QWidget

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
    dialogs = (
        SettingsDialog(window.preferences, window, language=window.ui_language),
        AboutDialog(window, window.updates),
        ExportDialog(window.data, 0, 10, window, store=store),
        BatchDialog(store, window),
        gps_dialog(GpsOverview((((0, 0), (1, 1)),), 2, 2), "GPS", window),
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

    try:
        window.set_appearance(0)
        for dialog in dialogs:
            dialog.show()
        QApplication.processEvents()
        for widget in (window, *dialogs):
            assert is_dark(widget), type(widget).__name__
        window.set_appearance(1)
        QApplication.processEvents()
        for widget in (window, *dialogs):
            assert not is_dark(widget), type(widget).__name__
        window.set_appearance(0)
        QApplication.processEvents()
        for dialog in dialogs:
            assert is_dark(dialog), type(dialog).__name__
            dialog.hide()
            dialog.show()
        QApplication.processEvents()
        for dialog in dialogs:
            assert is_dark(dialog), type(dialog).__name__
        # A queued caption update must not outlive its dialog.
        transient = QMessageBox(window)
        transient.show()
        transient.deleteLater()
        QApplication.processEvents()
    finally:
        for dialog in reversed(dialogs):
            dialog.close()
