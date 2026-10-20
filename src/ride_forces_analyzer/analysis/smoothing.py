"""Centered force smoothing with truncated, renormalized recording edges.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""


def centered_mean(values: tuple[float, ...], window: int) -> tuple[float, ...]:
    """Centered odd-window mean; truncate and renormalize at recording edges."""
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
