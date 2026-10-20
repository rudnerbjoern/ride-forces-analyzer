"""Native Qt interactions; fixture-wide data contracts live in the pure suites."""

# cspell:words Quelle Verarbeitung Aktueller Messpunkt

from hashlib import sha256
from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QTextDocument, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QStyle,
    QStyleOptionSlider,
    QStyleOptionSpinBox,
)
import pytest

from ride_forces_analyzer.domain import Recording
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.ui import loading
from ride_forces_analyzer.ui.window import ExplorerWindow
from tests.ui.helpers import resize_workspace, wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


@pytest.mark.parametrize("field", ["first", "last"], ids=["from", "to"])
@pytest.mark.parametrize("direction", [1, -1], ids=["up", "down"])
def test_selection_arrows_accelerate_while_held_and_reset_on_release(
    explorer_window: ExplorerWindow,
    field: str,
    direction: int,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    resize_workspace(window, 1280, 820)
    window.first.setValue(3000)
    window.last.setValue(7000)
    control = window.first if field == "first" else window.last
    option = QStyleOptionSpinBox()
    option.initFrom(control)
    button = (
        control.style()
        .subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxUp if direction > 0 else QStyle.SubControl.SC_SpinBoxDown,
            control,
        )
        .center()
    )
    initial = control.value()
    values = [initial]
    control.valueChanged.connect(values.append)
    QTest.mousePress(control, Qt.MouseButton.LeftButton, pos=button)
    try:
        QTest.qWait(5500)
        assert (control.value() - initial) * direction > 1
        increments = {(last - first) * direction for first, last in zip(values, values[1:])}
        assert {1, 5, 10, 20, 50} <= increments
        assert window.selection_band.isVisible()
        assert window.first.value() <= window.last.value()
    finally:
        QTest.mouseRelease(control, Qt.MouseButton.LeftButton, pos=button)
    released = control.value()
    QTest.qWait(200)
    assert control.value() == released
    QTest.mouseClick(control, Qt.MouseButton.LeftButton, pos=button)
    assert control.value() == released + direction
    released = control.value()
    QTest.keyClick(control, Qt.Key.Key_Up if direction > 0 else Qt.Key.Key_Down)
    assert control.value() == released + direction


@pytest.mark.parametrize("appearance", [0, 1], ids=["dark", "light"])
def test_selection_highlight_tracks_fields_zoom_and_resize_without_changing_data(
    explorer_window: ExplorerWindow,
    appearance: int,
) -> None:
    window = explorer_window
    assert not window.selection_band.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.set_appearance(appearance)
    data = window.data
    assert data is not None
    for reference in (False, True):
        window.reference_toggle.setChecked(reference)
        points = tuple(window.series[0].points())
        current = window.position.value()
        window.last.setValue(data.count - 1)
        window.first.setValue(4200)
        window.last.setValue(5100)
        for first, last, size in (
            (4000, 5200, (1280, 820)),
            (4400, 4800, (1600, 1100)),
            (5200, 5500, (1280, 820)),
        ):
            window.axis_x.setRange(data.time_at(first), data.time_at(last))
            resize_workspace(window, *size)
            QApplication.processEvents()
            plot = window.chart.plotArea()
            band = window.selection_band
            assert band.isVisible() == (first <= 5100 and last >= 4200)
            if band.isVisible():
                rect = band.rect()
                assert rect.left() == pytest.approx(
                    plot.left() + (max(first, 4200) - first) / (last - first) * plot.width(),
                )
                assert rect.right() == pytest.approx(
                    plot.left() + (min(last, 5100) - first) / (last - first) * plot.width(),
                )
                assert rect.top() == pytest.approx(plot.top())
                assert rect.bottom() == pytest.approx(plot.bottom())
            assert tuple(window.series[0].points()) == points
            assert window.position.value() == current
            assert band.acceptedMouseButtons() == Qt.MouseButton.NoButton
            color = window.chart_view.palette().highlight().color()
            assert band.brush().color().rgb() == color.rgb()
            assert 0 < band.brush().color().alpha() < 255
        window.first.setValue(4500)
        window.last.setValue(4500)
        window.axis_x.setRange(data.time_at(4400), data.time_at(4600))
        assert window.selection_band.isVisible()
        assert window.selection_band.rect().width() >= 2


