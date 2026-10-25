"""Inclusive explorer selections and source-time/sample coordinate conversion.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from math import ceil, floor, isclose, isfinite

if TYPE_CHECKING:
    from .model import ExplorerData


@dataclass(frozen=True, slots=True)
class SampleRange:
    """Inclusive local selection; unrelated to source marker slicing semantics.

    Attributes:
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
    """

    first: int
    last: int

    @property
    def count(self) -> int:
        """Return the number of retained samples or items represented by this object.

        Returns:
            The number of retained samples or items represented by this object.
        """
        return self.last - self.first + 1


def default_time_range(data: ExplorerData) -> tuple[float, float]:
    """Return the default chart interval in recording seconds.

    Args:
        data: Bound explorer presentation data.

    Returns:
        The default chart interval in recording seconds.
    """
    first, last = data.ride_bounds
    low, high = data.time_at(first), data.time_at(last)
    if low == high:
        low = max(0.0, min(low, data.duration - 1 / data.sample_rate))
        high = min(data.duration, low + 1 / data.sample_rate)
    return low, high


def time_at(data: ExplorerData, index: int) -> float:
    """Convert a source sample index to recording seconds.

    Args:
        data: Bound explorer presentation data.
        index: Source or collection index selected for this operation.

    Returns:
        Time from the recording origin in seconds.
    """
    data.select(index, index)
    return index / data.sample_rate


def sample_at_time(data: ExplorerData, seconds: float) -> int:
    """Return the nearest sample, clamped to the recording bounds.

    Args:
        data: Bound explorer presentation data.
        seconds: Time in seconds in the clock or coordinate system used by this operation.

    Returns:
        The nearest sample, clamped to the recording bounds.

    Raises:
        ValueError: Sample time must be finite.
    """
    if not isfinite(seconds):
        raise ValueError("Sample time must be finite")
    return round(min(data.count - 1, max(0.0, seconds * data.sample_rate)))


def select(data: ExplorerData, first: int, last: int) -> SampleRange:
    """Create an inclusive selection from source sample indices.

    Args:
        data: Bound explorer presentation data.
        first: First included source sample index.
        last: Last included source sample index.

    Returns:
        Inclusive selection admitted by this object's bounds or placement contract.

    Raises:
        ValueError: Selection requires bounded, ordered sample indices.
    """
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < data.count:
        raise ValueError("Selection requires bounded, ordered sample indices")
    return SampleRange(first, last)


def select_visible(data: ExplorerData, low: float, high: float) -> SampleRange:
    """Select the source samples intersecting a visible time interval.

    Args:
        data: Bound explorer presentation data.
        low: Lower bound in the coordinate system declared by the operation.
        high: Upper bound in the coordinate system declared by the operation.

    Returns:
        Inclusive source-sample interval intersecting the visible time range.

    Raises:
        ValueError: Visible range must be finite and ordered.
    """
    if not isfinite(low) or not isfinite(high) or low > high:
        raise ValueError("Visible range must be finite and ordered")

    def sample_coordinate(seconds: float) -> float:
        coordinate = min(float(data.count - 1), max(0.0, seconds * data.sample_rate))
        nearest = round(coordinate)
        # Avoid selecting an adjacent sample solely due to float round-trip error.
        return (
            float(nearest) if isclose(coordinate, nearest, rel_tol=0, abs_tol=1e-9) else coordinate
        )

    first = floor(sample_coordinate(low))
    last = ceil(sample_coordinate(high))
    return data.select(first, last)
