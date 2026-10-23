"""Native sample controls follow the same 1× clock in raw and calibrated views."""

# cspell:words Wiedergabe Aufnahme Geschwindigkeit wiedergeben anhalten

from pathlib import Path

from PySide6.QtCharts import QCategoryAxis
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.ui import loading, window as window_module
from ride_forces_analyzer.ui.window import ExplorerWindow
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
    monkeypatch.setattr(window_module, "monotonic", lambda: 0.0)

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/arrow-recording.forces"))
    wait_until(window.open_action.isEnabled)
    window.activateWindow()
    window.chart_view.setFocus()
    wait_until(window.chart_view.hasFocus)
    window.position.setValue(100)
    QTest.keyClick(window.chart_view, Qt.Key.Key_Right)
    assert window.position.value() == 101
    QTest.keyClick(window.chart_view, Qt.Key.Key_Left)
    assert window.position.value() == 100
    window.position.setValue(0)
    QTest.keyClick(window.chart_view, Qt.Key.Key_Left)
    assert window.position.value() == 0
    window.position.setValue(recording.count - 1)
    QTest.keyClick(window.chart_view, Qt.Key.Key_Right)
    assert window.position.value() == recording.count - 1

    window.position.setValue(100)
    for field in (window.position, window.first, window.last):
        field.setFocus()
        wait_until(field.hasFocus)
        QTest.keyClick(field, Qt.Key.Key_Right)
        QTest.keyClick(field, Qt.Key.Key_Left)
        assert window.position.value() == 100

    window.chart_view.setFocus()
    window.toggle_playback()
    QTest.keyClick(window.chart_view, Qt.Key.Key_Right)
    QTest.keyClick(window.chart_view, Qt.Key.Key_Left)
    assert window.position.value() == 100
    assert window.playback is not None and window.playback.playing
    window.slider.setFocus()
    QTest.keyClick(window.slider, Qt.Key.Key_Right)
    assert window.position.value() == 100
    window.toggle_playback()
    QTest.keyClick(window.slider, Qt.Key.Key_Right)
    assert window.position.value() == 101


