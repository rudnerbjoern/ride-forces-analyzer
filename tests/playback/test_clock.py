"""Recording-time playback uses elapsed time, not the number of timer callbacks."""

import pytest

from ride_forces_analyzer.playback import SamplePlayback


@pytest.mark.parametrize("rate", [25.0, 50.0, 59.94, 100.0])
@pytest.mark.parametrize("speed", [0.5, 1.0, 2.0])
def test_elapsed_time_and_ui_feedback_do_not_accumulate_drift(rate: float, speed: float) -> None:
    now = [0.0]
    playback = SamplePlayback(10000, rate, clock=lambda: now[0])
    assert playback.speed == 1.0
    playback.set_speed(speed)
    assert playback.play(10) == 10
    for elapsed in (0.01, 0.125, 0.5, 1.0, 2.0):
        now[0] = elapsed
        expected = 10 + int(elapsed * rate * speed)
        assert playback.current_sample() == expected
        playback.seek(expected)
    now[0] = 5.0  # A delayed callback catches up immediately.
    assert playback.current_sample() == 10 + int(5 * rate * speed)


def test_speed_changes_preserve_continuous_position_pause_seek_and_end() -> None:
    now = [0.0]
    playback = SamplePlayback(200, 50, clock=lambda: now[0])
    playback.set_speed(0.5)
    assert not playback.playing
    playback.play(10)
    now[0] = 0.5
    assert playback.current_position() == 22.5
    playback.set_speed(2.0)
    assert playback.current_position() == 22.5
    now[0] = 0.75
    assert playback.current_position() == 47.5
    playback.seek(80)
    now[0] = 1.0
    assert playback.pause() == 105
    now[0] = 100.0
    playback.set_speed(1.0)
    assert not playback.playing
    assert playback.current_position() == 105.0
    playback.play(105)
    now[0] = 100.5
    assert playback.current_sample() == 130
    now[0] = 200.0
    assert playback.current_sample() == 199
    assert not playback.playing


@pytest.mark.parametrize("speed", [0.0, -1.0, 0.75, float("nan"), float("inf")])
def test_unsupported_speed_preserves_playback(speed: float) -> None:
    playback = SamplePlayback(100, 50)
    with pytest.raises(ValueError, match="speed"):
        playback.set_speed(speed)
    assert playback.speed == 1.0


def test_pause_seek_resume_and_recording_end() -> None:
    now = [0.0]
    playback = SamplePlayback(200, 50, clock=lambda: now[0])
    playback.play(20)
    now[0] = 1.0
    assert playback.pause() == 70
    now[0] = 100.0
    assert playback.current_sample() == 70
    assert not playback.playing
    playback.seek(80)
    playback.play(80)
    now[0] = 101.0
    assert playback.current_sample() == 130
    playback.seek(30)
    now[0] = 101.5
    assert playback.current_sample() == 55
    now[0] = 200.0
    assert playback.current_sample() == 199
    assert not playback.playing
    assert playback.play(199) == 0
    assert playback.playing
    playback.seek(199)
    assert not playback.playing


def test_single_sample_has_no_running_playback() -> None:
    playback = SamplePlayback(1, 50)
    assert playback.play(0) == 0
    assert not playback.playing
    assert playback.current_sample() == playback.pause() == 0


def test_continuous_display_position_keeps_integer_samples_and_pause_contract() -> None:
    now = [0.0]
    playback = SamplePlayback(100, 50, clock=lambda: now[0])
    playback.play(10)
    for elapsed in (0.005, 0.01, 0.025, 0.05):
        now[0] = elapsed
        assert playback.current_position() == pytest.approx(10 + elapsed * 50)
        assert playback.current_sample() == int(10 + elapsed * 50)
        playback.seek(playback.current_sample())
        assert playback.current_position() == pytest.approx(10 + elapsed * 50)
    assert playback.pause() == 12
    now[0] = 10.0
    assert playback.current_position() == 12.0
    playback.play(12)
    now[0] = 10.01
    assert playback.current_position() == pytest.approx(12.5)
    playback.seek(98)
    assert playback.current_position() == 98.0
    now[0] = 20.0
    assert playback.current_position() == 99.0
    assert not playback.playing


@pytest.mark.parametrize(
    "count,rate",
    [(0, 50), (-1, 50), (2, 0), (2, -1), (2, float("nan")), (2, float("inf"))],
)
def test_invalid_recording_is_rejected(count: int, rate: float) -> None:
    with pytest.raises(ValueError):
        SamplePlayback(count, rate)


@pytest.mark.parametrize("index", [-1, 2])
def test_invalid_seek_or_start_is_rejected(index: int) -> None:
    playback = SamplePlayback(2, 50)
    for action in (playback.seek, playback.play):
        with pytest.raises(ValueError):
            action(index)
