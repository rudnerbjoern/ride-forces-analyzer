"""Centered mean contracts, including short recordings and filter edges."""

import pytest

from ride_forces_analyzer.analysis.smoothing import centered_mean, combined_force
from ride_forces_analyzer.domain import Vector3


def test_combined_smooths_device_axes_before_taking_the_norm() -> None:
    samples = (Vector3(3, 4, 0), Vector3(-3, -4, 0), Vector3(0, 0, 12))
    assert combined_force(samples, 1) == (5.0, 5.0, 12.0)
    assert combined_force(samples, 3) == (0.0, 4.0, 6.5)
    assert combined_force((Vector3(1e200, 0, 0),), 1) == (1e200,)
    with pytest.raises(ValueError, match="requires samples"):
        combined_force((), 3)
    assert combined_force((Vector3(1.7e308, 1.7e308, 1.7e308),), 1) == (None,)


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
