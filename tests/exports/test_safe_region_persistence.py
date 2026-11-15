"""Safe Region choices survive storage, real batch metadata and archived repeats."""

import json
from pathlib import Path
from contextlib import closing
import sqlite3
import subprocess
from typing import Literal

import pytest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.exports.batches import make_job, run_batches
from ride_forces_analyzer.exports.history import ExportAttempt, prepare_repeat
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    ExportSnapshot,
    VideoAspect,
    VideoOutput,
    prepare_export,
)
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.library_history import ExportRequest, HistoryEntry, LibraryHistory


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
