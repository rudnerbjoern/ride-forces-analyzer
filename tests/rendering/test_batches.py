"""SQLite persistence, immutable queue snapshots and real sequential export contracts."""

# cspell:words Xnotes

from dataclasses import replace
from pathlib import Path
import json
import sqlite3
from threading import Event
from typing import cast

import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.batches import build_jobs, make_job, run_batches
from ride_forces_analyzer.rendering.encoding import ExportCancelled
from ride_forces_analyzer.rendering.model import ExportSettings, ExportTimeline
from ride_forces_analyzer.storage.export_models import BatchJob, SavedBatch, SavedPreset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def preset(name: str = "Ribbon") -> SavedPreset:
    return SavedPreset(name=name, settings=ExportSettings(layout="ribbon", prefer_gpu=False))


def test_portrait_persistence_and_legacy_landscape_default(
    export_directory: Path,
    manta: ExplorerData,
) -> None:
    chosen = SavedPreset(name="Portrait", settings=ExportSettings(aspect="portrait"))
    legacy = json.loads(chosen.model_dump_json())
    del legacy["settings"]["aspect"]
    assert SavedPreset.model_validate_json(json.dumps(legacy)).settings.aspect == "landscape"
    path = export_directory / "aspect.sqlite3"
    store = ExportStore(path)
    store.save_preset(chosen)
    store.create_batch("Mixed formats")
    store.append_jobs("Mixed formats", (short_job(manta, chosen), short_job(manta)))
    reopened = ExportStore(path)
    assert reopened.presets()[0].settings.dimensions == (2160, 3840)
    assert [job.preset.settings.aspect for job in reopened.batch("Mixed formats").jobs] == [
        "portrait",
        "landscape",
    ]


def short_job(data: ExplorerData, chosen: SavedPreset | None = None) -> BatchJob:
    first = data.source.recording.indices.start
    return make_job(data, chosen or preset(), range_mode="selection", first=first, last=first + 1)


def test_sqlite_survives_reopen_with_snapshots_and_transaction_rollback(
    export_directory: Path,
    manta: ExplorerData,
) -> None:
    path = export_directory / "exports.sqlite3"
    store = ExportStore(path)
    chosen = preset()
    store.save_preset(chosen)
    store.create_batch("Weekend")
    store.append_jobs("Weekend", (short_job(manta, chosen),))
    reopened = ExportStore(path)
    assert reopened.presets() == (chosen,)
    saved = reopened.batch("Weekend")
    store.save_preset(
        chosen.model_copy(update={"settings": replace(chosen.settings, fps=30)}),
        overwrite=True,
    )
    assert ExportStore(path).presets()[0].settings.fps == 30
    assert ExportStore(path).batch("Weekend").jobs[0].preset.settings.fps == 50
    with pytest.raises(ExportStoreError):
        store.save_preset(chosen.model_copy(update={"name": "ribbon"}))
    with pytest.raises(ExportStoreError):
        store.append_jobs("Weekend", cast(tuple[BatchJob, ...], ("invalid",)))
    assert reopened.batch("Weekend") == saved
    store.delete_preset("Ribbon")
    assert reopened.presets() == () and reopened.batch("Weekend") == saved
    store.remove_jobs("Weekend", (0,))
    assert reopened.batch("Weekend").jobs == ()
    assert path.read_bytes().startswith(b"SQLite format 3")


def test_future_database_version_is_preserved(export_directory: Path) -> None:
    path = export_directory / "future.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version=99")
    connection.close()
    original = path.read_bytes()
    with pytest.raises(ExportStoreError, match="unsupported"):
        ExportStore(path).presets()
    assert path.read_bytes() == original


@pytest.mark.parametrize("kind", ["foreign", "corrupt"])
def test_unrecognized_database_is_not_replaced(export_directory: Path, kind: str) -> None:
    path = export_directory / "existing.sqlite3"
    if kind == "foreign":
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE sqliteXnotes (text TEXT)")
        connection.close()
    else:
        path.write_bytes(b"not a SQLite database")
    original = path.read_bytes()
    with pytest.raises(ExportStoreError):
        ExportStore(path).presets()
    assert path.read_bytes() == original


