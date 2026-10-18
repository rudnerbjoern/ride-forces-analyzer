"""Export clocks, source-bound orientation, real RGBA geometry and offline encoding."""

# cspell:words ffprobe frombytes getcolors getpixel getchannel getextrema hwupload prores qscale rawvideo libx

from dataclasses import replace
from math import radians, sin, cos
from pathlib import Path
import json
import subprocess
from threading import Event
from tempfile import TemporaryDirectory
from collections.abc import Iterator
from typing import Literal
from unittest.mock import patch

from PIL import Image
import pytest

from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.encoding import ExportCancelled, encoder_command, export_video
from ride_forces_analyzer.rendering.frames import COLUMN_X, WIDTH, OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.rendering.layouts import COLORS, REGIONS, create_renderer, lateral_x
from ride_forces_analyzer.rendering.layouts.charts import ChartRenderer
from ride_forces_analyzer.rendering.layouts.column import ColumnRenderer
from ride_forces_analyzer.rendering.layouts.orbit import OrbitRenderer
from test_project import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


@pytest.fixture
def export_directory() -> Iterator[Path]:
    with TemporaryDirectory(dir=".tmp") as directory:
        yield Path(directory)


@pytest.fixture
def manta() -> ExplorerData:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


@pytest.mark.parametrize("seconds,expected", [(0, 92), (10, 0), (67, 47), (72, 120), (86, 77)])
def test_orientation_matches_independent_app_snapshots(
    manta: ExplorerData,
    seconds: int,
    expected: int,
) -> None:
    recording = manta.source.recording
    angle = orientation_degrees(recording)[recording.indices.start + seconds * 50]
    assert angle is not None
    assert round(angle) == expected


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
    timeline = prepare_export(manta, ExportSettings(fps=fps), 100, 149)
    assert timeline.frame_count == fps  # 50 complete source sample intervals = one second.
    assert timeline.sample_position(0) == 100
    assert timeline.sample_position(fps - 1) <= 149
    assert timeline.settings.fps == fps
    with pytest.raises(ValueError):
        timeline.sample_position(fps)
    single = prepare_export(manta, ExportSettings(fps=fps), 100, 100)
    assert single.frame_count >= 1 and single.sample_position(0) == 100


def test_interpolation_preserves_exact_samples_and_gaps(manta: ExplorerData) -> None:
    timeline = prepare_export(manta, ExportSettings(fps=60), 100, 149)
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
    assert isinstance(data, ExplorerData)
    timeline = prepare_export(data, ExportSettings(), 0, data.count - 1)
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


@pytest.mark.parametrize("mode", ["transparent", "opaque"])
def test_4k_canvas_has_single_right_column_and_all_panels(manta: ExplorerData, mode: str) -> None:
    settings = ExportSettings(output="transparent" if mode == "transparent" else "opaque")
    timeline = prepare_export(manta, settings, 3600, 3649)
    renderer = OverlayRenderer(timeline)
    frame = renderer.render_frame(0)
    assert frame.size == (3840, 2160) and frame.mode == "RGBA"
    assert frame.getpixel((0, 0)) == (0, 0, 0, 0 if mode == "transparent" else 255)
    assert frame.getpixel((COLUMN_X, 0)) == (0, 0, 0, 255)
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
    timeline = prepare_export(manta, ExportSettings(), 0, 1)
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
        ("column", "transparent", "landscape", False, "en"),
        ("ribbon", "transparent", "landscape", True, "en"),
        ("corners", "transparent", "portrait", False, "de"),
        ("orbit", "transparent", "portrait", True, "en"),
        ("capsule", "opaque", "landscape", False, "en"),
        ("column", "opaque", "landscape", True, "de"),
        ("orbit", "opaque", "portrait", False, "en"),
        ("ribbon", "opaque", "portrait", True, "en"),
    ],
)
def test_native_encoder_produces_4k_video_with_verified_alpha(
    manta: ExplorerData,
    export_directory: Path,
    mode: str,
    prefer_gpu: bool,
    layout: Literal["column", "ribbon", "corners", "capsule", "orbit"],
    aspect: Literal["landscape", "portrait"],
    language: Literal["en", "de"],
) -> None:
    # Cover codec × aspect × backend preference once; pure tests own layout/language geometry.
    # Local integration is explicit; clean CI without FFmpeg still runs all pure contracts.
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Native FFmpeg integration requires installed export tools")
    settings = ExportSettings(
        fps=25,
        output="transparent" if mode == "transparent" else "opaque",
        prefer_gpu=prefer_gpu,
        layout=layout,
        aspect=aspect,
        language=language,
    )
    timeline = prepare_export(manta, settings, 3600, 3603)
    output = export_directory / ("overlay.mov" if mode == "transparent" else "opaque.mp4")
    progress: list[tuple[int, int]] = []
    with patch(
        "ride_forces_analyzer.rendering.encoding.subprocess.Popen",
        wraps=subprocess.Popen,
    ) as processes:
        export_video(timeline, output, ffmpeg=ffmpeg, progress=lambda a, b: progress.append((a, b)))
    # One encoder process, plus the optional GPU capability probe.
    assert processes.call_count == 1 + int(prefer_gpu)
    assert progress[-1] == (2, 2)
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
    assert stream["r_frame_rate"] == "25/1"
    assert int(stream["nb_frames"]) == 2
    assert stream["codec_name"] == ("prores" if mode == "transparent" else "h264")
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
    assert left[3] == (0 if mode == "transparent" else 255)
    expected_alpha = 255 if mode == "opaque" or layout == "column" else 210
    assert abs(right[3] - expected_alpha) <= 2


