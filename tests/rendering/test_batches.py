"""SQLite persistence, immutable queue snapshots and real sequential export contracts."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
)

# cspell:words Xnotes

from collections.abc import Callable
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import json
import sqlite3
from threading import Event
from typing import cast

import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.batches import build_jobs, make_job, run_batches
from ride_forces_analyzer.rendering.encoding import ExportCancelled
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    FrameRate,
    ExportLayout,
    VideoAspect,
    ExportSettings,
    ExportTimeline,
)
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.storage.export_models import BatchJob, SavedBatch, SavedPreset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def preset(name: str = "Ribbon", window: int = 11) -> SavedPreset:
    configuration = source_app_configuration()
    configuration = replace(
        configuration,
        smoothing=replace(configuration.smoothing, parameters=(("window_samples", window),)),
    )
    return SavedPreset(
        name=name,
        settings=ExportSettings(layout=ExportLayout.RIBBON, prefer_gpu=False),
        smoothing_window=window,
        analysis_configuration=configuration,
        schema_version=1,
        range_mode="markers",
    )


def test_portrait_and_landscape_persistence(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.rendering import batches

    chosen = SavedPreset(
        name="Portrait",
        settings=ExportSettings(aspect=VideoAspect.PORTRAIT, position=LayoutPosition.LEFT),
        analysis_configuration=source_app_configuration(),
        schema_version=1,
        smoothing_window=11,
        range_mode="markers",
    )
    path = export_directory / "aspect.sqlite3"
    store = ExportStore(path)
    store.save_preset(chosen)
    store.create_batch("Mixed formats")
    store.append_jobs("Mixed formats", (short_job(manta, chosen), short_job(manta)))
    assert preset().settings.position is LayoutPosition.BOTTOM
    store.save_preset(
        chosen.model_copy(
            update={"settings": replace(chosen.settings, position=LayoutPosition.RIGHT)},
        ),
        overwrite=True,
    )
    reopened = ExportStore(path)
    assert reopened.presets()[0].settings.dimensions == (2160, 3840)
    assert reopened.presets()[0].settings.position is LayoutPosition.RIGHT
    jobs = reopened.batch("Mixed formats").jobs
    assert [job.preset.settings.position for job in jobs] == [
        LayoutPosition.LEFT,
        LayoutPosition.BOTTOM,
    ]
    assert [job.preset.settings.aspect for job in reopened.batch("Mixed formats").jobs] == [
        VideoAspect.PORTRAIT,
        VideoAspect.LANDSCAPE,
    ]
    rendered: list[ExportSettings] = []
    renderer_counts: list[object] = []

    def export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        rendered.append(timeline.settings)
        renderer_counts.append(kwargs["render_jobs"])
        target.write_bytes(b"completed")
        return target

    monkeypatch.setattr(batches, "export_video", export)
    result = run_batches(reopened.batches(), export_directory, render_jobs=2)
    assert [item.status for item in result.results] == ["completed", "completed"]
    assert rendered == [job.preset.settings for job in jobs]
    assert renderer_counts == [2, 2]


def test_hud_preset_round_trip_and_removed_layout_rejection() -> None:
    from pydantic import ValidationError

    chosen = preset().model_copy(update={"settings": ExportSettings(layout=ExportLayout.HUD)})
    saved = SavedPreset.model_validate_json(chosen.model_dump_json())
    assert saved.settings.layout == ExportLayout.HUD
    assert saved.settings.dimensions == (1920, 1080)
    assert replace(saved.settings, aspect=VideoAspect.PORTRAIT).dimensions == (1080, 1920)
    assert saved.settings.position is LayoutPosition.FULL_SCREEN
    payload = json.loads(saved.model_dump_json())
    payload["settings"]["layout"] = "capsule"
    with pytest.raises(ValidationError):
        SavedPreset.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("aspect", list(VideoAspect))
def test_video_aspect_preserves_saved_codes_and_requires_enum_members(
    aspect: VideoAspect,
) -> None:
    from pydantic import ValidationError

    assert ExportSettings().aspect is VideoAspect.LANDSCAPE
    assert VideoAspect(aspect.value) is aspect
    chosen = preset().model_copy(update={"settings": ExportSettings(aspect=aspect)})
    payload = json.loads(chosen.model_dump_json())
    assert payload["settings"]["aspect"] == aspect.value
    assert SavedPreset.model_validate_json(json.dumps(payload)).settings.aspect is aspect
    with pytest.raises(ValueError, match="Unknown export aspect ratio"):
        ExportSettings(aspect=cast(VideoAspect, aspect.value))
    payload["settings"]["aspect"] = "square"
    with pytest.raises(ValidationError):
        SavedPreset.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("layout", list(ExportLayout))
def test_layout_members_preserve_saved_text_keys(layout: ExportLayout) -> None:
    assert ExportLayout(layout.value) is layout
    chosen = preset().model_copy(update={"settings": ExportSettings(layout=layout)})
    payload = json.loads(chosen.model_dump_json())
    assert payload["settings"]["layout"] == layout.value
    assert SavedPreset.model_validate_json(json.dumps(payload)).settings.layout is layout


@pytest.mark.parametrize("output", list(VideoOutput))
def test_video_output_preserves_saved_codes_and_requires_enum_members(
    output: VideoOutput,
) -> None:
    assert ExportSettings().output is VideoOutput.TRANSPARENT
    assert VideoOutput(output.value) is output
    chosen = preset().model_copy(update={"settings": ExportSettings(output=output)})
    payload = json.loads(chosen.model_dump_json())
    assert payload["settings"]["output"] == output.value
    assert SavedPreset.model_validate_json(json.dumps(payload)).settings.output is output
    with pytest.raises(ValueError, match="Unknown export output mode"):
        ExportSettings(output=cast(VideoOutput, output.value))
    with pytest.raises(ValueError):
        VideoOutput("other")


@pytest.mark.parametrize("rate", list(StandardFrameRate))
def test_standard_rates_keep_existing_json_values_and_restore_enum_members(
    rate: StandardFrameRate,
) -> None:
    expected: int | str = rate.value if "/" in rate.value else int(rate.value)
    base = preset()
    settings = replace(base.settings, fps=rate)
    chosen = base.model_copy(update={"settings": settings})
    payload = json.loads(chosen.model_dump_json())
    assert payload["settings"]["fps"] == expected
    assert type(payload["settings"]["fps"]) is type(expected)
    restored = SavedPreset.model_validate_json(json.dumps(payload))
    assert restored.settings.fps is rate
    assert restored.settings.frame_rate == rate.fraction
    assert restored.settings.fps_label == rate.label
    assert restored == chosen
    if type(expected) is int:
        assert ExportSettings(fps=expected).fps is rate
    with pytest.raises(ValueError, match="Frame rate"):
        ExportSettings(fps=cast(FrameRate, rate.value))


def test_custom_frame_rates_preserve_integer_storage_and_reject_invalid_values() -> None:
    assert ExportSettings().fps is StandardFrameRate.FPS_50
    for value in (1, 27, 120):
        settings = ExportSettings(fps=value)
        chosen = preset().model_copy(update={"settings": settings})
        restored = SavedPreset.model_validate_json(chosen.model_dump_json())
        assert type(restored.settings.fps) is int and restored.settings.fps == value
        assert restored.settings.frame_rate == value
    for value in (True, False, 0, 121, 50.0, "23.976", "59.94", "50"):
        with pytest.raises(ValueError, match="Frame rate"):
            ExportSettings(fps=cast(FrameRate, value))


def short_job(data: ExplorerData, chosen: SavedPreset | None = None) -> BatchJob:
    assert data.analysis is not None
    first = data.source.recording.indices.start
    return make_job(
        data.analysis,
        chosen or preset(),
        range_mode="selection",
        first=first,
        last=first + 1,
    )


@pytest.mark.parametrize("fps", [StandardFrameRate.FPS_23_976, StandardFrameRate.FPS_59_94])
def test_sqlite_survives_reopen_with_snapshots_and_transaction_rollback(
    export_directory: Path,
    manta: ExplorerData,
    fps: FrameRate,
) -> None:
    path = export_directory / "exports.sqlite3"
    store = ExportStore(path)
    chosen = SavedPreset(
        name="Ribbon",
        settings=ExportSettings(fps=fps),
        analysis_configuration=source_app_configuration(),
        schema_version=1,
        smoothing_window=11,
        range_mode="markers",
    )
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
    assert ExportStore(path).presets()[0].settings.fps is StandardFrameRate.FPS_30
    assert ExportStore(path).batch("Weekend").jobs[0].preset.settings.fps == fps
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
    assert manta.analysis is not None
    paths = tuple(
        next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces")) for ride in ("Manta", "Kraken")
    )
    chosen = (
        preset(),
        preset("Orbit").model_copy(update={"settings": ExportSettings(layout=ExportLayout.ORBIT)}),
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
        make_job(manta.analysis, preset().model_copy(update={"range_mode": "selection"}))
    with pytest.raises(ValueError):
        SavedPreset(
            name="",
            settings=ExportSettings(),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        )
    with pytest.raises(ValueError, match="odd"):
        SavedPreset(
            name="bad",
            settings=ExportSettings(),
            smoothing_window=2,
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            range_mode="markers",
        )


def test_batch_continues_after_changed_recording_and_preserves_outputs(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.rendering import batches

    calls: list[Path] = []

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        calls.append(target)
        callback = cast(Callable[[ExportProgress], None], kwargs["progress"])
        callback(ExportProgress(ExportPhase.RENDERING, 1, 2, 10, True))
        callback(ExportProgress(ExportPhase.FINALIZING, 2, 2, 20, True))
        target.write_bytes(b"completed")
        callback(ExportProgress(ExportPhase.COMPLETED, 2, 2, 20, True))
        assert timeline.smoothing_window == 3
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    job = short_job(manta, preset(window=3))
    changed = job.model_copy(update={"source_sha256": "0" * 64})
    missing = job.model_copy(
        update={"recording_path": (export_directory / "missing.forces").resolve()},
    )
    saved = (
        SavedBatch(name="A", jobs=(job, changed, missing), schema_version=1),
        SavedBatch(name="B", jobs=(job,), schema_version=1),
    )
    updates: list[tuple[int, ExportProgress | None]] = []
    result = run_batches(
        saved,
        export_directory,
        progress=lambda job, total, update, label: updates.append((job, update)),
    )
    assert [job for job, update in updates if update is None] == [1, 2, 3, 4]
    for job_index in range(1, 5):
        events = [update for job, update in updates if job == job_index and update is not None]
        assert events[0] == ExportProgress(ExportPhase.PREPARING)
        if job_index in (1, 4):
            assert [event.phase for event in events] == list(ExportPhase)
            assert events[1].remaining_seconds == 10 and events[1].use_gpu is True
        else:
            assert len(events) == 1
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
        (SavedBatch(name="Cancel", jobs=(job, job, job), schema_version=1),),
        export_directory,
        cancelled=cancel,
    )
    assert [item.status for item in result.results] == ["completed", "cancelled", "skipped"]
    assert calls == 2
    output = result.results[0].output
    assert output is not None and output.read_bytes() == b"complete"
    with pytest.raises(ValueError, match="no export jobs"):
        run_batches((SavedBatch(name="Empty", schema_version=1, jobs=()),), export_directory)


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
        SavedPreset(
            name="Ribbon",
            settings=ExportSettings(layout=ExportLayout.RIBBON, prefer_gpu=False),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
        SavedPreset(
            name="Orbit opaque",
            settings=ExportSettings(
                layout=ExportLayout.ORBIT,
                output=VideoOutput.OPAQUE,
                prefer_gpu=False,
            ),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
    )
    for ride, chosen in zip(("Manta", "Kraken"), presets, strict=True):
        path = next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces"))
        sources.append((path, path.read_bytes()))
        data = load_recording(path)
        assert isinstance(data, ExplorerData) and data.analysis is not None
        jobs.append(short_job(data, chosen))
    store.save_batch(SavedBatch(name="Real", jobs=tuple(jobs), schema_version=1))
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


@pytest.mark.parametrize("table", ("presets", "batches"))
@pytest.mark.parametrize(
    "field",
    (
        ("analysis_configuration",),
        ("settings", "aspect"),
        ("settings", "language"),
        ("settings", "position"),
        ("analysis_configuration", "events_input"),
        ("analysis_configuration", "smoothing", "parameters"),
        ("analysis_configuration", "profile", "assumptions"),
        ("range_mode",),
        ("schema_version",),
    ),
)
def test_incomplete_stored_configuration_is_rejected_without_rewriting_database(
    export_directory: Path,
    manta: ExplorerData,
    table: str,
    field: tuple[str, ...],
) -> None:
    path = export_directory / "incomplete.sqlite3"
    store = ExportStore(path)
    chosen = preset()
    store.save_preset(chosen)
    store.save_batch(SavedBatch(name="Batch", jobs=(short_job(manta, chosen),), schema_version=1))
    with closing(sqlite3.connect(path)) as db, db:
        payload = json.loads(db.execute(f"SELECT payload FROM {table}").fetchone()[0])
        item = payload if table == "presets" else payload["jobs"][0]["preset"]
        for name in field[:-1]:
            item = item[name]
        del item[field[-1]]
        db.execute(f"UPDATE {table} SET payload=?", (json.dumps(payload),))
    before = path.read_bytes()
    with pytest.raises(ExportStoreError, match="incomplete|Field required"):
        store.presets() if table == "presets" else store.batches()
    assert path.read_bytes() == before


@pytest.mark.parametrize("table", ("presets", "batches"))
@pytest.mark.parametrize("position", ("left", "unknown"))
def test_invalid_stored_position_is_rejected_without_rewriting_database(
    export_directory: Path,
    manta: ExplorerData,
    table: str,
    position: str,
) -> None:
    path = export_directory / "invalid-position.sqlite3"
    store = ExportStore(path)
    chosen = preset()
    store.save_preset(chosen)
    store.save_batch(SavedBatch(name="Batch", jobs=(short_job(manta, chosen),), schema_version=1))
    with closing(sqlite3.connect(path)) as db, db:
        payload = json.loads(db.execute(f"SELECT payload FROM {table}").fetchone()[0])
        item = payload if table == "presets" else payload["jobs"][0]["preset"]
        item["settings"]["position"] = position
        db.execute(f"UPDATE {table} SET payload=?", (json.dumps(payload),))
    before = path.read_bytes()
    with pytest.raises(ExportStoreError, match="position|Input should be"):
        store.presets() if table == "presets" else store.batches()
    assert path.read_bytes() == before