def test_multiple_rides_cross_multiple_presets_and_custom_bounds(manta: ExplorerData) -> None:
    paths = tuple(
        next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces")) for ride in ("Manta", "Kraken")
    )
    chosen = (
        preset(),
        preset("Orbit").model_copy(update={"settings": ExportSettings(layout="orbit")}),
    )
    jobs = build_jobs(paths, chosen, "entire")
    assert len(jobs) == 4
    assert [(job.ride, job.preset.name) for job in jobs] == [
        ("Manta", "Ribbon"),
        ("Manta", "Orbit"),
        ("Kraken", "Ribbon"),
        ("Kraken", "Orbit"),
    ]
    assert all(job.first_sample == 0 and job.last_sample > 9000 for job in jobs)
    assert short_job(manta).last_sample - short_job(manta).first_sample == 1
    with pytest.raises(ValueError, match="explicit bounds"):
        make_job(manta, preset().model_copy(update={"range_mode": "selection"}))
    with pytest.raises(ValueError):
        SavedPreset(name="", settings=ExportSettings())
    with pytest.raises(ValueError, match="odd"):
        SavedPreset(name="bad", settings=ExportSettings(), smoothing_window=2)


def test_batch_continues_after_changed_recording_and_preserves_outputs(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.rendering import batches

    calls: list[Path] = []

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        calls.append(target)
        target.write_bytes(b"completed")
        assert timeline.smoothing_window == 3
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    job = short_job(manta, preset().model_copy(update={"smoothing_window": 3}))
    changed = job.model_copy(update={"source_sha256": "0" * 64})
    missing = job.model_copy(
        update={"recording_path": (export_directory / "missing.forces").resolve()},
    )
    saved = (SavedBatch(name="A", jobs=(job, changed, missing)), SavedBatch(name="B", jobs=(job,)))
    result = run_batches(saved, export_directory)
    assert [item.status for item in result.results] == [
        "completed",
        "failed",
        "failed",
        "completed",
    ]
    assert "changed" in (result.results[1].error or "")
    assert len(calls) == 2 and calls[0] != calls[1]
    assert all(path.read_bytes() == b"completed" for path in calls)
    assert len(json.loads((result.directory / "run-report.json").read_text())["results"]) == 4
    second = run_batches(saved, export_directory)
    assert second.directory != result.directory
    assert calls[0].read_bytes() == b"completed"


def test_cancel_stops_remaining_jobs_and_keeps_completed_files(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.rendering import batches

    calls = 0
    cancel = Event()

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            cancel.set()
            raise ExportCancelled()
        target.write_bytes(b"complete")
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    job = short_job(manta)
    result = run_batches(
        (SavedBatch(name="Cancel", jobs=(job, job, job)),),
        export_directory,
        cancelled=cancel,
    )
    assert [item.status for item in result.results] == ["completed", "cancelled", "skipped"]
    assert calls == 2
    output = result.results[0].output
    assert output is not None and output.read_bytes() == b"complete"
    with pytest.raises(ValueError, match="no export jobs"):
        run_batches((SavedBatch(name="Empty"),), export_directory)


def test_saved_batch_reopens_and_exports_different_rides_and_formats(
    export_directory: Path,
) -> None:
    ffmpeg = Path(".tmp/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg.is_file():
        pytest.skip("Requires native export tools")
    store = ExportStore(export_directory / "real.sqlite3")
    sources: list[tuple[Path, bytes]] = []
    jobs: list[BatchJob] = []
    presets = (
        SavedPreset(name="Ribbon", settings=ExportSettings(layout="ribbon", prefer_gpu=False)),
        SavedPreset(
            name="Orbit opaque",
            settings=ExportSettings(layout="orbit", output="opaque", prefer_gpu=False),
        ),
    )
    for ride, chosen in zip(("Manta", "Kraken"), presets, strict=True):
        path = next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces"))
        sources.append((path, path.read_bytes()))
        data = load_recording(path)
        assert isinstance(data, ExplorerData)
        jobs.append(short_job(data, chosen))
    store.save_batch(SavedBatch(name="Real", jobs=tuple(jobs)))
    result = run_batches(ExportStore(store.path).batches(), export_directory, ffmpeg=ffmpeg)
    assert len(result.results) == 2
    assert all(
        item.status == "completed" and item.output is not None and item.output.stat().st_size > 0
        for item in result.results
    )
    assert [item.output.suffix for item in result.results if item.output] == [
        ".mov",
        ".mp4",
    ]
    assert all(path.read_bytes() == original for path, original in sources)
