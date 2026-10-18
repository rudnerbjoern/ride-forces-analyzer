"""Planning estimates follow export length and codec without running an encoder."""

from dataclasses import replace

from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.rendering.size_estimate import estimate_size_bytes


def test_estimate_scales_with_duration_and_frame_rate_and_distinguishes_codec() -> None:
    settings = ExportSettings(layout="orbit")
    low, high = estimate_size_bytes(settings, 500, 50)
    assert 0 < low < high
    longer = estimate_size_bytes(settings, 1000, 50)
    faster = estimate_size_bytes(replace(settings, fps=100), 500, 50)
    assert all(abs(b - 2 * a) <= 1 for a, b in zip((low, high), longer, strict=True))
    assert faster == longer
    opaque = estimate_size_bytes(replace(settings, output="opaque"), 500, 50)
    assert opaque[0] < low and opaque[1] < high


def test_single_sample_is_rounded_to_full_output_frame() -> None:
    settings = ExportSettings(fps=25)
    assert estimate_size_bytes(settings, 1, 50) == estimate_size_bytes(settings, 2, 50)
