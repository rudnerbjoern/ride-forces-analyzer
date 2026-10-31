"""Native sample controls follow the same 1× clock in raw and calibrated views."""

# cspell:words Wiedergabe Aufnahme Geschwindigkeit wiedergeben anhalten

from pathlib import Path

from PySide6.QtCharts import QCategoryAxis
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.ui.explorer import loading
from ride_forces_analyzer.ui.explorer import navigation as navigation_module
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import resize_workspace, wait_until


@pytest.fixture(scope="module")
def recording() -> ExplorerData:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Taron-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


def test_arrow_keys_step_samples_only_when_paused_and_outside_inputs(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    monkeypatch.setattr(navigation_module, "monotonic", lambda: 0.0)

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/arrow-recording.forces"))
    wait_until(window.open_action.isEnabled)
    window.activateWindow()
    window.plot.chart_view.setFocus()
    wait_until(window.plot.chart_view.hasFocus)
    window.navigation.position.setValue(100)
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Right)
    assert window.navigation.position.value() == 101
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Left)
    assert window.navigation.position.value() == 100
    window.navigation.position.setValue(0)
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Left)
    assert window.navigation.position.value() == 0
    window.navigation.position.setValue(recording.count - 1)
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Right)
    assert window.navigation.position.value() == recording.count - 1

    window.navigation.position.setValue(100)
    for field in (window.navigation.position, window.inspector.first, window.inspector.last):
        field.setFocus()
        wait_until(field.hasFocus)
        QTest.keyClick(field, Qt.Key.Key_Right)
        QTest.keyClick(field, Qt.Key.Key_Left)
        assert window.navigation.position.value() == 100

    window.plot.chart_view.setFocus()
    window.navigation.toggle_playback()
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Right)
    QTest.keyClick(window.plot.chart_view, Qt.Key.Key_Left)
    assert window.navigation.position.value() == 100
    assert window.navigation.playback is not None and window.navigation.playback.playing
    window.navigation.slider.setFocus()
    QTest.keyClick(window.navigation.slider, Qt.Key.Key_Right)
    assert window.navigation.position.value() == 100
    window.navigation.toggle_playback()
    QTest.keyClick(window.navigation.slider, Qt.Key.Key_Right)
    assert window.navigation.position.value() == 101


