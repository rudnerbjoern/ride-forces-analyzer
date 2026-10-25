"""Export, preview and persisted jobs bind complete immutable analysis snapshots."""

from dataclasses import replace
from datetime import UTC, datetime
from math import nan
from pathlib import Path
from typing import cast
from unittest.mock import Mock
import json

import numpy as np
import pytest
from PIL import Image

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.analysis import preparation
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.models import AnalysisProfile, SampleValues
from ride_forces_analyzer.analysis.recording import AnalysisStage, StageConfiguration
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.exports import batches
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    ExportTimeline,
    ExportValues,
    prepare_export,
    prepare_export_analysis,
)
from ride_forces_analyzer.rendering.preview import build_previews
from ride_forces_analyzer.storage.export_models import SavedBatch, make_preset
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.storage.preferences import Preferences


def test_markers_bind_export_and_batch_without_leaking_into_reusable_presets(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    snapshot = manta.analysis
    assert snapshot is not None
    changed = snapshot.with_configuration(
        replace(snapshot.configuration, ride_bounds=(3600, 3700)),
        revision=snapshot.revision + 1,
        calculation_time=datetime.now(UTC),
    )
    preset = make_preset("Markers", ExportSettings(), 11, "markers", changed.configuration)
    assert preset.analysis_configuration.ride_bounds is None
    timeline = prepare_export(changed, preset.settings, 3600, 3700)
    assert timeline.replay_origin == 3600
    job = batches.make_job(changed, preset)
    assert (job.first_sample, job.last_sample) == (3600, 3700)
    store = ExportStore(export_directory / "marker-jobs.sqlite3")
    store.save_batch(SavedBatch(schema_version=1, name="Markers", jobs=(job,)))
    saved = store.batch("Markers").jobs[0]
    restored = prepare_export_analysis(snapshot, saved.preset.analysis_configuration)
    assert restored.ride_bounds == (3600, 3700) and restored.replay_origin == 3600
    assert restored.source.recording.indices == snapshot.source.recording.indices


def test_bound_calibration_jobs_ignore_later_preferences_and_preserve_preset_scope(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(export_directory.resolve()))
    original = manta.analysis
    assert original is not None
    source = original.source
    choice = CalibrationOverrides(
        source.recording.indices.gravity,
        source.recording.indices.incline,
    )
    changed = original.with_configuration(
        replace(original.configuration, ride_bounds=(3600, 3700), calibration=choice),
        revision=original.revision + 1,
        calculation_time=datetime.now(UTC),
    )
    preset = make_preset("References", ExportSettings(), 11, "markers", changed.configuration)
    assert preset.analysis_configuration.ride_bounds is None
    assert not preset.analysis_configuration.calibration.active
    timeline = prepare_export(changed, preset.settings, 3600, 3700)
    job = batches.make_job(changed, preset)
    assert job.preset.analysis_configuration.calibration == choice
    store = ExportStore(export_directory / "references.sqlite3")
    store.save_batch(SavedBatch(schema_version=1, name="References", jobs=(job,)))
    batch = store.batch("References")
    saved = batch.jobs[0]
    preferences = Preferences()
    assert preferences.remember_recording_bounds(source.source_sha256, (1, 10))
    assert preferences.remember_recording_calibration(source, CalibrationOverrides())
    captured: list[ExportTimeline] = []

    def encode(timeline: ExportTimeline, path: Path, **options: object) -> Path:
        captured.append(timeline)
        path.write_bytes(b"encoded")
        return path

    monkeypatch.setattr(batches, "export_video", encode)
    report = batches.run_batches((batch,), export_directory)
    assert [result.status for result in report.results] == ["completed"]
    restored = captured[0].analysis
    assert restored is not None
    assert restored.configuration == changed.configuration
    assert restored.forces.smoothed.channels == changed.forces.smoothed.channels
    assert restored.orientation.values == changed.orientation.values
    assert timeline.analysis is changed
    reset = changed.with_configuration(
        original.configuration,
        revision=changed.revision + 1,
        calculation_time=datetime.now(UTC),
    )
    assert reset.calibration is None and changed.calibration is not None
    seen: list[ExportTimeline] = []

    def preview(self: OverlayRenderer, position: float) -> Image.Image:
        seen.append(self.timeline)
        assert self.timeline.analysis is changed
        assert self.timeline.value_at(self.timeline.channels[0], position) == (
            timeline.value_at(timeline.channels[0], position)
        )
        assert self.timeline.context_at(position) == timeline.context_at(position)
        return Image.new("RGBA", (8, 8))

    monkeypatch.setattr(OverlayRenderer, "render_sample", preview)
    build_previews(changed, timeline.settings, 3600, 3700, 3650)
    assert len(seen) == 5
    assert timeline.analysis is changed and timeline.analysis.configuration.calibration == choice
    assert preferences.remember_recording_calibration(source, choice)
    jobs = batches.build_jobs((saved.recording_path,), (preset,), "markers")
    assert jobs[0].preset.analysis_configuration.calibration == choice
    assert jobs[0].first_sample == 1 and jobs[0].last_sample == 10


@pytest.mark.parametrize(
    "field,value",
    (("algorithm_version", "unsupported"), ("window_samples", 11), ("window_samples", None)),
)
def test_saved_calibration_recipe_requires_supported_explicit_parameters(
    field: str,
    value: str | int | None,
) -> None:
    from ride_forces_analyzer.analysis.preparation import (
        source_app_configuration,
    )
    from ride_forces_analyzer.storage.export_models import SavedPreset

    preset = make_preset("References", ExportSettings(), 11, "markers", source_app_configuration())
    payload = json.loads(preset.model_dump_json())
    if value is None:
        del payload["analysis_configuration"]["calibration"][field]
    else:
        payload["analysis_configuration"]["calibration"][field] = value
    with pytest.raises(ValueError):
        SavedPreset.model_validate_json(json.dumps(payload))


def test_export_reuses_buffers_orientation_and_full_history_context(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    snapshot = manta.analysis
    assert snapshot is not None and snapshot.forces.smoothed.channels is not None
    assert snapshot.context.labels is not None and snapshot.orientation.values is not None
    for name in ("project_directions", "centered_mean", "orientation_degrees"):
        monkeypatch.setattr(
            preparation,
            name,
            Mock(side_effect=AssertionError("Repeated analysis")),
        )
    monkeypatch.setattr(
        preparation.airtime.AirtimeContext,
        "prepare",
        Mock(side_effect=AssertionError("Repeated context")),
    )
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout=ExportLayout.RIBBON),
        3600,
        3700,
    )
    assert timeline.analysis is snapshot
    for channel, samples in zip(
        timeline.channels[:3],
        snapshot.forces.smoothed.channels,
        strict=True,
    ):
        assert isinstance(channel.values, ExportValues)
        assert channel.values.samples is samples
        assert np.shares_memory(channel.values.samples.values, samples.values)
    orientation = timeline.channels[3].values
    assert (
        isinstance(orientation, ExportValues) and orientation.samples is snapshot.orientation.values
    )
    for position in (3600.0, 3600.9, 3650.5):
        assert (
            timeline.context_at(position)
            == snapshot.context.labels[int(position)]
            .value.replace(
                "_",
                " ",
            )
            .title()
        )
    before = tuple(timeline.channels[0].values)
    OverlayRenderer(timeline).render_sample(3650)
    build_previews(snapshot, timeline.settings, 3600, 3700, 3650)
    assert tuple(timeline.channels[0].values) == before


