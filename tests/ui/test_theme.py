"""Shared theme behavior without repeating GUI workflows for each palette."""

# cspell:words Dunkel Über

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QToolBar,
)
import pytest

from ride_forces_analyzer.storage.preferences import Appearance
from ride_forces_analyzer.ui.presentation.theme import THEMES, ThemeName
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from tests.ui.helpers import wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from ride_forces_analyzer.runtime.config import AppSettings


def test_system_appearance_follows_changes_until_manually_selected(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui.explorer import window as ui_window

    window = explorer_window
    effective_theme: ThemeName = Appearance.LIGHT

    def current_theme(application: QApplication) -> ThemeName:
        return effective_theme

    monkeypatch.setattr(ui_window, "system_theme", current_theme)
    window.set_appearance(0)
    window.set_appearance(2)
    assert window.theme.name == "light"
    assert window.preferences.appearance() is Appearance.SYSTEM
    effective_theme = Appearance.DARK
    application = QApplication.instance()
    assert isinstance(application, QApplication)
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.theme.name == "dark"
    window.show_settings()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.DARK.value))
    effective_theme = Appearance.LIGHT
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert window.theme is THEMES[Appearance.DARK]
    assert window.preferences.appearance() is Appearance.SYSTEM
    dialog.reject()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    assert window.appearance_preference is Appearance.SYSTEM
    assert window.theme is THEMES[Appearance.LIGHT]
    window.set_appearance(1)
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.theme.name == "light"
    assert window.preferences.appearance() is Appearance.LIGHT


