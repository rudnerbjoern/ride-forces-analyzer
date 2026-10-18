"""Explicit export defaults persist independently of temporary settings and presets."""

# cspell:words Einstellungen

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QToolBar

from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.storage.export_models import SavedPreset
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.preferences import SettingsDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_settings_save_cancel_and_new_exports_keep_independent_frame_rates(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.set_ui_language(1)
    window.set_appearance(1)
    toolbar = window.findChild(QToolBar)
    assert toolbar is not None and not toolbar.findChildren(QComboBox)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and dialog.isVisible()
    assert dialog.windowTitle() == "Einstellungen"
    assert dialog.frame_rate.currentText() == "50"
    dialog.frame_rate.setCurrentText("59.94")
    dialog.language.setCurrentIndex(0)
    dialog.appearance.setCurrentIndex(0)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert window.ui_language == "de" and window.appearance_preference == "light"
    assert window.preferences.export_fps() == 50
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)

    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    dialog.frame_rate.setCurrentText("59.94")
    dialog.language.setCurrentIndex(0)
    dialog.appearance.setCurrentIndex(0)
    dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert window.ui_language == "en" and window.appearance_preference == "dark"
    assert Preferences(window.preferences.path).export_fps() == "60000/1001"
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and dialog.frame_rate.currentText() == "59.94"
    dialog.reject()

    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    with TemporaryDirectory(dir=".tmp") as temporary:
        store = ExportStore(Path(temporary) / "exports.sqlite3")
        store.save_preset(SavedPreset(name="Film", settings=ExportSettings(fps=25)))
        export = ExportDialog(window.data, 0, 10, window, store=store)
        assert export.fps.currentText() == "59.94"
        export.fps.setCurrentText("60")
        export.close()
        reopened = ExportDialog(window.data, 0, 10, window, store=store)
        assert reopened.fps.currentText() == "59.94"
        reopened.preset_selector.setCurrentIndex(1)
        reopened.load_preset.click()
        assert reopened.fps.currentText() == "25"
        assert Preferences(window.preferences.path).export_fps() == "60000/1001"
        reopened.close()
