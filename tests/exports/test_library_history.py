"""Frozen attempts, honest outcomes and repeats independent of current Library state."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
import json

import pytest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.exports import batches
from ride_forces_analyzer.exports.batches import make_job, run_batches
from ride_forces_analyzer.exports.csv import export_csv
from ride_forces_analyzer.exports.history import ExportAttempt, prepare_repeat
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.rendering.encoding import ExportCancelled
from ride_forces_analyzer.rendering.model import ExportSettings, StandardFrameRate, prepare_export
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError
from ride_forces_analyzer.storage.library_history import ExportRequest, LibraryHistory
from tests.analysis.test_recording_preparation import synthetic_source


@pytest.fixture
def recording(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ExplorerData, LibraryHistory, Path]:
    monkeypatch.setenv("LOCALAPPDATA", str(export_directory.resolve()))
    source = synthetic_source(name="Original ride", location="Original park")
    path = export_directory / "source.forces"
    path.write_bytes(source.recording.source.original_bytes)
    data = load_recording(path)
    assert isinstance(data, ExplorerData) and data.analysis is not None
    history = LibraryHistory()
    history.store.archive(data.source, path.name, data.ride_bounds, CalibrationOverrides())
    return data, history, path


def test_requests_results_recovery_and_source_integrity(
    recording: tuple[ExplorerData, LibraryHistory, Path],
) -> None:
    data, history, path = recording
    assert data.analysis is not None
    source = data.source
    request = ExportRequest.capture(data.analysis, "csv", 2, 5)
    assert ExportRequest.model_validate_json(request.model_dump_json()) == request
    before = history.store.source(source.source_sha256)
    history.store.set_workflow_status(source.source_sha256, "uploaded")
    original_entry = history.store.entries()[0]
    output = path.with_suffix(".csv")
    for status in ("completed", "failed", "cancelled"):
        attempt = ExportAttempt(request, history=history)
        attempt.prepared(request)
        if status == "completed":
            export_csv(data.analysis, output, 2, 5)
            attempt.finish("completed", output=output)
        elif status == "failed":
            attempt.finish("failed", error="Injected exporter failure")
        else:
            attempt.finish("cancelled", error="User cancelled")
    pending = ExportAttempt(request, history=history)
    assert pending.id is not None
    history.interrupt_running()
    entries = LibraryHistory(LibraryStore(history.store.path)).entries(source.source_sha256)
    assert [entry.status for entry in entries] == [
        "interrupted",
        "cancelled",
        "failed",
        "completed",
    ]
    assert entries[0].finished_at is None and entries[0].duration is None
    assert entries[-1].file_size == output.stat().st_size
    assert entries[-1].output_path == str(output.resolve())
    assert all(entry.duration is not None and entry.duration >= 0 for entry in entries[1:])
    assert len({entry.id for entry in entries}) == 4
    assert history.store.source(source.source_sha256) == before
    assert replace(history.store.entries()[0], export_count=0) == original_entry
    assert path.read_bytes() == source.recording.source.original_bytes
    with pytest.raises(LibraryStoreError):
        history.finish(entries[-1].id, "failed", 1.0, error="Cannot rewrite terminal history")


def test_repeat_uses_captured_recipe_without_original_or_old_output(
    recording: tuple[ExplorerData, LibraryHistory, Path],
) -> None:
    data, history, path = recording
    assert data.analysis is not None
    additions = RecordingAdditions(ride_name="Captured ride", row="Front", notes="Captured notes")
    source = ImportSuccess(data.source.recording, data.source.diagnostics, additions=additions)
    analysis = replace(data.analysis, source=source)
    analysis = analysis.with_configuration(
        replace(analysis.configuration, ride_bounds=(2, 5)),
        revision=2,
        calculation_time=datetime.now(UTC),
    )
    settings = ExportSettings(fps=StandardFrameRate.FPS_59_94)
    timeline = prepare_export(analysis, settings, 2, 5)
    attempt = ExportAttempt(
        ExportRequest.capture(analysis, "video", 2, 5, settings),
        history=history,
    )
    attempt.prepared(timeline.snapshot)
    output = path.with_suffix(".mov")
    output.write_bytes(b"published")
    attempt.finish("completed", output=output, gpu=True)
    entry = history.entries(source.source_sha256)[0]
    saved_json = entry.snapshot_json
    history.store.update_metadata(source.source_sha256, {"ride_name": "Later", "row": "Back"})
    history.store.update_markers(source, (3, 6), CalibrationOverrides(gravity_index=0))
    path.unlink()
    output.unlink()
    repeated = prepare_repeat(entry, history)
    assert repeated.data.analysis is not None
    assert repeated.data.source.recording.source.provenance.path is None
    assert repeated.data.source.source_sha256 == source.source_sha256
    assert repeated.data.source.additions == additions
    assert repeated.data.analysis.configuration == analysis.configuration
    assert repeated.request.settings == settings
    assert (repeated.request.first_sample, repeated.request.last_sample) == (2, 5)
    assert repeated.video_snapshot == timeline.snapshot
    assert history.entries(source.source_sha256)[0].snapshot_json == saved_json
    # Unsupported versions and algorithms remain intact and cannot silently use defaults.
    assert saved_json is not None
    for field in ("schema", "algorithm"):
        payload = json.loads(saved_json)
        if field == "schema":
            payload["schema_version"] = 999
        else:
            payload["analysis_configuration"]["smoothing"]["version"] = "999"
        unsupported = replace(entry, snapshot_json=json.dumps(payload))
        with pytest.raises(ValueError):
            prepare_repeat(unsupported, history)
    legacy_payload = json.loads(saved_json)
    legacy_payload["schema_version"] = 1
    legacy_payload.pop("recording_metadata")
    legacy = prepare_repeat(replace(entry, snapshot_json=json.dumps(legacy_payload)), history)
    assert legacy.data.source.additions == RecordingAdditions()


def test_data_repeat_and_history_failures_never_remove_published_files(
    recording: tuple[ExplorerData, LibraryHistory, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, history, path = recording
    assert data.analysis is not None
    request = ExportRequest.capture(data.analysis, "csv", 1, 4)
    attempt = ExportAttempt(request, history=history)
    attempt.prepared(request)
    output = path.with_suffix(".csv")
    export_csv(data.analysis, output, 1, 4)

    def broken(*args: object, **kwargs: object) -> None:
        raise LibraryStoreError("Injected history-write failure")

    monkeypatch.setattr(history, "finish", broken)
    attempt.finish("completed", output=output)
    assert attempt.warning and output.is_file()
    entry = LibraryHistory(history.store).entries(data.source.source_sha256)[0]
    assert entry.status == "running"
    repeated = prepare_repeat(entry, history)
    assert repeated.request == request and repeated.video_snapshot is None
    assert repeated.data.analysis is not None
    assert repeated.data.analysis.configuration == data.analysis.configuration
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")


def test_batch_attempts_include_preparation_failures_and_exclude_skipped_jobs(
    recording: tuple[ExplorerData, LibraryHistory, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, history, path = recording
    assert data.analysis is not None
    preset = SavedPreset(
        schema_version=1,
        name="Captured",
        settings=ExportSettings(),
        smoothing_window=11,
        range_mode="selection",
        analysis_configuration=data.analysis.configuration,
    )
    job = make_job(data.analysis, preset, first=2, last=5)
    cancel = Event()
    count = 0

    def export(timeline: object, target: Path, **kwargs: object) -> Path:
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("Injected encoder failure")
        if count == 3:
            raise ExportCancelled()
        target.write_bytes(b"complete")
        return target

    monkeypatch.setattr(batches, "export_video", export)
    report = run_batches(
        (SavedBatch(schema_version=1, name="Attempts", jobs=(job, job, job, job)),),
        path.parent / "batch-output",
        cancelled=cancel,
    )
    assert [result.status for result in report.results] == [
        "completed",
        "failed",
        "cancelled",
        "skipped",
    ]
    entries = history.entries(data.source.source_sha256)
    assert len(entries) == 3 and {entry.status for entry in entries} == {
        "completed",
        "failed",
        "cancelled",
    }
    assert all(entry.origin == "batch" for entry in entries)
    assert all(entry.request_json and entry.snapshot_json for entry in entries)
    path.unlink()
    report = run_batches(
        (SavedBatch(schema_version=1, name="Missing source", jobs=(job,)),),
        path.parent / "missing-output",
    )
    assert report.results[0].status == "failed"
    failed = history.entries(data.source.source_sha256)[0]
    assert failed.request_json and failed.snapshot_json is None


def test_non_archived_requests_do_not_create_history(
    recording: tuple[ExplorerData, LibraryHistory, Path],
) -> None:
    data, history, _ = recording
    assert data.analysis is not None
    request = ExportRequest.capture(data.analysis, "json", 2, 5).model_copy(
        update={"source_sha256": "f" * 64},
    )
    attempt = ExportAttempt(request, history=history)
    assert attempt.id is None and not attempt.warning
    assert history.entries(data.source.source_sha256) == ()


def test_attempt_duration_excludes_destination_and_queue_waiting(
    recording: tuple[ExplorerData, LibraryHistory, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data, history, _ = recording
    assert data.analysis is not None
    clock = iter((10.0, 12.0, 100.0, 104.0))
    monkeypatch.setattr("ride_forces_analyzer.exports.history.monotonic", lambda: next(clock))
    attempt = ExportAttempt(ExportRequest.capture(data.analysis, "csv", 2, 5), history=history)
    attempt.pause()
    attempt.resume()
    attempt.finish("cancelled", error="Cancelled after waiting")
    assert history.entries(data.source.source_sha256)[0].duration == 6.0
