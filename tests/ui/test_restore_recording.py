"""Opt-in startup restoration uses normal imports and preserves manual choices."""

# cspell:words Letzte Datei wieder öffnen

from pathlib import Path

from PySide6.QtCore import QEvent, QThreadPool
from PySide6.QtWidgets import QApplication, QDialogButtonBox
import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.preferences import SettingsDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


def test_restore_setting_is_localized_and_saved_only_on_save(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.set_ui_language(1)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    assert dialog.restore_last_file.text() == "Letzte Datei wieder öffnen"
    assert not dialog.restore_last_file.isChecked()
    dialog.restore_last_file.setChecked(True)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert not window.preferences.restore_last_file()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and not dialog.restore_last_file.isChecked()
    dialog.restore_last_file.setChecked(True)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert Preferences(window.preferences.path).restore_last_file()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and dialog.restore_last_file.isChecked()
    dialog.reject()


@pytest.mark.parametrize("extension", ["forces", "zforces"])
def test_successful_recording_restores_on_new_window_and_failed_open_keeps_path(
    explorer_window: ExplorerWindow,
    extension: str,
    export_directory: Path,
) -> None:
    window = explorer_window
    source = next(REAL_FIXTURE_DIRECTORY.glob(f"Manta-*.{extension}"))
    window.open_path(source)
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    assert window.preferences.last_recording() == source.resolve()
    window.preferences.remember_restore_last_file(True)
    restored = ExplorerWindow(AppSettings(language=Language.ENGLISH))
    try:
        restored.show()
        wait_until(lambda: restored.data is not None and restored.open_action.isEnabled())
        assert restored.data is not None
        assert restored.data.source.source_sha256 == window.data.source.source_sha256
        restored.open_path(export_directory / "missing.forces")
        wait_until(restored.open_action.isEnabled)
        assert restored.preferences.last_recording() == source.resolve()
        assert restored.data is not None
        assert restored.data.source.source_sha256 == window.data.source.source_sha256
    finally:
        restored.close()
        QThreadPool.globalInstance().waitForDone()
        restored.deleteLater()
        QApplication.sendPostedEvents(restored, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("case", ["disabled", "missing", "manual"])
def test_startup_skips_disabled_or_missing_file_and_respects_manual_import(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    case: str,
) -> None:
    source = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    preferences = explorer_window.preferences
    preferences.remember_recording(
        export_directory / "missing.forces" if case == "missing" else source,
    )
    preferences.remember_restore_last_file(case != "disabled")
    restored = ExplorerWindow(AppSettings(language=Language.ENGLISH))
    try:
        if case == "manual":
            source = next(REAL_FIXTURE_DIRECTORY.glob("Taron-*.forces"))
            restored.open_path(source)
        restored.show()
        wait_until(lambda: restored.windowHandle().isExposed())
        wait_until(restored.open_action.isEnabled)
        if case == "manual":
            assert restored.data is not None and restored.data.title == "Taron"
            assert preferences.last_recording() == source.resolve()
        else:
            assert restored.data is None
    finally:
        restored.close()
        QThreadPool.globalInstance().waitForDone()
        restored.deleteLater()
        QApplication.sendPostedEvents(restored, QEvent.Type.DeferredDelete)
