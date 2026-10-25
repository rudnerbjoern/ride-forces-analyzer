"""Export clocks, source-bound orientation, real RGBA geometry and offline encoding."""

# cspell:words ffprobe frombytes getcolor getcolors getrgb getpixel getchannel getextrema hwupload prores qscale rawvideo libx

from dataclasses import replace
from fractions import Fraction
from math import radians, sin, cos
from pathlib import Path
import json
import subprocess
from threading import Event
from typing import Literal, cast
from unittest.mock import patch

from PIL import Image, ImageColor
import pytest

from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.encoding import ExportCancelled, encoder_command, export_video
from ride_forces_analyzer.rendering.frames import COLUMN_X, WIDTH, OverlayRenderer
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    FrameRate,
    VideoAspect,
    ExportLayout,
    ExportSettings,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.rendering.layouts import COLORS, REGIONS, create_renderer, lateral_x
from ride_forces_analyzer.rendering.layouts import orbit
from ride_forces_analyzer.rendering.layouts.common import ACCELERATION_COLOR, BRAKING_COLOR
from ride_forces_analyzer.rendering.layouts.charts import ChartRenderer
from ride_forces_analyzer.rendering.layouts.column import BACKGROUND_COLOR, ColumnRenderer
from ride_forces_analyzer.rendering.layouts.orbit import OrbitRenderer
from ride_forces_analyzer.rendering.layouts.hud import HudRenderer
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


@pytest.mark.parametrize(
    "offset,expected",
    [(0, 1.45), (500, 42.16), (2000, 145.85), (2032, 177.92), (3600, 48.06)],
)
def test_orientation_matches_independent_app_export(
    manta: ExplorerData,
    offset: int,
    expected: float,
) -> None:
    recording = manta.source.recording
    angle = orientation_degrees(recording)[recording.indices.start + offset]
    assert angle is not None
    assert round(angle, 2) == expected


def test_missing_gravity_remains_unavailable(manta: ExplorerData) -> None:
    recording = manta.source.recording
    missing = replace(recording, motion=replace(recording.motion, gravity=None))
    assert set(orientation_degrees(missing)) == {None}
    gravity = recording.motion.gravity
    assert gravity is not None
    zero = replace(gravity[0], x=0.0, y=0.0, z=0.0)
    changed = replace(recording, motion=replace(recording.motion, gravity=(zero, *gravity[1:])))
    assert orientation_degrees(changed)[0] is None


@pytest.mark.parametrize("fps", [24, 25, 30, 50, 60])
def test_export_uses_real_duration_at_independent_video_rate(manta: ExplorerData, fps: int) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(fps=fps), 100, 149)
    assert timeline.frame_count == fps  # 50 complete source sample intervals = one second.
    assert timeline.sample_position(0) == 100
    assert timeline.sample_position(fps - 1) <= 149
    assert timeline.settings.fps == fps
    with pytest.raises(ValueError):
        timeline.sample_position(fps)
    single = prepare_export(manta.analysis, ExportSettings(fps=fps), 100, 100)
    assert single.frame_count >= 1 and single.sample_position(0) == 100


