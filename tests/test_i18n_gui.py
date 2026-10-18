"""Native language switching and German layouts over unchanged recording data."""

# cspell:words Aufnahme öffnen Ansicht zurücksetzen Kalibrierte Kräfte Reihe Fahrtzeit Messpunkte zurück Abbrechen prüfen Bahn Schließen Hochformat Meine Vorgabe exportieren Quellwert bleibt erhalten

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import sys
from textwrap import dedent

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QInputDialog,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
)
import pytest

from ride_forces_analyzer.i18n import get_language
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.batches import BatchDialog
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.window import ExplorerWindow
from ride_forces_analyzer.ui.preferences import SettingsDialog
from test_explorer_gui import explorer_window as explorer_window, resize_workspace, wait_until
from test_project import REAL_FIXTURE_DIRECTORY


def assert_combo_text_fits(combo: QComboBox) -> None:
    option = QStyleOptionComboBox()
    option.initFrom(combo)
    option.currentText = combo.currentText()
    field = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxEditField,
        combo,
    )
    for index in range(combo.count()):
        text = combo.itemText(index)
        assert field.width() >= combo.fontMetrics().horizontalAdvance(text), (
            text,
            field.width(),
            combo.width(),
        )


@pytest.mark.parametrize("appearance", [0, 1])
def test_settings_choices_fit_after_repeated_language_switches(
    explorer_window: ExplorerWindow,
    appearance: int,
) -> None:
    window = explorer_window
    window.set_appearance(appearance)
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    try:
        for language in (0, 1, 0, 1):
            window.set_ui_language(language)
            QApplication.processEvents()
            assert_combo_text_fits(dialog.appearance)
            assert_combo_text_fits(dialog.language)
    finally:
        dialog.reject()
        window.set_ui_language(0)
        window.set_appearance(0)