def test_play_pause_seek_end_and_translations(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.navigation.play_button.isEnabled()
    now = [0.0]
    monkeypatch.setattr(navigation_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.navigation.play_button.isEnabled()
    assert not window.navigation.play_button.icon().isNull()
    assert window.navigation.play_button.toolTip() == "Play recording"
    assert window.navigation.playback_speed.currentIndex() == 1
    assert [window.navigation.playback_speed.itemText(index) for index in range(3)] == [
        "0.5×",
        "1×",
        "2×",
    ]
    button_width = window.navigation.play_button.width()
    controls = (
        window.navigation.play_button,
        window.navigation.playback_speed,
        window.navigation.position,
    )
    assert len({control.height() for control in controls}) == 1
    assert len({control.geometry().top() for control in controls}) == 1
    assert (
        window.navigation.play_button.minimumWidth()
        == window.navigation.play_button.maximumWidth()
        == button_width
    )
    assert (
        window.navigation.slider.geometry().right()
        < window.navigation.play_button.geometry().left()
    )
    window.reference_toggle.setChecked(False)
    window.navigation.position.setValue(100)
    QTest.mouseClick(window.navigation.play_button, Qt.MouseButton.LeftButton)
    assert window.navigation.play_button.accessibleName() == "Pause"
    assert window.navigation.play_button.toolTip() == "Pause playback"
    QTest.qWait(20)
    assert window.navigation.play_button.width() == button_width
    assert window.navigation.play_button.sizeHint().width() <= button_width
    assert window.navigation.playback_timer.isActive()
    now[0] = 0.5
    expected = 100 + int(0.5 * recording.sample_rate)
    wait_until(lambda: window.navigation.position.value() == expected)
    assert window.data is not None
    assert window.navigation.time_readout.text() == window.data.sample_clock_text(expected)
    window.navigation.position.setValue(400)
    now[0] = 1.0
    expected = 400 + int(0.5 * recording.sample_rate)
    wait_until(lambda: window.navigation.slider.value() == expected)
    QTest.mouseClick(window.navigation.play_button, Qt.MouseButton.LeftButton)
    assert not window.navigation.playback_timer.isActive()
    now[0] = 50.0
    QTest.qWait(40)
    assert window.navigation.play_button.width() == button_width
    assert window.navigation.slider.value() == expected
    QTest.mouseClick(window.navigation.play_button, Qt.MouseButton.LeftButton)
    window.navigation.position.setValue(recording.count - 2)
    now[0] = 51.0
    wait_until(lambda: window.navigation.slider.value() == recording.count - 1)
    assert window.navigation.play_button.accessibleName() == "Play"
    assert window.navigation.play_button.toolTip() == "Play recording"
    assert not window.navigation.playback_timer.isActive()
    window.set_ui_language(1)
    assert window.navigation.play_button.accessibleName() == "Wiedergabe"
    assert window.navigation.play_button.toolTip() == "Aufnahme wiedergeben"
    assert window.navigation.playback_speed.itemText(0) == "0,5×"
    assert window.navigation.play_button.sizeHint().width() <= button_width
    resize_workspace(window, 720, 480)
    window.inspector_button.setChecked(False)
    assert window.navigation.play_button.isVisible()
    assert len({control.height() for control in controls}) == 1
    assert len({control.geometry().top() for control in controls}) == 1
    assert window.navigation.play_button.width() == button_width
    assert (
        window.navigation.slider.geometry().right()
        < window.navigation.play_button.geometry().left()
    )
    assert (
        window.navigation.play_button.geometry().right()
        < window.navigation.playback_speed.geometry().left()
    )
    assert (
        window.navigation.playback_speed.geometry().right()
        < window.navigation.position.geometry().left()
    )
    QTest.mouseClick(window.navigation.play_button, Qt.MouseButton.LeftButton)
    assert window.navigation.slider.value() == 0
    assert window.navigation.play_button.accessibleName() == "Pause"
    assert window.navigation.play_button.toolTip() == "Wiedergabe anhalten"
    QTest.qWait(20)
    assert window.navigation.play_button.width() == button_width
    window.close()
    assert not window.navigation.playback_timer.isActive()


def test_open_and_export_pause_without_reusing_the_old_clock(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    small_preview_frames: None,
) -> None:
    window = explorer_window
    assert not window.navigation.playback_speed.isEnabled()

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    window.navigation.toggle_playback()
    window.navigation.playback_speed.setCurrentIndex(2)
    previous_clock = window.navigation.playback
    window.open_path(Path(".tmp/playback-recording.forces"))
    assert not window.navigation.playback_timer.isActive()
    assert previous_clock is not None and not previous_clock.playing
    wait_until(window.open_action.isEnabled)
    assert window.navigation.playback is not previous_clock
    assert window.navigation.playback_speed.currentIndex() == 1
    assert window.navigation.playback is not None and window.navigation.playback.speed == 1.0
    window.navigation.toggle_playback()
    window.show_export()
    assert not window.navigation.playback_timer.isActive()
    assert window.navigation.playback is not None and not window.navigation.playback.playing


def test_speed_dropdown_changes_running_and_paused_playback(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    now = [0.0]
    monkeypatch.setattr(navigation_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.navigation.playback_speed.isEnabled()
    window.navigation.position.setValue(100)
    window.navigation.playback_speed.setCurrentIndex(0)
    assert not window.navigation.playback_timer.isActive()
    window.navigation.toggle_playback()
    now[0] = 0.5
    wait_until(lambda: window.navigation.position.value() == 112)
    before = window.plot.sample_cursor.at(0).x()
    window.navigation.playback_speed.setCurrentIndex(2)
    assert window.plot.sample_cursor.at(0).x() == pytest.approx(before)
    assert window.navigation.playback_timer.isActive()
    now[0] = 0.75
    wait_until(lambda: window.navigation.position.value() == 137)
    window.navigation.toggle_playback()
    now[0] = 100.0
    window.navigation.playback_speed.setCurrentIndex(1)
    assert not window.navigation.playback_timer.isActive()
    assert window.navigation.position.value() == 137
    window.navigation.toggle_playback()
    now[0] = 100.5
    wait_until(lambda: window.navigation.position.value() == 162)


def test_zoomed_playback_slides_without_changing_zoom_or_selection(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    now = [0.0]
    monkeypatch.setattr(navigation_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    for calibrated in (False, True):
        now[0] = 0.0
        window.reference_toggle.setChecked(calibrated)
        assert isinstance(window.plot.axis_x, QCategoryAxis)
        selection = (window.inspector.first.value(), window.inspector.last.value())
        window.navigation.position.setValue(int(14 * recording.sample_rate))
        window.plot.axis_x.setRange(10.0, 20.0)
        window.navigation.toggle_playback()
        now[0] = 0.5
        wait_until(lambda: window.navigation.position.value() == int(14.5 * recording.sample_rate))
        assert window.plot.axis_x.min() == pytest.approx(10.0)
        now[0] = 1.0
        wait_until(lambda: window.navigation.position.value() == int(15 * recording.sample_rate))
        plot_sizes: list[tuple[float, float]] = []
        tick_positions: dict[str, float] = {}
        offsets = [(step / 2 + 0.01) / recording.sample_rate for step in range(1, 21)]
        offsets.extend((1.999, 2.001, 2.01))
        for offset in offsets:
            # Two frames per sample: the camera/cursor move even before values change.
            now[0] = 1.0 + offset
            index = int((15.0 + offset) * recording.sample_rate)
            expected = 10.0 + offset
            wait_until(lambda: abs(window.plot.axis_x.min() - expected) < 1e-8)
            assert window.navigation.position.value() == index
            assert window.plot.axis_x.min() == pytest.approx(expected)
            assert window.plot.axis_x.max() == pytest.approx(expected + 10.0)
            assert window.plot.sample_cursor.at(0).x() == pytest.approx(15.0 + offset)
            labels = window.plot.axis_x.categoriesLabels()
            for label in labels:
                position = window.plot.axis_x.endValue(label)
                assert position == tick_positions.setdefault(label, position)
            QTest.qWait(20)
            plot = window.plot.chart.plotArea()
            plot_sizes.append((plot.width(), plot.height()))
        assert max(width for width, _ in plot_sizes) - min(width for width, _ in plot_sizes) < 0.5
        assert (
            max(height for _, height in plot_sizes) - min(height for _, height in plot_sizes) < 0.5
        )
        window.navigation.toggle_playback()
        paused = window.plot.axis_x.min()
        now[0] += 10.0
        QTest.qWait(40)
        assert window.plot.axis_x.min() == pytest.approx(paused)
        # Starting near the right edge moves only by the elapsed sample time.
        window.navigation.position.setValue(int(19 * recording.sample_rate))
        window.plot.axis_x.setRange(10.0, 20.0)
        window.navigation.toggle_playback()
        now[0] += 0.5
        wait_until(lambda: window.navigation.position.value() == int(19.5 * recording.sample_rate))
        assert window.plot.axis_x.min() == pytest.approx(10.5)
        window.navigation.toggle_playback()
        # At maximum zoom the integer value sample may lie left of the continuous
        # viewport. Adopting it must not trigger a second, conflicting camera move.
        window.navigation.position.setValue(int(19 * recording.sample_rate))
        width = 1 / recording.sample_rate
        window.plot.axis_x.setRange(19.0, 19.0 + width)
        window.navigation.toggle_playback()
        started = now[0]
        for offset in (1.75 * width, 2.25 * width):
            now[0] = started + offset
            expected = 19.0 + offset - width / 2
            wait_until(lambda: abs(window.plot.axis_x.min() - expected) < 1e-8)
            assert window.plot.axis_x.max() == pytest.approx(expected + width)
            assert window.plot.sample_cursor.at(0).x() == pytest.approx(19.0 + offset)
        # The viewport stops at the recording end and retains its width.
        window.navigation.position.setValue(recording.count - 11)
        window.plot.axis_x.setRange(recording.duration - 10.1, recording.duration - 0.1)
        now[0] += 1.0
        wait_until(lambda: window.navigation.position.value() == recording.count - 1)
        assert window.plot.axis_x.min() == pytest.approx(recording.duration - 10.0)
        assert window.plot.axis_x.max() == pytest.approx(recording.duration)
        assert not window.navigation.playback_timer.isActive()
        assert (window.inspector.first.value(), window.inspector.last.value()) == selection
