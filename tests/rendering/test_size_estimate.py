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
    VideoAspect,
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
    "layout,output,prefer_gpu,measured_bytes",
    [
        (ExportLayout.RIBBON, VideoOutput.TRANSPARENT, True, 2_668_950_544),
        (ExportLayout.CORNERS, VideoOutput.TRANSPARENT, True, 2_679_877_705),
        (ExportLayout.HUD, VideoOutput.TRANSPARENT, True, 903_143_298),
        (ExportLayout.ORBIT, VideoOutput.TRANSPARENT, True, 1_099_437_272),
        (ExportLayout.RIBBON, VideoOutput.OPAQUE, True, 7_141_078),
        (ExportLayout.CORNERS, VideoOutput.OPAQUE, True, 7_152_713),
        (ExportLayout.HUD, VideoOutput.OPAQUE, True, 6_386_732),
        (ExportLayout.ORBIT, VideoOutput.OPAQUE, True, 2_909_826),
        (ExportLayout.RIBBON, VideoOutput.OPAQUE, False, 4_229_764),
        (ExportLayout.CORNERS, VideoOutput.OPAQUE, False, 4_215_813),
        (ExportLayout.HUD, VideoOutput.OPAQUE, False, 3_254_464),
        (ExportLayout.ORBIT, VideoOutput.OPAQUE, False, 1_484_353),
        (ExportLayout.RIBBON, VideoOutput.TRANSPARENT, False, 813_316_855),
        (ExportLayout.CORNERS, VideoOutput.TRANSPARENT, False, 821_954_307),
        (ExportLayout.HUD, VideoOutput.TRANSPARENT, False, 610_934_100),
        (ExportLayout.ORBIT, VideoOutput.TRANSPARENT, False, 494_918_229),
    ],
)
def test_portrait_estimates_cover_snapshot_confirmed_report_measurements(
    layout: ExportLayout,
    output: VideoOutput,
    prefer_gpu: bool,
    measured_bytes: int,
) -> None:
    settings = ExportSettings(
        layout=layout,
        aspect=VideoAspect.PORTRAIT,
        extent=ExportExtent.FULL_FRAME,
        output=output,
        fps=StandardFrameRate.FPS_23_976,
        window_seconds=30,
        prefer_gpu=prefer_gpu,
    )
    # Report and embedded snapshots agree: samples 4000..4999 at 50 Hz, 480 frames.
    low, high = estimate_size_bytes(settings, 1000, 50)
    assert low < measured_bytes < high
    # The measured rate must match the anchor within its documented rounding.
    pixels = 480 * (1920 * 1080 if layout is ExportLayout.HUD else 3840 * 2160)
    rounding = 0.005 if output is VideoOutput.TRANSPARENT else 0.0000005
    assert abs((low + high) / 2 - measured_bytes) <= pixels * rounding + 1
    other_backend = estimate_size_bytes(replace(settings, prefer_gpu=not prefer_gpu), 1000, 50)
    assert low > other_backend[0] if prefer_gpu else high < other_backend[1]


@pytest.mark.parametrize("portrait_rate", [None, (0.03, 0.04)])
def test_portrait_prores_override_keeps_codec_and_extent_fallbacks_separate(
    portrait_rate: tuple[float, float] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS[ExportLayout.RIBBON],
        prores_4444_size_rates={ExportExtent.FULL_FRAME: (0.01, 0.02)},
        prores_4444_portrait_size_rates={ExportExtent.CONTENT_AREA: portrait_rate},
        prores_4444_cpu_portrait_size_rates={},
        h264_portrait_size_rates={},
        h264_nvenc_portrait_size_rates={},
        h264_size_rates={ExportExtent.FULL_FRAME: (0.001, 0.002)},
        h264_nvenc_size_rates={},
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    settings = ExportSettings(layout=plugin.key, aspect=VideoAspect.PORTRAIT, fps=50)
    assert estimate_size_bytes(settings, 10, 50) == (829_440, 1_658_880)
    assert estimate_size_bytes(replace(settings, output=VideoOutput.OPAQUE), 10, 50) == (
        82_944,
        165_888,
    )
    content = replace(settings, extent=ExportExtent.CONTENT_AREA)
    if portrait_rate:
        assert estimate_size_bytes(content, 10, 50) == (282_240, 376_320)
    else:
        fallback = estimate_size_bytes(content, 10, 50)
        plugin = replace(plugin, prores_4444_portrait_size_rates={})
        monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
        assert estimate_size_bytes(content, 10, 50) == fallback


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
        h264_nvenc_size_rates={},
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
        h264_nvenc_size_rates={},
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
        prefer_gpu=False,
    )
    low, high = estimate_size_bytes(settings, sample_count, sample_rate)
    assert measured_bytes * (1 - tolerance) <= low < measured_bytes < high
    assert high <= measured_bytes * (1 + tolerance)
    if output is VideoOutput.TRANSPARENT:
        assert estimate_size_bytes(
            replace(settings, prefer_gpu=True),
            sample_count,
            sample_rate,
        ) == (
            low,
            high,
        )