def test_vertical_context_bar_preserves_curve_and_tracks_viewport(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.calibrated_enabled
    original = tuple(data.plotted_channels[0])
    for appearance in (0, 1):
        window.set_appearance(appearance)
        QApplication.processEvents()
        segments = data.vertical_context_segments
        assert len(window.vertical_context_bars) == len(segments)
        assert window.series[0].pen().style() == Qt.PenStyle.SolidLine
        assert window.series[0].pen().color().name() == window.theme.forces[0]
        assert tuple(p.y() for p in window.series[0].points()) == original
        for bar, (label, _, _) in zip(window.vertical_context_bars, segments, strict=True):
            assert bar.brush().color().name() == window.theme.vertical_context_colors[label]
        window.axis_x.setRange(data.time_at(4200), data.time_at(4300))
        window.zoom_wheel(0.5, 2)
        QApplication.processEvents()
        plot = window.chart.plotArea()
        visible = [bar for bar in window.vertical_context_bars if bar.isVisible()]
        assert visible
        low, high = window.axis_x.min(), window.axis_x.max()
        for bar, (_, first, last) in zip(window.vertical_context_bars, segments, strict=True):
            start = max(low, data.time_at(first))
            end = min(high, data.time_at(last))
            assert bar.isVisible() == (end > start)
            if bar.isVisible():
                assert bar.rect().left() == pytest.approx(
                    plot.left() + (start - low) / (high - low) * plot.width(),
                )
                assert bar.rect().right() == pytest.approx(
                    plot.left() + (end - low) / (high - low) * plot.width(),
                )
        for bar in visible:
            assert bar.rect().height() == 10
            assert bar.rect().bottom() == pytest.approx(plot.bottom())
            assert bar.rect().left() >= plot.left() - 1e-6
            assert bar.rect().right() <= plot.right() + 1e-6
        window.visibility[0].setChecked(False)
        assert all(not bar.isVisible() for bar in window.vertical_context_bars)
        window.set_smoothing(5)
        assert all(not bar.isVisible() for bar in window.vertical_context_bars)
        window.visibility[0].setChecked(True)
        assert any(bar.isVisible() for bar in window.vertical_context_bars)
    window.reference_toggle.setChecked(False)
    assert not window.vertical_context_bars
    assert window.series[0].pen().style() == Qt.PenStyle.SolidLine
    assert tuple(p.y() for p in window.series[0].points()) == data.channels[0]


@pytest.mark.parametrize(
    "filename",
    [name for name in REAL_FIXTURES if name.startswith(("Manta-", "IronGwazi-"))],
)
def test_open_chart_navigation_selection_and_integrity(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
) -> None:
    window = explorer_window
    path = REAL_FIXTURE_DIRECTORY / filename
    original = path.read_bytes()
    mtime = path.stat().st_mtime_ns

    def chosen(*args: object, **kwargs: object) -> tuple[str, str]:
        return str(path), "Ride Forces (*.forces)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", chosen)
    window.open_action.trigger()
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None, window.statusBar().currentMessage()
    assert window.windowTitle() == f"{data.title} · Ride Forces Analyzer"
    assert not window.windowIcon().isNull()
    assert window.ride_metadata.isVisible()
    assert window.ride_metadata.text() == data.metadata_rows_text
    assert f"Ride: {data.source.recording.metadata.name}" in window.ride_metadata.text()
    park = data.source.recording.metadata.location
    assert (
        (f"Park: {park}" in window.ride_metadata.text())
        if park
        else "Park:" not in window.ride_metadata.text()
    )
    assert "Train:" not in window.ride_metadata.text()
    assert "Row:" in window.ride_metadata.text()
    assert window.reference_toggle.isEnabled() and window.reference_toggle.isChecked()
    assert data.calibrated_enabled
    assert data.count == len(data.source.recording.motion.acceleration)
    for series, values in zip(window.series, data.plotted_channels, strict=True):
        assert series.count() == data.count
        assert window.axis_y.min() <= min(values) <= max(values) <= window.axis_y.max()
        assert tuple(point.y() for point in series.points()) == tuple(values)
        assert tuple(point.x() for point in series.points()) == tuple(
            data.time_at(index) for index in range(data.count)
        )
    assert len(data.markers) == 4
    for name, index in data.markers:
        points = window.source_marker_lines[name].points()
        assert [point.x() for point in points] == [data.time_at(index)] * 2
        assert [point.y() for point in points] == list(data.value_range)
        label = window.source_marker_labels[name]
        assert name in label.text()
        assert label.isVisible() == (
            data.default_time_range[0] <= data.time_at(index) <= data.default_time_range[1]
        )
    window.position.setValue(12)
    assert window.slider.value() == 12
    assert window.readout.text() == data.sample_text(12, rich=True)
    assert "0.240 s" in window.readout.text()
    assert window.sample_cursor.points()[0].x() == data.time_at(12)
    assert window.axis_x.titleText() == data.replay_time_label
    assert "INFERRED_UNIFORM" in window.summary.text()
    window.first.setValue(5)
    window.last.setValue(50)
    assert "46 samples" in window.selection_label.text()
    window.zoom_button.click()
    assert window.axis_x.min() == 5 / data.sample_rate
    assert window.axis_x.max() == 50 / data.sample_rate
    window.axis_x.setRange(10.2 / data.sample_rate, 20.8 / data.sample_rate)
    window.visible_button.click()
    assert window.first.value() == 10 and window.last.value() == 21
    window.position.setValue(data.count - 1)
    assert window.axis_x.min() <= data.duration <= window.axis_x.max()
    window.first.setValue(21)
    window.last.setValue(21)
    window.zoom_button.click()
    assert window.axis_x.max() > window.axis_x.min()
    window.visibility[1].setChecked(False)
    assert not window.series[1].isVisible()
    window.reset_button.click()
    assert (window.axis_x.min(), window.axis_x.max()) == data.default_time_range
    assert ("G-force (g)" if data.calibrated_enabled else "unknown") in window.axis_y.titleText()
    window.notes_button.click()
    assert window.notes.isVisible()
    if filename.startswith("IronGwazi"):
        assert window.summary.text() == data.technical_summary
        assert "absent" in window.summary.text()
    assert path.read_bytes() == original and path.stat().st_mtime_ns == mtime
    expected_size, expected_hash = REAL_FIXTURES[filename]
    assert len(original) == expected_size and sha256(original).hexdigest() == expected_hash