@pytest.mark.parametrize("mode", ["transparent", "opaque"])
def test_encoder_commands_preserve_codec_specific_options(manta: ExplorerData, mode: str) -> None:
    settings = ExportSettings(output="transparent" if mode == "transparent" else "opaque")
    timeline = prepare_export(manta, settings, 3600, 3603)
    cpu = encoder_command(Path("ffmpeg.exe"), timeline, Path("output"))
    gpu = encoder_command(Path("ffmpeg.exe"), timeline, Path("output"), use_gpu=True)
    for command in (cpu, gpu):
        assert "-an" in command and "-n" in command
    assert "-qscale:v" not in gpu  # This CPU option corrupts Vulkan 4444 output.
    if mode == "transparent":
        assert "prores_ks" in cpu and "-qscale:v" in cpu
        assert "prores_ks_vulkan" in gpu and "hwupload" in gpu[gpu.index("-vf") + 1]
    else:
        assert "libx264" in cpu and "h264_nvenc" in gpu


def test_cancel_during_real_encoding_leaves_no_output(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Native FFmpeg integration requires installed export tools")
    timeline = prepare_export(manta, ExportSettings(prefer_gpu=False), 3600, 3699)
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
        )
    assert not output.exists()


@pytest.mark.parametrize("layout", ["ribbon", "corners", "capsule"])
def test_compact_profiles_preserve_alpha_color_and_force_scales(
    manta: ExplorerData,
    layout: Literal["ribbon", "corners", "capsule"],
) -> None:
    timeline = prepare_export(
        manta,
        ExportSettings(layout=layout, invert_vertical=False, invert_lateral=False),
        3600,
        3699,
    )
    renderer = OverlayRenderer(timeline)
    region = renderer.render_region(0)
    frame = renderer.render_frame(0)
    x, y, width, height = REGIONS[layout]
    assert region.size == (width, height)
    assert frame.getpixel((100, 100)) == (0, 0, 0, 0)
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
        replace(timeline, settings=replace(timeline.settings, output="opaque")),
    ).render_frame(0)
    assert opaque.getchannel("A").getextrema() == (255, 255)


@pytest.mark.parametrize("layout", [layout for layout, _ in PROFILES])
def test_vertical_force_direction_and_manual_override(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    default = prepare_export(manta, ExportSettings(layout=layout), 3600, 3699)
    reversed_direction = prepare_export(
        manta,
        replace(default.settings, invert_vertical=False),
        3600,
        3699,
    )
    assert default.channels[0].values == reversed_direction.channels[0].values
    for timeline in (default, reversed_direction):
        vertical = timeline.channels[0]
        renderer = OverlayRenderer(timeline)
        if layout == "orbit":
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
def test_lateral_direction_is_horizontal_and_time_advances_up(
    manta: ExplorerData,
    layout: ExportLayout,
) -> None:
    timeline = prepare_export(manta, ExportSettings(layout=layout), 3600, 3699)
    channel = timeline.channels[1]
    # Unequal source bounds must still give equal distances from the centered zero.
    channel = replace(channel, low=-2.1, high=1.05)
    left = lateral_x(channel, -1, 0, 200)
    zero = lateral_x(channel, 0, 0, 200)
    right = lateral_x(channel, 1, 0, 200)
    assert left < zero == 100 < right
    assert zero - left == pytest.approx(right - zero)
    assert lateral_x(replace(channel, inverted=False), -1, 0, 200) == left
    if layout == "orbit":
        return
    renderer = OverlayRenderer(timeline)
    chart = renderer.renderer
    assert isinstance(chart, (ChartRenderer, ColumnRenderer))
    points = [chart.trace_point(channel, value, 0.5, 1) for value in (-1, 0, 1)]
    assert points[0][0] < points[1][0] < points[2][0]
    assert points[0][1] == points[1][1] == points[2][1]
    earlier = chart.trace_point(channel, 0, 0.25, 1)
    later = chart.trace_point(channel, 0, 0.75, 1)
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
    timeline = prepare_export(manta, ExportSettings(layout=layout), 3600, 3601)
    channel = timeline.channels[2]
    assert not channel.inverted
    renderer = OverlayRenderer(timeline)
    if layout != "orbit":
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


@pytest.mark.parametrize("row", [0, 1, 2])
def test_orbit_signed_arcs_paint_physical_directions(manta: ExplorerData, row: int) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3601)
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

        expected = (*bytes.fromhex(COLORS[row][1:]), 255)
        assert image.getpixel(pixel(value / 2)) == expected
        assert image.getpixel(pixel(-value / 2)) != expected
        if row == 1:
            assert (pixel(value)[0] < 400) == (value < 0)


