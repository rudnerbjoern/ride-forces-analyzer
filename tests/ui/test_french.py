"""French switching, Qt dialogs and explicit saved export language."""

# cspell:words Français Paramètres Annuler Préréglage Inclinaison aperçu

from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QInputDialog, QPushButton
import pytest

from ride_forces_analyzer.i18n import get_language
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.preferences import SettingsDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until
from tests.ui.test_localization import assert_combo_text_fits


def test_french_settings_and_export_preserve_source_and_explicit_language(
    explorer_window: ExplorerWindow,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    window.position.setValue(3600)
    window.settings_action.trigger()
    preferences = window.findChild(SettingsDialog, "settingsDialog")
    assert preferences is not None
    assert [preferences.language.itemText(index) for index in range(3)] == [
        "English",
        "Deutsch",
        "Français",
    ]
    preferences.language.setCurrentIndex(2)
    preferences.save()
    assert get_language() == "fr"
    assert window.preferences.language() == "fr"
    assert window.data is data and window.position.value() == 3600
    assert window.settings_action.text() == "Paramètres…"
    window.settings_action.trigger()
    preferences = next(
        dialog for dialog in window.findChildren(SettingsDialog) if dialog.isVisible()
    )
    assert preferences.language.currentText() == "Français"
    assert preferences.buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Annuler"
    assert_combo_text_fits(preferences.language)
    preferences.reject()

    store = ExportStore(export_directory / "french.sqlite3")
    dialog = ExportDialog(data, 3500, 3700, window, current_sample=3600, store=store)
    try:
        dialog.show()
        wait_until(lambda: dialog.preview_result is not None)
        assert dialog.overlay_language.currentText() == "Français"
        for combo in (
            dialog.overlay_language,
            dialog.layout_profile,
            dialog.position,
            dialog.aspect,
        ):
            assert_combo_text_fits(combo)
        for button in dialog.findChildren(QPushButton):
            if button.isVisible():
                assert (
                    button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 12
                ), button.text()

        def preset_name(*args: object, **kwargs: object) -> tuple[str, bool]:
            return "Préréglage {0}", True

        monkeypatch.setattr(QInputDialog, "getText", preset_name)
        dialog.save_preset.click()
        assert store.presets()[0].settings.language == "fr"
        dialog.overlay_language.setCurrentIndex(0)
        dialog.load_preset.click()
        assert dialog.overlay_language.currentText() == "Français"
        window.set_ui_language(0)
        QApplication.processEvents()
        assert dialog.overlay_language.currentIndex() == 2
        assert window.data is not None
        assert data.source is window.data.source
    finally:
        dialog.close()
