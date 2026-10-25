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
# Kraken, Iron Gwazi and Voltron HUD Vulkan ProRes 4444 span 0.734–0.764
# bytes/pixel/frame including MOV overhead. Their frame-weighted mean rounds to
# 0.75; retain a 10% planning margin for content variation.
HUD_GPU_PRORES = (0.675, 0.825)
# Matching Kraken HUD CPU H.264: 17,181,504 bytes, about 0.00085
# bytes/pixel/frame including MP4 overhead. Allow 50% for content/encoder variation.
HUD_H264 = (0.000425, 0.001275)


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
    if settings.layout == "hud" and (settings.output == "opaque" or settings.prefer_gpu):
        low_rate, high_rate = HUD_H264 if settings.output == "opaque" else HUD_GPU_PRORES
        pixels = frames * width * height
        return ceil(pixels * low_rate), ceil(pixels * high_rate)
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
