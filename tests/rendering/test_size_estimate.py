"""Planning estimates follow export length and codec without running an encoder."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

from dataclasses import replace
from typing import Literal

import pytest

from ride_forces_analyzer.rendering.layouts import registry

from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    VideoOutput,
    ExportLayout,
    ExportSettings,
)
from ride_forces_analyzer.rendering.size_estimate import estimate_size_bytes


@pytest.mark.parametrize("layout", [ExportLayout.ORBIT, ExportLayout.HUD])
@pytest.mark.parametrize("prefer_gpu", [False, True])
def test_estimate_scales_with_duration_and_frame_rate_and_distinguishes_codec(
    layout: Literal[ExportLayout.ORBIT, ExportLayout.HUD],
    prefer_gpu: bool,
) -> None:
    settings = ExportSettings(layout=layout, prefer_gpu=prefer_gpu)
    low, high = estimate_size_bytes(settings, 500, 50)
    assert 0 < low < high
    longer = estimate_size_bytes(settings, 1000, 50)
    faster = estimate_size_bytes(replace(settings, fps=100), 500, 50)
    assert all(abs(b - 2 * a) <= 1 for a, b in zip((low, high), longer, strict=True))
    assert faster == longer
    opaque = estimate_size_bytes(replace(settings, output=VideoOutput.OPAQUE), 500, 50)
    assert opaque[0] < low and opaque[1] < high


def test_single_sample_is_rounded_to_full_output_frame() -> None:
    settings = ExportSettings(fps=25)
    assert estimate_size_bytes(settings, 1, 50) == estimate_size_bytes(settings, 2, 50)


@pytest.mark.parametrize(
    "layout,expected",
    [
        (ExportLayout.COLUMN, (8_294_400, 16_588_800)),
        (ExportLayout.RIBBON, (8_294_400, 16_588_800)),
        (ExportLayout.CORNERS, (8_294_400, 16_588_800)),
        (ExportLayout.ORBIT, (8_294_400, 16_588_800)),
        (ExportLayout.HUD, (2_073_600, 4_147_200)),
    ],
)
@pytest.mark.parametrize("prefer_gpu", [False, True])
def test_estimate_uses_registered_layout_rates(
    layout: ExportLayout,
    expected: tuple[int, int],
    prefer_gpu: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS[layout],
        prores_4444_size_rates={ExportExtent.FULL_FRAME: (0.1, 0.2)},
        h264_size_rates={ExportExtent.FULL_FRAME: (0.01, 0.02)},
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    settings = ExportSettings(layout=layout, fps=50, prefer_gpu=prefer_gpu)
    assert estimate_size_bytes(settings, 10, 50) == expected
    assert estimate_size_bytes(replace(settings, output=VideoOutput.OPAQUE), 10, 50) == (
        expected[0] // 10,
        expected[1] // 10,
    )


def test_content_estimates_use_their_own_geometry_and_codec_rates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS[ExportLayout.ORBIT],
        prores_4444_size_rates={
            ExportExtent.FULL_FRAME: (0.1, 0.2),
            ExportExtent.CONTENT_AREA: (0.01, 0.02),
        },
        h264_size_rates={ExportExtent.CONTENT_AREA: (0.001, 0.002)},
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    settings = ExportSettings(layout=plugin.key, extent=ExportExtent.CONTENT_AREA, fps=50)
    assert estimate_size_bytes(settings, 10, 50) == (64_000, 128_000)
    assert estimate_size_bytes(replace(settings, output=VideoOutput.OPAQUE), 10, 50) == (
        6_400,
        12_800,
    )
    plugin = replace(plugin, prores_4444_size_rates={ExportExtent.FULL_FRAME: (0.1, 0.2)})
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    fallback = estimate_size_bytes(settings, 10, 50)
    plugin = replace(plugin, prores_4444_size_rates={})
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    assert estimate_size_bytes(settings, 10, 50) == fallback


@pytest.mark.parametrize(
    "output,sample_count,sample_rate,measured_bytes,tolerance",
    [
        pytest.param(VideoOutput.TRANSPARENT, 8226, 50, 15_301_686_528, 0.15, id="kraken-prores"),
        pytest.param(
            VideoOutput.TRANSPARENT,
            7128,
            50,
            13_004_672_088,
            0.15,
            id="iron-gwazi-prores",
        ),
        pytest.param(VideoOutput.TRANSPARENT, 8636, 50, 16_397_302_310, 0.15, id="voltron-prores"),
        # Synthetic source clock reproduces the measured 9,544 encoded frames.
        pytest.param(
            VideoOutput.TRANSPARENT,
            9544 * 1001,
            60_000,
            15_856_749_604,
            0.15,
            id="kraken-batch-prores",
        ),
        pytest.param(VideoOutput.OPAQUE, 8226, 50, 17_181_504, 0.55, id="kraken-h264"),
    ],
)
def test_hud_estimate_tracks_measured_exports(
    output: VideoOutput,
    sample_count: int,
    sample_rate: int,
    measured_bytes: int,
    tolerance: float,
) -> None:
    settings = ExportSettings(
        layout=ExportLayout.HUD,
        fps=StandardFrameRate.FPS_59_94,
        output=output,
    )
    low, high = estimate_size_bytes(settings, sample_count, sample_rate)
    assert measured_bytes * (1 - tolerance) <= low < measured_bytes < high
    assert high <= measured_bytes * (1 + tolerance)
    assert estimate_size_bytes(replace(settings, prefer_gpu=False), sample_count, sample_rate) == (
        low,
        high,
    )


@pytest.mark.parametrize("prefer_gpu", [False, True])
@pytest.mark.parametrize(
    "layout,measured_bytes,tolerance",
    [
        pytest.param(ExportLayout.RIBBON, 16_010_922_883, 0.11, id="ribbon"),
        pytest.param(ExportLayout.CORNERS, 13_791_547_469, 0.11, id="corners"),
        pytest.param(ExportLayout.ORBIT, 9_153_051_038, 0.11, id="orbit"),
        # Rounding 0.30667 to 0.31 puts the upper bound 11.2% above the measurement.
        pytest.param(ExportLayout.COLUMN, 6_069_102_102, 0.12, id="column"),
    ],
)
def test_content_estimate_tracks_measured_kraken_exports(
    layout: ExportLayout,
    measured_bytes: int,
    tolerance: float,
    prefer_gpu: bool,
) -> None:
    settings = ExportSettings(
        layout=layout,
        extent=ExportExtent.CONTENT_AREA,
        fps=StandardFrameRate.FPS_59_94,
        prefer_gpu=prefer_gpu,
    )
    # Synthetic source clock: 1,001 ticks per encoded frame at 60,000 ticks/second.
    # Preserve the measured 9,544 frames without assuming a recording sample count.
    low, high = estimate_size_bytes(settings, 9544 * 1001, 60_000)
    assert measured_bytes * (1 - tolerance) <= low < measured_bytes < high
    assert high <= measured_bytes * (1 + tolerance)