def test_interpolation_preserves_exact_samples_and_gaps(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(fps=60), 100, 149)
    channel = replace(timeline.channels[0], values=tuple(float(i) for i in range(manta.count)))
    assert timeline.value_at(channel, 100.5) == 100.5
    assert timeline.value_at(channel, 149) == 149
    gapped = replace(channel, values=(*channel.values[:101], None, *channel.values[102:]))
    assert timeline.value_at(gapped, 100) == 100
    assert timeline.value_at(gapped, 100.5) is None


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_all_originals_prepare_four_panels_without_source_writes(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    original, modified = path.read_bytes(), path.stat().st_mtime_ns
    data = load_recording(path)
    assert isinstance(data, ExplorerData) and data.analysis is not None
    timeline = prepare_export(data.analysis, ExportSettings(), 0, data.count - 1)
    assert [channel.name for channel in timeline.channels] == [
        "Vertical",
        "Lateral",
        "Longitudinal",
        "Orientation",
    ]
    assert all(len(channel.values) == data.count for channel in timeline.channels)
    for channel in timeline.channels[:3]:
        assert {-1.0, 0.0, 1.0} <= set(channel.ticks)
        assert channel.low <= min(value for value in channel.values if value is not None)
        assert channel.high >= max(value for value in channel.values if value is not None)
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified


@pytest.mark.parametrize("mode", [VideoOutput.TRANSPARENT, VideoOutput.OPAQUE])
def test_4k_canvas_has_single_right_column_and_all_panels(
    manta: ExplorerData,
    mode: VideoOutput,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(
        output=VideoOutput.TRANSPARENT if mode == VideoOutput.TRANSPARENT else VideoOutput.OPAQUE,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3649)
    renderer = OverlayRenderer(timeline)
    frame = renderer.render_frame(0)
    assert frame.size == (3840, 2160) and frame.mode == "RGBA"
    assert frame.getchannel("A").getpixel((0, 0)) == (0 if mode == VideoOutput.TRANSPARENT else 255)
    assert frame.getpixel((COLUMN_X, 0)) == BACKGROUND_COLOR
    for row, channel in enumerate(timeline.channels):
        panel = frame.crop((COLUMN_X, row * 540, WIDTH, (row + 1) * 540))
        colors = panel.getcolors(960 * 540)
        assert colors is not None
        rgb = tuple(bytes.fromhex(channel.color[1:])) + (255,)
        assert any(color == rgb for _, color in colors)
    column = renderer.renderer
    assert isinstance(column, ColumnRenderer)
    assert column.value_y(timeline.channels[0], 1, 0) > column.value_y(
        timeline.channels[0],
        0,
        0,
    )
    assert column.value_y(timeline.channels[2], 1, 2) < column.value_y(
        timeline.channels[2],
        0,
        2,
    )


def test_cancel_and_existing_destination_preserve_files(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(), 0, 1)
    destination = export_directory / "existing.mov"
    destination.write_bytes(b"owner data")
    with pytest.raises(ValueError, match="already exists"):
        export_video(timeline, destination)
    assert destination.read_bytes() == b"owner data"
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ExportCancelled):
        export_video(
            timeline,
            export_directory / "cancel.mov",
            ffmpeg=Path(__file__),
            cancelled=cancelled,
        )
    assert not (export_directory / "cancel.mov").exists()


@pytest.mark.parametrize(
    "layout,mode,aspect,prefer_gpu,language",
    [
        (ExportLayout.COLUMN, VideoOutput.TRANSPARENT, VideoAspect.LANDSCAPE, False, "en"),
        (ExportLayout.RIBBON, VideoOutput.TRANSPARENT, VideoAspect.LANDSCAPE, True, "en"),
        (ExportLayout.CORNERS, VideoOutput.TRANSPARENT, VideoAspect.PORTRAIT, False, "de"),
        (ExportLayout.ORBIT, VideoOutput.TRANSPARENT, VideoAspect.PORTRAIT, True, "en"),
        (ExportLayout.HUD, VideoOutput.OPAQUE, VideoAspect.LANDSCAPE, False, "en"),
        (ExportLayout.COLUMN, VideoOutput.OPAQUE, VideoAspect.LANDSCAPE, True, "de"),
        (ExportLayout.ORBIT, VideoOutput.OPAQUE, VideoAspect.PORTRAIT, False, "en"),
        (ExportLayout.RIBBON, VideoOutput.OPAQUE, VideoAspect.PORTRAIT, True, "en"),
        (ExportLayout.HUD, VideoOutput.TRANSPARENT, VideoAspect.PORTRAIT, False, "fr"),
    ],
)
def test_native_encoder_produces_layout_resolution_with_verified_alpha(
    manta: ExplorerData,
    export_directory: Path,
    mode: VideoOutput,
    prefer_gpu: bool,
    layout: Literal[
        ExportLayout.COLUMN,
        ExportLayout.RIBBON,
        ExportLayout.CORNERS,
        ExportLayout.HUD,
        ExportLayout.ORBIT,
    ],
    aspect: VideoAspect,
    language: Literal["en", "de"],
) -> None:
    # Cover codec × aspect × backend preference once; pure tests own layout/language geometry.
    # Local integration is explicit; clean CI without FFmpeg still runs all pure contracts.
    assert manta.analysis is not None
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Native FFmpeg integration requires installed export tools")
    settings = ExportSettings(
        fps="60000/1001" if not prefer_gpu and aspect is VideoAspect.LANDSCAPE else 25,
        output=VideoOutput.TRANSPARENT if mode == VideoOutput.TRANSPARENT else VideoOutput.OPAQUE,
        prefer_gpu=prefer_gpu,
        layout=layout,
        aspect=aspect,
        language=Language(language),
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3603)
    output = export_directory / ("overlay.mov" if mode == VideoOutput.TRANSPARENT else "opaque.mp4")
    progress: list[tuple[int, int]] = []
    with patch(
        "ride_forces_analyzer.rendering.encoding.subprocess.Popen",
        wraps=subprocess.Popen,
    ) as processes:
        export_video(
            timeline,
            output,
            ffmpeg=ffmpeg,
            progress=lambda a, b: progress.append((a, b)),
            render_jobs=2 if layout == ExportLayout.HUD else 1,
        )
    # One encoder process, plus the optional GPU capability probe.
    assert processes.call_count == 1 + int(prefer_gpu)
    assert progress[-1] == (timeline.frame_count, timeline.frame_count)
    probe = subprocess.run(
        [
            str(ffmpeg.with_name("ffprobe.exe")),
            "-v",
            "error",
            "-show_streams",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert (stream["width"], stream["height"]) == settings.dimensions
    assert stream["r_frame_rate"] == ("60000/1001" if settings.fps == "60000/1001" else "25/1")
    assert int(stream["nb_frames"]) == timeline.frame_count
    assert stream["codec_name"] == ("prores" if mode == VideoOutput.TRANSPARENT else "h264")
    result = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(output),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    image = Image.frombytes("RGBA", settings.dimensions, result.stdout)
    left = image.getpixel((100, 100))
    from ride_forces_analyzer.rendering.layouts import export_region

    x, y, _, height = export_region(settings)
    right = image.getpixel((x + 18, y + height // 2))
    assert isinstance(left, tuple) and isinstance(right, tuple)
    assert left[3] == (0 if mode == VideoOutput.TRANSPARENT else 255)
    expected_alpha = (
        255
        if mode == VideoOutput.OPAQUE or layout == ExportLayout.COLUMN
        else 0
        if layout == ExportLayout.HUD
        else 210
    )
    assert abs(right[3] - expected_alpha) <= 2
    if layout == ExportLayout.HUD and mode == VideoOutput.TRANSPARENT:
        alpha = image.getchannel("A").histogram()
        assert alpha[0] > 0 and alpha[255] > 0
        assert sum(alpha[1:255]) > 0  # Glow/shadow opacity survives real ProRes encoding.


@pytest.mark.parametrize("mode", [VideoOutput.TRANSPARENT, VideoOutput.OPAQUE])
def test_encoder_commands_preserve_codec_specific_options(
    manta: ExplorerData,
    mode: VideoOutput,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(
        output=VideoOutput.TRANSPARENT if mode == VideoOutput.TRANSPARENT else VideoOutput.OPAQUE,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3603)
    cpu = encoder_command(Path("ffmpeg.exe"), timeline, Path("output"))
    gpu = encoder_command(Path("ffmpeg.exe"), timeline, Path("output"), use_gpu=True)
    for command in (cpu, gpu):
        assert "-an" in command and "-n" in command
    assert "-qscale:v" not in gpu  # This CPU option corrupts Vulkan 4444 output.
    if mode == VideoOutput.TRANSPARENT:
        assert "prores_ks" in cpu and "-qscale:v" in cpu
        assert "prores_ks_vulkan" in gpu and "hwupload" in gpu[gpu.index("-vf") + 1]
    else:
        assert "libx264" in cpu and "h264_nvenc" in gpu


def test_cancel_during_real_encoding_leaves_no_output(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    assert manta.analysis is not None
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Native FFmpeg integration requires installed export tools")
    timeline = prepare_export(manta.analysis, ExportSettings(prefer_gpu=False), 3600, 3699)
    cancelled = Event()

    def cancel_after_frame(current: int, total: int) -> None:
        cancelled.set()

    output = export_directory / "cancel.mov"
    with pytest.raises(ExportCancelled):
        export_video(
            timeline,
            output,
            ffmpeg=ffmpeg,
            cancelled=cancelled,
            progress=cancel_after_frame,
            render_jobs=2,
        )
    assert not output.exists()


@pytest.mark.parametrize("layout", [ExportLayout.RIBBON, ExportLayout.CORNERS])
def test_compact_profiles_preserve_alpha_color_and_force_scales(
    manta: ExplorerData,
    layout: Literal[ExportLayout.RIBBON, ExportLayout.CORNERS],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout=layout, invert_vertical=False, invert_lateral=False),
        3600,
        3699,
    )
    renderer = OverlayRenderer(timeline)
    region = renderer.render_region(0)
    frame = renderer.render_frame(0)
    x, y, width, height = REGIONS[layout]
    assert region.size == (width, height)
    assert frame.getchannel("A").getpixel((100, 100)) == 0
    assert region.getchannel("A").histogram()[210] > width * height / 3
    assert region.getchannel("A").getextrema() == (0, 255)
    assert frame.crop((x, y, x + width, y + height)).tobytes() == region.tobytes()
    colors = region.getcolors(width * height)
    assert colors is not None
    assert all(
        any(color == (*bytes.fromhex(rgb[1:]), 255) for _, color in colors) for rgb in COLORS
    )
    compact = create_renderer(timeline)
    assert isinstance(compact, ChartRenderer)
    for row, channel in enumerate(timeline.channels[:3]):
        assert {-1.0, 0.0, 1.0} <= set(channel.ticks)
        assert compact.value_y(channel, 1, row) < compact.value_y(channel, 0, row)
        inverted = replace(channel, inverted=True)
        assert compact.value_y(inverted, 1, row) > compact.value_y(inverted, 0, row)
    opaque = OverlayRenderer(
        replace(timeline, settings=replace(timeline.settings, output=VideoOutput.OPAQUE)),
    ).render_frame(0)
    assert opaque.getchannel("A").getextrema() == (255, 255)


@pytest.mark.parametrize("layout", [layout for layout, _ in PROFILES])
def test_vertical_force_direction_and_manual_override(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    assert manta.analysis is not None
    default = prepare_export(manta.analysis, ExportSettings(layout=layout), 3600, 3699)
    reversed_direction = prepare_export(
        manta.analysis,
        replace(default.settings, invert_vertical=False),
        3600,
        3699,
    )
    assert default.channels[0].values == reversed_direction.channels[0].values
    for timeline in (default, reversed_direction):
        vertical = timeline.channels[0]
        renderer = OverlayRenderer(timeline)
        if layout == ExportLayout.HUD:
            assert isinstance(renderer.renderer, HudRenderer)
            ys = [renderer.renderer.vertical_y(value) for value in (-1, 0, 1)]
        elif layout == ExportLayout.ORBIT:
            assert isinstance(renderer.renderer, OrbitRenderer)
            ys = [sin(radians(renderer.renderer.orbit_angle(value))) for value in (-1, 0, 1)]
            assert renderer.renderer.orbit_angle(0) == 180
        else:
            chart = renderer.renderer
            assert isinstance(chart, (ChartRenderer, ColumnRenderer))
            ys = [chart.value_y(vertical, value, 0) for value in (-1, 0, 1)]
        if timeline.settings.invert_vertical:
            assert ys[0] < ys[1] < ys[2]  # Negative lifts; positive presses into the seat.
        else:
            assert ys[0] > ys[1] > ys[2]


@pytest.mark.parametrize("layout", [layout for layout, _ in PROFILES])
def test_lateral_direction_and_time_follow_layout_axes(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=layout), 3600, 3699)
    channel = timeline.channels[1]
    # Unequal source bounds must still give equal distances from the centered zero.
    channel = replace(channel, low=-2.1, high=1.05)
    left = lateral_x(channel, -1, 0, 200)
    zero = lateral_x(channel, 0, 0, 200)
    right = lateral_x(channel, 1, 0, 200)
    assert left < zero == 100 < right
    assert zero - left == pytest.approx(right - zero)
    assert lateral_x(replace(channel, inverted=False), -1, 0, 200) == left
    if layout in (ExportLayout.ORBIT, ExportLayout.HUD):
        return
    renderer = OverlayRenderer(timeline)
    chart = renderer.renderer
    assert isinstance(chart, (ChartRenderer, ColumnRenderer))
    points = [chart.trace_point(channel, value, 0.5, 1) for value in (-1, 0, 1)]
    earlier = chart.trace_point(channel, 0, 0.25, 1)
    later = chart.trace_point(channel, 0, 0.75, 1)
    if layout == ExportLayout.COLUMN:
        assert points[0][0] == points[1][0] == points[2][0]
        assert points[0][1] < points[1][1] < points[2][1]
        assert earlier[0] < later[0] and earlier[1] == later[1]
    else:
        assert points[0][0] < points[1][0] < points[2][0]
        assert points[0][1] == points[1][1] == points[2][1]
        assert earlier[0] == later[0] and earlier[1] > later[1]
    for row in (0, 2):
        earlier = chart.trace_point(timeline.channels[row], 0, 0.25, row)
        later = chart.trace_point(timeline.channels[row], 0, 0.75, row)
        assert earlier[0] < later[0] and earlier[1] == later[1]


@pytest.mark.parametrize("layout", [layout for layout, _ in PROFILES])
def test_longitudinal_acceleration_up_and_braking_down(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=layout), 3600, 3601)
    channel = timeline.channels[2]
    assert not channel.inverted
    renderer = OverlayRenderer(timeline)
    if layout == ExportLayout.HUD:
        assert isinstance(renderer.renderer, HudRenderer)
        ys = [renderer.renderer.longitudinal_y(value) for value in (-1, 0, 1)]
        assert ys[2] < ys[1] < ys[0]
    elif layout != ExportLayout.ORBIT:
        chart = renderer.renderer
        assert isinstance(chart, (ChartRenderer, ColumnRenderer))
        braking, zero, acceleration = [
            chart.trace_point(channel, value, 0.5, 2) for value in (-1, 0, 1)
        ]
        assert braking[0] == zero[0] == acceleration[0]
        assert acceleration[1] < zero[1] < braking[1]
    else:
        assert isinstance(renderer.renderer, OrbitRenderer)
        assert sin(radians(renderer.renderer.orbit_angle(1, 2))) < 0
        assert sin(radians(renderer.renderer.orbit_angle(-1, 2))) > 0


@pytest.mark.parametrize("layout", [ExportLayout.COLUMN, ExportLayout.RIBBON, ExportLayout.CORNERS])
def test_longitudinal_trace_changes_color_at_zero(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout=layout, window_seconds=2),
        3600,
        3699,
    )
    values = tuple((3649.5 - index) / 49.5 for index in range(manta.count))
    channel = replace(timeline.channels[2], values=values, low=-1.05, high=1.05)
    timeline = replace(timeline, channels=(*timeline.channels[:2], channel, timeline.channels[3]))
    renderer = OverlayRenderer(timeline).renderer
    assert isinstance(renderer, (ChartRenderer, ColumnRenderer))
    image = renderer.render_position(3650)
    for index, color in ((3620, ACCELERATION_COLOR), (3679, BRAKING_COLOR)):
        x, y = renderer.trace_point(channel, values[index], (index - 3600) / 100, 2)
        pixels = {
            image.getpixel((round(x) + dx, round(y) + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        }
        assert ImageColor.getcolor(color, "RGBA") in pixels


@pytest.mark.parametrize("row", [0, 1, 2])
def test_orbit_signed_arcs_paint_physical_directions(manta: ExplorerData, row: int) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.ORBIT), 3600, 3601)
    for value in (-1.0, 1.0):
        channels = tuple(
            replace(channel, values=(value,) * manta.count, low=-1.05, high=1.05)
            if index == row
            else channel
            for index, channel in enumerate(timeline.channels)
        )
        renderer = OrbitRenderer(replace(timeline, channels=channels))
        image = renderer.render_position(3600)
        radius = 192 if row == 1 else 282

        def pixel(v: float) -> tuple[int, int]:
            angle = radians(renderer.orbit_angle(v, row))
            return round(400 + radius * cos(angle)), round(400 + radius * sin(angle))

        color = (
            (ACCELERATION_COLOR if value >= 0 else BRAKING_COLOR)
            if row == 2
            else orbit.CHANNEL_COLORS[row]
        )
        expected = (*bytes.fromhex(color[1:]), 255)
        assert image.getpixel(pixel(value / 2)) == expected
        assert image.getpixel(pixel(-value / 2)) != expected
        if row == 1:
            assert (pixel(value)[0] < 400) == (value < 0)


def test_orbit_orientation_keeps_real_degrees() -> None:
    assert [OrbitRenderer.orientation_angle(v) for v in (0, 90, 180)] == [-90, 0, 90]


def test_orbit_peak_hold_shading_and_markers(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.ORBIT), 3600, 3700)
    values = tuple(0.8 if index == 3600 else 0.0 for index in range(manta.count))
    longitudinal = replace(timeline.channels[2], values=values, low=-1.05, high=1.05)
    renderer = OrbitRenderer(
        replace(timeline, channels=(*timeline.channels[:2], longitudinal, timeline.channels[3])),
    )
    image = renderer.render_position(3605)
    a = radians(-40)
    pixel = (round(400 + 275 * cos(a)), round(400 + 275 * sin(a)))
    expected = Image.alpha_composite(
        Image.new("RGBA", (1, 1), orbit.TRACK_COLOR),
        Image.new("RGBA", (1, 1), (*ImageColor.getrgb(ACCELERATION_COLOR), orbit.PEAK_FILL_ALPHA)),
    ).getpixel((0, 0))
    assert image.getpixel(pixel) == expected
    a = radians(renderer.orbit_angle(0.8, 2))
    marker_pixel = (round(400 + 275 * cos(a)), round(400 + 275 * sin(a)))
    assert image.getpixel(marker_pixel) == ImageColor.getcolor(ACCELERATION_COLOR, "RGBA")
    assert image.getpixel((665, 400)) == ImageColor.getcolor(orbit.CURRENT_MARKER_COLOR, "RGBA")
    assert image.getpixel((62, 400)) == orbit.PANEL_FILL  # No unsupported left orientation arc.


def test_orbit_lateral_stroke_grows_outward_with_shifted_scale(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.ORBIT), 3600, 3601)
    lateral = replace(timeline.channels[1], values=(1.0,) * manta.count, low=-1.05, high=1.05)
    renderer = OrbitRenderer(
        replace(timeline, channels=(timeline.channels[0], lateral, *timeline.channels[2:])),
    )
    image = renderer.render_position(3600)
    expected = (*bytes.fromhex(orbit.CHANNEL_COLORS[1][1:]), 255)

    def pixel(radius: int) -> object:
        a = radians(310)
        return image.getpixel((round(400 + radius * cos(a)), round(400 + radius * sin(a))))

    assert pixel(186) == expected  # Original inner portion remains occupied.
    assert pixel(208) == expected  # Additional twelve pixels extend outward.
    assert pixel(178) != expected
    assert pixel(218) != expected
    # Allow the adjacent raster column when cos(270°) falls just below zero.
    assert any(
        image.getpixel((x, 179)) == ImageColor.getcolor(orbit.SCALE_COLOR, "RGBA")
        for x in (399, 400)
    )


@pytest.mark.parametrize("row,angle,inner", [(0, 140, 264), (2, -40, 264)])
def test_orbit_force_stroke_thickens_inward(
    manta: ExplorerData,
    row: int,
    angle: int,
    inner: int,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.ORBIT), 3600, 3601)
    channels = tuple(
        replace(channel, values=(1.0,) * manta.count, low=-1.05, high=1.05)
        if index == row
        else channel
        for index, channel in enumerate(timeline.channels)
    )
    renderer = OrbitRenderer(replace(timeline, channels=channels))
    image = renderer.render_position(3600)
    color = ACCELERATION_COLOR if row == 2 else orbit.CHANNEL_COLORS[row]
    expected = (*bytes.fromhex(color[1:]), 255)

    # Probe within the filled quadrant, away from ticks and the value marker.
    def pixel(radius: int) -> object:
        a = radians(angle)
        return image.getpixel((round(400 + radius * cos(a)), round(400 + radius * sin(a))))

    assert pixel(288) == expected
    assert pixel(inner) == expected  # Newly occupied inner part of the stroke.
    assert pixel(256) != expected
    assert pixel(294) != expected  # Outer edge remains at radius 290.


def test_orbit_orientation_marker_is_omitted_when_unavailable(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout=ExportLayout.ORBIT), 3600, 3601)
    for value in (45.0, None):
        orientation = replace(timeline.channels[3], values=(value,) * manta.count)
        renderer = OrbitRenderer(
            replace(timeline, channels=(*timeline.channels[:3], orientation)),
        )
        image = renderer.render_position(3600)
        a = radians(renderer.orientation_angle(45))
        pixel = (round(400 + 344 * cos(a)), round(400 + 344 * sin(a)))
        assert (
            image.getpixel(pixel) == ImageColor.getcolor(orbit.ORIENTATION_BUG_COLOR, "RGBA")
        ) == (value is not None)