def test_orbit_orientation_keeps_real_degrees() -> None:
    assert [OrbitRenderer.orientation_angle(v) for v in (0, 90, 180)] == [-90, 0, 90]


def test_orbit_peak_hold_shading_and_markers(manta: ExplorerData) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3700)
    values = tuple(0.8 if index == 3600 else 0.0 for index in range(manta.count))
    longitudinal = replace(timeline.channels[2], values=values, low=-1.05, high=1.05)
    renderer = OrbitRenderer(
        replace(timeline, channels=(*timeline.channels[:2], longitudinal, timeline.channels[3])),
    )
    image = renderer.render_position(3605)
    a = radians(-40)
    pixel = (round(400 + 275 * cos(a)), round(400 + 275 * sin(a)))
    expected = Image.alpha_composite(
        Image.new("RGBA", (1, 1), (210, 230, 245, 75)),
        Image.new("RGBA", (1, 1), (173, 108, 46, 65)),
    ).getpixel((0, 0))
    assert image.getpixel(pixel) == expected
    a = radians(renderer.orbit_angle(0.8, 2))
    assert image.getpixel((round(400 + 275 * cos(a)), round(400 + 275 * sin(a)))) == (
        173,
        108,
        46,
        255,
    )
    assert image.getpixel((665, 400)) == (255, 255, 255, 255)
    assert image.getpixel((62, 400)) == (7, 15, 25, 210)  # No unsupported left orientation arc.


def test_orbit_lateral_stroke_grows_outward_with_shifted_scale(manta: ExplorerData) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3601)
    lateral = replace(timeline.channels[1], values=(1.0,) * manta.count, low=-1.05, high=1.05)
    renderer = OrbitRenderer(
        replace(timeline, channels=(timeline.channels[0], lateral, *timeline.channels[2:])),
    )
    image = renderer.render_position(3600)
    expected = (*bytes.fromhex(COLORS[1][1:]), 255)

    def pixel(radius: int) -> object:
        a = radians(310)
        return image.getpixel((round(400 + radius * cos(a)), round(400 + radius * sin(a))))

    assert pixel(186) == expected  # Original inner portion remains occupied.
    assert pixel(208) == expected  # Additional twelve pixels extend outward.
    assert pixel(178) != expected
    assert pixel(218) != expected
    # Allow the adjacent raster column when cos(270°) falls just below zero.
    assert any(image.getpixel((x, 179)) == (228, 237, 245, 255) for x in (399, 400))


@pytest.mark.parametrize("row,angle,inner", [(0, 140, 264), (2, -40, 264)])
def test_orbit_force_stroke_thickens_inward(
    manta: ExplorerData,
    row: int,
    angle: int,
    inner: int,
) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3601)
    channels = tuple(
        replace(channel, values=(1.0,) * manta.count, low=-1.05, high=1.05)
        if index == row
        else channel
        for index, channel in enumerate(timeline.channels)
    )
    renderer = OrbitRenderer(replace(timeline, channels=channels))
    image = renderer.render_position(3600)
    expected = (*bytes.fromhex(COLORS[row][1:]), 255)

    # Probe within the filled quadrant, away from ticks and the value marker.
    def pixel(radius: int) -> object:
        a = radians(angle)
        return image.getpixel((round(400 + radius * cos(a)), round(400 + radius * sin(a))))

    assert pixel(288) == expected
    assert pixel(inner) == expected  # Newly occupied inner part of the stroke.
    assert pixel(256) != expected
    assert pixel(294) != expected  # Outer edge remains at radius 290.


def test_orbit_orientation_marker_is_omitted_when_unavailable(manta: ExplorerData) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3601)
    for value in (45.0, None):
        orientation = replace(timeline.channels[3], values=(value,) * manta.count)
        renderer = OrbitRenderer(
            replace(timeline, channels=(*timeline.channels[:3], orientation)),
        )
        image = renderer.render_position(3600)
        a = radians(renderer.orientation_angle(45))
        pixel = (round(400 + 344 * cos(a)), round(400 + 344 * sin(a)))
        assert (image.getpixel(pixel) == (255, 255, 255, 255)) == (value is not None)


def test_orbit_preserves_negative_forces_and_absent_orientation(manta: ExplorerData) -> None:
    start = manta.source.recording.indices.start + 72 * 50
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), start, start + 1)
    assert timeline.value_at(timeline.channels[0], start) == pytest.approx(-3.44, abs=0.01)
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