@pytest.mark.parametrize(
    "layout,extent,measured_bytes",
    [
        pytest.param(
            ExportLayout.RIBBON,
            ExportExtent.FULL_FRAME,
            24_441_395,
            id="ribbon-full-frame",
        ),
        pytest.param(
            ExportLayout.CORNERS,
            ExportExtent.FULL_FRAME,
            29_023_934,
            id="corners-full-frame",
        ),
        pytest.param(
            ExportLayout.ORBIT,
            ExportExtent.FULL_FRAME,
            8_061_387,
            id="orbit-full-frame",
        ),
        pytest.param(
            ExportLayout.COLUMN,
            ExportExtent.FULL_FRAME,
            69_336_081,
            id="column-full-frame",
        ),
        pytest.param(
            ExportLayout.RIBBON,
            ExportExtent.CONTENT_AREA,
            22_602_237,
            id="ribbon-content",
        ),
        pytest.param(
            ExportLayout.CORNERS,
            ExportExtent.CONTENT_AREA,
            27_062_402,
            id="corners-content",
        ),
        pytest.param(
            ExportLayout.ORBIT,
            ExportExtent.CONTENT_AREA,
            6_136_463,
            id="orbit-content",
        ),
        pytest.param(
            ExportLayout.COLUMN,
            ExportExtent.CONTENT_AREA,
            43_889_261,
            id="column-content",
        ),
    ],
)
def test_h264_estimate_tracks_measured_kraken_exports(
    layout: ExportLayout,
    extent: ExportExtent,
    measured_bytes: int,
) -> None:
    settings = ExportSettings(
        layout=layout,
        extent=extent,
        output=VideoOutput.OPAQUE,
        fps=StandardFrameRate.FPS_59_94,
        prefer_gpu=False,
    )
    # Synthetic source clock reproduces the measured 9,544 encoded frames.
    low, high = estimate_size_bytes(settings, 9544 * 1001, 60_000)
    assert measured_bytes * 0.45 <= low < measured_bytes < high <= measured_bytes * 1.55


def test_hud_h264_estimate_covers_additional_kraken_reference() -> None:
    settings = ExportSettings(
        layout=ExportLayout.HUD,
        output=VideoOutput.OPAQUE,
        fps=StandardFrameRate.FPS_59_94,
        prefer_gpu=False,
    )
    low, high = estimate_size_bytes(settings, 9544 * 1001, 60_000)
    assert low < 23_256_703 < high


@pytest.mark.parametrize(
    "layout,extent,measured_bytes",
    [
        (ExportLayout.RIBBON, ExportExtent.FULL_FRAME, 75_440_403),
        (ExportLayout.RIBBON, ExportExtent.CONTENT_AREA, 76_217_448),
        (ExportLayout.CORNERS, ExportExtent.FULL_FRAME, 78_626_283),
        (ExportLayout.CORNERS, ExportExtent.CONTENT_AREA, 79_139_381),
        (ExportLayout.HUD, ExportExtent.FULL_FRAME, 73_904_770),
        (ExportLayout.ORBIT, ExportExtent.FULL_FRAME, 15_774_006),
        (ExportLayout.ORBIT, ExportExtent.CONTENT_AREA, 14_267_683),
        (ExportLayout.COLUMN, ExportExtent.FULL_FRAME, 188_122_482),
        (ExportLayout.COLUMN, ExportExtent.CONTENT_AREA, 190_277_305),
    ],
)
def test_nvenc_estimate_tracks_measured_voltron_exports(
    layout: ExportLayout,
    extent: ExportExtent,
    measured_bytes: int,
) -> None:
    settings = ExportSettings(
        layout=layout,
        extent=extent,
        output=VideoOutput.OPAQUE,
        fps=StandardFrameRate.FPS_59_94,
        prefer_gpu=True,
    )
    # Synthetic source clock reproduces the measured 10,353 encoded frames.
    low, high = estimate_size_bytes(settings, 10_353 * 1001, 60_000)
    assert measured_bytes * 0.45 <= low < measured_bytes < high <= measured_bytes * 1.55
    assert estimate_size_bytes(replace(settings, prefer_gpu=False), 10_353 * 1001, 60_000)[1] < (
        measured_bytes
    )