def test_orbit_preserves_negative_forces_and_absent_orientation(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    start = 4782  # Original app CSV: replay 00:40.32, negative vertical load.
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout=ExportLayout.ORBIT),
        start,
        start + 1,
    )
    assert timeline.value_at(timeline.channels[0], start) == pytest.approx(-3.55, abs=0.01)
    orientation = replace(timeline.channels[3], values=(None,) * manta.count)
    timeline = replace(timeline, channels=(*timeline.channels[:3], orientation))
    image = OverlayRenderer(timeline).render_region(0)
    assert image.size == (800, 800)
    assert all(
        image.getchannel("A").getpixel(point) == 0
        for point in ((0, 0), (799, 0), (0, 799), (799, 799))
    )
    assert image.getchannel("A").getextrema() == (0, 255)
    assert image.getchannel("A").histogram()[210] > 400_000
    colors = image.getcolors(800 * 800)
    assert colors is not None
    assert all(
        any(color == (*bytes.fromhex(rgb[1:]), 255) for _, color in colors) for rgb in COLORS
    )


@pytest.mark.parametrize(
    "fps,label,numerator",
    [("24000/1001", "23.976", 24000), ("60000/1001", "59.94", 60000)],
)
def test_fractional_frame_rate_keeps_exact_duration_and_source_positions(
    manta: ExplorerData,
    fps: FrameRate,
    label: str,
    numerator: int,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(fps=fps)
    timeline = prepare_export(manta.analysis, settings, 100, 149)
    assert settings.fps_label == label
    assert settings.frame_rate == Fraction(numerator, 1001)
    assert timeline.frame_count == numerator // 1000
    assert timeline.sample_position(1) == pytest.approx(100 + 50 * 1001 / numerator)
    # Isolate clock arithmetic over 1001 seconds without rendering or inventing sensor data.
    clock = replace(timeline, first=0, last=50 * 1001 - 1)
    assert clock.frame_count == numerator
    assert clock.sample_position(numerator // 2) == 25025
    command = encoder_command(Path("ffmpeg.exe"), timeline, Path("out.mov"), use_gpu=False)
    assert command[command.index("-framerate") + 1] == fps
    for rounded in (label, float(label)):
        with pytest.raises(ValueError, match="Frame rate"):
            ExportSettings(fps=cast(FrameRate, rounded))
