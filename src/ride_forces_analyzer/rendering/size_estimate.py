"""Heuristic file-size planning ranges, not measured encoder guarantees.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from fractions import Fraction
from math import ceil

from .layouts import export_region, registry
from .model import VideoOutput, ExportSettings

# Bytes per pixel per frame: uniform canvas plus active overlay. These broad
# planning assumptions are not calibrated against every recording or GPU.
PRORES_BASE = (0.01, 0.08)
PRORES_OVERLAY = (0.08, 0.8)
H264_BASE = (0.0001, 0.001)
H264_OVERLAY = (0.003, 0.06)
CONTAINER_ALLOWANCE = 1.02


def estimate_size_bytes(
    settings: ExportSettings,
    sample_count: int,
    sample_rate: float,
) -> tuple[int, int]:
    """Account for the final sample interval and rounding to an encoded frame.

    Args:
        settings: Validated settings controlling this operation.
        sample_count: Number of source samples, including both interval endpoints.
        sample_rate: Effective source samples per second.

    Returns:
        Lower and upper estimated output sizes in bytes.

    Raises:
        ValueError: A positive sample count and sample rate are required.
    """
    if sample_count < 1 or sample_rate <= 0:
        raise ValueError("A positive sample count and sample rate are required")
    frames = ceil(Fraction(sample_count) * settings.frame_rate / Fraction(str(sample_rate)))
    width, height = settings.dimensions
    plugin = registry.PLUGINS[settings.layout]
    rates = (
        plugin.h264_size_rates
        if settings.output == VideoOutput.OPAQUE
        else plugin.prores_4444_size_rates
        if settings.prefer_gpu
        else None
    )
    if rates is not None:
        low_rate, high_rate = rates
        pixels = frames * width * height
        return ceil(pixels * low_rate), ceil(pixels * high_rate)
    _, _, overlay_width, overlay_height = export_region(settings)
    base, overlay = (
        (PRORES_BASE, PRORES_OVERLAY)
        if settings.output == VideoOutput.TRANSPARENT
        else (H264_BASE, H264_OVERLAY)
    )
    low = ceil(
        frames
        * (width * height * base[0] + overlay_width * overlay_height * overlay[0])
        * CONTAINER_ALLOWANCE,
    )
    high = ceil(
        frames
        * (width * height * base[1] + overlay_width * overlay_height * overlay[1])
        * CONTAINER_ALLOWANCE,
    )
    return low, high