@pytest.mark.parametrize(
    "scale_factor,workspace_size,dialog_size",
    [("1.5", (2560, 1400), (2200, 1200)), ("2", (1920, 1040), (1800, 960))],
    ids=["4k-150-percent", "4k-200-percent"],
)
def test_german_export_in_4k_workspace_keeps_controls_reachable(
    scale_factor: str,
    workspace_size: tuple[int, int],
    dialog_size: tuple[int, int],
) -> None:
    script = dedent("""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import time
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QComboBox, QScrollArea, QStyle, QStyleOptionComboBox
        from ride_forces_analyzer.config import AppSettings
        from ride_forces_analyzer.explorer import ExplorerData, load_recording
        from ride_forces_analyzer.storage.exports import ExportStore
        from ride_forces_analyzer.ui.window import ExplorerWindow
        from ride_forces_analyzer.ui.export import ExportDialog
        app = QApplication([])
        directory = TemporaryDirectory(dir='.tmp')
        window = ExplorerWindow(AppSettings(language='de'))
        data = load_recording(next(Path('tests').rglob('Manta-*.forces')))
        assert isinstance(data, ExplorerData)
        window._loaded(data)
        # Test layout dimensions independently of the runner's physical desktop.
        window.setMinimumSize(*WORKSPACE_SIZE)
        window.show()
        dialog = ExportDialog(data, 0, data.count-1, window,
                              store=ExportStore(Path(directory.name)/'exports.sqlite3'))
        dialog.setMinimumSize(*DIALOG_SIZE)
        dialog.show()
        deadline = time.monotonic() + 20
        failures = []
        def inspect():
            if dialog.preview_result is None and time.monotonic() < deadline:
                QTimer.singleShot(50, inspect)
                return
            try:
                assert dialog.preview_result is not None
                scroll = dialog.findChild(QScrollArea, 'exportContentScroll')
                assert (window.width(), window.height()) == WORKSPACE_SIZE
                assert (dialog.width(), dialog.height()) == DIALOG_SIZE
                assert scroll is not None and scroll.verticalScrollBar().maximum() == 0
                assert dialog.next.isVisible() and dialog.rect().contains(dialog.next.geometry())
                assert dialog.next.text() == 'Export prüfen →'
                for language in (0, 1, 0, 1):
                    window.set_ui_language(language)
                    app.processEvents()
                    for parent in (window, dialog):
                        for combo in parent.findChildren(QComboBox):
                            if not combo.isVisible():
                                continue
                            option = QStyleOptionComboBox()
                            option.initFrom(combo)
                            option.currentText = combo.currentText()
                            field = combo.style().subControlRect(
                                QStyle.ComplexControl.CC_ComboBox, option,
                                QStyle.SubControl.SC_ComboBoxEditField, combo)
                            for index in range(combo.count()):
                                text = combo.itemText(index)
                                assert field.width() >= combo.fontMetrics().horizontalAdvance(text), text
                assert scroll.horizontalScrollBar().maximum() == 0
                # One separate compact fallback check; this is not the 4K reference layout.
                if DIALOG_SIZE == (1800, 960):
                    dialog.setMinimumSize(0, 0)
                    available = dialog.screen().availableGeometry()
                    decoration = dialog.frameGeometry().size() - dialog.size()
                    dialog.resize(min(960, available.width() - decoration.width()),
                                  min(400, available.height() - decoration.height()))
                    app.processEvents()
                    assert scroll.verticalScrollBar().maximum() > 0
                    assert dialog.next.isVisible() and dialog.rect().contains(dialog.next.geometry())
                    assert dialog.frameGeometry().height() <= available.height()
                print('PASS: native German export in 4K layout with visible settings and actions')
            except BaseException as error:
                failures.append(error)
            finally:
                dialog.close()
                window.close()
                app.quit()
        QTimer.singleShot(100, inspect)
        app.exec()
        directory.cleanup()
        if failures:
            raise failures[0]
    """)
    script = script.replace("WORKSPACE_SIZE", repr(workspace_size)).replace(
        "DIALOG_SIZE",
        repr(dialog_size),
    )
    environment = {**os.environ, "QT_SCALE_FACTOR": scale_factor, "QT_QPA_PLATFORM": "windows"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: native German export" in result.stdout


def test_language_switch_preserves_state_and_source_metadata(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.slider.setValue(3600)
    window.first.setValue(3500)
    window.last.setValue(3700)
    window.zoom_button.click()
    window.visibility[1].setChecked(False)
    data = window.data
    bounds = window.axis_x.min(), window.axis_x.max()
    values = tuple(tuple(series.points()) for series in window.series)
    try:
        window.set_ui_language(1)
        assert get_language() == "de"
        assert window.open_action.text() == "Aufnahme öffnen…"
        assert window.reset_button.text() == "Ansicht zurücksetzen"
        assert window.reference_toggle.text() == "Kalibrierte Kräfte"
        window.notes_button.click()
        assert "GPS_NEGATIVE_VALUE" in window.notes.toPlainText()
        assert "Quellwert bleibt erhalten" in window.notes.toPlainText()
        window.original_diagnostics.setChecked(True)
        assert window.notes.toPlainText() == data.notes
        window.original_diagnostics.setChecked(False)
        window.notes_button.click()
        assert "Reihe:" in window.ride_metadata.text()
        assert "Voltron Nevera" in window.ride_metadata.text()
        assert "Fahrtzeit" in window.time_readout.text()
        assert "Messpunkte" in window.selection_label.text()
        assert window.data is data
        assert (window.first.value(), window.last.value(), window.slider.value()) == (
            3500,
            3700,
            3600,
        )
        assert (window.axis_x.min(), window.axis_x.max()) == bounds
        assert tuple(tuple(series.points()) for series in window.series) == values
        assert not window.series[1].isVisible()
        assert "zurück" not in window.heading.text()  # Source names are opaque.
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Abbrechen"
        resize_workspace(window, 720, 480)
        assert window.inspector_button.text() == "Details"
        assert window.inspector_button.isVisible()
        window.set_ui_language(0)
        assert window.open_action.text() == "Open recording…"
        assert "Row:" in window.ride_metadata.text()
    finally:
        window.set_ui_language(0)


def test_german_export_and_batch_dialogs_fit_and_save_language(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.set_ui_language(1)
    try:
        with TemporaryDirectory(dir=".tmp") as directory:
            store = ExportStore(Path(directory) / "exports.sqlite3")
            dialog = ExportDialog(
                window.data,
                0,
                window.data.count - 1,
                window,
                current_sample=3600,
                store=store,
            )
            dialog.show()
            wait_until(lambda: dialog.preview_result is not None)
            assert dialog.overlay_language.currentIndex() == 1
            assert dialog.aspect.itemText(1).startswith("Hochformat")
            assert dialog.next.text() == "Export prüfen →"
            for combo in dialog.findChildren(QComboBox):
                if combo.isVisible():
                    assert_combo_text_fits(combo)

            def preset_name(*args: object, **kwargs: object) -> tuple[str, bool]:
                return "Meine Vorgabe", True

            monkeypatch.setattr(QInputDialog, "getText", preset_name)
            dialog.save_preset.click()
            assert store.presets()[0].name == "Meine Vorgabe"
            assert store.presets()[0].settings.language == "de"
            dialog.overlay_language.setCurrentIndex(0)
            dialog.load_preset.click()
            assert dialog.overlay_language.currentIndex() == 1
            for button in dialog.findChildren(QPushButton):
                if button.isVisible():
                    assert (
                        button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 12
                    ), button.text()
            dialog.aspect.setCurrentIndex(1)
            wait_until(lambda: dialog.preview_result is None)
            wait_until(lambda: dialog.preview_result is not None)
            assert dialog.preview_result is not None
            assert all(
                profile.image.size == (540, 960) for profile in dialog.preview_result.profiles
            )
            dialog.next.click()
            assert "Messpunkte" in dialog.summary.text()
            assert "2160×3840" in dialog.summary.text()
            assert dialog.start.text() == "Video exportieren…"
            assert all(label.text() != "Overlay language" for label in dialog.findChildren(QLabel))
            dialog.close()
            batches = BatchDialog(store, window)
            batches.show()
            QApplication.processEvents()
            for combo in batches.findChildren(QComboBox):
                if combo.isVisible():
                    assert_combo_text_fits(combo)
            header = batches.table.horizontalHeaderItem(0)
            assert header is not None and header.text() == "Bahn"
            assert batches.close_button.text() == "Schließen"
            batches.close()
    finally:
        window.set_ui_language(0)