def test_toolbar_controls_share_one_height(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    for language, appearance in ((0, 0), (1, 1)):
        window.set_ui_language(language)
        window.set_appearance(appearance)
        QApplication.processEvents()
        controls = [toolbar.widgetForAction(action) for action in toolbar.actions()]
        heights = {
            widget.height()
            for widget in controls
            if isinstance(widget, (QAbstractButton, QComboBox))
        }
        assert len(heights) == 1, heights


def test_native_file_dialog_inherits_valid_point_size(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    dialog = QFileDialog(window)
    try:
        dialog.ensurePolished()
        assert window.font().pointSizeF() > 0
        assert dialog.font().pointSizeF() > 0
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    "name",
    [Appearance.LIGHT, Appearance.FALCONS_FLIGHT, Appearance.TOP_THRILL_2],
)
def test_light_text_and_channel_colors_have_readable_contrast(name: ThemeName) -> None:
    theme = THEMES[name]

    def luminance(color: str) -> float:
        value = QColor(color)
        rgb = (value.redF(), value.greenF(), value.blueF())
        linear = tuple(
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb
        )
        return sum(
            value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
        )

    for color in (
        theme.text,
        theme.muted,
        *theme.forces,
        *theme.raw,
        *theme.vertical_context_colors.values(),
    ):
        assert (luminance(theme.panel) + 0.05) / (luminance(color) + 0.05) >= 4.5
    for color in (
        *theme.markers,
        *(theme.chart_forces or theme.forces),
        *(theme.chart_raw or theme.raw),
    ):
        values = sorted((luminance(theme.chart_background or theme.panel), luminance(color)))
        assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5
    if theme.chart_background is not None:
        assert theme.chart_foreground is not None
        assert (luminance(theme.chart_foreground) + 0.05) / (
            luminance(theme.chart_background) + 0.05
        ) >= 7
        assert (luminance(theme.panel) + 0.05) / (luminance(theme.text) + 0.05) >= 7
        for background in (theme.accent, theme.link):
            assert (luminance(theme.accent_text) + 0.05) / (luminance(background) + 0.05) >= 7


def test_theme_switch_preserves_recording_and_chart_state(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    for calibrated in (True, False):
        window.reference_toggle.setChecked(calibrated)
        window.navigation.slider.setValue(3600)
        window.inspector.first.setValue(3500)
        window.inspector.last.setValue(3700)
        window.zoom_button.click()
        window.visibility[1].setChecked(False)
        data = window.data
        points = tuple(tuple(line.points()) for line in window.plot.series)
        viewport = (
            window.plot.axis_x.min(),
            window.plot.axis_x.max(),
            window.plot.axis_y.min(),
            window.plot.axis_y.max(),
        )
        for index, name in (
            (1, Appearance.LIGHT),
            (tuple(Appearance).index(Appearance.TOP_THRILL_2), Appearance.TOP_THRILL_2),
        ):
            window.set_appearance(index)
            QApplication.processEvents()
            theme = THEMES[window.theme.name]
            assert window.theme.name == name
            assert window.data is data
            assert tuple(tuple(line.points()) for line in window.plot.series) == points
            assert not window.plot.series[1].isVisible()
            assert (
                window.inspector.first.value(),
                window.inspector.last.value(),
                window.navigation.slider.value(),
            ) == (
                3500,
                3700,
                3600,
            )
            assert viewport == (
                window.plot.axis_x.min(),
                window.plot.axis_x.max(),
                window.plot.axis_y.min(),
                window.plot.axis_y.max(),
            )
            assert window.plot.chart.backgroundBrush().color() == QColor(
                theme.chart_background or theme.panel,
            )
            assert window.plot.axis_x.labelsBrush().color() == QColor(
                theme.chart_foreground or theme.muted,
            )
            assert [line.pen().color().name() for line in window.plot.series] == list(
                (theme.chart_forces or theme.forces)
                if calibrated
                else (theme.chart_raw or theme.raw),
            )
            assert window.palette().color(QPalette.ColorRole.WindowText) == QColor(theme.text)
            for label, color in zip(
                window.navigation.value_labels,
                theme.forces if calibrated else theme.raw,
                strict=True,
            ):
                assert label.styleSheet() == f"color: {color};"
            assert [
                label.brush().color().name() for label in window.plot.source_marker_labels.values()
            ] == list(theme.markers)


def test_theme_settings_save_cancel_and_restart(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.set_appearance(0)
    window.show_settings()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    assert tuple(
        dialog.appearance.itemText(index) for index in range(dialog.appearance.count())
    ) == (
        "System",
        "Light",
        "Dark",
        "Falcons Flight",
        "Loch Ness",
        "Manta",
        "Red Force",
        "Slinky Dog Dash",
        "Taron",
        "Top Thrill 2",
        "Verbolten",
    )
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.TARON.value))
    assert window.theme is THEMES[Appearance.TARON]
    assert dialog.palette().color(QPalette.ColorRole.Window) == QColor(window.theme.background)
    assert window.preferences.appearance() is Appearance.DARK
    window.set_ui_language(1)
    assert tuple(
        dialog.appearance.itemText(index) for index in range(dialog.appearance.count())
    ) == (
        "System",
        "Hell",
        "Dunkel",
        "Falcons Flight",
        "Loch Ness",
        "Manta",
        "Red Force",
        "Slinky Dog Dash",
        "Taron",
        "Top Thrill 2",
        "Verbolten",
    )
    assert dialog.appearance.currentData() == Appearance.TARON.value
    assert window.theme is THEMES[Appearance.TARON]
    window.set_ui_language(0)
    assert dialog.appearance.currentData() == Appearance.TARON.value
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.RED_FORCE.value))
    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    assert window.theme.name == "dark"
    assert window.preferences.appearance() is Appearance.DARK
    window.show_settings()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.LIGHT.value))
    assert window.theme is THEMES[Appearance.LIGHT]
    dialog.close()
    wait_until(lambda: window.findChild(SettingsDialog, "settingsDialog") is None)
    assert window.theme is THEMES[Appearance.DARK]
    assert window.preferences.appearance() is Appearance.DARK
    window.show_settings()
    dialog = window.findChild(SettingsDialog, "settingsDialog")
    assert dialog is not None
    dialog.appearance.setCurrentIndex(dialog.appearance.findData(Appearance.RED_FORCE.value))
    dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
    assert window.theme is THEMES[Appearance.RED_FORCE]
    assert window.preferences.appearance() is Appearance.RED_FORCE
    assert (
        window.theme.vertical_context_colors
        == THEMES[
            Appearance.DARK if window.theme.is_dark else Appearance.LIGHT
        ].vertical_context_colors
    )
    window.set_ui_language(1)
    restored = ExplorerWindow(AppSettings())
    try:
        assert restored.ui_language == "de"
        assert restored.appearance_preference is Appearance.RED_FORCE
        assert restored.theme is THEMES[Appearance.RED_FORCE]
        assert restored.about_action.text() == "Über …"
    finally:
        restored.close()
        restored.deleteLater()