@pytest.mark.parametrize("calibrated", [False, True], ids=["raw", "calibrated"])
def test_left_click_selects_nearest_sample_in_current_chart_view(
    explorer_window: ExplorerWindow,
    calibrated: bool,
) -> None:
    window = explorer_window
    view = window.chart_view
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.reference_toggle.setChecked(calibrated)
    data = window.data
    assert data is not None
    selection = (window.first.value(), window.last.value())
    for zoomed in (False, True):
        if zoomed:
            window.zoom_wheel(0.5, 6)
        time_range = (window.axis_x.min(), window.axis_x.max())
        QApplication.processEvents()
        plot = window.chart.plotArea()
        for fraction in (0.0, 0.25, 0.75, 1.0):
            chart_point = plot.topLeft()
            chart_point.setX(plot.left() + fraction * plot.width())
            chart_point.setY(plot.center().y())
            point = view.mapFromScene(window.chart.mapToScene(chart_point))
            # Keep rounded edge pixels inside the actual plot rectangle.
            point.setX(max(int(plot.left()) + 1, min(int(plot.right()), point.x())))
            actual = window.chart.mapFromScene(view.mapToScene(point))
            seconds = time_range[0] + ((actual.x() - plot.left()) / plot.width()) * (
                time_range[1] - time_range[0]
            )
            expected = data.sample_at_time(seconds)
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
            assert window.position.value() == window.slider.value() == expected
            assert window.sample_cursor.points()[0].x() == data.time_at(expected)
            assert (window.axis_x.min(), window.axis_x.max()) == time_range
            assert (window.first.value(), window.last.value()) == selection
        previous = window.position.value()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
        assert window.position.value() == previous
        center = view.mapFromScene(window.chart.mapToScene(plot.center()))
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=center)
        QTest.mouseMove(view.viewport(), center + QPoint(2, 0))
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=center + QPoint(2, 0))
        assert window.position.value() != previous
        assert (window.axis_x.min(), window.axis_x.max()) == time_range


