"""Native language switching and localized layouts over unchanged recording data."""

# cspell:words Aufnahme öffnen Ansicht zurücksetzen Kalibrierte Kräfte Reihe Fahrtzeit Messpunkte zurück Abbrechen prüfen Bahn Schließen Hochformat Meine Vorgabe exportieren Quellwert bleibt erhalten
# cspell:words Oben Unten rechts Schwerkraftmarkierung Neigungsmarkierung Startmarkierung Endmarkierung Schwerkraft hier setzen Original Neigung einschließlich

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import sys
from textwrap import dedent

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QComboBox,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QToolButton,
    QToolBar,
)
import pytest

from ride_forces_analyzer.i18n import get_language, tr
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.exports.batches import BatchDialog
from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from tests.ui.helpers import resize_workspace, wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


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


pytestmark = pytest.mark.usefixtures("small_preview_frames")


def test_settings_choices_fit_after_repeated_language_switches(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.settings_action.trigger()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    try:
        for language in (0, 1, 2, 0, 2):
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
def test_localized_export_in_4k_workspace_keeps_controls_reachable(
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
        from ride_forces_analyzer.runtime.config import AppSettings
        from ride_forces_analyzer.i18n import Language
        from ride_forces_analyzer.explorer import ExplorerData, load_recording
        from ride_forces_analyzer.storage.exports import ExportStore
        from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
        from ride_forces_analyzer.ui.exports.video import ExportDialog
        from tests.ui.helpers import SmallPreviewRenderer
        from unittest.mock import patch
        patch('ride_forces_analyzer.rendering.preview.OverlayRenderer', SmallPreviewRenderer).start()
        app = QApplication([])
        directory = TemporaryDirectory(dir='.tmp')
        window = ExplorerWindow(AppSettings(language=Language.GERMAN))
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
            if dialog.previews.result is None and time.monotonic() < deadline:
                QTimer.singleShot(50, inspect)
                return
            try:
                assert dialog.previews.result is not None
                scroll = dialog.findChild(QScrollArea, 'exportContentScroll')
                assert (window.width(), window.height()) == WORKSPACE_SIZE
                assert (dialog.width(), dialog.height()) == DIALOG_SIZE
                assert scroll is not None and scroll.verticalScrollBar().maximum() == 0
                assert dialog.next.isVisible() and dialog.rect().contains(dialog.next.geometry())
                assert dialog.next.text() == 'Export prüfen →'
                for language in (0, 1, 2, 0, 2):
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
                print('PASS: native localized export in 4K layout with visible settings and actions')
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
    assert "PASS: native localized export" in result.stdout


def test_native_alt_access_keys_preserve_standard_open_shortcut(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    opened: list[bool] = []

    def choose(*args: object, **kwargs: object) -> tuple[str, str]:
        opened.append(True)
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", choose)
    assert window.open_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Open)
    window.activateWindow()
    wait_until(window.isActiveWindow)
    open_button = next(
        button
        for button in window.findChildren(QToolButton)
        if button.defaultAction() is window.open_action
    )
    initial = open_button.grab().toImage()
    QTest.keyClick(window, Qt.Key.Key_Alt)
    QApplication.processEvents()
    shown = open_button.grab().toImage()
    assert shown != initial
    QTest.keyClick(window, Qt.Key.Key_Alt)
    QApplication.processEvents()
    assert open_button.grab().toImage() == initial
    for count, (language, open_key, save_key) in enumerate(
        (
            (0, Qt.Key.Key_O, Qt.Key.Key_S),
            (1, Qt.Key.Key_Odiaeresis, Qt.Key.Key_S),
            (2, Qt.Key.Key_O, Qt.Key.Key_E),
        ),
        start=1,
    ):
        window.set_ui_language(language)
        window.activateWindow()
        wait_until(window.isActiveWindow)
        QTest.keyClick(window, open_key, Qt.KeyboardModifier.AltModifier)
        wait_until(lambda: len(opened) == count)
        assert not open_button.style().styleHint(
            QStyle.StyleHint.SH_UnderlineShortcut,
            None,
            open_button,
        )
        window.settings_action.trigger()
        dialog = window.findChild(SettingsDialog, "settingsDialog")
        assert dialog is not None
        dialog.activateWindow()
        wait_until(dialog.isActiveWindow)
        save_button = next(
            button
            for button in dialog.buttons.buttons()
            if button.shortcut() == QKeySequence(f"Alt+{chr(save_key)}")
        )
        save_button.setFocus()
        QApplication.processEvents()
        assert QApplication.activeWindow() is dialog
        QTest.keyClick(save_button, save_key, Qt.KeyboardModifier.AltModifier)
        wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
        window.settings_action.trigger()
        dialog = window.findChild(SettingsDialog, "settingsDialog")
        assert dialog is not None
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)


@pytest.mark.usefixtures("small_preview_frames")
def test_action_buttons_have_localized_tooltips_and_accessible_names(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    for open_dialog in (
        window.show_settings,
        window.show_about,
        window.show_batches,
        window.show_gps,
        window.show_export,
    ):
        open_dialog()
        dialog = next(dialog for dialog in window.findChildren(QDialog) if dialog.isVisible())
        for language in (1, 0):
            window.set_ui_language(language)
            assert (
                window.export_button.toolTip()
                == window.export_button.accessibleName()
                == tr("Export video…")
            )
            if isinstance(dialog, BatchDialog):
                assert dialog.run_all.toolTip() == tr(
                    "Export all jobs in all saved batches, regardless of batch or job-row selection.",
                )
            if isinstance(dialog, ExportDialog):
                assert dialog.form.browse.toolTip() == tr("Choose FFmpeg executable")
            for button in window.findChildren(QAbstractButton):
                if not isinstance(button, QPushButton | QToolButton):
                    continue
                if button.objectName().startswith("qt_"):
                    continue
                assert button.toolTip(), button.text()
                assert button.accessibleName(), button.text()
        dialog.close()
        QApplication.processEvents()


def test_language_switch_preserves_state_and_source_metadata(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.navigation.slider.setValue(3600)
    window.inspector.first.setValue(3500)
    window.inspector.last.setValue(3700)
    window.zoom_button.click()
    window.visibility[1].setChecked(False)
    data = window.data
    bounds = window.plot.axis_x.min(), window.plot.axis_x.max()
    values = tuple(tuple(series.points()) for series in window.plot.series)

    def assert_marker_names(names: tuple[str, ...], menu_texts: tuple[str, ...]) -> None:
        for (key, _index), name in zip(data.markers, names, strict=True):
            label = window.plot.source_marker_labels[key]
            assert label.text().startswith(name + " · ")
            assert label.toolTip().startswith(name + ": ")

        def inspect_menu() -> None:
            menu = QApplication.activePopupWidget()
            assert isinstance(menu, QMenu)
            texts = [action.text() for action in menu.actions()]
            assert all(text in texts for text in menu_texts)
            menu.close()

        QTimer.singleShot(0, inspect_menu)
        window.show_marker_menu(0.5, window.mapToGlobal(window.rect().center()))

    try:
        window.set_ui_language(1)
        assert get_language() == "de"
        assert window.open_action.text() == "Aufnahme &öffnen…"
        assert window.reset_button.text() == ""
        assert window.reset_button.toolTip() == "Ansicht zurücksetzen"
        assert window.reset_button.accessibleName() == "Ansicht zurücksetzen"
        assert window.reference_toggle.text() == "Kalibrierte Kräfte"
        assert_marker_names(
            ("Startmarkierung", "Endmarkierung", "Schwerkraftmarkierung", "Neigungsmarkierung"),
            (
                "Schwerkraft hier setzen",
                "Neigung hier setzen",
                "Schwerkraft auf Original zurücksetzen",
                "Neigung auf Original zurücksetzen",
            ),
        )
        window.notes_button.click()
        assert "GPS_NEGATIVE_VALUE" in window.inspector.notes.toPlainText()
        assert "Quellwert bleibt erhalten" in window.inspector.notes.toPlainText()
        window.inspector.original_diagnostics.setChecked(True)
        assert window.inspector.notes.toPlainText() == data.notes
        window.inspector.original_diagnostics.setChecked(False)
        window.notes_button.click()
        assert "Reihe:" in window.inspector.ride_metadata.text()
        assert "Voltron Nevera" in window.inspector.ride_metadata.text()
        assert "Fahrtzeit" in window.navigation.time_readout.text()
        assert "Messpunkte" in window.inspector.selection_label.text()
        assert window.data is data
        assert (
            window.inspector.first.value(),
            window.inspector.last.value(),
            window.navigation.slider.value(),
        ) == (
            3500,
            3700,
            3600,
        )
        assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == bounds
        assert tuple(tuple(series.points()) for series in window.plot.series) == values
        assert not window.plot.series[1].isVisible()
        assert "zurück" not in window.heading.text()  # Source names are opaque.
        assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Abbrechen"
        resize_workspace(window, 720, 480)
        assert window.inspector_button.text() == "Details"
        if not window.inspector_button.isVisible():
            toolbar = window.findChild(QToolBar)
            assert toolbar is not None
            overflow = toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            assert overflow is not None and overflow.isVisible()

            overflow.click()
            wait_until(window.inspector_button.isVisible, timeout=2)
            assert window.inspector_button.isEnabled()
            overflow.click()
        window.set_ui_language(0)
        assert window.open_action.text() == "&Open recording…"
        assert "Row:" in window.inspector.ride_metadata.text()
        assert_marker_names(
            ("Start marker", "End marker", "Gravity marker", "Incline marker"),
            (
                "Set gravity here",
                "Set incline here",
                "Reset gravity to original",
                "Reset incline to original",
            ),
        )
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
            wait_until(lambda: dialog.previews.result is not None)
            assert dialog.form.overlay_language.currentIndex() == 1
            assert dialog.form.aspect.itemText(1).startswith("Hochformat")
            assert [
                dialog.form.position.itemText(i) for i in range(dialog.form.position.count())
            ] == [
                "Oben",
                "Unten",
            ]
            selected_position = dialog.form.position.currentData()
            window.set_ui_language(0)
            assert dialog.form.position.currentText() == "Bottom"
            window.set_ui_language(1)
            assert dialog.form.position.currentText() == "Unten"
            assert dialog.form.position.currentData() == selected_position
            dialog.form.layout_profile.setCurrentIndex(3)
            QCoreApplication.processEvents()
            assert dialog.form.position.count() == 4
            assert "Oben rechts" in [dialog.form.position.itemText(i) for i in range(4)]
            assert_combo_text_fits(dialog.form.position)
            for language in (2, 0, 1):
                window.set_ui_language(language)
                QCoreApplication.processEvents()
                assert_combo_text_fits(dialog.form.position)
            dialog.form.layout_profile.setCurrentIndex(0)
            assert dialog.form.position.count() == 2
            assert dialog.next.text() == "Export prüfen →"
            for combo in dialog.findChildren(QComboBox):
                if combo.isVisible():
                    assert_combo_text_fits(combo)

            def preset_name(*args: object, **kwargs: object) -> tuple[str, bool]:
                return "Meine Vorgabe", True

            monkeypatch.setattr(QInputDialog, "getText", preset_name)
            dialog.presets.save_preset.click()
            assert store.presets()[0].name == "Meine Vorgabe"
            assert store.presets()[0].settings.language == "de"
            dialog.form.overlay_language.setCurrentIndex(0)
            dialog.presets.preset_selector.activated.emit(
                dialog.presets.preset_selector.currentIndex(),
            )
            assert dialog.form.overlay_language.currentIndex() == 1
            for button in dialog.findChildren(QPushButton):
                if button.isVisible():
                    assert (
                        button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 12
                    ), button.text()
            dialog.form.aspect.setCurrentIndex(1)
            wait_until(lambda: dialog.previews.result is None)
            wait_until(lambda: dialog.previews.result is not None)
            assert dialog.previews.result is not None
            assert all(
                profile.image.size == (540, 960) for profile in dialog.previews.result.profiles
            )
            dialog.next.click()
            assert dialog.review_fields["samples"].text().endswith("(einschließlich)")
            assert dialog.review_fields["resolution"].text() == "2160×3840"
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
