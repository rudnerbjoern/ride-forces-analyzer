"""Native Qt interactions; fixture-wide data contracts live in the pure suites."""

# cspell:words Quelle Verarbeitung Aktueller Messpunkt

from hashlib import sha256
from pathlib import Path
from threading import Event
from tempfile import TemporaryDirectory

from PySide6.QtCore import QElapsedTimer, QPoint, QTimer, Qt
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
from ride_forces_analyzer.ui.explorer import loading
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.ui.helpers import resize_workspace, wait_until
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def test_selection_arrows_accelerate_while_held_and_reset_on_release(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    resize_workspace(window, 1280, 820)
    for field, direction in (("first", 1), ("first", -1), ("last", 1), ("last", -1)):
        window.inspector.first.setValue(3000)
        window.inspector.last.setValue(7000)
        control = window.inspector.first if field == "first" else window.inspector.last
        option = QStyleOptionSpinBox()
        option.initFrom(control)
        button = (
            control.style()
            .subControlRect(
                QStyle.ComplexControl.CC_SpinBox,
                option,
                QStyle.SubControl.SC_SpinBoxUp
                if direction > 0
                else QStyle.SubControl.SC_SpinBoxDown,
                control,
            )
            .center()
        )
        initial = control.value()
        values = [initial]
        control.valueChanged.connect(values.append)
        elapsed_ms = 0

        def elapsed(_: QElapsedTimer) -> int:
            return elapsed_ms

        monkeypatch.setattr(QElapsedTimer, "elapsed", elapsed)
        QTest.mousePress(control, Qt.MouseButton.LeftButton, pos=button)
        try:
            assert control.value() == initial + direction
            # Drive the clock at each boundary without waiting five real seconds.
            # Native stepping still updates the real selection controls and chart.
            for elapsed_ms, stride in (
                (999, 1),
                (1000, 5),
                (1999, 5),
                (2000, 10),
                (2999, 10),
                (3000, 20),
                (4999, 20),
                (5000, 50),
            ):
                previous = control.value()
                control.stepBy(direction)
                assert control.value() == previous + direction * stride
            # Retain a real native auto-repeat: range updates must not stop its timer.
            previous = control.value()
            wait_until(lambda: control.value() != previous)
            assert (control.value() - previous) * direction >= 50
            increments = {(last - first) * direction for first, last in zip(values, values[1:])}
            assert {1, 5, 10, 20, 50} <= increments
            assert window.plot.selection_band.isVisible()
            assert window.inspector.first.value() <= window.inspector.last.value()
        finally:
            QTest.mouseRelease(control, Qt.MouseButton.LeftButton, pos=button)
        released = control.value()
        QTest.qWait(200)
        assert control.value() == released
        # The released hold must not accelerate keyboard steps even at the old time.
        QTest.keyClick(control, Qt.Key.Key_Up if direction > 0 else Qt.Key.Key_Down)
        assert control.value() == released + direction
        released = control.value()
        elapsed_ms = 0
        QTest.mouseClick(control, Qt.MouseButton.LeftButton, pos=button)
        assert control.value() == released + direction


def test_selection_and_context_overlays_follow_the_viewport(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.plot.selection_band.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    for appearance in (0, 1):
        window.set_appearance(appearance)
        data = window.data
        assert data is not None
        for reference in (False, True):
            window.reference_toggle.setChecked(reference)
            points = tuple(window.plot.series[0].points())
            current = window.navigation.position.value()
            window.inspector.last.setValue(data.count - 1)
            window.inspector.first.setValue(4200)
            window.inspector.last.setValue(5100)
            for first, last, size in (
                (4000, 5200, (1280, 820)),
                (4400, 4800, (1600, 1100)),
                (5200, 5500, (1280, 820)),
            ):
                window.plot.axis_x.setRange(data.time_at(first), data.time_at(last))
                resize_workspace(window, *size)
                QApplication.processEvents()
                plot = window.plot.chart.plotArea()
                band = window.plot.selection_band
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
                assert tuple(window.plot.series[0].points()) == points
                assert window.navigation.position.value() == current
                assert band.acceptedMouseButtons() == Qt.MouseButton.NoButton
                color = window.plot.chart_view.palette().highlight().color()
                assert band.brush().color().rgb() == color.rgb()
                assert 0 < band.brush().color().alpha() < 255
            window.inspector.first.setValue(4500)
            window.inspector.last.setValue(4500)
            window.plot.axis_x.setRange(data.time_at(4400), data.time_at(4600))
            assert window.plot.selection_band.isVisible()
            assert window.plot.selection_band.rect().width() >= 2

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
        assert len(window.plot.vertical_context_bars) == len(segments)
        assert window.plot.series[0].pen().style() == Qt.PenStyle.SolidLine
        assert window.plot.series[0].pen().color().name() == window.theme.forces[0]
        assert tuple(p.y() for p in window.plot.series[0].points()) == original
        for bar, (label, _, _) in zip(window.plot.vertical_context_bars, segments, strict=True):
            assert bar.brush().color().name() == window.theme.vertical_context_colors[label]
        window.plot.axis_x.setRange(data.time_at(4200), data.time_at(4300))
        window.zoom_wheel(0.5, 2)
        QApplication.processEvents()
        plot = window.plot.chart.plotArea()
        visible = [bar for bar in window.plot.vertical_context_bars if bar.isVisible()]
        assert visible
        low, high = window.plot.axis_x.min(), window.plot.axis_x.max()
        for bar, (_, first, last) in zip(window.plot.vertical_context_bars, segments, strict=True):
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
        assert all(not bar.isVisible() for bar in window.plot.vertical_context_bars)
        window.set_smoothing(5)
        assert all(not bar.isVisible() for bar in window.plot.vertical_context_bars)
        window.visibility[0].setChecked(True)
        assert any(bar.isVisible() for bar in window.plot.vertical_context_bars)
    window.reference_toggle.setChecked(False)
    assert not window.plot.vertical_context_bars
    assert window.plot.series[0].pen().style() == Qt.PenStyle.SolidLine
    assert tuple(p.y() for p in window.plot.series[0].points()) == data.channels[0]


def test_open_chart_navigation_selection_and_integrity(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    for filename, expected_identity in [
        (name, identity)
        for name, identity in REAL_FIXTURES.items()
        if name.startswith(("Manta-", "IronGwazi-"))
    ] + [
        (
            "Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.zforces",
            (91361, "005ce708ec946bcf4dbe0163fc2fb23c629b65c1ed11706000c130855c4ba1e5"),
        ),
    ]:
        window = explorer_window
        window.visibility[1].setChecked(True)
        window.notes_button.setChecked(False)
        path = REAL_FIXTURE_DIRECTORY / filename
        original = path.read_bytes()
        mtime = path.stat().st_mtime_ns

        def chosen(*args: object, **kwargs: object) -> tuple[str, str]:
            assert args[3] == "Ride Forces (*.forces *.zforces);;All files (*)"
            return str(path), "Ride Forces (*.forces *.zforces)"

        monkeypatch.setattr(QFileDialog, "getOpenFileName", chosen)
        window.open_action.trigger()
        wait_until(window.open_action.isEnabled)
        data = window.data
        assert data is not None, window.statusBar().currentMessage()
        assert window.windowTitle() == f"{data.title} · Ride Forces Analyzer"
        assert not window.windowIcon().isNull()
        assert window.inspector.ride_metadata.isVisible()
        assert window.inspector.ride_metadata.text() == data.metadata_rows_text
        assert (
            f"Ride: {data.source.recording.metadata.name}" in window.inspector.ride_metadata.text()
        )
        park = data.source.recording.metadata.location
        assert (
            (f"Park: {park}" in window.inspector.ride_metadata.text())
            if park
            else "Park:" not in window.inspector.ride_metadata.text()
        )
        assert "Train:" not in window.inspector.ride_metadata.text()
        assert "Row:" in window.inspector.ride_metadata.text()
        assert window.reference_toggle.isEnabled() and window.reference_toggle.isChecked()
        assert data.calibrated_enabled
        assert data.count == len(data.source.recording.motion.acceleration)
        for series, values in zip(window.plot.series, data.plotted_channels, strict=True):
            assert series.count() == data.count
            assert (
                window.plot.axis_y.min() <= min(values) <= max(values) <= window.plot.axis_y.max()
            )
            assert tuple(point.y() for point in series.points()) == tuple(values)
            assert tuple(point.x() for point in series.points()) == tuple(
                data.time_at(index) for index in range(data.count)
            )
        assert len(data.markers) == 4
        marker_names = {
            "startIndex": "Start marker",
            "endIndex": "End marker",
            "gravityIndex": "Gravity marker",
            "inclineIndex": "Incline marker",
        }
        for name, index in data.markers:
            points = window.plot.source_marker_lines[name].points()
            assert [point.x() for point in points] == [data.time_at(index)] * 2
            assert [point.y() for point in points] == list(data.value_range)
            label = window.plot.source_marker_labels[name]
            assert label.text() == f"{marker_names[name]} · {data.replay_text(index)}"
            assert label.toolTip().startswith(marker_names[name] + ": sample ")
            assert label.isVisible() == (
                data.default_time_range[0] <= data.time_at(index) <= data.default_time_range[1]
            )
        window.navigation.position.setValue(12)
        assert window.navigation.slider.value() == 12
        assert window.inspector.readout.text() == data.sample_text(12, rich=True)
        assert "0.240 s" in window.inspector.readout.text()
        assert window.plot.sample_cursor.points()[0].x() == data.time_at(12)
        assert window.plot.axis_x.titleText() == data.replay_time_label
        assert "INFERRED_UNIFORM" in window.inspector.summary.text()
        window.inspector.first.setValue(5)
        window.inspector.last.setValue(50)
        assert "46 samples" in window.inspector.selection_label.text()
        window.zoom_button.click()
        assert window.plot.axis_x.min() == 5 / data.sample_rate
        assert window.plot.axis_x.max() == 50 / data.sample_rate
        window.plot.axis_x.setRange(10.2 / data.sample_rate, 20.8 / data.sample_rate)
        window.visible_button.click()
        assert window.inspector.first.value() == 10 and window.inspector.last.value() == 21
        window.navigation.position.setValue(data.count - 1)
        assert window.plot.axis_x.min() <= data.duration <= window.plot.axis_x.max()
        window.inspector.first.setValue(21)
        window.inspector.last.setValue(21)
        window.zoom_button.click()
        assert window.plot.axis_x.max() > window.plot.axis_x.min()
        window.visibility[1].setChecked(False)
        assert not window.plot.series[1].isVisible()
        window.reset_button.click()
        assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == data.default_time_range
        assert (
            "G-force (g)" if data.calibrated_enabled else "unknown"
        ) in window.plot.axis_y.titleText()
        window.notes_button.click()
        assert window.inspector.notes.isVisible()
        if filename.startswith("IronGwazi"):
            assert window.inspector.summary.text() == data.technical_summary
            assert "absent" in window.inspector.summary.text()
        assert path.read_bytes() == original and path.stat().st_mtime_ns == mtime
        expected_size, expected_hash = expected_identity
        assert len(original) == expected_size and sha256(original).hexdigest() == expected_hash


def test_chart_click_and_wheel_navigation_preserve_view_and_selection(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    view = window.plot.chart_view
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    for calibrated in (False, True):
        window.reset_view()
        window.reference_toggle.setChecked(calibrated)
        data = window.data
        assert data is not None
        selection = (window.inspector.first.value(), window.inspector.last.value())
        for zoomed in (False, True):
            if zoomed:
                window.zoom_wheel(0.5, 6)
            time_range = (window.plot.axis_x.min(), window.plot.axis_x.max())
            QApplication.processEvents()
            plot = window.plot.chart.plotArea()
            for fraction in (0.0, 0.25, 0.75, 1.0):
                chart_point = plot.topLeft()
                chart_point.setX(plot.left() + fraction * plot.width())
                chart_point.setY(plot.center().y())
                point = view.mapFromScene(window.plot.chart.mapToScene(chart_point))
                # Keep rounded edge pixels inside the actual plot rectangle.
                point.setX(max(int(plot.left()) + 1, min(int(plot.right()), point.x())))
                actual = window.plot.chart.mapFromScene(view.mapToScene(point))
                seconds = time_range[0] + ((actual.x() - plot.left()) / plot.width()) * (
                    time_range[1] - time_range[0]
                )
                expected = data.sample_at_time(seconds)
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
                assert (
                    window.navigation.position.value()
                    == window.navigation.slider.value()
                    == expected
                ), (
                    calibrated,
                    zoomed,
                    fraction,
                    point,
                    plot,
                    window.plot.chart.plotArea(),
                    time_range,
                )
                assert window.plot.sample_cursor.points()[0].x() == data.time_at(expected)
                assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == time_range
                assert (window.inspector.first.value(), window.inspector.last.value()) == selection
            previous = window.navigation.position.value()
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(1, 1))
            assert window.navigation.position.value() == previous
            center = view.mapFromScene(window.plot.chart.mapToScene(plot.center()))
            QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=center)
            QTest.mouseMove(view.viewport(), center + QPoint(2, 0))
            QTest.mouseRelease(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                pos=center + QPoint(2, 0),
            )
            assert window.navigation.position.value() != previous
            assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == time_range

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None

    def wheel(delta: int, fraction: float = 0.25) -> None:
        plot = window.plot.chart.plotArea()
        point = plot.center()
        point.setX(plot.left() + fraction * plot.width())
        position = window.plot.chart_view.mapFromScene(window.plot.chart.mapToScene(point))
        event = QWheelEvent(
            position,
            window.plot.chart_view.viewport().mapToGlobal(position),
            QPoint(),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(window.plot.chart_view.viewport(), event)

    window.plot.axis_x.setRange(0, data.duration)
    wheel(120)
    assert window.plot.axis_x.max() - window.plot.axis_x.min() == pytest.approx(
        data.duration / 1.25,
    )
    assert window.plot.axis_x.min() == pytest.approx(
        data.duration * 0.05,
        abs=data.duration * 0.002,
    )
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == data.value_range
    wheel(-120)
    assert window.plot.axis_x.min() == pytest.approx(0, abs=1e-10)
    assert window.plot.axis_x.max() == pytest.approx(data.duration)
    for _ in range(5):
        wheel(-120)
        assert window.plot.axis_x.min() == 0 and window.plot.axis_x.max() == data.duration
    for _ in range(5):
        wheel(2400, 0.5)
    assert window.plot.axis_x.max() - window.plot.axis_x.min() == pytest.approx(
        1 / data.sample_rate,
    )
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == data.value_range
    wheel(0)
    assert window.plot.axis_x.max() - window.plot.axis_x.min() == pytest.approx(
        1 / data.sample_rate,
    )


def test_zoom_and_reference_changes_preserve_recording_bounds_and_data(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == data.default_time_range
    fixed_range = data.value_range
    initial_sample = window.navigation.position.value()
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
    plot = window.plot.chart.plotArea()
    start = plot.topLeft() + (plot.center() - plot.topLeft()) / 2
    QTest.mousePress(
        window.plot.chart_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=start.toPoint(),
    )
    QTest.mouseMove(window.plot.chart_view.viewport(), plot.center().toPoint())
    QTest.mouseRelease(
        window.plot.chart_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=plot.center().toPoint(),
    )
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
    assert window.plot.axis_x.max() - window.plot.axis_x.min() < data.duration
    assert window.navigation.position.value() == initial_sample
    window.plot.chart.zoom(4)
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
    assert window.plot.axis_x.max() - window.plot.axis_x.min() < data.duration
    for _ in range(8):
        window.zoom_wheel(0.5, -4)
        assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
        assert 0 <= window.plot.axis_x.min() < window.plot.axis_x.max() <= data.duration
    assert window.plot.axis_x.min() == 0 and window.plot.axis_x.max() == data.duration
    for low, high in (
        (-10, 10),
        (data.duration - 5, data.duration + 5),
        (-100, data.duration + 100),
    ):
        window.plot.axis_x.setRange(low, high)
        assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
        assert 0 <= window.plot.axis_x.min() < window.plot.axis_x.max() <= data.duration
    window.plot.axis_y.setRange(-1000, 1000)
    assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == fixed_range
    window.inspector.first.setValue(data.count - 1)
    window.inspector.last.setValue(data.count - 1)
    window.zoom_button.click()
    assert window.plot.axis_x.min() <= data.duration == window.plot.axis_x.max()
    window.reset_button.click()
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == data.default_time_range

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.calibration_available and data.calibrated_enabled
    assert [line.name() for line in window.plot.series] == [
        "Vertical",
        "Lateral (+ right / − left)",
        "Longitudinal (+ acceleration / − braking)",
    ]
    assert all(name in window.inspector.readout.text() for name in data.channel_names)
    assert window.inspector.readout.wordWrap()
    assert window.visibility[1].text() == "Lateral"
    assert window.visibility[1].toolTip() == "Lateral (+ right / − left)"
    assert window.visibility[2].text() == "Longitudinal"
    assert window.visibility[2].toolTip() == "Longitudinal (+ acceleration / − braking)"
    assert window.reference_toggle.text() == "Calibrated forces"
    for value, line in window.plot.force_references.items():
        assert line.isVisible()
        area = window.plot.chart.plotArea()
        expected_y = (
            area.bottom()
            - (value - window.plot.axis_y.min())
            / (window.plot.axis_y.max() - window.plot.axis_y.min())
            * area.height()
        )
        assert line.line().y1() == pytest.approx(expected_y)
        assert line.line().y2() == pytest.approx(expected_y)
    assert window.reference_toggle.toolTip() == "App reference available for Manta"
    assert "Calibrated forces" in window.inspector.disclaimer.text()
    assert "11 samples" in window.inspector.disclaimer.text()
    before = (
        window.plot.axis_x.min(),
        window.plot.axis_x.max(),
        window.inspector.first.value(),
        window.inspector.last.value(),
    )
    window.reference_toggle.setChecked(False)
    assert all(not line.isVisible() for line in window.plot.force_references.values())
    assert [line.name() for line in window.plot.series] == ["x", "y", "z"]
    document = QTextDocument()
    document.setHtml(window.inspector.readout.text())
    assert "braking" not in document.toPlainText() and "right" not in document.toPlainText()
    assert tuple(point.y() for point in window.plot.series[0].points()) == data.channels[0]
    assert (
        window.plot.axis_x.min(),
        window.plot.axis_x.max(),
        window.inspector.first.value(),
        window.inspector.last.value(),
    ) == before
    window.reference_toggle.setChecked(True)
    assert all(line.isVisible() for line in window.plot.force_references.values())
    assert tuple(point.y() for point in window.plot.series[0].points()) == tuple(
        data.plotted_channels[0],
    )
    assert window.data is not None and window.data.channels == data.channels


def test_failed_and_cancelled_opens_preserve_previous_recording(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("*.forces")))
    wait_until(window.open_action.isEnabled)
    previous = window.data
    assert previous is not None
    points = window.plot.series[0].count()

    def cancelled(*args: object, **kwargs: object) -> tuple[str, str]:
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", cancelled)
    window.open_action.trigger()
    assert window.data is previous
    window.open_path(Path(".tmp/this-recording-does-not-exist.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.data is previous and window.plot.series[0].count() == points
    assert "SOURCE_NOT_FOUND" in window.statusBar().currentMessage()
    with TemporaryDirectory(dir=".tmp") as directory:
        malformed = Path(directory) / "synthetic.forces"
        malformed.write_bytes(b"{")
        window.open_path(malformed)
        wait_until(window.open_action.isEnabled)
        assert window.data is previous
        assert "INVALID_JSON" in window.statusBar().currentMessage()
    window.navigation.position.setValue(previous.count - 1)
    replacement = next(
        path
        for path in REAL_FIXTURE_DIRECTORY.glob("*.forces")
        if path != previous.source.recording.source.provenance.path
    )
    window.open_path(replacement)
    wait_until(window.open_action.isEnabled)
    assert window.data is not None and window.data is not previous
    assert window.navigation.position.value() == window.data.source.recording.indices.start
    assert window.inspector.first.value() == 0
    assert window.inspector.last.value() == window.data.count - 1
    assert window.plot.series[0].count() == window.data.count
    assert window.statusBar().toolTip() == ""
    for name, index in window.data.markers:
        assert window.plot.source_marker_lines[name].points()[0].x() == window.data.time_at(index)


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
from ride_forces_analyzer.ui.explorer import loading
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.__main__ import main
original_load = loading.load_recording
def delayed(path):
    time.sleep(0.2)
    return original_load(path)
loading.load_recording = delayed
original_init = ExplorerWindow.__init__
def initialize(self, settings, *, restore_last_file=True):
    original_init(self, settings, restore_last_file=restore_last_file)
    self.open_path(next(Path('tests/fixtures/real').glob('*.forces')))
    QTimer.singleShot(10, self.close)
ExplorerWindow.__init__ = initialize
assert main() == 0
print('Closed cleanly with background import drained')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert b"Closed cleanly with background import drained" in result.stdout


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
    assert (
        window.inspector.ride_metadata.text() == ""
        and not window.inspector.ride_metadata.isVisible()
    )
    assert window.plot.source_marker_lines["gravityIndex"].count() == 0
    assert not window.plot.source_marker_labels["gravityIndex"].isVisible()
    window.plot.axis_x.setRange(0.005, 0.015)
    assert not window.plot.source_marker_labels["startIndex"].isVisible()
    assert not window.plot.source_marker_labels["endIndex"].isVisible()
    window.reset_view()
    assert window.plot.source_marker_labels["startIndex"].isVisible()
    assert window.plot.source_marker_labels["endIndex"].isVisible()


def test_load_and_reset_use_independent_marker_defaults(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for start, end in ((1, 2), (None, 2), (1, None), (None, None)):
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
        assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == expected
        assert window.navigation.position.value() == (start if start is not None else 0)
        window.plot.chart.zoomOut()
        window.plot.axis_x.setRange(0, data.duration)
        window.reset_button.click()
        assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == expected
        assert window.plot.source_marker_lines["startIndex"].count() == (0 if start is None else 2)
        assert window.plot.source_marker_lines["endIndex"].count() == (0 if end is None else 2)


def test_technical_details_and_replay_labels_follow_language_and_sample(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    for language, headings in (
        (0, ("Source", "Processing", "Current sample")),
        (1, ("Quelle", "Verarbeitung", "Aktueller Messpunkt")),
    ):
        window.set_ui_language(language)
        window.inspector.details_button.setChecked(False)
        collapsed_icon = window.inspector.details_button.icon().pixmap(16, 16).toImage()
        window.inspector.details_button.setChecked(True)
        assert window.inspector.details_button.icon().pixmap(16, 16).toImage() != collapsed_icon
        assert window.inspector.details_button.layoutDirection() == Qt.LayoutDirection.RightToLeft
        captions = [label.text() for label in window.inspector.details_body.findChildren(QLabel)]
        assert all(heading in captions for heading in headings)
        for index in (1571, 4960):
            window.navigation.position.setValue(index)
            assert window.data is not None
            assert window.inspector.readout.text() == window.data.sample_text(index, rich=True)
            assert window.inspector.summary.text() == window.data.technical_summary
            assert window.inspector.readout.textFormat() == Qt.TextFormat.RichText
            assert window.inspector.summary.textFormat() == Qt.TextFormat.RichText
            document = QTextDocument()
            document.setHtml(window.inspector.readout.text())
            seconds = f"{window.data.time_at(index):.3f} s"
            assert (
                seconds.replace(".", ",") if language == 1 else seconds
            ) in document.toPlainText()
        assert "\n" in window.inspector.disclaimer.text()

    window.set_ui_language(0)
    from PySide6.QtCharts import QCategoryAxis

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Kraken-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    assert isinstance(window.plot.axis_x, QCategoryAxis)
    assert "00:00.00" in window.plot.axis_x.categoriesLabels()
    assert "ff = sample" in window.plot.axis_x.titleText()
    window.navigation.position.setValue(5510)
    assert (
        "Replay" in window.inspector.readout.text()
        and "01:31.47 @ 50 Hz" in window.inspector.readout.text()
    )
    assert (
        "Recording" in window.inspector.readout.text()
        and "110.200 s" in window.inspector.readout.text()
    )
    window.inspector.first.setValue(5510)
    window.inspector.last.setValue(5511)
    assert "01:31.47–01:31.48" in window.inspector.selection_label.text()
    assert "Start marker · 00:00.00" == window.plot.source_marker_labels["startIndex"].text()
    window.zoom_button.click()
    assert window.plot.axis_x.categoriesLabels() == ["01:31.47", "01:31.48"]
    window.reset_button.click()
    assert "00:00.00" in window.plot.axis_x.categoriesLabels()


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
        assert [series.name() for series in window.plot.series] == [
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
        assert "CALIBRATION_UNAVAILABLE" in window.inspector.notes.toPlainText()
        assert [series.name() for series in window.plot.series] == ["x", "y", "z"]


def test_gps_dialog_is_independent_and_replaced_with_recording(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.gps_button.isEnabled()
    # Two GPS sources cover replacement; Watch covers removal/disabled controls.
    # Per-recording geometry and source preservation belong to test_gps.py.
    for pattern in (
        "VoltronNevera-*.forces",
        "Manta-*.forces",
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
                window.plot.axis_x.min(),
                window.plot.axis_x.max(),
                window.navigation.slider.value(),
                window.inspector.first.value(),
                window.inspector.last.value(),
            )
            window.gps_button.click()
            assert window.gps_window is not None and window.gps_window.isVisible()
            assert window.data.title in window.gps_window.windowTitle()
            assert before == (
                window.plot.axis_x.min(),
                window.plot.axis_x.max(),
                window.navigation.slider.value(),
                window.inspector.first.value(),
                window.inspector.last.value(),
            )
            window.close()
            assert not window.gps_window.isVisible()
            window.show()
            wait_until(lambda: window.windowHandle().isExposed())


def test_smoothing_slider_preserves_source_time_and_selection(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert not window.inspector.smoothing_slider.isEnabled()
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    window.open_path(path)
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None and data.calibration_available
    default = tuple(tuple(axis) for axis in data.plotted_channels)
    before = (
        window.plot.axis_x.min(),
        window.plot.axis_x.max(),
        window.inspector.first.value(),
        window.inspector.last.value(),
        window.navigation.slider.value(),
    )
    assert (
        window.inspector.smoothing_slider.isEnabled()
        and window.inspector.smoothing_slider.value() == 5
    )
    option = QStyleOptionSlider()
    window.inspector.smoothing_slider.initStyleOption(option)
    handle = (
        window.inspector.smoothing_slider.style()
        .subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            window.inspector.smoothing_slider,
        )
        .center()
    )
    target = QPoint(min(window.inspector.smoothing_slider.width() - 1, handle.x() + 80), handle.y())
    QTest.mousePress(window.inspector.smoothing_slider, Qt.MouseButton.LeftButton, pos=handle)
    try:
        QTest.mouseMove(window.inspector.smoothing_slider, target)
        QTest.qWait(20)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.inspector.smoothing_slider.isSliderDown()
        assert window.inspector.smoothing_slider.value() != 5
        assert window.data is not None and window.data.calibration_available
        assert window.data.smoothing_window == window.inspector.smoothing_slider.value() * 2 + 1
        assert tuple(point.y() for point in window.plot.series[0].points()) == tuple(
            window.data.plotted_channels[0],
        )
        assert f"{window.data.smoothing_window} samples" in window.inspector.smoothing_label.text()
        visible = window.data.select_visible(window.plot.axis_x.min(), window.plot.axis_x.max())
        extrema_context, extrema_rows = window.data.extrema_text(
            visible.first,
            visible.last,
            rich=True,
        )
        assert window.inspector.extrema_context.text() == extrema_context
        assert tuple(label.text() for label in window.inspector.extrema_labels) == extrema_rows
    finally:
        QTest.mouseRelease(window.inspector.smoothing_slider, Qt.MouseButton.LeftButton, pos=target)
    window.inspector.smoothing_slider.setFocus()
    QTest.keyClick(window.inspector.smoothing_slider, Qt.Key.Key_Home)
    wait_until(
        lambda: window.analysis_controller is not None and not window.analysis_controller.pending,
    )
    assert window.data is not None and window.data.calibration_available
    assert window.data.smoothing_window == 1
    assert data.analysis is not None and data.analysis.forces.projected.channels is not None
    assert tuple(tuple(axis) for axis in window.data.plotted_channels) == tuple(
        tuple(axis.values) for axis in data.analysis.forces.projected.channels
    )
    assert "Smoothing off" in window.inspector.smoothing_label.text()
    assert window.data.channels == data.channels
    for position in (10, 25, 5):
        window.inspector.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.data.smoothing_window == position * 2 + 1
        assert (
            window.plot.axis_x.min(),
            window.plot.axis_x.max(),
            window.inspector.first.value(),
            window.inspector.last.value(),
            window.navigation.slider.value(),
        ) == before
        assert (window.plot.axis_y.min(), window.plot.axis_y.max()) == window.data.value_range
    assert tuple(tuple(axis) for axis in window.data.plotted_channels) == default
    from PySide6.QtCharts import QCategoryAxis

    assert isinstance(window.plot.axis_y, QCategoryAxis)
    for position in (0, 2, 5, 25):
        window.inspector.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.plot.axis_y.min() < -1 and window.plot.axis_y.max() > 1
        for value in (-1, 0, 1):
            label = f"{value} g"
            assert label in window.plot.axis_y.categoriesLabels()
            assert window.plot.axis_y.endValue(label) == value
    for position in (0, 10, 25):
        window.inspector.smoothing_slider.setValue(position)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        QTest.mouseClick(window.inspector.smoothing_slider, Qt.MouseButton.RightButton)
        wait_until(
            lambda: (
                window.analysis_controller is not None and not window.analysis_controller.pending
            ),
        )
        assert window.inspector.smoothing_slider.value() == 5
        assert window.data.smoothing_window == 11
        assert tuple(tuple(axis) for axis in window.data.plotted_channels) == default
        assert "11 samples" in window.inspector.smoothing_label.text()
        assert (
            window.plot.axis_x.min(),
            window.plot.axis_x.max(),
            window.inspector.first.value(),
            window.inspector.last.value(),
            window.navigation.slider.value(),
        ) == before
    window.inspector.smoothing_slider.setValue(2)
    wait_until(
        lambda: window.analysis_controller is not None and not window.analysis_controller.pending,
    )
    window.reference_toggle.setChecked(False)
    assert not window.inspector.smoothing_slider.isEnabled()
    assert window.data.plotted_channels == data.channels
    window.reference_toggle.setChecked(True)
    assert window.inspector.smoothing_slider.isEnabled() and window.data.smoothing_window == 5
    window.open_path(path)
    wait_until(window.open_action.isEnabled)
    assert window.inspector.smoothing_slider.value() == 5 and window.data.smoothing_window == 11


def test_workspace_layout_and_cards_follow_size_language_and_theme(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    assert window.inspector.isVisible()
    assert window.workspace.orientation() == Qt.Orientation.Horizontal
    resize_workspace(window, 720, 480)
    window.inspector_button.setChecked(False)
    window.inspector.details_button.setChecked(False)
    assert not window.inspector.isVisible()
    assert window.plot_panel.isVisible()
    assert window.workspace.orientation() == Qt.Orientation.Vertical
    window.inspector_button.click()
    assert window.inspector.isVisible()
    assert not window.plot_panel.isVisible()
    resize_workspace(window, 1280, 820)
    QTest.qWait(50)
    assert window.inspector.isVisible()
    assert window.workspace.orientation() == Qt.Orientation.Horizontal
    assert not window.inspector.details_body.isVisible()
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    assert window.data is not None
    assert window.header_summary.text() == window.data.overview_text
    QApplication.processEvents()
    baselines = [
        label.geometry().top() + label.contentsRect().bottom() - label.fontMetrics().descent()
        for label in (window.heading, window.header_summary)
    ]
    assert baselines[0] == baselines[1]
    for index in (2013, 4782):
        window.navigation.position.setValue(index)
        assert window.navigation.time_readout.text() == window.data.sample_clock_text(index)
        assert [label.text() for label in window.navigation.value_labels] == [
            card[1] for card in window.data.sample_cards(index)
        ]
        context = window.data.vertical_context_label(index)
        assert context is not None
        assert window.navigation.value_hints[0].text() == window.data.sample_cards(index)[0][2]
        assert window.theme.vertical_context_colors[context] in (
            window.navigation.value_hints[0].styleSheet()
        )
    window.reference_toggle.setChecked(False)
    assert [label.text() for label in window.navigation.value_names] == ["x", "y", "z"]
    assert all("unknown" in label.text() for label in window.navigation.value_hints)
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
    assert window.inspector.details_body.isVisible() and window.inspector.notes.isVisible()
    QTest.qWait(20)
    note_position = window.inspector.notes.mapTo(window.inspector.viewport(), QPoint(0, 0))
    assert note_position.y() < window.inspector.viewport().height()
    assert note_position.y() + window.inspector.notes.height() > 0
    window.inspector.details_button.click()
    assert not window.notes_button.isChecked() and not window.inspector.notes.isVisible()
    resize_workspace(window, 1280, 820)
    QTest.qWait(50)
    assert window.workspace.orientation() == Qt.Orientation.Horizontal
    assert window.inspector.isVisible()
    assert window.plot.chart.plotArea().width() > 0

    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces")))
    wait_until(window.open_action.isEnabled)
    for language, appearance in ((0, 0), (1, 0), (0, 1), (1, 1)):
        resize_workspace(window, 1920, 1040)
        window.set_ui_language(language)
        window.set_appearance(appearance)
        window.navigation.position.setValue(4960)
        points = tuple(window.plot.series[0].points())
        time_range = (window.plot.axis_x.min(), window.plot.axis_x.max())
        heights: list[int] = []
        for width, height in ((1600, 1100), (1280, 820), (1280, 720), (1600, 1100)):
            resize_workspace(window, width, height)
            QApplication.processEvents()
            assert window.plot_scroll.verticalScrollBar().maximum() == 0
            assert not window.plot_scroll.verticalScrollBar().isVisible()
            viewport = window.plot_scroll.viewport()
            assert window.plot.airtime_legend.isVisible()
            assert window.plot.airtime_legend.y() >= window.plot.chart_view.geometry().bottom()
            assert (
                window.plot.airtime_legend.mapTo(viewport, QPoint()).y()
                < window.navigation.slider.mapTo(
                    viewport,
                    QPoint(),
                ).y()
            )
            for control in (
                window.reference_toggle,
                window.plot.airtime_legend,
                window.navigation.slider,
                window.navigation.position,
                *window.navigation.value_labels,
            ):
                bounds = control.rect().translated(control.mapTo(viewport, QPoint(0, 0)))
                assert viewport.rect().contains(bounds)
            assert window.plot.chart.plotArea().height() > 100
            assert tuple(window.plot.series[0].points()) == points
            assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == time_range
            assert window.navigation.position.value() == 4960
            heights.append(window.plot.chart_view.height())
        assert heights[0] > heights[1] > heights[2]
        assert heights[3] == heights[0]

    window.set_appearance(0)
    """Disabled-handle styling must never paint a light rectangle behind the track."""
    window = explorer_window
    for slider in (window.navigation.slider, window.inspector.smoothing_slider):
        for enabled in (False, True):
            slider.setEnabled(enabled)
            QApplication.processEvents()
            pixels = slider.grab().toImage()
            # Away from the handle and above the narrow track: only panel background.
            color = pixels.pixelColor(pixels.width() // 2, 0)
            assert max(color.red(), color.green(), color.blue()) < 70


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
        metadata=replace(synthetic_recording.metadata, device="<b>Watch</b>", location=None),
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
    assert explorer_window.heading.text() == view.title
    recording = replace(recording, metadata=replace(recording.metadata, location="Europa-Park"))
    view = present_recording(ImportSuccess(recording))
    explorer_window.open_path(Path("synthetic-header-park.forces"))
    wait_until(explorer_window.open_action.isEnabled)
    assert explorer_window.heading.text() == f"{view.title} · Europa-Park"


def test_visible_extrema_follow_zoom_and_ignore_selection_and_cursor(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    window.open_path(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    wait_until(window.open_action.isEnabled)
    data = window.data
    assert data is not None
    window.inspector.first.setValue(10)
    window.inspector.last.setValue(100)
    window.navigation.position.setValue(50)
    viewport = (window.plot.axis_x.min(), window.plot.axis_x.max())
    for reference in (False, True):
        window.reference_toggle.setChecked(reference)
        for position in (0, 5, 25) if reference else (5,):
            window.inspector.smoothing_slider.setValue(position)
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
            assert window.inspector.extrema_context.text() == context
            assert tuple(label.text() for label in window.inspector.extrema_labels) == rows
            assert all(
                label.textFormat() == Qt.TextFormat.RichText
                for label in window.inspector.extrema_labels
            )
            assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == viewport
            assert window.navigation.position.value() == 50
    window.visibility[0].setChecked(False)
    assert "Vertical" in window.inspector.extrema_labels[0].text()
    texts = tuple(label.text() for label in window.inspector.extrema_labels)
    window.inspector.first.setValue(100)
    assert tuple(label.text() for label in window.inspector.extrema_labels) == texts
    window.navigation.position.setValue(75)
    assert tuple(label.text() for label in window.inspector.extrema_labels) == texts
    for change in (window.zoom_selection, lambda: window.zoom_wheel(0.5, -3), window.reset_view):
        change()
        visible = data.select_visible(window.plot.axis_x.min(), window.plot.axis_x.max())
        context, rows = data.extrema_text(visible.first, visible.last, rich=True)
        assert window.inspector.extrema_context.text() == context
        assert tuple(label.text() for label in window.inspector.extrema_labels) == rows
    window.zoom_selection()
    assert (
        "1 selected" in window.inspector.extrema_context.text()
        or "2 selected" in window.inspector.extrema_context.text()
    )
    assert tuple(label.text() for label in window.inspector.extrema_labels) != texts
    window.reset_button.click()
    visible = data.select_visible(*data.default_time_range)
    assert (
        tuple(label.text() for label in window.inspector.extrema_labels)
        == data.extrema_text(
            visible.first,
            visible.last,
            rich=True,
        )[1]
    )
    resize_workspace(window, 720, 480)
    window.inspector_button.setChecked(True)
    QApplication.processEvents()
    window.inspector.ensureWidgetVisible(window.inspector.extrema_labels[-1])
    QApplication.processEvents()
    assert window.inspector.extrema_labels[-1].isVisible()
    assert (
        window.inspector.viewport()
        .rect()
        .intersects(
            window.inspector.extrema_labels[-1]
            .rect()
            .translated(
                window.inspector.extrema_labels[-1].mapTo(window.inspector.viewport(), QPoint()),
            ),
        )
    )
