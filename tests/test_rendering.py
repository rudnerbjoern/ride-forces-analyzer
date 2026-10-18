"""Export clocks, source-bound orientation, real RGBA geometry and offline encoding."""

# cspell:words ffprobe frombytes getcolors getpixel getchannel getextrema hwupload prores qscale rawvideo libx

from dataclasses import replace
from pathlib import Path
import json
import subprocess
from threading import Event
from tempfile import TemporaryDirectory
from collections.abc import Iterator
from typing import Literal

from PIL import Image
import pytest

from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.encoding import ExportCancelled, encoder_command, export_video
from ride_forces_analyzer.rendering.frames import COLUMN_X, WIDTH, OverlayRenderer
from ride_forces_analyzer.rendering.model import ExportSettings, prepare_export
from ride_forces_analyzer.rendering.layouts import COLORS, REGIONS, CompactRenderer
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
    assert renderer.value_y(timeline.channels[0], 1, 0) > renderer.value_y(
        timeline.channels[0],
        0,
        0,
    )
    assert renderer.value_y(timeline.channels[2], 1, 2) < renderer.value_y(
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
    export_video(timeline, output, ffmpeg=ffmpeg, progress=lambda a, b: progress.append((a, b)))
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


def test_decoder_rejects_corrupt_output(export_directory: Path) -> None:
    from ride_forces_analyzer.rendering.encoding import validate_video

    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Native FFmpeg integration requires installed export tools")
    broken = export_directory / "broken.mov"
    broken.write_bytes(b"not a video")
    with pytest.raises(RuntimeError, match="failed decoding"):
        validate_video(ffmpeg, broken, 1, Event())


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
    compact = CompactRenderer(timeline)
    for row, channel in enumerate(timeline.channels[:3]):
        assert {-1.0, 0.0, 1.0} <= set(channel.ticks)
        assert compact.value_y(channel, 1, row) < compact.value_y(channel, 0, row)
        inverted = replace(channel, inverted=True)
        assert compact.value_y(inverted, 1, row) > compact.value_y(inverted, 0, row)
    opaque = OverlayRenderer(
        replace(timeline, settings=replace(timeline.settings, output="opaque")),
    ).render_frame(0)
    assert opaque.getchannel("A").getextrema() == (255, 255)


def test_orbit_preserves_negative_forces_and_absent_orientation(manta: ExplorerData) -> None:
    start = manta.source.recording.indices.start + 72 * 50
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), start, start + 1)
    assert timeline.value_at(timeline.channels[0], start) == pytest.approx(-3.44, abs=0.01)
    orientation = replace(timeline.channels[3], values=(None,) * manta.count)
    timeline = replace(timeline, channels=(*timeline.channels[:3], orientation))
    image = OverlayRenderer(timeline).render_region(0)
    assert image.size == (1120, 792)
    assert image.getchannel("A").getextrema() == (0, 255)
    assert image.getchannel("A").histogram()[210] > 400_000
    colors = image.getcolors(1120 * 792)
    assert colors is not None
    assert all(
        any(color == (*bytes.fromhex(rgb[1:]), 255) for _, color in colors) for rgb in COLORS
    )
