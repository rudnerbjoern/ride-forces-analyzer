"""Peak hold uses source time and independent signed envelopes, never render order."""

import pytest

from ride_forces_analyzer.rendering.peaks import PeakEnvelope


def test_hold_then_linear_release_at_fractional_source_time() -> None:
    envelope = PeakEnvelope.prepare((3.0,) + (0.0,) * 60, 0, 60, 10)
    assert envelope.at(15, 0) == (3, 0)
    assert envelope.at(20.5, 0)[0] == pytest.approx(2.45)
    assert envelope.at(45, 0)[0] == pytest.approx(0, abs=1e-12)


def test_signed_peaks_and_new_extreme_restart_hold_independently() -> None:
    values = [0.0] * 70
    values[0], values[5], values[10] = 3, -2, 4
    envelope = PeakEnvelope.prepare(tuple(values), 0, 69, 10)
    assert envelope.at(25, 0)[0] == 4
    assert envelope.at(30, 0) == pytest.approx((3.5, -1))


def test_gap_resets_both_directions_and_selection_starts_fresh() -> None:
    values = (5.0, -3.0, None) + (0.0,) * 30
    envelope = PeakEnvelope.prepare(values, 0, 32, 10)
    assert envelope.at(2, None) == (0, 0)
    assert envelope.at(3, 0) == (0, 0)
    selected = PeakEnvelope.prepare(values, 5, 32, 10)
    assert selected.at(5, 0) == (0, 0)


@pytest.mark.parametrize("rate", [10, 50])
def test_peak_release_is_source_rate_and_query_order_independent(rate: int) -> None:
    envelope = PeakEnvelope.prepare((3.0,) + (0.0,) * (rate * 4), 0, rate * 4, rate)
    positions = (2.25 * rate, 0.5 * rate, 3 * rate, 2.25 * rate)
    actual = [envelope.at(position, 0)[0] for position in positions]
    assert actual == pytest.approx([2.25, 3, 1.5, 2.25])


def test_interpolated_current_cannot_exceed_its_own_peak() -> None:
    envelope = PeakEnvelope.prepare((0.0,) * 20, 0, 19, 10)
    assert envelope.at(4.5, 0.7) == (0.7, 0)
    assert envelope.at(4.5, -0.4) == (0, -0.4)


def test_layout_can_configure_hold_duration_and_release_speed() -> None:
    envelope = PeakEnvelope.prepare(
        (3.0, -2.0) + (0.0,) * 20,
        0,
        21,
        10,
        hold_seconds=0.5,
        release_g_per_second=2,
    )
    assert envelope.at(10, 0) == pytest.approx((2, -1.2))


@pytest.mark.parametrize("hold,speed", [(-1.0, 1.0), (1.5, 0.0)])
def test_invalid_peak_configuration_is_rejected(hold: float, speed: float) -> None:
    with pytest.raises(ValueError, match="Peak"):
        PeakEnvelope.prepare((1.0,), 0, 0, 10, hold_seconds=hold, release_g_per_second=speed)
