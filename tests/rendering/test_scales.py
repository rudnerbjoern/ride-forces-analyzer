"""All layouts share fixed lateral/longitudinal limits from valid selected force values."""

# cspell:words getpixel getcolor

from datetime import UTC, datetime

import pytest
from PIL import ImageColor

from ride_forces_analyzer.analysis.preparation import (
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.rendering.layouts.orbit import OrbitRenderer
from ride_forces_analyzer.rendering.layouts import create_renderer
from ride_forces_analyzer.rendering.layouts.charts import ChartRenderer
from ride_forces_analyzer.rendering.layouts.column import ColumnRenderer, SCALE_COLOR
from ride_forces_analyzer.rendering.layouts.hud import HudRenderer
from ride_forces_analyzer.rendering.model import (
    ExportChannel,
    ExportLayout,
    ExportSettings,
    VideoAspect,
    prepare_export,
)
from tests.analysis.test_recording_preparation import synthetic_source


def test_other_channels_retain_zero_reference_and_integer_ticks() -> None:
    channel = ExportChannel("Other", "g", "#ffffff", "", (0.0,), -2.0, 2.0, False)
    assert channel.reference == 0
    assert channel.ticks == (-2, -1, 0, 1, 2)


@pytest.mark.parametrize(
    "peak,lateral_extent,longitudinal_extent",
    [
        (0.0, 1.25, 1.0),
        (1.0, 1.25, 1.0),
        (1.00001, 1.25, 1.25),
        (1.25, 1.25, 1.25),
        (-1.25, 1.25, 1.25),
        (1.25001, 1.5, 1.5),
        (-1.50001, 1.75, 1.75),
        (1.75, 1.75, 1.75),
        (3.01, 3.25, 3.25),
        (1000.01, 1000.25, 1000.25),
    ],
)
def test_all_layouts_fit_selected_symmetric_peaks_without_padding_or_outside_spikes(
    peak: float,
    lateral_extent: float,
    longitudinal_extent: float,
) -> None:
    values = [9999.0, *([peak] * 31), -9999.0]
    source = synthetic_source(
        accelerationSequence=[{"x": value, "y": value, "z": 1} for value in values],
        gravitySequence=[{"x": 0, "y": 0, "z": 1}] * len(values),
        startIndex=11,
        endIndex=21,
    )
    analysis = prepare_recording_analysis(
        source,
        source_app_configuration(),
        revision=0,
        calculation_time=datetime.now(UTC),
    )
    for layout in ExportLayout:
        timeline = prepare_export(analysis, ExportSettings(layout=layout), 11, 21)
        for channel, extent in zip(
            timeline.channels[1:3],
            (lateral_extent, longitudinal_extent),
            strict=True,
        ):
            assert (channel.low, channel.high) == (-extent, extent)
            assert {channel.low, 0.0, channel.high} <= set(channel.ticks)
            assert len(channel.ticks) <= 13
            assert channel.ticks == tuple(sorted(set(channel.ticks)))
        if layout is ExportLayout.ORBIT:
            renderer = OrbitRenderer(timeline)
            assert renderer.orbit_angle(-lateral_extent, 1) == 180
            assert renderer.orbit_angle(0, 1) == 270
            assert renderer.orbit_angle(lateral_extent, 1) == 360
            assert renderer.orbit_angle(-longitudinal_extent, 2) == 90
            assert renderer.orbit_angle(0, 2) == 0
            assert renderer.orbit_angle(longitudinal_extent, 2) == -90


@pytest.mark.parametrize("posture", ["Seated", "Flying"])
@pytest.mark.parametrize("aspect", list(VideoAspect))
def test_all_layouts_use_one_g_reference_with_absolute_values(
    posture: str,
    aspect: VideoAspect,
) -> None:
    source = synthetic_source(
        ridingPosition=posture,
        accelerationSequence=[{"x": 0, "y": 0, "z": 1}] * 7,
    )
    analysis = prepare_recording_analysis(
        source,
        source_app_configuration(),
        revision=0,
        calculation_time=datetime.now(UTC),
    )
    for layout in ExportLayout:
        timeline = prepare_export(analysis, ExportSettings(layout=layout, aspect=aspect), 2, 6)
        vertical = timeline.channels[0]
        assert [channel.reference for channel in timeline.channels] == [1, 0, 0, 0]
        assert (vertical.low, vertical.high) == pytest.approx((0.9, 1.1))
        assert vertical.ticks == pytest.approx((0.9, 1.0, 1.1))
        assert timeline.value_at(vertical, 2) == 1
        renderer = create_renderer(timeline)
        if isinstance(renderer, (ChartRenderer, ColumnRenderer)):
            left, top, right, bottom = renderer.plot_box(0)
            center = (top + bottom) / 2
            assert renderer.value_y(vertical, 1, 0) == pytest.approx(center)
            color = renderer.zero_grid_color if isinstance(renderer, ChartRenderer) else SCALE_COLOR
            point = (round(left + (right - left) * 0.37), int(center))
            expected_color = ImageColor.getcolor(color, "RGBA") if isinstance(color, str) else color
            assert renderer.base.getpixel(point) == expected_color
        elif isinstance(renderer, OrbitRenderer):
            assert renderer.orbit_angle(1) == 180
            assert {0, 1} <= set(renderer.vertical.ticks)
            assert renderer.peaks[0].at(2, 1) == (1, 1)
            expected = (-4, 3) if posture == "Flying" else (-1.5, 5)
            assert (renderer.vertical.low, renderer.vertical.high) == expected
        else:
            assert isinstance(renderer, HudRenderer)
            assert renderer.references == (1, 0, 0)
            assert renderer.vertical_history_bounds == (1, 1)
            assert renderer.peaks[0].at(2, 1) == (1, 1)
