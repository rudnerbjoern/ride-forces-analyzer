"""Centered mean contracts, including short recordings and filter edges."""

import pytest

from ride_forces_analyzer.analysis.smoothing import centered_mean


def test_centered_mean_constant_impulse_and_explicit_edge_policy() -> None:
    assert centered_mean((2.0,) * 21, 11) == (2.0,) * 21
    impulse = (0.0,) * 10 + (11.0,) + (0.0,) * 10
    assert centered_mean(impulse, 11) == (0.0,) * 5 + (1.0,) * 11 + (0.0,) * 5
    ramp = centered_mean(tuple(float(i) for i in range(21)), 11)
    assert ramp[0] == 2.5 and ramp[10] == 10 and ramp[-1] == 17.5
    assert centered_mean((1.0, 3.0), 11) == (2.0, 2.0)
    assert centered_mean((7.0,), 11) == (7.0,)
    with pytest.raises(ValueError):
        centered_mean((), 11)


@pytest.mark.parametrize("window", range(1, 52, 2))
def test_configurable_mean_matches_direct_available_neighbor_average(window: int) -> None:
    values = (0.0, 1.0, 4.0, 9.0, 16.0, 0.0, -3.0)
    half = window // 2
    expected = tuple(
        sum(neighbors) / len(neighbors)
        for i in range(len(values))
        for neighbors in (values[max(0, i - half) : i + half + 1],)
    )
    assert centered_mean(values, window) == expected


@pytest.mark.parametrize("window", [0, -1, 2, 52, True])
def test_configurable_mean_rejects_invalid_windows(window: int) -> None:
    with pytest.raises(ValueError, match="odd integer"):
        centered_mean((1.0,), window)