@pytest.mark.parametrize("gpu_rate", [None, (0.03, 0.04)])
def test_nvenc_rates_follow_preference_and_fall_back_within_the_same_extent(
    gpu_rate: tuple[float, float] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS[ExportLayout.RIBBON],
        h264_size_rates={ExportExtent.CONTENT_AREA: (0.01, 0.02)},
        h264_nvenc_size_rates={
            ExportExtent.FULL_FRAME: (0.3, 0.4),
            ExportExtent.CONTENT_AREA: gpu_rate,
        },
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    settings = ExportSettings(
        layout=plugin.key,
        extent=ExportExtent.CONTENT_AREA,
        output=VideoOutput.OPAQUE,
        fps=50,
    )
    assert estimate_size_bytes(replace(settings, prefer_gpu=False), 10, 50) == (110_592, 221_184)
    expected = (331_776, 442_368) if gpu_rate else (110_592, 221_184)
    assert estimate_size_bytes(settings, 10, 50) == expected
    plugin = replace(plugin, h264_nvenc_size_rates={ExportExtent.FULL_FRAME: (0.3, 0.4)})
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    assert estimate_size_bytes(settings, 10, 50) == (110_592, 221_184)


@pytest.mark.parametrize("prefer_gpu", [False, True])
@pytest.mark.parametrize(
    "layout,extent,measured_bytes,tolerance",
    [
        pytest.param(
            ExportLayout.RIBBON,
            ExportExtent.CONTENT_AREA,
            16_010_922_883,
            0.11,
            id="ribbon-content",
        ),
        pytest.param(
            ExportLayout.CORNERS,
            ExportExtent.CONTENT_AREA,
            13_791_547_469,
            0.11,
            id="corners-content",
        ),
        pytest.param(
            ExportLayout.ORBIT,
            ExportExtent.CONTENT_AREA,
            9_153_051_038,
            0.11,
            id="orbit-content",
        ),
        # Rounding 0.30667 to 0.31 puts the upper bound 11.2% above the measurement.
        pytest.param(
            ExportLayout.COLUMN,
            ExportExtent.CONTENT_AREA,
            6_069_102_102,
            0.12,
            id="column-content",
        ),
        pytest.param(
            ExportLayout.RIBBON,
            ExportExtent.FULL_FRAME,
            17_267_346_554,
            0.11,
            id="ribbon-full-frame",
        ),
        pytest.param(
            ExportLayout.CORNERS,
            ExportExtent.FULL_FRAME,
            15_202_085_911,
            0.11,
            id="corners-full-frame",
        ),
        pytest.param(
            ExportLayout.ORBIT,
            ExportExtent.FULL_FRAME,
            10_236_947_676,
            0.11,
            id="orbit-full-frame",
        ),
        # Rounding 0.08884 to 0.09 puts the upper bound 11.4% above the measurement.
        pytest.param(
            ExportLayout.COLUMN,
            ExportExtent.FULL_FRAME,
            7_032_587_238,
            0.12,
            id="column-full-frame",
        ),
    ],
)
def test_estimate_tracks_measured_kraken_layout_exports(
    layout: ExportLayout,
    extent: ExportExtent,
    measured_bytes: int,
    tolerance: float,
    prefer_gpu: bool,
) -> None:
    settings = ExportSettings(
        layout=layout,
        extent=extent,
        fps=StandardFrameRate.FPS_59_94,
        prefer_gpu=prefer_gpu,
    )
    # Synthetic source clock: 1,001 ticks per encoded frame at 60,000 ticks/second.
    # Preserve the measured 9,544 frames without assuming a recording sample count.
    low, high = estimate_size_bytes(settings, 9544 * 1001, 60_000)
    assert measured_bytes * (1 - tolerance) <= low < measured_bytes < high
    assert high <= measured_bytes * (1 + tolerance)


@pytest.mark.parametrize("prefer_gpu", [False, True])
@pytest.mark.parametrize("portrait_rate", [None, (0.003, 0.004)])
def test_portrait_nvenc_missing_rate_prefers_portrait_cpu_before_default_rates(
    prefer_gpu: bool,
    portrait_rate: tuple[float, float] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS[ExportLayout.RIBBON],
        h264_size_rates={ExportExtent.FULL_FRAME: (0.001, 0.002)},
        h264_nvenc_size_rates={ExportExtent.FULL_FRAME: (0.01, 0.02)},
        h264_portrait_size_rates={ExportExtent.FULL_FRAME: portrait_rate},
        h264_nvenc_portrait_size_rates={ExportExtent.FULL_FRAME: None},
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: plugin})
    settings = ExportSettings(
        layout=plugin.key,
        aspect=VideoAspect.PORTRAIT,
        output=VideoOutput.OPAQUE,
        prefer_gpu=prefer_gpu,
        fps=50,
    )
    expected = (
        (248_832, 331_776)
        if portrait_rate
        else ((829_440, 1_658_880) if prefer_gpu else (82_944, 165_888))
    )
    assert estimate_size_bytes(settings, 10, 50) == expected
    landscape = replace(settings, aspect=VideoAspect.LANDSCAPE)
    assert estimate_size_bytes(landscape, 10, 50) == (
        (829_440, 1_658_880) if prefer_gpu else (82_944, 165_888)
    )
