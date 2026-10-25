"""Provisional airtime-context contracts.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ride_forces_analyzer.analysis.airtime import AirtimeContext


@pytest.mark.parametrize(
    "value,label",
    [
        (2.0, "Heavy Gs"),
        (1.0, "Normal Gs"),
        (0.5, "Light Gs"),
        (0.25001, "Light Gs"),
        (0.25, "Floater Airtime"),
        (0.1, "Floater Airtime"),
        (-0.1, "Floater Airtime"),
        (-0.25, "Floater Airtime"),
        (-0.25001, "Airtime"),
        (-0.5, "Airtime"),
        (-0.6, "Strong Airtime"),
        (None, "Unavailable"),
    ],
)
def test_constant_load_has_no_rapid_onset(value: float | None, label: str) -> None:
    context = AirtimeContext.prepare((value,) * 50, 50)
    assert context.at(49) == label


@pytest.mark.parametrize("rate", [25, 50, 100])
def test_rapid_strong_onset_persists_and_seek_order_is_independent(rate: int) -> None:
    values = (1.0,) * rate + (-0.8,) * rate + (0.0,) * rate
    context = AirtimeContext.prepare(values, rate)
    assert context.at(2 * rate) == "Airtime"
    assert context.at(2 * rate + rate // 2) == "Floater Airtime"
    assert context.at(2 * rate - 1) == "Ejector Airtime"
    assert context.at(rate) == "Airtime"
    assert context.at(rate + rate // 2) == "Ejector Airtime"
    assert context.at(rate - 1) == "Normal Gs"
    assert context.at(rate + 0.5) == "Airtime"


def test_gap_resets_onset_and_ejector_history() -> None:
    context = AirtimeContext.prepare((1.0,) * 20 + (-0.8,) * 20 + (None,) + (-0.8,) * 20, 50)
    assert context.at(39) == "Ejector Airtime"
    assert context.at(40) == "Unavailable"
    assert context.at(41) == "Airtime"
    assert context.at(60) == "Strong Airtime"


def test_slow_entry_is_strong_airtime() -> None:
    values = tuple(1.0 - index / 100 for index in range(181))
    assert AirtimeContext.prepare(values, 50).at(180) == "Strong Airtime"


def test_one_sample_ejector_does_not_replace_generic_airtime() -> None:
    values = (1.0,) * 50 + (-0.2,) * 10 + (-0.6,) + (-0.2,) * 20
    context = AirtimeContext.prepare(values, 50)
    assert "Ejector Airtime" not in context.labels
    assert context.at(50) == "Airtime"


def test_floater_tolerates_small_boundary_fluctuations() -> None:
    values = (0.0,) * 50 + (-0.28, 0.28) * 25
    context = AirtimeContext.prepare(values, 50)
    assert set(context.labels[50:]) == {"Floater Airtime"}


@pytest.mark.parametrize("value,label", ((0.32, "Light Gs"), (-0.32, "Airtime")))
def test_floater_exits_beyond_hysteresis(value: float, label: str) -> None:
    context = AirtimeContext.prepare((0.2,) * 50 + (value,) * 50, 50)
    assert context.at(49) == "Floater Airtime"
    assert context.at(99) == label


def test_return_to_positive_load_immediately_clears_airtime() -> None:
    context = AirtimeContext.prepare((0.0,) * 50 + (2.0,) * 10, 50)
    assert context.at(50) == "Heavy Gs"


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf")])
def test_invalid_rate_is_rejected(rate: float) -> None:
    with pytest.raises(ValueError):
        AirtimeContext.prepare((0.0,), rate)


@pytest.mark.parametrize("position", [-1, 1, float("nan"), float("inf")])
def test_context_lookup_rejects_outside_and_non_finite_positions(position: float) -> None:
    with pytest.raises(ValueError, match="Position outside airtime context"):
        AirtimeContext.prepare((1.0,), 50).at(position)
