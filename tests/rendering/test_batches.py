"""SQLite persistence, immutable queue snapshots and real sequential export contracts."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
)
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides

# cspell:words Xnotes

from collections.abc import Callable
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import subprocess
from threading import Event
from typing import cast

import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer import __version__
from ride_forces_analyzer.exports.batches import BatchReport, build_jobs, make_job, run_batches
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.rendering.encoding import ExportCancelled
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    FrameRate,
    ExportLayout,
    ExportExtent,
    VideoAspect,
    ExportSettings,
    ExportSnapshot,
    ExportTimeline,
    prepare_export,
)
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from ride_forces_analyzer.storage.export_models import BatchJob, SavedBatch, SavedPreset
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_saved_metadata_does_not_follow_later_library_edits(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.exports import batches
    from ride_forces_analyzer.storage.library import LibraryStore
    from ride_forces_analyzer.explorer.library import LibraryArchive

    monkeypatch.setenv("LOCALAPPDATA", str(export_directory.resolve()))
    assert manta.analysis is not None
    additions = RecordingAdditions(ride_name="Captured", riding_position="Seated", notes="Saved")
    source = ImportSuccess(manta.source.recording, manta.source.diagnostics, additions=additions)
    analysis = replace(manta.analysis, source=source)
    job = make_job(analysis, preset(), first=3600, last=3609)
    old_snapshot = prepare_export(analysis, preset().settings, 3600, 3609).snapshot
    assert job.ride == "Captured" and job.metadata_additions == additions
    assert BatchJob.model_validate_json(job.model_dump_json()) == job
    path = manta.source.recording.source.provenance.path
    assert path is not None
    store = LibraryStore()
    LibraryArchive(store).import_paths((path,))
    store.update_metadata(source.source_sha256, {"ride_name": "Later", "riding_position": "Flying"})
    markers = CalibrationOverrides(gravity_index=source.recording.indices.gravity)
    store.update_markers(source, (4000, 5000), markers)
    payload = job.model_dump(mode="json")
    payload.pop("metadata_additions")
    legacy = BatchJob.model_validate_json(json.dumps(payload))
    assert legacy.metadata_additions is None
    observed: list[ImportSuccess] = []
    observed_configurations: list[object] = []

    def fake_export(
        timeline: ExportTimeline,
        target: Path,
        *args: object,
        **kwargs: object,
    ) -> Path:
        observed.append(timeline.analysis.source)
        observed_configurations.append(timeline.analysis.configuration)
        target.write_bytes(b"encoded")
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    report = run_batches(
        (SavedBatch(name="Metadata", jobs=(job, legacy), schema_version=1),),
        export_directory,
    )
    assert [result.status for result in report.results] == ["completed", "completed"]
    assert observed[0].effective_metadata.name == "Captured"
    assert observed[0].additions == additions
    assert observed[1].additions == RecordingAdditions()
    assert observed[1].effective_metadata == manta.source.recording.metadata
    assert observed_configurations == [
        job.preset.analysis_configuration,
        legacy.preset.analysis_configuration,
    ]
    assert old_snapshot.analysis_configuration == analysis.configuration
    current = build_jobs((path,), (preset(),), "entire")[0]
    assert current.ride == "Later" and current.metadata_additions is not None
    assert current.metadata_additions.riding_position == "Flying"
    assert current.preset.analysis_configuration.ride_bounds == (4000, 5000)
    assert current.preset.analysis_configuration.calibration == markers


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
    from ride_forces_analyzer.exports import batches

    chosen = SavedPreset(
        name="Portrait",
        settings=ExportSettings(
            layout=ExportLayout.CORNERS,
            aspect=VideoAspect.PORTRAIT,
            position=LayoutPosition.TOP_LEFT,
            extent=ExportExtent.CONTENT_AREA,
        ),
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
            update={
                "settings": replace(
                    chosen.settings,
                    position=LayoutPosition.TOP_RIGHT,
                    extent=ExportExtent.FULL_FRAME,
                ),
            },
        ),
        overwrite=True,
    )
    reopened = ExportStore(path)
    assert reopened.presets()[0].settings.dimensions == (2160, 3840)
    assert reopened.presets()[0].settings.position is LayoutPosition.TOP_RIGHT
    assert reopened.presets()[0].settings.extent is ExportExtent.FULL_FRAME
    jobs = reopened.batch("Mixed formats").jobs
    assert [job.preset.settings.extent for job in jobs] == [
        ExportExtent.CONTENT_AREA,
        ExportExtent.FULL_FRAME,
    ]
    assert [resolve_geometry(job.preset.settings).output_size for job in jobs] == [
        (840, 1120),
        (3840, 2160),
    ]
    store.delete_preset(chosen.name)
    assert reopened.batch("Mixed formats").jobs == jobs
    assert [job.preset.settings.position for job in jobs] == [
        LayoutPosition.TOP_LEFT,
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


def test_hud_preset_round_trip_and_invalid_settings_rejection() -> None:
    from pydantic import ValidationError

    chosen = preset().model_copy(update={"settings": ExportSettings(layout=ExportLayout.HUD)})
    saved = SavedPreset.model_validate_json(chosen.model_dump_json())
    assert saved.settings.layout == ExportLayout.HUD
    assert saved.settings.dimensions == (1920, 1080)
    assert replace(saved.settings, aspect=VideoAspect.PORTRAIT).dimensions == (1080, 1920)
    assert saved.settings.position is LayoutPosition.FULL_SCREEN
    assert saved.settings.extent is ExportExtent.FULL_FRAME
    payload = json.loads(saved.model_dump_json())
    del payload["settings"]["extent"]
    assert (
        SavedPreset.model_validate_json(json.dumps(payload)).settings.extent
        is ExportExtent.FULL_FRAME
    )
    for extent in (ExportExtent.CONTENT_AREA.value, "unknown"):
        payload["settings"]["extent"] = extent
        with pytest.raises(ValidationError, match="extent|Input should be"):
            SavedPreset.model_validate_json(json.dumps(payload))
    payload = json.loads(saved.model_dump_json())
    payload["settings"]["layout"] = "unknown-layout"
    with pytest.raises(ValidationError):
        SavedPreset.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("aspect", list(VideoAspect))
def test_video_aspect_preserves_saved_codes_and_requires_enum_members(
    aspect: VideoAspect,
) -> None:
    from pydantic import ValidationError

    assert ExportSettings().aspect is VideoAspect.LANDSCAPE
    assert VideoAspect(aspect.value) is aspect
    chosen = preset().model_copy(
        update={"settings": ExportSettings(layout=ExportLayout.RIBBON, aspect=aspect)},
    )
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
        preset("Orbit").model_copy(
            update={
                "settings": ExportSettings(
                    layout=ExportLayout.ORBIT,
                    extent=ExportExtent.CONTENT_AREA,
                ),
            },
        ),
    )
    jobs = build_jobs(paths, chosen, "entire")
    assert len(jobs) == 4
    assert [job.preset.settings.extent for job in jobs] == [
        ExportExtent.FULL_FRAME,
        ExportExtent.CONTENT_AREA,
        ExportExtent.FULL_FRAME,
        ExportExtent.CONTENT_AREA,
    ]
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


def test_batch_report_retains_complete_settings_and_actual_execution(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.exports import batches

    renderer_counts: list[object] = []
    snapshots: list[ExportSnapshot] = []

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        snapshots.append(timeline.snapshot)
        renderer_counts.append(kwargs["render_jobs"])
        callback = cast(Callable[[ExportProgress], None], kwargs["progress"])
        callback(ExportProgress(ExportPhase.RENDERING, 1, timeline.frame_count, 1, False))
        target.write_bytes(b"encoded")
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    chosen = preset("Complete settings", window=5).model_copy(
        update={
            "settings": ExportSettings(
                layout=ExportLayout.CORNERS,
                extent=ExportExtent.CONTENT_AREA,
                aspect=VideoAspect.PORTRAIT,
                position=LayoutPosition.TOP_LEFT,
                output=VideoOutput.OPAQUE,
                fps=StandardFrameRate.FPS_59_94,
                window_seconds=8,
                invert_vertical=True,
                invert_lateral=True,
                language=Language.FRENCH,
                prefer_gpu=True,
            ),
        },
    )
    job = short_job(manta, chosen)
    ffmpeg = export_directory / "selected-ffmpeg.exe"
    ticks = iter((100.0, 102.75))
    monkeypatch.setattr(batches, "monotonic", lambda: next(ticks))
    result = run_batches(
        (SavedBatch(name="Settings", jobs=(job,), schema_version=1),),
        export_directory,
        ffmpeg=ffmpeg,
        render_jobs=2,
    )
    payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert payload["application_version"] == __version__
    assert payload["render_jobs"] == renderer_counts[0]
    assert payload["requested_ffmpeg"] == str(ffmpeg)
    outcome = payload["results"][0]
    assert outcome["status"] == "completed"
    assert outcome["job_snapshot"] == json.loads(job.model_dump_json())
    assert outcome["job_snapshot"]["preset"]["settings"]["fps"] == "60000/1001"
    assert outcome["job_snapshot"]["preset"]["settings"]["prefer_gpu"] is True
    assert outcome["gpu_encoding"] is False
    assert result.results[0].export_snapshot is snapshots[0]
    assert outcome["export_snapshot"] == snapshots[0].model_dump(mode="json")
    assert outcome["export_snapshot"]["sample_rate"] == 50
    assert outcome["export_snapshot"]["output_dimensions"] == [840, 1120]
    assert outcome["export_snapshot"]["planned_frame_count"] == 3
    assert outcome["file_size_bytes"] == len(b"encoded")
    assert outcome["duration_seconds"] == 2.75
    restored = BatchReport.model_validate_json(result.report_path.read_text(encoding="utf-8"))
    assert restored.results[0].job_snapshot == job


def test_batch_overall_progress_weights_intervals_and_frame_rates(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.exports import batches

    short = short_job(manta)
    slow = short.preset.model_copy(
        update={"settings": replace(short.preset.settings, fps=StandardFrameRate.FPS_25)},
    )
    short = short.model_copy(update={"preset": slow})
    long = short.model_copy(
        update={"last_sample": short.first_sample + 5, "preset": preset()},
    )
    frames: list[int] = []
    overall: list[tuple[int, int]] = []

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        frames.append(timeline.frame_count)
        callback = cast(Callable[[ExportProgress], None], kwargs["progress"])
        callback(ExportProgress(ExportPhase.RENDERING, 1, timeline.frame_count))
        target.write_bytes(b"completed")
        return target

    monkeypatch.setattr(batches, "export_video", fake_export)
    report = run_batches(
        (
            SavedBatch(name="Short", jobs=(short,), schema_version=1),
            SavedBatch(name="Long", jobs=(long,), schema_version=1),
        ),
        export_directory,
        overall_progress=lambda done, total: overall.append((done, total)),
    )
    assert frames == [1, 6]
    assert overall == [(0, 7), (1, 7), (1, 7), (2, 7), (7, 7)]
    assert all(result.status == "completed" for result in report.results)


def test_batch_continues_after_changed_recording_and_preserves_outputs(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.exports import batches

    calls: list[Path] = []
    ticks = iter(index * 0.5 for index in range(16))
    monkeypatch.setattr(batches, "monotonic", lambda: next(ticks))

    def fake_export(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        calls.append(target)
        callback = cast(Callable[[ExportProgress], None], kwargs["progress"])
        callback(ExportProgress(ExportPhase.RENDERING, 1, 2, 10, True))
        callback(ExportProgress(ExportPhase.FINALIZING, 2, 2, 20, True))
        with target.open("xb") as output:
            output.write(b"completed")
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
    overall: list[tuple[int, int]] = []
    result = run_batches(
        saved,
        export_directory,
        progress=lambda job, total, update, label: updates.append((job, update)),
        overall_progress=lambda done, total: overall.append((done, total)),
    )
    assert overall[0] == (0, 6)
    assert overall[-1] == (6, 6)
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
    assert [item.job_snapshot for item in result.results] == [job, changed, missing, job]
    assert all(item.duration_seconds == 0.5 for item in result.results)
    assert result.results[0].gpu_encoding is True
    assert result.results[1].gpu_encoding is None
    assert result.results[1].export_snapshot is None
    assert result.results[1].file_size_bytes is None
    assert "changed" in (result.results[1].error or "")
    assert len(calls) == 2 and calls[0] != calls[1]
    assert all(path.read_bytes() == b"completed" for path in calls)
    assert result.directory == export_directory
    assert calls[0].parent == export_directory / "001-A"
    assert calls[1].parent == export_directory / "002-B"
    assert not list(export_directory.glob("export-*"))
    assert result.report_path == export_directory / "run-report.json"
    original_report = result.report_path.read_bytes()
    saved_results = json.loads(original_report)["results"]
    assert len(saved_results) == 4
    assert saved_results[1]["job_snapshot"] == json.loads(changed.model_dump_json())
    assert saved_results[2]["job_snapshot"] == json.loads(missing.model_dump_json())
    second = run_batches(saved, export_directory)
    assert second.directory == result.directory
    assert second.report_path != result.report_path and second.report_path.is_file()
    assert result.report_path.read_bytes() == original_report
    assert all(item.status == "failed" for item in second.results)
    assert all(item.duration_seconds == 0.5 for item in second.results)
    assert calls[0].read_bytes() == b"completed"


def test_cancel_stops_remaining_jobs_and_keeps_completed_files(
    export_directory: Path,
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ride_forces_analyzer.exports import batches

    calls = 0
    cancel = Event()
    ticks = iter((100.0, 101.25, 110.0, 112.5))
    monkeypatch.setattr(batches, "monotonic", lambda: next(ticks))

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
    overall: list[tuple[int, int]] = []
    result = run_batches(
        (SavedBatch(name="Cancel", jobs=(job, job, job), schema_version=1),),
        export_directory,
        cancelled=cancel,
        overall_progress=lambda done, total: overall.append((done, total)),
    )
    assert overall == [(0, 6), (2, 6)]
    assert [item.status for item in result.results] == ["completed", "cancelled", "skipped"]
    assert [item.duration_seconds for item in result.results] == [1.25, 2.5, None]
    payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert [item["duration_seconds"] for item in payload["results"]] == [1.25, 2.5, None]
    assert all(item.job_snapshot == job for item in result.results)
    assert result.results[1].file_size_bytes is None
    assert result.results[2].export_snapshot is None
    assert result.results[2].gpu_encoding is None
    assert calls == 2
    output = result.results[0].output
    assert output is not None and output.read_bytes() == b"complete"
    with pytest.raises(ValueError, match="no export jobs"):
        run_batches((SavedBatch(name="Empty", schema_version=1, jobs=()),), export_directory)


def test_saved_batch_reopens_and_exports_mixed_extents_and_outputs(
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
                extent=ExportExtent.CONTENT_AREA,
            ),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
        SavedPreset(
            name="HUD full frame",
            settings=ExportSettings(layout=ExportLayout.HUD, prefer_gpu=False),
            analysis_configuration=source_app_configuration(),
            schema_version=1,
            smoothing_window=11,
            range_mode="markers",
        ),
    )
    for ride, chosen in zip(("Manta", "Kraken", "Manta"), presets, strict=True):
        path = next(REAL_FIXTURE_DIRECTORY.glob(f"{ride}-*.forces"))
        sources.append((path, path.read_bytes()))
        data = load_recording(path)
        assert isinstance(data, ExplorerData) and data.analysis is not None
        jobs.append(short_job(data, chosen))
    store.save_batch(SavedBatch(name="Real", jobs=tuple(jobs), schema_version=1))
    result = run_batches(ExportStore(store.path).batches(), export_directory, ffmpeg=ffmpeg)
    assert len(result.results) == 3
    assert all(
        item.status == "completed" and item.output is not None and item.output.stat().st_size > 0
        for item in result.results
    )
    assert [item.output.suffix for item in result.results if item.output] == [
        ".mov",
        ".mp4",
        ".mov",
    ]
    for item, dimensions in zip(
        result.results,
        ((3840, 2160), (800, 800), (1920, 1080)),
        strict=True,
    ):
        assert item.output is not None
        assert item.export_snapshot is not None
        assert item.export_snapshot.output_dimensions == dimensions
        assert item.export_snapshot.planned_frame_count == 2
        assert item.file_size_bytes == item.output.stat().st_size
        assert item.gpu_encoding is False
        assert item.duration_seconds is not None and item.duration_seconds > 0
        probe = subprocess.run(
            [
                str(ffmpeg.with_name("ffprobe.exe")),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,nb_frames:format_tags=comment",
                "-of",
                "json",
                str(item.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(probe.stdout)
        stream = metadata["streams"][0]
        assert (stream["width"], stream["height"]) == dimensions
        assert int(stream["nb_frames"]) == 2
        comment = json.loads(metadata["format"]["tags"]["comment"])
        assert comment["export_snapshot"] == item.export_snapshot.model_dump(mode="json")
    assert all(path.read_bytes() == original for path, original in sources)


@pytest.mark.parametrize("table", ("presets", "batches"))
@pytest.mark.parametrize(
    "field",
    (
        ("analysis_configuration",),
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
    with pytest.raises(ExportStoreError, match="Field required|assumptions"):
        store.presets() if table == "presets" else store.batches()
    assert path.read_bytes() == before


@pytest.mark.parametrize("table", ("presets", "batches"))
def test_missing_optional_fields_use_defaults_without_rewriting_database(
    export_directory: Path,
    manta: ExplorerData,
    table: str,
) -> None:
    path = export_directory / "defaults.sqlite3"
    store = ExportStore(path)
    chosen = preset()
    batch = SavedBatch(name="Batch", jobs=(short_job(manta, chosen),), schema_version=1)
    store.save_preset(chosen)
    store.save_batch(batch)
    with closing(sqlite3.connect(path)) as db, db:
        payload = json.loads(db.execute(f"SELECT payload FROM {table}").fetchone()[0])
        item = payload if table == "presets" else payload["jobs"][0]["preset"]
        for name in ("aspect", "language", "position", "extent"):
            del item["settings"][name]
        for name in ("calibration", "events", "context_input", "events_input"):
            del item["analysis_configuration"][name]
        del item["analysis_configuration"]["projection"]["parameters"]
        del item["analysis_configuration"]["profile"]["schema_version"]
        db.execute(f"UPDATE {table} SET payload=?", (json.dumps(payload),))
    before = path.read_bytes()
    assert store.presets() == (chosen,)
    assert store.batches() == (batch,)
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