def test_export_reconfiguration_reuses_upstream_and_keeps_running_snapshot(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = manta.analysis
    assert snapshot is not None
    timeline = prepare_export(snapshot, ExportSettings(), 100, 149)
    before = tuple(timeline.channels[0].values)
    mean = Mock(wraps=preparation.centered_mean)
    orientation = Mock(side_effect=AssertionError("Orientation changed with smoothing"))
    monkeypatch.setattr(preparation, "centered_mean", mean)
    monkeypatch.setattr(preparation, "orientation_degrees", orientation)
    assert prepare_export_analysis(snapshot, snapshot.configuration) is snapshot
    configuration = replace(
        snapshot.configuration,
        smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 3),)),
    )
    changed = prepare_export_analysis(snapshot, configuration)
    assert mean.call_count == 3 and not orientation.called
    assert changed.forces.projected is snapshot.forces.projected
    assert changed.orientation is snapshot.orientation
    assert timeline.analysis is snapshot and tuple(timeline.channels[0].values) == before
    assert prepare_export(changed, ExportSettings(fps=60), 100, 149).analysis is changed
    assert prepare_export_analysis(changed, configuration) is changed


def test_previews_bind_one_snapshot_across_layouts_settings_and_outside_range(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    seen: list[ExportTimeline] = []

    def capture(self: OverlayRenderer, position: float) -> Image.Image:
        seen.append(self.timeline)
        assert position == 3600
        return Image.new("RGBA", (8, 8))

    monkeypatch.setattr(OverlayRenderer, "render_sample", capture)
    result = build_previews(
        manta.analysis,
        ExportSettings(fps=24, language=Language.GERMAN),
        0,
        100,
        3600,
    )
    assert result.outside_range
    assert len(seen) == 5 and all(timeline.analysis is manta.analysis for timeline in seen)
    assert all(timeline.first == 0 and timeline.last == manta.count - 1 for timeline in seen)


def test_shared_export_values_preserve_gaps_slices_and_fractional_interpolation(
    manta: ExplorerData,
) -> None:
    assert manta.analysis is not None
    values = ExportValues(SampleValues(np.array([1.0, nan, 3.0]), valid_rows=(True, False, True)))
    assert tuple(values) == (1.0, None, 3.0)
    assert values[::-1] == (3.0, None, 1.0) and values[-1] == 3.0
    with pytest.raises(IndexError):
        _ = values[3]
    timeline = replace(prepare_export(manta.analysis, ExportSettings(), 0, 2), first=0, last=2)
    channel = replace(timeline.channels[0], values=values)
    assert timeline.value_at(channel, 0) == 1.0
    assert timeline.value_at(channel, 0.5) is None
    assert timeline.value_at(channel, 1) is None
    assert timeline.value_at(channel, 2) == 3.0


def test_recipe_round_trip_preserves_explicit_policy_dependencies(
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    assert manta.analysis is not None
    snapshot = manta.analysis
    assert snapshot is not None
    configuration = replace(snapshot.configuration, context_input=AnalysisStage.PROJECTION)
    preset = make_preset("Unfiltered context", ExportSettings(), 11, "markers", configuration)
    store = ExportStore(export_directory / "analysis.sqlite3")
    store.save_preset(preset)
    store.save_batch(
        SavedBatch(
            name="Snapshots",
            jobs=(batches.make_job(manta.analysis, preset),),
            schema_version=1,
        ),
    )
    reopened = ExportStore(store.path)
    assert reopened.presets()[0].analysis_configuration == configuration
    assert reopened.batch("Snapshots").jobs[0].preset.analysis_configuration == configuration
    payload = json.loads(preset.model_dump_json())
    assert set(payload["analysis_configuration"]) == {
        "profile",
        "projection",
        "smoothing",
        "orientation",
        "context",
        "events",
        "context_input",
        "events_input",
        "ride_bounds",
        "calibration",
    }
    with pytest.raises(ValueError, match="must match"):
        make_preset("Mismatched", ExportSettings(), 3, "markers", configuration)


def test_batch_restores_complete_recipe_without_recomputing_independent_orientation(
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    snapshot = manta.analysis
    assert snapshot is not None
    configuration = replace(
        snapshot.configuration,
        context_input=AnalysisStage.PROJECTION,
        smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 3),)),
    )
    preset = make_preset("Recipe", ExportSettings(), 3, "selection", configuration)
    job = batches.make_job(manta.analysis, preset, first=100, last=149)

    def load(path: Path) -> ImportSuccess:
        return snapshot.source

    monkeypatch.setattr(batches, "import_forces", load)
    orientation = Mock(wraps=preparation.orientation_degrees)
    monkeypatch.setattr(preparation, "orientation_degrees", orientation)
    seen: list[ExportTimeline] = []

    def encode(timeline: ExportTimeline, target: Path, **kwargs: object) -> Path:
        seen.append(timeline)
        target.write_bytes(b"complete")
        return target

    monkeypatch.setattr(batches, "export_video", encode)
    report = batches.run_batches(
        (SavedBatch(name="Recipe", jobs=(job,), schema_version=1),),
        export_directory,
    )
    assert report.results[0].status == "completed"
    assert seen[0].analysis.configuration == configuration
    assert orientation.call_count == 1
    assert seen[0].analysis.orientation.values == snapshot.orientation.values
    assert seen[0].analysis.forces.projected.channels == snapshot.forces.projected.channels
    assert seen[0].first == 100 and len(seen[0].analysis.time.source_indices) == manta.count


def test_unavailable_stages_do_not_invent_export_values(manta: ExplorerData) -> None:
    snapshot = manta.analysis
    assert snapshot is not None
    raw = prepare_export_analysis(
        snapshot,
        replace(snapshot.configuration, profile=AnalysisProfile()),
    )
    with pytest.raises(ValueError, match="Projection is unavailable"):
        prepare_export(raw, ExportSettings(), 0, 1)
    for first, last in ((-1, 1), (1, 0), (0, manta.count)):
        with pytest.raises(ValueError, match="interval"):
            prepare_export(snapshot, ExportSettings(), first, last)
    for position in (-1.0, nan, float(manta.count)):
        with pytest.raises(ValueError, match="outside"):
            prepare_export(snapshot, ExportSettings(), 0, 1).context_at(position)


def test_outside_preview_still_validates_original_interval(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    for first, last in ((-1, 1), (2, 1), (0, manta.count), (1.5, 2.5), (False, 2)):
        with pytest.raises(ValueError, match="interval"):
            build_previews(
                manta.analysis,
                ExportSettings(),
                cast(int, first),
                cast(int, last),
                3600,
            )