def test_zoom_out_stops_at_recording_bounds(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert (window.axis_x.min(), window.axis_x.max()) == data.default_time_range
    fixed_range = data.value_range
    initial_sample = window.position.value()
    assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
    plot = window.chart.plotArea()
    start = plot.topLeft() + (plot.center() - plot.topLeft()) / 2
    QTest.mousePress(
        window.chart_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=start.toPoint(),
    )
    QTest.mouseMove(window.chart_view.viewport(), plot.center().toPoint())
    QTest.mouseRelease(
        window.chart_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=plot.center().toPoint(),
    )
    assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
    assert window.axis_x.max() - window.axis_x.min() < data.duration
    assert window.position.value() == initial_sample
    window.chart.zoom(4)
    assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
    assert window.axis_x.max() - window.axis_x.min() < data.duration
    for _ in range(8):
        QTest.mouseClick(
            window.chart_view.viewport(),
            Qt.MouseButton.RightButton,
            pos=window.chart.plotArea().center().toPoint(),
        )
        assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
        assert 0 <= window.axis_x.min() < window.axis_x.max() <= data.duration
    assert window.axis_x.min() == 0 and window.axis_x.max() == data.duration
    for low, high in (
        (-10, 10),
        (data.duration - 5, data.duration + 5),
        (-100, data.duration + 100),
    ):
        window.axis_x.setRange(low, high)
        assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
        assert 0 <= window.axis_x.min() < window.axis_x.max() <= data.duration
    window.axis_y.setRange(-1000, 1000)
    assert (window.axis_y.min(), window.axis_y.max()) == fixed_range
    window.first.setValue(data.count - 1)
    window.last.setValue(data.count - 1)
    window.zoom_button.click()
    assert window.axis_x.min() <= data.duration == window.axis_x.max()
    window.reset_button.click()
    assert (window.axis_x.min(), window.axis_x.max()) == data.default_time_range


def test_failed_and_cancelled_opens_preserve_previous_recording(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("*.forces")))
    wait_until(window.open_action.isEnabled)
    previous = window.data
    assert previous is not None
    points = window.series[0].count()

    def cancelled(*args: object, **kwargs: object) -> tuple[str, str]:
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", cancelled)
    window.open_action.trigger()
    assert window.data is previous
    window.open_path(Path(".tmp/this-recording-does-not-exist.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.data is previous and window.series[0].count() == points
    assert "SOURCE_NOT_FOUND" in window.statusBar().currentMessage()
    with TemporaryDirectory(dir=".tmp") as directory:
        malformed = Path(directory) / "synthetic.forces"
        malformed.write_bytes(b"{")
        window.open_path(malformed)
        wait_until(window.open_action.isEnabled)
        assert window.data is previous
        assert "INVALID_JSON" in window.statusBar().currentMessage()
    window.position.setValue(previous.count - 1)
    replacement = next(
        path
        for path in REAL_FIXTURE_DIRECTORY.glob("*.forces")
        if path != previous.source.recording.source.provenance.path
    )
    window.open_path(replacement)
    wait_until(window.open_action.isEnabled)
    assert window.data is not None and window.data is not previous
    assert window.position.value() == window.data.source.recording.indices.start
    assert window.first.value() == 0
    assert window.last.value() == window.data.count - 1
    assert window.series[0].count() == window.data.count
    assert window.statusBar().toolTip() == ""
    for name, index in window.data.markers:
        assert window.source_marker_lines[name].points()[0].x() == window.data.time_at(index)


def test_background_loading_keeps_event_loop_alive_and_recovers_worker_errors(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    release = Event()
    ticks: list[bool] = []
    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(True))

    def delayed(path: Path) -> ExplorerData:
        if not release.wait(5):
            raise RuntimeError("Timed out waiting for test release")
        raise RuntimeError("Synthetic worker error")

    monkeypatch.setattr(loading, "load_recording", delayed)
    timer.start()
    try:
        window.open_path(Path("synthetic.forces"))
        QTest.qWait(100)
        assert not window.open_action.isEnabled() and window.progress.isVisible()
        assert len(ticks) >= 2
    finally:
        release.set()
    wait_until(window.open_action.isEnabled)
    timer.stop()
    assert "Unexpected load error" in window.statusBar().currentMessage()
    assert window.data is None


def test_actual_entry_point_closes_safely_during_background_import() -> None:
    import subprocess
    import sys

    script = """
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from ride_forces_analyzer.ui import loading
from ride_forces_analyzer.ui.window import ExplorerWindow
from ride_forces_analyzer.__main__ import main
original_load = loading.load_recording
def delayed(path):
    time.sleep(0.2)
    return original_load(path)
loading.load_recording = delayed
original_init = ExplorerWindow.__init__
def initialize(self, settings):
    original_init(self, settings)
    self.open_path(next(Path('tests/fixtures/real').glob('*.forces')))
    QTimer.singleShot(10, self.close)
ExplorerWindow.__init__ = initialize
assert main() == 0
print('Closed cleanly with background import drained')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert b"Closed cleanly with background import drained" in result.stdout


def test_mouse_wheel_zooms_time_at_pointer_with_fixed_value_axis(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None

    def wheel(delta: int, fraction: float = 0.25) -> None:
        plot = window.chart.plotArea()
        point = plot.center()
        point.setX(plot.left() + fraction * plot.width())
        position = window.chart_view.mapFromScene(window.chart.mapToScene(point))
        event = QWheelEvent(
            position,
            window.chart_view.viewport().mapToGlobal(position),
            QPoint(),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(window.chart_view.viewport(), event)

    window.axis_x.setRange(0, data.duration)
    wheel(120)
    assert window.axis_x.max() - window.axis_x.min() == pytest.approx(data.duration / 1.25)
    assert window.axis_x.min() == pytest.approx(data.duration * 0.05, abs=data.duration * 0.002)
    assert (window.axis_y.min(), window.axis_y.max()) == data.value_range
    wheel(-120)
    assert window.axis_x.min() == pytest.approx(0, abs=1e-10)
    assert window.axis_x.max() == pytest.approx(data.duration)
    for _ in range(5):
        wheel(-120)
        assert window.axis_x.min() == 0 and window.axis_x.max() == data.duration
    for _ in range(5):
        wheel(2400, 0.5)
    assert window.axis_x.max() - window.axis_x.min() == pytest.approx(1 / data.sample_rate)
    assert (window.axis_y.min(), window.axis_y.max()) == data.value_range
    wheel(0)
    assert window.axis_x.max() - window.axis_x.min() == pytest.approx(1 / data.sample_rate)


def test_optional_markers_are_absent_and_labels_follow_time_view(
    explorer_window: ExplorerWindow,
    synthetic_recording: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.domain import Recording
    from ride_forces_analyzer.explorer import present_recording
    from ride_forces_analyzer.importers import ImportSuccess

    assert isinstance(synthetic_recording, Recording)
    window = explorer_window
    view = present_recording(ImportSuccess(synthetic_recording))

    def load_synthetic(path: Path) -> ExplorerData:
        return view

    monkeypatch.setattr(loading, "load_recording", load_synthetic)
    window.open_path(Path("synthetic.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.ride_metadata.text() == "" and not window.ride_metadata.isVisible()
    assert window.source_marker_lines["gravityIndex"].count() == 0
    assert not window.source_marker_labels["gravityIndex"].isVisible()
    window.axis_x.setRange(0.005, 0.015)
    assert not window.source_marker_labels["startIndex"].isVisible()
    assert not window.source_marker_labels["endIndex"].isVisible()
    window.reset_view()
    assert window.source_marker_labels["startIndex"].isVisible()
    assert window.source_marker_labels["endIndex"].isVisible()


@pytest.mark.parametrize("start,end", [(1, 2), (None, 2), (1, None), (None, None)])
def test_load_and_reset_use_independent_marker_defaults(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
    start: int | None,
    end: int | None,
) -> None:
    import json

    from ride_forces_analyzer.explorer import present_recording
    from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes

    root: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "accelerationSequence": [{"x": 0, "y": 0, "z": 1}] * 4,
    }
    if start is not None:
        root["startIndex"] = start
    if end is not None:
        root["endIndex"] = end
    imported = import_forces_bytes(json.dumps(root).encode())
    assert isinstance(imported, ImportSuccess)
    data = present_recording(imported)

    def load_synthetic(path: Path) -> ExplorerData:
        return data

    monkeypatch.setattr(loading, "load_recording", load_synthetic)
    window = explorer_window
    window.open_path(Path("synthetic.forces"))
    wait_until(window.open_action.isEnabled)
    expected = ((start if start is not None else 0) / 50, (end if end is not None else 3) / 50)
    assert (window.axis_x.min(), window.axis_x.max()) == expected
    assert window.position.value() == (start if start is not None else 0)
    window.chart.zoomOut()
    window.axis_x.setRange(0, data.duration)
    window.reset_button.click()
    assert (window.axis_x.min(), window.axis_x.max()) == expected
    assert window.source_marker_lines["startIndex"].count() == (0 if start is None else 2)
    assert window.source_marker_lines["endIndex"].count() == (0 if end is None else 2)


def test_app_reference_toggle_for_manta_preserves_raw_values_selection_and_time(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.calibration_available and data.calibrated_enabled
    assert [line.name() for line in window.series] == [
        "Vertical",
        "Lateral (+ right / − left)",
        "Longitudinal (+ acceleration / − braking)",
    ]
    assert all(name in window.readout.text() for name in data.channel_names)
    assert window.readout.wordWrap()
    assert window.visibility[1].text() == "Lateral"
    assert window.visibility[1].toolTip() == "Lateral (+ right / − left)"
    assert window.visibility[2].text() == "Longitudinal"
    assert window.visibility[2].toolTip() == "Longitudinal (+ acceleration / − braking)"
    assert window.reference_toggle.text() == "Calibrated forces"
    assert window.reference_toggle.toolTip() == "App reference available for Manta"
    assert "Calibrated forces" in window.disclaimer.text()
    assert "11 samples" in window.disclaimer.text()
    before = (window.axis_x.min(), window.axis_x.max(), window.first.value(), window.last.value())
    window.reference_toggle.setChecked(False)
    assert [line.name() for line in window.series] == ["x", "y", "z"]
    document = QTextDocument()
    document.setHtml(window.readout.text())
    assert "braking" not in document.toPlainText() and "right" not in document.toPlainText()
    assert tuple(point.y() for point in window.series[0].points()) == data.channels[0]
    assert (
        window.axis_x.min(),
        window.axis_x.max(),
        window.first.value(),
        window.last.value(),
    ) == before
    window.reference_toggle.setChecked(True)
    assert tuple(point.y() for point in window.series[0].points()) == tuple(
        data.plotted_channels[0],
    )
    assert window.data is not None and window.data.channels == data.channels


@pytest.mark.parametrize(
    ("language", "headings"),
    [
        (0, ("Source", "Processing", "Current sample")),
        (1, ("Quelle", "Verarbeitung", "Aktueller Messpunkt")),
    ],
)
def test_technical_details_sections_translate_and_update_sample(
    explorer_window: ExplorerWindow,
    language: int,
    headings: tuple[str, str, str],
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.set_ui_language(language)
    window.details_button.setChecked(True)
    captions = [label.text() for label in window.details_body.findChildren(QLabel)]
    assert all(heading in captions for heading in headings)
    for index in (1571, 4960):
        window.position.setValue(index)
        assert window.data is not None
        assert window.readout.text() == window.data.sample_text(index, rich=True)
        assert window.summary.text() == window.data.technical_summary
        assert window.readout.textFormat() == Qt.TextFormat.RichText
        assert window.summary.textFormat() == Qt.TextFormat.RichText
        document = QTextDocument()
        document.setHtml(window.readout.text())
        seconds = f"{window.data.time_at(index):.3f} s"
        assert (seconds.replace(".", ",") if language == 1 else seconds) in document.toPlainText()
    assert "\n" in window.disclaimer.text()


def test_replay_notation_on_chart_cursor_selection_and_markers(
    explorer_window: ExplorerWindow,
) -> None:
    from PySide6.QtCharts import QCategoryAxis

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Kraken-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert isinstance(window.axis_x, QCategoryAxis)
    assert "00:00.00" in window.axis_x.categoriesLabels()
    assert "ff = sample" in window.axis_x.titleText()
    window.position.setValue(5510)
    assert "Replay" in window.readout.text() and "01:31.47 @ 50 Hz" in window.readout.text()
    assert "Recording" in window.readout.text() and "110.200 s" in window.readout.text()
    window.first.setValue(5510)
    window.last.setValue(5511)
    assert "01:31.47–01:31.48" in window.selection_label.text()
    assert "startIndex · 00:00.00" == window.source_marker_labels["startIndex"].text()
    window.zoom_button.click()
    assert window.axis_x.categoriesLabels() == ["01:31.47", "01:31.48"]
    window.reset_button.click()
    assert "00:00.00" in window.axis_x.categoriesLabels()


def test_new_file_calibration_defaults_on_and_bad_directions_keep_raw_view(
    explorer_window: ExplorerWindow,
) -> None:
    import json

    window = explorer_window
    root: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "name": "Newly imported ride",
        "accelerationSequence": [{"x": 2, "y": 3, "z": 4}] * 2,
        "verticalDirectionVector": {"x": 0, "y": 1, "z": 0},
        "lateralDirectionVector": {"x": 0, "y": 0, "z": 1},
        "longitudinalDirectionVector": {"x": 1, "y": 0, "z": 0},
    }
    with TemporaryDirectory(dir=".tmp") as directory:
        path = Path(directory) / "new-recording.forces"
        path.write_text(json.dumps(root), encoding="utf-8")
        window.open_path(path)
        wait_until(window.open_action.isEnabled)
        assert window.reference_toggle.isEnabled() and window.reference_toggle.isChecked()
        assert [series.name() for series in window.series] == [
            "Vertical",
            "Lateral (+ right / − left)",
            "Longitudinal (+ acceleration / − braking)",
        ]
        window.reference_toggle.setChecked(False)
        window.open_path(path)
        wait_until(window.open_action.isEnabled)
        assert window.reference_toggle.isChecked()
        root["lateralDirectionVector"] = root["verticalDirectionVector"]
        path.write_text(json.dumps(root), encoding="utf-8")
        window.open_path(path)
        wait_until(window.open_action.isEnabled)
        assert window.data is not None and window.data.title == "Newly imported ride"
        assert not window.reference_toggle.isChecked()
        assert "calibration unavailable" in window.statusBar().currentMessage()
        assert "CALIBRATION_UNAVAILABLE" in window.notes.toPlainText()
        assert [series.name() for series in window.series] == ["x", "y", "z"]


def test_gps_dialog_is_independent_and_replaced_with_recording(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.gps_button.isEnabled()
    for pattern in (
        "VoltronNevera-*.forces",
        "Manta-*.forces",
        "Kraken-*.forces",
        "Taron-*.forces",
        "IronGwazi-*.forces",
    ):
        window.open_path(next(REAL_FIXTURE_DIRECTORY.glob(pattern)))
        wait_until(window.open_action.isEnabled)
        assert window.data is not None
        available = window.data.source.recording.gps is not None
        assert window.gps_button.isEnabled() == available
        assert window.gps_window is None
        if available:
            before = (
                window.axis_x.min(),
                window.axis_x.max(),
                window.slider.value(),
                window.first.value(),
                window.last.value(),
            )
            window.gps_button.click()
            assert window.gps_window is not None and window.gps_window.isVisible()
            assert window.data.title in window.gps_window.windowTitle()
            assert before == (
                window.axis_x.min(),
                window.axis_x.max(),
                window.slider.value(),
                window.first.value(),
                window.last.value(),
            )
            window.close()
            assert not window.gps_window.isVisible()
            window.show()
            wait_until(lambda: window.windowHandle().isExposed())


def test_smoothing_slider_preserves_source_time_and_selection(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.smoothing_slider.isEnabled()
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    window.open_path(path)
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.calibration_available
    default = tuple(tuple(axis) for axis in data.plotted_channels)
    before = (
        window.axis_x.min(),
        window.axis_x.max(),
        window.first.value(),
        window.last.value(),
        window.slider.value(),
    )
    assert window.smoothing_slider.isEnabled() and window.smoothing_slider.value() == 5
    option = QStyleOptionSlider()
    window.smoothing_slider.initStyleOption(option)
    handle = (
        window.smoothing_slider.style()
        .subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            window.smoothing_slider,
        )
        .center()
    )
    target = QPoint(min(window.smoothing_slider.width() - 1, handle.x() + 80), handle.y())
    QTest.mousePress(window.smoothing_slider, Qt.MouseButton.LeftButton, pos=handle)
    try:
        QTest.mouseMove(window.smoothing_slider, target)
        QTest.qWait(20)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.smoothing_slider.isSliderDown()
        assert window.smoothing_slider.value() != 5
        assert window.data is not None and window.data.calibration_available
        assert window.data.smoothing_window == window.smoothing_slider.value() * 2 + 1
        assert tuple(point.y() for point in window.series[0].points()) == tuple(
            window.data.plotted_channels[0],
        )
        assert f"{window.data.smoothing_window} samples" in window.smoothing_label.text()
        visible = window.data.select_visible(window.axis_x.min(), window.axis_x.max())
        extrema_context, extrema_rows = window.data.extrema_text(
            visible.first,
            visible.last,
            rich=True,
        )
        assert window.extrema_context.text() == extrema_context
        assert tuple(label.text() for label in window.extrema_labels) == extrema_rows
    finally:
        QTest.mouseRelease(window.smoothing_slider, Qt.MouseButton.LeftButton, pos=target)
    window.smoothing_slider.setFocus()
    QTest.keyClick(window.smoothing_slider, Qt.Key.Key_Home)
    wait_until(
        lambda: window.analysis_controller is not None and not window.analysis_controller.pending,
    )
    assert window.data is not None and window.data.calibration_available
    assert window.data.smoothing_window == 1
    assert data.analysis is not None and data.analysis.forces.projected.channels is not None
    assert tuple(tuple(axis) for axis in window.data.plotted_channels) == tuple(
        tuple(axis.values) for axis in data.analysis.forces.projected.channels
    )
    assert "Smoothing off" in window.smoothing_label.text()
    assert window.data.channels == data.channels
    for position in (10, 25, 5):
        window.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.data.smoothing_window == position * 2 + 1
        assert (
            window.axis_x.min(),
            window.axis_x.max(),
            window.first.value(),
            window.last.value(),
            window.slider.value(),
        ) == before
        assert (window.axis_y.min(), window.axis_y.max()) == window.data.value_range
    assert tuple(tuple(axis) for axis in window.data.plotted_channels) == default
    from PySide6.QtCharts import QCategoryAxis

    assert isinstance(window.axis_y, QCategoryAxis)
    for position in (0, 2, 5, 25):
        window.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.axis_y.min() < -1 and window.axis_y.max() > 1
        for value in (-1, 0, 1):
            label = f"{value} g"
            assert label in window.axis_y.categoriesLabels()
            assert window.axis_y.endValue(label) == value
    for position in (0, 10, 25):
        window.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        QTest.mouseClick(window.smoothing_slider, Qt.MouseButton.RightButton)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.smoothing_slider.value() == 5
        assert window.data.smoothing_window == 11
        assert tuple(tuple(axis) for axis in window.data.plotted_channels) == default
        assert "11 samples" in window.smoothing_label.text()
        assert (
            window.axis_x.min(),
            window.axis_x.max(),
            window.first.value(),
            window.last.value(),
            window.slider.value(),
        ) == before
    window.smoothing_slider.setValue(2)
    wait_until(
        lambda: window.analysis_controller is not None and not window.analysis_controller.pending,
    )
    window.reference_toggle.setChecked(False)
    assert not window.smoothing_slider.isEnabled()
    assert window.data.plotted_channels == data.channels
    window.reference_toggle.setChecked(True)
    assert window.smoothing_slider.isEnabled() and window.data.smoothing_window == 5
    window.open_path(path)
    wait_until(window.open_action.isEnabled)
    assert window.smoothing_slider.value() == 5 and window.data.smoothing_window == 11


@pytest.mark.parametrize("language", [0, 1], ids=["english", "german"])
@pytest.mark.parametrize("appearance", [0, 1], ids=["dark", "light"])
def test_chart_shrinks_to_available_height_without_workspace_scrolling(
    explorer_window: ExplorerWindow,
    language: int,
    appearance: int,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    window.set_ui_language(language)
    window.set_appearance(appearance)
    window.position.setValue(4960)
    points = tuple(window.series[0].points())
    time_range = (window.axis_x.min(), window.axis_x.max())
    heights: list[int] = []
    for width, height in ((1600, 1100), (1280, 820), (1280, 720), (1600, 1100)):
        resize_workspace(window, width, height)
        QApplication.processEvents()
        assert window.plot_scroll.verticalScrollBar().maximum() == 0
        assert not window.plot_scroll.verticalScrollBar().isVisible()
        viewport = window.plot_scroll.viewport()
        assert window.airtime_legend.isVisible()
        assert window.airtime_legend.y() >= window.chart_view.geometry().bottom()
        assert (
            window.airtime_legend.mapTo(viewport, QPoint()).y()
            < window.slider.mapTo(
                viewport,
                QPoint(),
            ).y()
        )
        for control in (
            window.reference_toggle,
            window.airtime_legend,
            window.slider,
            window.position,
            *window.value_labels,
        ):
            bounds = control.rect().translated(control.mapTo(viewport, QPoint(0, 0)))
            assert viewport.rect().contains(bounds)
        assert window.chart.plotArea().height() > 100
        assert tuple(window.series[0].points()) == points
        assert (window.axis_x.min(), window.axis_x.max()) == time_range
        assert window.position.value() == 4960
        heights.append(window.chart_view.height())
    assert heights[0] > heights[1] > heights[2]
    assert heights[3] == heights[0]


@pytest.mark.parametrize("initial_width", [720, 1280], ids=["compact", "wide"])
def test_focus_workspace_layout_and_current_value_cards(
    explorer_window: ExplorerWindow,
    initial_width: int,
) -> None:
    window = explorer_window
    resize_workspace(window, initial_width, 480)
    QTest.qWait(50)
    wide = initial_width >= 1080
    assert window.inspector.isVisible() == wide
    assert window.plot_panel.isVisible()
    assert window.workspace.orientation() == (
        Qt.Orientation.Horizontal if wide else Qt.Orientation.Vertical
    )
    if not wide:
        window.inspector_button.click()
        assert window.inspector.isVisible()
        assert not window.plot_panel.isVisible()
    resize_workspace(window, 1280, 820)
    QTest.qWait(50)
    assert window.inspector.isVisible()
    assert window.workspace.orientation() == Qt.Orientation.Horizontal
    assert not window.details_body.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    assert window.header_summary.text() == window.data.overview_text
    for index in (2013, 4782):
        window.position.setValue(index)
        assert window.time_readout.text() == window.data.sample_clock_text(index)
        assert [label.text() for label in window.value_labels] == [
            card[1] for card in window.data.sample_cards(index)
        ]
        context = window.data.vertical_context_label(index)
        assert context is not None
        assert window.value_hints[0].text() == window.data.sample_cards(index)[0][2]
        assert window.theme.vertical_context_colors[context] in (window.value_hints[0].styleSheet())
    window.reference_toggle.setChecked(False)
    assert [label.text() for label in window.value_names] == ["x", "y", "z"]
    assert all("unknown" in label.text() for label in window.value_hints)
    window.reference_toggle.setChecked(True)
    resize_workspace(window, 720, 480)
    QTest.qWait(50)
    assert (window.width(), window.height()) == (720, 480)
    assert window.workspace.orientation() == Qt.Orientation.Vertical
    assert not window.inspector.isVisible()
    window.inspector_button.click()
    assert window.inspector.isVisible()
    assert not window.plot_panel.isVisible()
    assert (window.width(), window.height()) == (720, 480)
    window.notes_button.click()
    assert window.details_body.isVisible() and window.notes.isVisible()
    QTest.qWait(20)
    note_position = window.notes.mapTo(window.inspector.viewport(), QPoint(0, 0))
    assert note_position.y() < window.inspector.viewport().height()
    assert note_position.y() + window.notes.height() > 0
    window.details_button.click()
    assert not window.notes_button.isChecked() and not window.notes.isVisible()
    resize_workspace(window, 1280, 820)
    QTest.qWait(50)
    assert window.workspace.orientation() == Qt.Orientation.Horizontal
    assert window.inspector.isVisible()
    assert window.chart.plotArea().width() > 0


def test_focus_header_preserves_literal_device_metadata(
    explorer_window: ExplorerWindow,
    synthetic_recording: Recording,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace
    from ride_forces_analyzer.explorer import present_recording
    from ride_forces_analyzer.importers import ImportSuccess

    recording = replace(
        synthetic_recording,
        metadata=replace(synthetic_recording.metadata, device="<b>Watch</b>"),
    )
    view = present_recording(ImportSuccess(recording))

    def load_synthetic(path: Path) -> ExplorerData:
        return view

    monkeypatch.setattr(loading, "load_recording", load_synthetic)
    explorer_window.open_path(Path("synthetic-header.forces"))
    wait_until(explorer_window.open_action.isEnabled)
    assert explorer_window.header_summary.text() == view.overview_text
    assert "<b>Watch</b>" in explorer_window.header_summary.text()
    assert explorer_window.header_summary.textFormat() == Qt.TextFormat.PlainText


def test_slider_background_stays_dark(explorer_window: ExplorerWindow) -> None:
    """Disabled-handle styling must never paint a light rectangle behind the track."""
    window = explorer_window
    for slider in (window.slider, window.smoothing_slider):
        for enabled in (False, True):
            slider.setEnabled(enabled)
            QApplication.processEvents()
            pixels = slider.grab().toImage()
            # Away from the handle and above the narrow track: only panel background.
            color = pixels.pixelColor(pixels.width() // 2, 0)
            assert max(color.red(), color.green(), color.blue()) < 70


def test_visible_extrema_follow_zoom_and_ignore_selection_and_cursor(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    window.first.setValue(10)
    window.last.setValue(100)
    window.position.setValue(50)
    viewport = (window.axis_x.min(), window.axis_x.max())
    for reference in (False, True):
        window.reference_toggle.setChecked(reference)
        for position in (0, 5, 25) if reference else (5,):
            window.smoothing_slider.setValue(position)
            wait_until(
                lambda: (
                    window.analysis_controller is not None
                    and not window.analysis_controller.pending
                ),
            )
            data = window.data
            assert data is not None
            visible = data.select_visible(*viewport)
            context, rows = data.extrema_text(visible.first, visible.last, rich=True)
            assert window.extrema_context.text() == context
            assert tuple(label.text() for label in window.extrema_labels) == rows
            assert all(
                label.textFormat() == Qt.TextFormat.RichText for label in window.extrema_labels
            )
            assert (window.axis_x.min(), window.axis_x.max()) == viewport
            assert window.position.value() == 50
    window.visibility[0].setChecked(False)
    assert "Vertical" in window.extrema_labels[0].text()
    texts = tuple(label.text() for label in window.extrema_labels)
    window.first.setValue(100)
    assert tuple(label.text() for label in window.extrema_labels) == texts
    window.position.setValue(75)
    assert tuple(label.text() for label in window.extrema_labels) == texts
    for change in (window.zoom_selection, lambda: window.zoom_wheel(0.5, -3), window.reset_view):
        change()
        visible = data.select_visible(window.axis_x.min(), window.axis_x.max())
        context, rows = data.extrema_text(visible.first, visible.last, rich=True)
        assert window.extrema_context.text() == context
        assert tuple(label.text() for label in window.extrema_labels) == rows
    window.zoom_selection()
    assert (
        "1 selected" in window.extrema_context.text()
        or "2 selected" in window.extrema_context.text()
    )
    assert tuple(label.text() for label in window.extrema_labels) != texts
    window.reset_button.click()
    visible = data.select_visible(*data.default_time_range)
    assert (
        tuple(label.text() for label in window.extrema_labels)
        == data.extrema_text(
            visible.first,
            visible.last,
            rich=True,
        )[1]
    )
    resize_workspace(window, 720, 480)
    window.inspector_button.setChecked(True)
    QApplication.processEvents()
    window.inspector.ensureWidgetVisible(window.extrema_labels[-1])
    QApplication.processEvents()
    assert window.extrema_labels[-1].isVisible()
    assert (
        window.inspector.viewport()
        .rect()
        .intersects(
            window.extrema_labels[-1]
            .rect()
            .translated(
                window.extrema_labels[-1].mapTo(window.inspector.viewport(), QPoint()),
            ),
        )
    )
