"""Heuristic file-size planning ranges, not measured encoder guarantees.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from fractions import Fraction
from math import ceil

from .layouts import export_region
from .model import ExportSettings

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
    """Account for the final sample interval and rounding to an encoded frame."""
    if sample_count < 1 or sample_rate <= 0:
        raise ValueError("A positive sample count and sample rate are required")
    frames = ceil(Fraction(sample_count) * settings.frame_rate / Fraction(str(sample_rate)))
    width, height = settings.dimensions
    _, _, overlay_width, overlay_height = export_region(settings)
    base, overlay = (
        (PRORES_BASE, PRORES_OVERLAY)
        if settings.output == "transparent"
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
