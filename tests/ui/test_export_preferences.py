"""Explicit export defaults persist independently of temporary settings and presets."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

from ride_forces_analyzer.analysis.recording import source_app_configuration

# cspell:words Einstellungen

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QToolBar

from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.storage.export_models import SavedPreset
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.storage.preferences import Appearance, Preferences
from ride_forces_analyzer.storage.map_tiles import TileCache, TileEntry
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.preferences import SettingsDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_settings_clear_map_cache_is_immediate_and_reports_failure(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.set_ui_language(1)
    cache = TileCache()
    entry = TileEntry(b"image", 1234, '"etag"', "date")
    cache.put("provider", 0, 0, 0, entry)
    assert cache.get("provider", 0, 0, 0) == entry
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    assert dialog.clear_map_cache.text() == tr("Clear map cache ({0} tiles)", 1)
    assert dialog.clear_map_cache.isEnabled()
    dialog.clear_map_cache.click()
    assert cache.get("provider", 0, 0, 0) is None
    assert dialog.clear_map_cache.text() == tr("Map cache cleared.")
    assert not dialog.clear_map_cache.isEnabled()
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    assert cache.get("provider", 0, 0, 0) is None
    assert window.preferences.language() == "de"
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and not dialog.clear_map_cache.isEnabled()
    dialog.reject()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    cache.path.unlink()
    cache.path.mkdir()
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    assert dialog.clear_map_cache.text() == tr("Clear map cache")
    dialog.clear_map_cache.click()
    assert dialog.clear_map_cache.text() == tr("Could not clear map cache. Try again later.")
    assert dialog.isVisible() and dialog.clear_map_cache.isEnabled()
    dialog.reject()


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
    assert dialog.render_jobs.currentText() == "1"
    assert [dialog.render_jobs.itemText(index) for index in range(dialog.render_jobs.count())] == [
        str(jobs) for jobs in range(1, dialog.render_jobs.count() + 1)
    ]
    jobs = min(2, dialog.render_jobs.count())
    dialog.render_jobs.setCurrentIndex(jobs - 1)
    dialog.frame_rate.setCurrentText("59.94")
    dialog.automatic_updates.setChecked(True)
    dialog.language.setCurrentIndex(0)
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.DARK.value))
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert window.ui_language == "de" and window.appearance_preference is Appearance.LIGHT
    assert window.preferences.export_fps() is StandardFrameRate.FPS_50
    assert window.preferences.render_jobs() == 1
    assert not window.preferences.automatic_updates()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)

    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    dialog.frame_rate.setCurrentText("59.94")
    dialog.automatic_updates.setChecked(True)
    dialog.render_jobs.setCurrentIndex(jobs - 1)
    dialog.language.setCurrentIndex(0)
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.DARK.value))
    dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert window.ui_language == "en" and window.appearance_preference is Appearance.DARK
    assert Preferences(window.preferences.path).export_fps() == "60000/1001"
    assert Preferences(window.preferences.path).render_jobs() == jobs
    assert Preferences(window.preferences.path).automatic_updates()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None and dialog.frame_rate.currentText() == "59.94"
    assert dialog.render_jobs.currentText() == str(jobs)
    dialog.frame_rate.setCurrentText("23.976")
    dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert Preferences(window.preferences.path).export_fps() == "24000/1001"

    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    with TemporaryDirectory(dir=".tmp") as temporary:
        store = ExportStore(Path(temporary) / "exports.sqlite3")
        store.save_preset(
            SavedPreset(
                name="Film",
                settings=ExportSettings(fps=25),
                analysis_configuration=source_app_configuration(),
                schema_version=1,
                smoothing_window=11,
                range_mode="markers",
            ),
        )
        store.save_preset(
            SavedPreset(
                name="Z custom rate",
                settings=ExportSettings(fps=27),
                analysis_configuration=source_app_configuration(),
                schema_version=1,
                smoothing_window=11,
                range_mode="markers",
            ),
        )
        export = ExportDialog(window.data, 0, 10, window, store=store)
        assert export.fps.currentText() == "23.976"
        assert StandardFrameRate(export.fps.currentData()) is StandardFrameRate.FPS_23_976
        export.fps.setCurrentText("60")
        export.close()
        reopened = ExportDialog(window.data, 0, 10, window, store=store)
        assert reopened.fps.currentText() == "23.976"
        reopened.preset_selector.setCurrentIndex(1)
        reopened.load_preset.click()
        assert reopened.fps.currentText() == "25"
        reopened.preset_selector.setCurrentIndex(
            reopened.preset_selector.findText("Z custom rate"),
        )
        reopened.load_preset.click()
        assert reopened.fps.currentText() == "27" and reopened.fps.currentData() == 27
        assert Preferences(window.preferences.path).export_fps() == "24000/1001"
        reopened.close()
