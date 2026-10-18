"""Native light/dark presentation without recording, viewport or export changes."""

# cspell:words Über

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QFileDialog,
    QGraphicsView,
    QToolBar,
)
import pytest

from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.batches import BatchDialog
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.theme import THEMES, ThemeName
from ride_forces_analyzer.ui.window import ExplorerWindow
from test_explorer_gui import explorer_window as explorer_window, wait_until
from test_project import REAL_FIXTURE_DIRECTORY
from ride_forces_analyzer.config import AppSettings


def test_system_appearance_follows_changes_until_manually_selected(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.ui import window as ui_window

    window = explorer_window
    effective_theme: ThemeName = "light"

    def current_theme(application: QApplication) -> ThemeName:
        return effective_theme

    monkeypatch.setattr(ui_window, "system_theme", current_theme)
    window.set_appearance(0)
    window.set_appearance(2)
    assert window.theme.name == "light"
    assert window.preferences.appearance() == "system"
    effective_theme = "dark"
    application = QApplication.instance()
    assert isinstance(application, QApplication)
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.theme.name == "dark"
    window.set_appearance(1)
    application.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.theme.name == "light"
    assert window.preferences.appearance() == "light"


def test_toolbar_controls_share_one_height(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    for language, appearance in ((0, 0), (1, 1), (1, 0), (0, 1)):
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


def test_new_window_restores_selected_language_and_theme(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    window.set_ui_language(1)
    window.set_appearance(1)
    restored = ExplorerWindow(AppSettings())
    try:
        assert restored.ui_language == "de"
        assert restored.appearance_preference == "light"
        assert restored.theme.name == "light"
        assert restored.about_action.text() == "Über …"
    finally:
        restored.close()
        restored.deleteLater()


def test_native_file_dialog_inherits_valid_point_size(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    for index in (0, 1):
        window.set_appearance(index)
        QApplication.processEvents()
        dialog = QFileDialog(window)
        try:
            dialog.ensurePolished()
            assert window.font().pointSizeF() > 0
            assert dialog.font().pointSizeF() > 0
        finally:
            dialog.deleteLater()


def test_light_text_and_channel_colors_have_readable_contrast() -> None:
    theme = THEMES["light"]

    def luminance(color: str) -> float:
        value = QColor(color)
        rgb = (value.redF(), value.greenF(), value.blueF())
        linear = tuple(
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb
        )
        return sum(
            value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
        )

    for color in (theme.text, theme.muted, *theme.forces, *theme.raw, *theme.markers):
        assert (luminance(theme.panel) + 0.05) / (luminance(color) + 0.05) >= 4.5


@pytest.mark.parametrize("calibrated", [True, False])
def test_theme_switch_preserves_recording_and_chart_state(
    explorer_window: ExplorerWindow,
    calibrated: bool,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.reference_toggle.setChecked(calibrated)
    window.slider.setValue(3600)
    window.first.setValue(3500)
    window.last.setValue(3700)
    window.zoom_button.click()
    window.visibility[1].setChecked(False)
    data = window.data
    points = tuple(tuple(line.points()) for line in window.series)
    viewport = (window.axis_x.min(), window.axis_x.max(), window.axis_y.min(), window.axis_y.max())
    for index, name in ((1, "light"), (0, "dark")):
        window.set_appearance(index)
        QApplication.processEvents()
        theme = THEMES["light" if name == "light" else "dark"]
        assert window.data is data
        assert tuple(tuple(line.points()) for line in window.series) == points
        assert not window.series[1].isVisible()
        assert (window.first.value(), window.last.value(), window.slider.value()) == (
            3500,
            3700,
            3600,
        )
        assert viewport == (
            window.axis_x.min(),
            window.axis_x.max(),
            window.axis_y.min(),
            window.axis_y.max(),
        )
        assert window.chart.backgroundBrush().color() == QColor(theme.panel)
        assert window.axis_x.labelsBrush().color() == QColor(theme.muted)
        assert [line.pen().color().name() for line in window.series] == list(
            theme.forces if calibrated else theme.raw,
        )
        assert window.palette().color(QPalette.ColorRole.WindowText) == QColor(theme.text)
        assert [
            label.brush().color().name() for label in window.source_marker_labels.values()
        ] == list(theme.markers)


def test_dialogs_and_gps_follow_light_and_dark(explorer_window: ExplorerWindow) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    window.gps_button.click()
    assert window.gps_window is not None
    view = window.gps_window.findChild(QGraphicsView)
    assert view is not None
    with TemporaryDirectory(dir=".tmp") as directory:
        store = ExportStore(Path(directory) / "exports.sqlite3")
        batches = BatchDialog(store, window)
        batches.show()
        dialog = ExportDialog(window.data, 0, window.data.count - 1, window, store=store)
        dialog.show()
        wait_until(lambda: dialog.preview_result is not None)
        result = dialog.preview_result
        for index in (1, 0):
            window.set_appearance(index)
            QApplication.processEvents()
            expected = QColor("#ffffff" if index else "#182330")
            assert view.palette().base().color() == expected
            assert dialog.seconds.palette().base().color() == QColor(
                "#ffffff" if index else "#111c29",
            )
            assert batches.table.palette().base().color() == QColor(
                "#ffffff" if index else "#111c29",
            )
            assert dialog.preview_result is result
            scene = view.scene()
            assert scene is not None
            assert scene.backgroundBrush().style().value == 0
        dialog.close()
        batches.close()
