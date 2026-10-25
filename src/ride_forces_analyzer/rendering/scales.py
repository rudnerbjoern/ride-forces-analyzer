"""Shared fixed force scales fitted to the selected export interval.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import ceil, floor
from collections.abc import Sequence

VERTICAL_SEATED = (-1.5, 5.0)  # Default vertical instrument bounds in g.
VERTICAL_FLYING = (-4.0, 3.0)  # Flying posture uses a larger negative range.
VERTICAL_RANGE_STEP = 0.5  # Expand each vertical bound independently in g.
VERTICAL_MAJOR_INTERVALS = 14  # Maximum major intervals across the vertical range.


def selected_bounds(
    values: Sequence[float | None],
    first: int,
    last: int,
    reference: float,
) -> tuple[float, float]:
    """Read selected force bounds including their neutral reference.

    Args:
        values: Absolute finite forces in g, with None for missing samples.
        first: First included source sample index.
        last: Last included source sample index.
        reference: Neutral force level in g, also used when all selected values are missing.

    Returns:
        Minimum and maximum absolute force including the reference.
    """
    low = high = reference
    for value in values[first : last + 1]:
        if value is not None:
            low, high = min(low, value), max(high, value)
    return low, high


def history_extent(peak: float) -> float:
    """Fit a symmetric history deviation with 5% headroom and a 0.1 g minimum.

    Args:
        peak: Largest finite absolute deviation from the channel reference, in g.

    Returns:
        Positive extent in g, rounded outward to 0.1 g.
    """
    return max(1, ceil(peak * 1.05 / 0.1)) * 0.1


def vertical_scale(
    low: float,
    high: float,
    *,
    flying: bool = False,
) -> tuple[float, float, float]:
    """Fit independent vertical bounds to the selected extrema and riding position.

    Args:
        low: Lowest finite selected vertical force in g, or zero without valid values.
        high: Highest finite selected vertical force in g, or zero without valid values.
        flying: Whether the source explicitly declares Flying; other positions use Seated.

    Returns:
        Negative/positive bounds expanded independently in half-g steps, and a whole-g
        major tick step. Minimum ranges are -1.5 to +5 g for Seated and -4 to +3 g
        for Flying.
    """
    defaults = VERTICAL_FLYING if flying else VERTICAL_SEATED
    low = floor(min(defaults[0], low) / VERTICAL_RANGE_STEP) * VERTICAL_RANGE_STEP
    high = ceil(max(defaults[1], high) / VERTICAL_RANGE_STEP) * VERTICAL_RANGE_STEP
    step = float(max(1, ceil((high - low) / VERTICAL_MAJOR_INTERVALS)))
    return low, high, step


def _symmetric_scale(peak: float, minimum: float) -> tuple[float, float, float]:
    """Fit quarter-g bounds independently of the bounded major tick spacing."""
    extent = max(minimum, ceil(peak / 0.25) * 0.25)
    step = 0.5 * max(1, ceil(extent / 2.5))
    return -extent, extent, step


def lateral_scale(peak: float) -> tuple[float, float, float]:
    """Fit a symmetric lateral scale in quarter-g steps with a 1.25 g minimum.

    Args:
        peak: Largest finite absolute lateral value in the selected interval, in g;
            zero when no valid values are available.

    Returns:
        Negative bound, positive bound and a bounded-density major tick step, in g.
    """
    return _symmetric_scale(peak, 1.25)


def longitudinal_scale(peak: float) -> tuple[float, float, float]:
    """Fit symmetric longitudinal bounds in quarter-g steps with a 1 g minimum.

    Args:
        peak: Largest finite absolute longitudinal value in the selected interval,
            in g; zero when no valid values are available.

    Returns:
        Negative bound, positive bound and a bounded-density major tick step, in g.
        Both bounds expand equally in quarter-g steps, independently of tick spacing.
    """
    return _symmetric_scale(peak, 1.0)
