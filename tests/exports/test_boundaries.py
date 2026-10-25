"""Export guards preserve rate, source and incomplete-preparation contracts."""

from dataclasses import replace
from contextlib import nullcontext
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.analysis.models import TimeBasis
from ride_forces_analyzer.analysis.preparation import prepare_recording_analysis
from ride_forces_analyzer.exports import batches
from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.exports.json import JsonExportCancelled, export_json
from ride_forces_analyzer.exports.validation import validate_export
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.storage.export_models import BatchJob, SavedBatch, make_preset
from tests.exports.test_csv_export import snapshot


def test_sample_exports_require_rate_even_for_a_valid_index_only_snapshot(
    export_directory: Path,
) -> None:
    original = snapshot(calibrated=False)
    time = replace(original.time, basis=TimeBasis())
    projected = replace(original.forces.projected, time=time)
    smoothed = replace(original.forces.smoothed, projection=projected)
    analysis = replace(
        original,
        time=time,
        forces=replace(original.forces, projected=projected, smoothed=smoothed),
        orientation=replace(original.orientation, time=time),
        context=replace(original.context, input=smoothed),
        events=replace(original.events, input=smoothed),
    )
    analysis.validate()
    for format in DataExportFormat:
        suffix = "csv" if format is DataExportFormat.CSV else "json"
        path = export_directory / f"output.{suffix}"
        with pytest.raises(ValueError, match="sample times require a sample rate"):
            validate_export(analysis, path, 0, 0, format)
        assert not path.exists()


def test_json_cancellation_is_checked_after_the_closing_brace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = StringIO()
    monkeypatch.setattr(
        "ride_forces_analyzer.exports.json.export_file",
        Mock(return_value=nullcontext(stream)),
    )
    with pytest.raises(JsonExportCancelled):
        export_json(
            snapshot(),
            Path("output.json"),
            0,
            0,
            cancelled=lambda: stream.getvalue().endswith("\n}"),
        )
    assert stream.getvalue().startswith("{\n") and stream.getvalue().endswith("\n}")


def test_batch_rejects_missing_sources_calibration_and_empty_inputs(
    export_directory: Path,
) -> None:
    original = snapshot(calibrated=False)
    preset = make_preset("Raw", ExportSettings(), 3, "markers", original.configuration)
    with pytest.raises(ValueError, match="file-backed"):
        batches.make_job(original, preset)
    with pytest.raises(ValueError, match="at least one recording"):
        batches.build_jobs((), (preset,), "markers")
    path = export_directory / "raw.forces"
    path.write_bytes(original.source.recording.source.original_bytes)
    with pytest.raises(ValueError, match="at least one recording"):
        batches.build_jobs((path,), (), "markers")
    source = import_forces(path)
    assert isinstance(source, ImportSuccess)
    analysis = prepare_recording_analysis(
        source,
        original.configuration,
        revision=0,
        calculation_time=datetime.now(UTC),
    )
    reason = analysis.forces.smoothed.availability.reason
    assert reason is not None
    with pytest.raises(ValueError, match=reason.message):
        batches.make_job(analysis, preset)
    smoothed = replace(
        analysis.forces.smoothed,
        availability=replace(
            analysis.forces.smoothed.availability,
            reason=None,
        ),
    )
    with pytest.raises(ValueError, match="Calibrated forces are unavailable"):
        batches.make_job(
            replace(analysis, forces=replace(analysis.forces, smoothed=smoothed)),
            preset,
        )


def test_batch_preparation_closes_service_when_no_snapshot_is_returned(
    monkeypatch: pytest.MonkeyPatch,
    export_directory: Path,
) -> None:
    analysis = snapshot()
    preset = make_preset("Prepared", ExportSettings(), 3, "markers", analysis.configuration)
    job = BatchJob(
        recording_path=(export_directory / "source.forces").resolve(),
        source_sha256=analysis.source.source_sha256,
        ride="Synthetic",
        preset=preset,
        range_mode="markers",
        first_sample=0,
        last_sample=0,
    )
    batch = SavedBatch(schema_version=1, name="Preparation", jobs=(job,))
    state = Mock(snapshot=None, failure=None)
    service = Mock()
    service.get_state.return_value = state
    monkeypatch.setattr(batches, "import_forces", Mock(return_value=analysis.source))
    monkeypatch.setattr(batches, "AnalysisService", lambda: service)
    for failure in (None, Mock(message="Preparation rejected")):
        state.failure = failure
        result = batches.run_batches((batch,), export_directory)
        assert result.results[0].status == "failed"
        assert result.results[0].error == (
            "Prepared recording analysis is unavailable"
            if failure is None
            else "Preparation rejected"
        )
        service.close.assert_called_once()
        service.reset_mock()
