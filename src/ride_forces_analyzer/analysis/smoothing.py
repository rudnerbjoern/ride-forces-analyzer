"""Centered force smoothing with truncated, renormalized recording edges.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import hypot, isfinite

from ride_forces_analyzer.domain import Vector3


def combined_force(samples: tuple[Vector3, ...], window: int) -> tuple[float | None, ...]:
    """Return the norm of centered-mean device axes, before directional projection.

    Uses full recording history and the same shortened edges as force smoothing.
    Source-app g interpretation remains provisional. Raises ValueError for an
    invalid window, empty input or non-finite smoothing results. A non-finite
    magnitude is returned as None, without hiding the other force channels.

    Args:
        samples: Sample values in the declared source or analysis representation.
        window: Odd number of source samples in the smoothing window.

    Returns:
        The norm of centered-mean device axes, before directional projection.
    """
    axes = tuple(
        centered_mean(axis, window)
        for axis in (
            tuple(sample.x for sample in samples),
            tuple(sample.y for sample in samples),
            tuple(sample.z for sample in samples),
        )
    )
    values = tuple(hypot(x, y, z) for x, y, z in zip(*axes, strict=True))
    return tuple(value if isfinite(value) else None for value in values)


def centered_mean(values: tuple[float, ...], window: int) -> tuple[float, ...]:
    """Centered odd-window mean; truncate and renormalize at recording edges.

    Args:
        values: Values to format, validate or add in their supplied order.
        window: Odd number of source samples in the smoothing window.

    Returns:
        Smoothed values aligned with the input samples.

    Raises:
        ValueError: Smoothing window must be an odd integer from 1 through 51. Smoothing
            requires samples. Smoothing exceeds finite display range.
    """
    if type(window) is not int or window < 1 or window > 51 or window % 2 == 0:
        raise ValueError("Smoothing window must be an odd integer from 1 through 51")
    if not values:
        raise ValueError("Smoothing requires samples")
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    weights = np.ones(window, dtype=np.float64)
    half = window // 2
    result = (
        np.convolve(array, weights, mode="full")[half : half + len(values)]
        / np.convolve(
            np.ones(len(values)),
            weights,
            mode="full",
        )[half : half + len(values)]
    )
    if not np.isfinite(result).all():
        raise ValueError("Smoothing exceeds finite display range")
    return tuple(float(v) for v in result)
