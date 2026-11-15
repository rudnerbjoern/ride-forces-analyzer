"""Optional Safe Region storage, real encoding and archived-repeat acceptance."""

# cspell:words getchannel getextrema rawvideo

import json
import os
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
from typing import Literal

import pytest
from dataclasses import replace
from PIL import Image, ImageChops, ImageFilter, ImageStat

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.exports.batches import make_job, run_batches
from ride_forces_analyzer.exports.history import ExportAttempt, prepare_repeat
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.encoding import export_video
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.preview import (
    PreviewBackground,
    build_previews,
    compose_preview,
)
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    ExportSnapshot,
    ExportValues,
    VideoAspect,
    VideoOutput,
    prepare_export,
    prepare_export_analysis,
)
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.library_history import ExportRequest, HistoryEntry, LibraryHistory


pytestmark = pytest.mark.skipif(
    os.environ.get("RFA_RUN_SAFE_REGION_PERSISTENCE_TESTS") != "1",
    reason="Optional tests; set RFA_RUN_SAFE_REGION_PERSISTENCE_TESTS=1 to run",
)


@pytest.fixture
def saved_exports(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[RecordingAnalysis, ExportStore, LibraryHistory]:
    monkeypatch.setenv("LOCALAPPDATA", str(export_directory.resolve()))
    library = LibraryStore()
    library.archive(manta.source, "Manta.forces", manta.ride_bounds, CalibrationOverrides())
    opened = LibraryArchive(library).reopen(manta.source.source_sha256)
    assert isinstance(opened, ExplorerData) and opened.analysis is not None
    return (
        opened.analysis,
        ExportStore(export_directory / "exports.sqlite3"),
        LibraryHistory(library),
    )


def choice(
    analysis: RecordingAnalysis,
    mode: ExportSafeRegion,
    *,
    name: str | None = None,
    layout: ExportLayout = ExportLayout.HUD,
    output: VideoOutput = VideoOutput.TRANSPARENT,
) -> SavedPreset:
    settings = ExportSettings(
        layout=layout,
        aspect=VideoAspect.PORTRAIT,
        safe_region=mode,
        output=output,
        fps=25,
        prefer_gpu=False,
    )
    return make_preset(name or mode.value, settings, 11, "selection", analysis.configuration)


def captured_attempt(analysis: RecordingAnalysis, history: LibraryHistory) -> HistoryEntry:
    settings = choice(analysis, ExportSafeRegion.OFF).settings
    timeline = prepare_export(analysis, settings, 3600, 3601)
    attempt = ExportAttempt(
        ExportRequest.capture(analysis, "video", 3600, 3601, settings),
        history=history,
    )
    attempt.prepared(timeline.snapshot)
    attempt.finish("failed", error="Persistence-only test; no encoder was started")
    return history.entries(analysis.source.source_sha256)[0]


def test_mixed_saved_modes_survive_preset_edits_real_encoding_and_repeat(
    saved_exports: tuple[RecordingAnalysis, ExportStore, LibraryHistory],
) -> None:
    analysis, store, history = saved_exports
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Requires native export tools")
    modes = list(ExportSafeRegion)
    layouts = (ExportLayout.HUD, ExportLayout.RIBBON, ExportLayout.CORNERS, ExportLayout.ORBIT)
    outputs = (VideoOutput.TRANSPARENT, VideoOutput.OPAQUE) * 2
    presets = tuple(
        choice(analysis, mode, layout=layout, output=output)
        for mode, layout, output in zip(modes, layouts, outputs, strict=True)
    )
    for preset in presets:
        store.save_preset(preset)
    jobs = tuple(make_job(analysis, preset, first=3600, last=3601) for preset in presets)
    store.save_batch(SavedBatch(schema_version=1, name="All modes", jobs=jobs))
    reopened = ExportStore(store.path)
    assert {preset.settings.safe_region for preset in reopened.presets()} == set(modes)
    for preset in presets:
        store.save_preset(choice(analysis, ExportSafeRegion.OFF, name=preset.name), overwrite=True)
        store.delete_preset(preset.name)
    assert reopened.presets() == ()
    saved = ExportStore(store.path).batch("All modes")
    assert saved.jobs == jobs
    assert [job.preset.settings.safe_region for job in saved.jobs] == modes
    with closing(sqlite3.connect(store.path)) as db, db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        payload = json.loads(db.execute("SELECT payload FROM batches").fetchone()[0])
    assert [job["preset"]["settings"]["safe_region"] for job in payload["jobs"]] == [
        "off",
        "portrait_social_a",
        "portrait_social_b",
        "portrait_social_c",
    ]
    report = run_batches((saved,), store.path.parent / "videos", ffmpeg=ffmpeg)
    assert [item.status for item in report.results] == ["completed"] * 4, [
        item.error for item in report.results
    ]
    for job, item in zip(jobs, report.results, strict=True):
        assert item.output is not None and item.export_snapshot is not None
        assert item.job_snapshot == job
        assert item.export_snapshot.settings == job.preset.settings
        probe = subprocess.run(
            [
                str(ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix == ".exe" else "ffprobe")),
                "-v",
                "error",
                "-show_entries",
                "stream=width,height:format_tags=comment",
                "-of",
                "json",
                str(item.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        encoded = json.loads(probe.stdout)
        metadata = json.loads(encoded["format"]["tags"]["comment"])
        snapshot = ExportSnapshot.model_validate_json(json.dumps(metadata["export_snapshot"]))
        assert snapshot == item.export_snapshot
        geometry = resolve_geometry(job.preset.settings)
        assert snapshot.output_dimensions == geometry.output_size
        assert (
            encoded["streams"][0]["width"],
            encoded["streams"][0]["height"],
        ) == geometry.output_size
    entries = LibraryHistory(LibraryStore(history.store.path)).entries(
        analysis.source.source_sha256,
    )
    assert len(entries) == 4 and all(entry.status == "completed" for entry in entries)
    for entry in entries:
        assert entry.snapshot_json is not None
        snapshot = ExportSnapshot.model_validate_json(entry.snapshot_json)
        repeated = prepare_repeat(entry, history)
        assert repeated.request.settings == snapshot.settings
        assert repeated.video_snapshot == snapshot
        assert repeated.data.analysis is not None
        rebuilt = prepare_export(repeated.data.analysis, snapshot.settings, 3600, 3601)
        assert resolve_geometry(rebuilt.settings) == resolve_geometry(snapshot.settings)
    assert [entry.snapshot_json for entry in history.entries(analysis.source.source_sha256)] == [
        entry.snapshot_json for entry in entries
    ]
    assert (
        history.store.source(analysis.source.source_sha256).data
        == analysis.source.recording.source.original_bytes
    )


def test_legacy_records_load_as_off_without_rewriting_stored_payloads(
    saved_exports: tuple[RecordingAnalysis, ExportStore, LibraryHistory],
) -> None:
    analysis, store, history = saved_exports
    preset = choice(analysis, ExportSafeRegion.OFF)
    batch = SavedBatch(
        schema_version=1,
        name="Legacy",
        jobs=(make_job(analysis, preset, first=3600, last=3601),),
    )
    store.save_preset(preset)
    store.save_batch(batch)
    preset_payload = json.loads(preset.model_dump_json())
    preset_payload["settings"].pop("safe_region")
    batch_payload = json.loads(batch.model_dump_json())
    batch_payload["jobs"][0]["preset"]["settings"].pop("safe_region")
    raw_preset, raw_batch = json.dumps(preset_payload), json.dumps(batch_payload)
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute("UPDATE presets SET payload=?", (raw_preset,))
        db.execute("UPDATE batches SET payload=?", (raw_batch,))
    assert ExportStore(store.path).presets()[0].settings.safe_region is ExportSafeRegion.OFF
    assert (
        ExportStore(store.path).batch("Legacy").jobs[0].preset.settings.safe_region
        is ExportSafeRegion.OFF
    )
    entry = captured_attempt(analysis, history)
    assert entry.snapshot_json is not None
    request, snapshot = json.loads(entry.request_json), json.loads(entry.snapshot_json)
    request["settings"].pop("safe_region")
    snapshot["settings"].pop("safe_region")
    raw_request, raw_snapshot = json.dumps(request), json.dumps(snapshot)
    with closing(sqlite3.connect(history.store.path)) as db, db:
        db.execute(
            "UPDATE export_history SET request_json=?, export_snapshot_json=? WHERE id=?",
            (raw_request, raw_snapshot, entry.id),
        )
    legacy = history.entries(analysis.source.source_sha256)[0]
    repeated = prepare_repeat(legacy, history)
    assert repeated.request.settings is not None
    assert repeated.request.settings.safe_region is ExportSafeRegion.OFF
    assert repeated.video_snapshot is not None
    assert repeated.video_snapshot.settings.safe_region is ExportSafeRegion.OFF
    with closing(sqlite3.connect(store.path)) as db, db:
        assert db.execute("SELECT payload FROM presets").fetchone()[0] == raw_preset
        assert db.execute("SELECT payload FROM batches").fetchone()[0] == raw_batch
    current = history.entries(analysis.source.source_sha256)[0]
    assert (current.request_json, current.snapshot_json) == (raw_request, raw_snapshot)


@pytest.mark.parametrize("table", ["presets", "batches"])
def test_unknown_stored_profile_fails_without_fallback_or_rewriting(
    saved_exports: tuple[RecordingAnalysis, ExportStore, LibraryHistory],
    table: Literal["presets", "batches"],
) -> None:
    analysis, store, _ = saved_exports
    preset = choice(analysis, ExportSafeRegion.OFF)
    store.save_preset(preset)
    store.save_batch(
        SavedBatch(
            schema_version=1,
            name="Unknown",
            jobs=(make_job(analysis, preset, first=3600, last=3601),),
        ),
    )
    with closing(sqlite3.connect(store.path)) as db, db:
        payload = json.loads(db.execute(f"SELECT payload FROM {table}").fetchone()[0])
        settings = (
            payload["settings"] if table == "presets" else payload["jobs"][0]["preset"]["settings"]
        )
        settings["safe_region"] = "unknown_profile"
        raw = json.dumps(payload)
        db.execute(f"UPDATE {table} SET payload=?", (raw,))
    reopened = ExportStore(store.path)
    read = reopened.presets if table == "presets" else reopened.batches
    with pytest.raises(ExportStoreError, match="safe_region"):
        read()
    with closing(sqlite3.connect(store.path)) as db, db:
        assert db.execute(f"SELECT payload FROM {table}").fetchone()[0] == raw


@pytest.mark.parametrize("field", ["request_json", "export_snapshot_json"])
def test_repeat_rejects_unknown_profile_and_retains_the_original_record(
    saved_exports: tuple[RecordingAnalysis, ExportStore, LibraryHistory],
    field: Literal["request_json", "export_snapshot_json"],
) -> None:
    analysis, _, history = saved_exports
    entry = captured_attempt(analysis, history)
    raw = entry.request_json if field == "request_json" else entry.snapshot_json
    assert raw is not None
    payload = json.loads(raw)
    payload["settings"]["safe_region"] = "unknown_profile"
    invalid = json.dumps(payload)
    with closing(sqlite3.connect(history.store.path)) as db, db:
        db.execute(f"UPDATE export_history SET {field}=? WHERE id=?", (invalid, entry.id))
    with pytest.raises(ValueError, match="safe_region"):
        prepare_repeat(history.entries(analysis.source.source_sha256)[0], history)
    with closing(sqlite3.connect(history.store.path)) as db, db:
        assert (
            db.execute(f"SELECT {field} FROM export_history WHERE id=?", (entry.id,)).fetchone()[0]
            == invalid
        )


def decoded_frame(ffmpeg: Path, video: Path, size: tuple[int, int]) -> Image.Image:
    result = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(video),
            "-threads",
            "1",
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
    return Image.frombytes("RGBA", size, result.stdout)


def verify_encoded_frame(
    ffmpeg: Path,
    video: Path,
    expected: Image.Image,
    snapshot: ExportSnapshot,
) -> bytes:
    probe = subprocess.run(
        [
            str(ffmpeg.with_name("ffprobe.exe")),
            "-v",
            "error",
            "-show_entries",
            "stream=width,height,nb_frames,pix_fmt:format_tags=comment",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    stream = info["streams"][0]
    assert (stream["width"], stream["height"]) == expected.size
    assert int(stream["nb_frames"]) == snapshot.planned_frame_count
    metadata = json.loads(info["format"]["tags"]["comment"])
    assert ExportSnapshot.model_validate_json(json.dumps(metadata["export_snapshot"])) == snapshot
    actual = decoded_frame(ffmpeg, video, expected.size)
    alpha = actual.getchannel("A")
    if snapshot.settings.output is VideoOutput.TRANSPARENT:
        assert "a" in stream["pix_fmt"]
        alpha_error = ImageChops.difference(alpha, expected.getchannel("A")).getextrema()[1]
        assert isinstance(alpha_error, (int, float)) and alpha_error <= 2
        assert alpha.getextrema() == (0, 255)
    else:
        assert stream["pix_fmt"] == "yuv420p" and alpha.getextrema() == (255, 255)
    expected_preview = compose_preview(expected, (540, 960), PreviewBackground.DARK)
    actual_preview = compose_preview(actual, (540, 960), PreviewBackground.DARK)
    difference = ImageChops.difference(actual_preview, expected_preview)
    # Codec conversion may change colors; the lossless layout and alpha stay fixed.
    assert max(ImageStat.Stat(difference).rms) <= 4, video
    background = Image.new("RGB", expected_preview.size, "black")
    ink = (
        expected_preview
        if snapshot.settings.output is VideoOutput.OPAQUE
        else expected.convert("RGB").resize(expected_preview.size)
    )
    channels = ImageChops.difference(ink, background).split()
    mask = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2]).point(
        [0] * 33 + [255] * 223,
    )
    assert max(ImageStat.Stat(difference, mask.filter(ImageFilter.MaxFilter(3))).rms) <= 12, video
    return actual.tobytes()


@pytest.mark.parametrize("mode", tuple(ExportSafeRegion))
@pytest.mark.parametrize("output", tuple(VideoOutput))
def test_decoded_single_batch_and_archived_repeat_preserve_the_selected_arrangement(
    saved_exports: tuple[RecordingAnalysis, ExportStore, LibraryHistory],
    mode: ExportSafeRegion,
    output: VideoOutput,
) -> None:
    analysis, store, history = saved_exports
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Requires native export tools")
    directory = store.path.parent
    settings = choice(analysis, mode, output=output).settings
    timeline = prepare_export(analysis, settings, 3600, 3603)
    assert timeline.frame_count == 2
    assert (
        timeline.analysis is prepare_export_analysis(analysis, analysis.configuration) is analysis
    )
    assert isinstance(timeline.channels[0].values, ExportValues)
    assert analysis.forces.smoothed.channels is not None
    assert timeline.channels[0].values.samples is analysis.forces.smoothed.channels[0]
    assert timeline.snapshot.settings.safe_region is mode
    expected = OverlayRenderer(timeline).render_frame(0)
    previews = build_previews(analysis, settings, 3600, 3603, 3600, PreviewBackground.DARK)
    preview = next(item.image for item in previews.profiles if item.layout is settings.layout)
    assert (
        preview.tobytes() == compose_preview(expected, (540, 960), PreviewBackground.DARK).tobytes()
    )
    suffix = ".mov" if output is VideoOutput.TRANSPARENT else ".mp4"
    single = export_video(timeline, directory / f"single{suffix}", ffmpeg=ffmpeg, render_jobs=2)
    single_pixels = verify_encoded_frame(ffmpeg, single, expected, timeline.snapshot)

    layout = {
        ExportSafeRegion.OFF: ExportLayout.ORBIT,
        ExportSafeRegion.PORTRAIT_SOCIAL_A: ExportLayout.RIBBON,
        ExportSafeRegion.PORTRAIT_SOCIAL_B: ExportLayout.CORNERS,
        ExportSafeRegion.PORTRAIT_SOCIAL_C: ExportLayout.RIBBON,
    }[mode]
    positions = {
        ExportLayout.ORBIT: LayoutPosition.BOTTOM_LEFT,
        ExportLayout.RIBBON: LayoutPosition.TOP
        if mode is ExportSafeRegion.PORTRAIT_SOCIAL_C
        else LayoutPosition.BOTTOM,
        ExportLayout.CORNERS: LayoutPosition.TOP_RIGHT,
    }
    batch_settings = replace(settings, layout=layout, position=positions[layout])
    preset = make_preset("Captured mode", batch_settings, 11, "selection", analysis.configuration)
    job = make_job(analysis, preset, first=3600, last=3603)
    same_settings = make_preset("Single parity", settings, 11, "selection", analysis.configuration)
    single_job = make_job(analysis, same_settings, first=3600, last=3603)
    store.save_batch(SavedBatch(schema_version=1, name="Output parity", jobs=(single_job, job)))
    report = run_batches(
        (ExportStore(store.path).batch("Output parity"),),
        directory / "batch",
        ffmpeg=ffmpeg,
    )
    same, item = report.results
    assert same.status == "completed", same.error
    assert same.export_snapshot == timeline.snapshot
    assert same.output is not None
    assert verify_encoded_frame(ffmpeg, same.output, expected, timeline.snapshot) == single_pixels
    assert item.status == "completed", item.error
    assert item.output is not None and item.export_snapshot is not None
    batch_timeline = prepare_export(analysis, batch_settings, 3600, 3603)
    assert item.export_snapshot == batch_timeline.snapshot
    batch_expected = OverlayRenderer(batch_timeline).render_frame(0)
    batch_pixels = verify_encoded_frame(
        ffmpeg,
        item.output,
        batch_expected,
        batch_timeline.snapshot,
    )
    previews = build_previews(analysis, batch_settings, 3600, 3603, 3600, PreviewBackground.DARK)
    preview = next(item.image for item in previews.profiles if item.layout is layout)
    assert (
        preview.tobytes()
        == compose_preview(batch_expected, (540, 960), PreviewBackground.DARK).tobytes()
    )
    entry = history.entries(analysis.source.source_sha256)[0]
    repeated = prepare_repeat(entry, history)
    assert repeated.video_snapshot == batch_timeline.snapshot
    assert repeated.request.settings == batch_settings
    assert repeated.data.analysis is not None
    repeat_timeline = prepare_export(repeated.data.analysis, batch_settings, 3600, 3603)
    repeated_video = export_video(
        repeat_timeline,
        directory / f"repeat{suffix}",
        ffmpeg=ffmpeg,
        render_jobs=2,
    )
    assert (
        verify_encoded_frame(ffmpeg, repeated_video, batch_expected, repeat_timeline.snapshot)
        == batch_pixels
    )
