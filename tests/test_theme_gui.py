"""Native light/dark presentation without recording, viewport or export changes."""

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QGraphicsView
import pytest

from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.batches import BatchDialog
from ride_forces_analyzer.ui.export import ExportDialog
from ride_forces_analyzer.ui.theme import THEMES
from ride_forces_analyzer.ui.window import ExplorerWindow
from test_explorer_gui import explorer_window as explorer_window, wait_until
from test_project import REAL_FIXTURE_DIRECTORY


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
        window.appearance.setCurrentIndex(index)
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
            window.appearance.setCurrentIndex(index)
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