def test_play_pause_seek_end_and_translations(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    assert not window.play_button.isEnabled()
    now = [0.0]
    monkeypatch.setattr(window_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.play_button.isEnabled()
    assert not window.play_button.text()
    assert not window.play_button.icon().isNull()
    assert window.play_button.toolTip() == "Play recording"
    assert window.playback_speed.currentIndex() == 1
    assert [window.playback_speed.itemText(index) for index in range(3)] == ["0.5×", "1×", "2×"]
    button_width = window.play_button.width()
    controls = (window.play_button, window.playback_speed, window.position)
    assert len({control.height() for control in controls}) == 1
    assert len({control.geometry().top() for control in controls}) == 1
    assert window.play_button.minimumWidth() == window.play_button.maximumWidth() == button_width
    assert window.slider.geometry().right() < window.play_button.geometry().left()
    window.reference_toggle.setChecked(False)
    window.position.setValue(100)
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    assert not window.play_button.text()
    assert window.play_button.accessibleName() == "Pause"
    assert window.play_button.toolTip() == "Pause playback"
    QTest.qWait(20)
    assert window.play_button.width() == button_width
    assert window.play_button.sizeHint().width() <= button_width
    assert window.playback_timer.isActive()
    now[0] = 0.5
    expected = 100 + int(0.5 * recording.sample_rate)
    wait_until(lambda: window.position.value() == expected)
    assert window.data is not None
    assert window.time_readout.text() == window.data.sample_clock_text(expected)
    window.position.setValue(400)
    now[0] = 1.0
    expected = 400 + int(0.5 * recording.sample_rate)
    wait_until(lambda: window.slider.value() == expected)
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    assert not window.playback_timer.isActive()
    now[0] = 50.0
    QTest.qWait(40)
    assert window.play_button.width() == button_width
    assert window.slider.value() == expected
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    window.position.setValue(recording.count - 2)
    now[0] = 51.0
    wait_until(lambda: window.slider.value() == recording.count - 1)
    assert not window.play_button.text()
    assert window.play_button.accessibleName() == "Play"
    assert window.play_button.toolTip() == "Play recording"
    assert not window.playback_timer.isActive()
    window.set_ui_language(1)
    assert not window.play_button.text()
    assert window.play_button.accessibleName() == "Wiedergabe"
    assert window.play_button.toolTip() == "Aufnahme wiedergeben"
    assert window.playback_speed.itemText(0) == "0,5×"
    assert window.play_button.sizeHint().width() <= button_width
    resize_workspace(window, 720, 480)
    window.inspector_button.setChecked(False)
    assert window.play_button.isVisible()
    assert len({control.height() for control in controls}) == 1
    assert len({control.geometry().top() for control in controls}) == 1
    assert window.play_button.width() == button_width
    assert window.slider.geometry().right() < window.play_button.geometry().left()
    assert window.play_button.geometry().right() < window.playback_speed.geometry().left()
    assert window.playback_speed.geometry().right() < window.position.geometry().left()
    QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
    assert window.slider.value() == 0
    assert not window.play_button.text()
    assert window.play_button.accessibleName() == "Pause"
    assert window.play_button.toolTip() == "Wiedergabe anhalten"
    QTest.qWait(20)
    assert window.play_button.width() == button_width
    window.close()
    assert not window.playback_timer.isActive()


def test_open_and_export_pause_without_reusing_the_old_clock(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    small_preview_frames: None,
) -> None:
    window = explorer_window
    assert not window.playback_speed.isEnabled()

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    window.toggle_playback()
    window.playback_speed.setCurrentIndex(2)
    previous_clock = window.playback
    window.open_path(Path(".tmp/playback-recording.forces"))
    assert not window.playback_timer.isActive()
    assert previous_clock is not None and not previous_clock.playing
    wait_until(window.open_action.isEnabled)
    assert window.playback is not previous_clock
    assert window.playback_speed.currentIndex() == 1
    assert window.playback is not None and window.playback.speed == 1.0
    window.toggle_playback()
    window.show_export()
    assert not window.playback_timer.isActive()
    assert window.playback is not None and not window.playback.playing


def test_speed_dropdown_changes_running_and_paused_playback(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    now = [0.0]
    monkeypatch.setattr(window_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    assert window.playback_speed.isEnabled()
    window.position.setValue(100)
    window.playback_speed.setCurrentIndex(0)
    assert not window.playback_timer.isActive()
    window.toggle_playback()
    now[0] = 0.5
    wait_until(lambda: window.position.value() == 112)
    before = window.sample_cursor.at(0).x()
    window.playback_speed.setCurrentIndex(2)
    assert window.sample_cursor.at(0).x() == pytest.approx(before)
    assert window.playback_timer.isActive()
    now[0] = 0.75
    wait_until(lambda: window.position.value() == 137)
    window.toggle_playback()
    now[0] = 100.0
    window.playback_speed.setCurrentIndex(1)
    assert not window.playback_timer.isActive()
    assert window.position.value() == 137
    window.toggle_playback()
    now[0] = 100.5
    wait_until(lambda: window.position.value() == 162)


@pytest.mark.parametrize("calibrated", [False, True], ids=["raw", "calibrated"])
def test_zoomed_playback_slides_without_changing_zoom_or_selection(
    explorer_window: ExplorerWindow,
    recording: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    calibrated: bool,
) -> None:
    window = explorer_window
    now = [0.0]
    monkeypatch.setattr(window_module, "monotonic", lambda: now[0])

    def load_sample(path: Path) -> ExplorerData:
        return recording

    monkeypatch.setattr(loading, "load_recording", load_sample)
    window.open_path(Path(".tmp/playback-recording.forces"))
    wait_until(window.open_action.isEnabled)
    window.reference_toggle.setChecked(calibrated)
    assert isinstance(window.axis_x, QCategoryAxis)
    selection = (window.first.value(), window.last.value())
    window.position.setValue(int(14 * recording.sample_rate))
    window.axis_x.setRange(10.0, 20.0)
    window.toggle_playback()
    now[0] = 0.5
    wait_until(lambda: window.position.value() == int(14.5 * recording.sample_rate))
    assert window.axis_x.min() == pytest.approx(10.0)
    now[0] = 1.0
    wait_until(lambda: window.position.value() == int(15 * recording.sample_rate))
    plot_sizes: list[tuple[float, float]] = []
    tick_positions: dict[str, float] = {}
    offsets = [(step / 2 + 0.01) / recording.sample_rate for step in range(1, 21)]
    offsets.extend((1.999, 2.001, 2.01))
    for offset in offsets:
        # Two frames per sample: the camera/cursor move even before values change.
        now[0] = 1.0 + offset
        index = int((15.0 + offset) * recording.sample_rate)
        expected = 10.0 + offset
        wait_until(lambda: abs(window.axis_x.min() - expected) < 1e-8)
        assert window.position.value() == index
        assert window.axis_x.min() == pytest.approx(expected)
        assert window.axis_x.max() == pytest.approx(expected + 10.0)
        assert window.sample_cursor.at(0).x() == pytest.approx(15.0 + offset)
        labels = window.axis_x.categoriesLabels()
        for label in labels:
            position = window.axis_x.endValue(label)
            assert position == tick_positions.setdefault(label, position)
        QTest.qWait(20)
        plot = window.chart.plotArea()
        plot_sizes.append((plot.width(), plot.height()))
    assert max(width for width, _ in plot_sizes) - min(width for width, _ in plot_sizes) < 0.5
    assert max(height for _, height in plot_sizes) - min(height for _, height in plot_sizes) < 0.5
    window.toggle_playback()
    paused = window.axis_x.min()
    now[0] += 10.0
    QTest.qWait(40)
    assert window.axis_x.min() == pytest.approx(paused)
    # Starting near the right edge moves only by the elapsed sample time.
    window.position.setValue(int(19 * recording.sample_rate))
    window.axis_x.setRange(10.0, 20.0)
    window.toggle_playback()
    now[0] += 0.5
    wait_until(lambda: window.position.value() == int(19.5 * recording.sample_rate))
    assert window.axis_x.min() == pytest.approx(10.5)
    window.toggle_playback()
    # At maximum zoom the integer value sample may lie left of the continuous
    # viewport. Adopting it must not trigger a second, conflicting camera move.
    window.position.setValue(int(19 * recording.sample_rate))
    width = 1 / recording.sample_rate
    window.axis_x.setRange(19.0, 19.0 + width)
    window.toggle_playback()
    started = now[0]
    for offset in (1.75 * width, 2.25 * width):
        now[0] = started + offset
        expected = 19.0 + offset - width / 2
        wait_until(lambda: abs(window.axis_x.min() - expected) < 1e-8)
        assert window.axis_x.max() == pytest.approx(expected + width)
        assert window.sample_cursor.at(0).x() == pytest.approx(19.0 + offset)
    # The viewport stops at the recording end and retains its width.
    window.position.setValue(recording.count - 11)
    window.axis_x.setRange(recording.duration - 10.1, recording.duration - 0.1)
    now[0] += 1.0
    wait_until(lambda: window.position.value() == recording.count - 1)
    assert window.axis_x.min() == pytest.approx(recording.duration - 10.0)
    assert window.axis_x.max() == pytest.approx(recording.duration)
    assert not window.playback_timer.isActive()
    assert (window.first.value(), window.last.value()) == selection
