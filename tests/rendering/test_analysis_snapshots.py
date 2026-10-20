"""Export, preview and persisted jobs bind complete immutable analysis snapshots."""

from dataclasses import replace
from math import nan
from pathlib import Path
from typing import cast
from unittest.mock import Mock
import json

import numpy as np
import pytest
from PIL import Image

from ride_forces_analyzer.analysis import recording
from ride_forces_analyzer.analysis.models import AnalysisProfile, SampleValues
from ride_forces_analyzer.analysis.recording import AnalysisStage, StageConfiguration
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.rendering import batches
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportSettings,
    ExportTimeline,
    ExportValues,
    prepare_export,
    prepare_export_analysis,
)
from ride_forces_analyzer.rendering.preview import build_previews
from ride_forces_analyzer.storage.export_models import SavedBatch, make_preset
from ride_forces_analyzer.storage.exports import ExportStore


def test_export_reuses_buffers_orientation_and_full_history_context(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    snapshot = manta.analysis
    assert snapshot is not None and snapshot.forces.smoothed.channels is not None
    assert snapshot.context.labels is not None and snapshot.orientation.values is not None
    for name in ("project_directions", "centered_mean", "orientation_degrees"):
        monkeypatch.setattr(recording, name, Mock(side_effect=AssertionError("Repeated analysis")))
    monkeypatch.setattr(
        recording.airtime.AirtimeContext,
        "prepare",
        Mock(side_effect=AssertionError("Repeated context")),
    )
    timeline = prepare_export(manta.analysis, ExportSettings(layout="ribbon"), 3600, 3700)
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
    mean = Mock(wraps=recording.centered_mean)
    orientation = Mock(side_effect=AssertionError("Orientation changed with smoothing"))
    monkeypatch.setattr(recording, "centered_mean", mean)
    monkeypatch.setattr(recording, "orientation_degrees", orientation)
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
    result = build_previews(manta.analysis, ExportSettings(fps=24, language="de"), 0, 100, 3600)
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
    orientation = Mock(wraps=recording.orientation_degrees)
    monkeypatch.setattr(recording, "orientation_degrees", orientation)
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
