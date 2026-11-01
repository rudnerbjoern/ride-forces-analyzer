"""Export-owned snapshots describe effective analysis independently of batching."""

from dataclasses import replace
import json
from pathlib import Path

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.domain import ValueOrigin
from ride_forces_analyzer.rendering.encoding import encoder_command
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSettings,
    ExportSnapshot,
    StandardFrameRate,
    VideoAspect,
    prepare_export,
)


def test_export_timeline_owns_the_effective_snapshot_and_embeds_it_in_video(
    manta: ExplorerData,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(
        layout=ExportLayout.CORNERS,
        extent=ExportExtent.CONTENT_AREA,
        aspect=VideoAspect.PORTRAIT,
        fps=StandardFrameRate.FPS_59_94,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3609)
    snapshot = timeline.snapshot
    assert snapshot.analysis_configuration is manta.analysis.configuration
    assert snapshot.settings == settings
    assert snapshot.source_sha256 == timeline.source_sha256
    assert (snapshot.first_sample, snapshot.last_sample_inclusive) == (3600, 3609)
    assert snapshot.output_dimensions == (840, 1120)
    assert snapshot.planned_frame_count == 12
    payload = snapshot.model_dump(mode="json")
    assert "recording_path" not in payload and "channels" not in payload
    assert ExportSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    command = encoder_command(Path("ffmpeg.exe"), timeline, Path("output.mov"))
    metadata = json.loads(command[command.index("-metadata") + 1].removeprefix("comment="))
    assert metadata["export_snapshot"] == payload
    assert metadata["source_sha256"] == timeline.source_sha256


def test_rebinding_a_timeline_refreshes_its_snapshot_without_changing_the_original(
    manta: ExplorerData,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(fps=StandardFrameRate.FPS_59_94),
        3600,
        3609,
    )
    changed = replace(timeline, settings=replace(timeline.settings, fps=50))
    assert changed.snapshot is not timeline.snapshot
    assert changed.snapshot.settings == changed.settings
    assert changed.snapshot.planned_frame_count == 10
    assert timeline.snapshot.planned_frame_count == 12
    assert changed.snapshot.analysis_configuration is timeline.snapshot.analysis_configuration


def test_effective_metadata_is_captured_without_changing_old_snapshots(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    original = prepare_export(manta.analysis, ExportSettings(), 3600, 3609)
    additions = RecordingAdditions(
        ride_name="Edited ride",
        park_name="Edited park",
        row="Front",
        seat="Left",
        train="Blue",
        riding_position="Seated",
        notes="Captured notes",
    )
    source = ImportSuccess(manta.source.recording, manta.source.diagnostics, additions=additions)
    analysis = replace(manta.analysis, source=source)
    changed = prepare_export(analysis, ExportSettings(), 3600, 3609)
    captured = changed.snapshot.recording_metadata
    assert changed.snapshot.schema_version == 2 and captured is not None
    assert captured.ride_name == "Edited ride" and captured.park_name == "Edited park"
    assert (captured.row, captured.seat, captured.train) == ("Front", "Left", "Blue")
    assert (
        captured.riding_position == "Seated" and captured.riding_position_origin is ValueOrigin.USER
    )
    assert captured.notes == "Captured notes"
    assert original.snapshot.recording_metadata is not None
    assert original.snapshot.recording_metadata.ride_name == "Manta"
    assert manta.source.recording.metadata.name == "Manta"
    assert analysis.forces is manta.analysis.forces
    payload = original.snapshot.model_dump(mode="json")
    payload["schema_version"] = 1
    payload.pop("recording_metadata")
    legacy = ExportSnapshot.model_validate_json(json.dumps(payload))
    assert legacy.schema_version == 1 and legacy.recording_metadata is None
    assert (
        ExportSnapshot.model_validate_json(changed.snapshot.model_dump_json()) == changed.snapshot
    )
