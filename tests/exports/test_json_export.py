"""App-shaped JSON, prepared sample correspondence and safe output lifecycle."""

import csv
from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import cast

import pytest

from ride_forces_analyzer.analysis.recording import (
    RecordingAnalysis,
)
from ride_forces_analyzer.analysis.preparation import (
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.exports.csv import export_csv
from ride_forces_analyzer.domain import SourceNumber
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.exports.json import (
    JSON_SAMPLE_KEYS,
    JsonExportCancelled,
    export_json,
)
from tests.exports.test_csv_export import snapshot
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_manta_app_shape_and_every_sample_match_csv(export_directory: Path) -> None:
    reference = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.json"))
    original = reference.read_bytes()
    imported = import_forces(reference.with_suffix(".forces"))
    assert isinstance(imported, ImportSuccess)
    analysis = prepare_recording_analysis(
        imported,
        source_app_configuration(),
        revision=0,
        calculation_time=datetime(2026, 10, 21, tzinfo=UTC),
    )
    first, last = imported.recording.indices.start, imported.recording.indices.end
    path = export_directory / "manta.json"
    assert export_json(analysis, path, first, last) == 6888
    encoded = path.read_bytes()
    result = json.loads(encoded)
    app = json.loads(original)
    assert list(result)[:5] == list(app)
    assert list(result) == [*JSON_SAMPLE_KEYS, "metadata"]
    assert all(len(result[key]) == 6888 for key in JSON_SAMPLE_KEYS)
    assert not encoded.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in encoded and encoded.endswith(b"\n}")
    lines = encoded.decode().splitlines()
    assert len(lines) == len(result) + 2
    assert all(line.startswith('\t"') and '": ' in line for line in lines[1:-1])
    assert all(", " not in line for line in lines[1:-1])
    csv_path = export_directory / "manta.csv"
    export_csv(analysis, csv_path, first, last)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for offset, row in enumerate(rows):
        for key in app:
            assert result[key][offset] == float(row[key])
        assert result["Timestamp"][offset] == row["Timestamp"]
        assert result["sample_index"][offset] == int(row["sample_index"])
        assert result["vertical_context"][offset] == row["vertical_context"]
        assert result["capabilities"][offset] == dict(
            item.split("=") for item in row["capabilities"].split(";")
        )
    assert result["metadata"]["recording"]["name"] == imported.recording.metadata.name
    date = imported.recording.metadata.date
    assert result["metadata"]["recording"]["date"] == (date.token if date else None)
    assert result["metadata"]["source_indices"]["start"] == first
    assert result["metadata"]["first_sample"] == first
    assert result["metadata"]["last_sample"] == last
    assert reference.read_bytes() == original


@pytest.mark.parametrize("calibrated", [True, False])
def test_prepared_values_metadata_and_nulls(
    export_directory: Path,
    calibrated: bool,
) -> None:
    analysis = snapshot(calibrated=calibrated)
    # Preserve numeric source-date tokens without converting them to an epoch.
    recording = analysis.source.recording
    analysis = replace(
        analysis,
        source=replace(
            analysis.source,
            recording=replace(
                recording,
                metadata=replace(recording.metadata, date=SourceNumber("123.4500")),
            ),
        ),
    )
    path = export_directory / "samples.JSON"
    progress: list[int] = []
    assert export_json(analysis, path, 1, 4, progress=progress.append) == 4
    result = json.loads(path.read_bytes())
    assert progress == [4]
    assert result["sample_index"] == [1, 2, 3, 4]
    assert result["Timestamp"] == ["-00:00.01", "00:00.00", "00:00.01", "00:00.02"]
    assert result["raw_x_source"] == [0.0] * 4
    assert result["metadata"]["recording"]["date"] == "123.4500"
    assert result["metadata"]["smoothing_window_samples"] == 3
    for offset, index in enumerate(range(1, 5)):
        sample = analysis.sample(index)
        assert result["Vertical Forces (g)"][offset] == (
            sample.smoothed.vertical if sample.smoothed else None
        )
        assert result["Combined Forces (g)"][offset] == sample.combined_g
        assert result["Tilt Angle Orientation (degrees)"][offset] == sample.orientation_degrees
        assert result["vertical_context"][offset] == (
            sample.context.value if sample.context is not None else None
        )
        assert result["diagnostic_codes"][offset] == [d.code for d in sample.quality.diagnostics]
    if not calibrated:
        assert result["Vertical Forces (g)"] == [None] * 4
        assert result["projected_vertical_g"] == [None] * 4
        assert result["Combined Forces (g)"] == [None] * 4


@pytest.mark.parametrize("first,last", [(-1, 2), (4, 2), (0, 6), (True, 2), (0, 2.0)])
def test_invalid_interval_does_not_create_output(
    export_directory: Path,
    first: int,
    last: int,
) -> None:
    path = export_directory / "invalid.json"
    with pytest.raises((TypeError, ValueError)):
        export_json(snapshot(), path, first, last)
    assert not path.exists()


def test_invalid_inputs_and_existing_files_are_preserved(export_directory: Path) -> None:
    path = export_directory / "existing.json"
    path.write_bytes(b"unchanged")
    with pytest.raises(FileExistsError):
        export_json(snapshot(), path, 0, 1)
    assert path.read_bytes() == b"unchanged"
    with pytest.raises(TypeError):
        export_json(cast(RecordingAnalysis, object()), path, 0, 1)
    with pytest.raises(ValueError):
        export_json(snapshot(), path.with_suffix(".forces"), 0, 1)


@pytest.mark.parametrize("after", [0, 250, 600])
def test_cancel_removes_only_partial_output(export_directory: Path, after: int) -> None:
    path = export_directory / "cancelled.json"
    written = 0

    def progress(count: int) -> None:
        nonlocal written
        written = count

    with pytest.raises(JsonExportCancelled):
        export_json(
            snapshot(count=600),
            path,
            0,
            599,
            cancelled=lambda: written >= after,
            progress=progress,
        )
    assert not path.exists()


def test_callback_failure_removes_partial_output(export_directory: Path) -> None:
    path = export_directory / "failed.json"

    def fail(count: int) -> None:
        raise OSError("callback failed")

    with pytest.raises(OSError, match="callback failed"):
        export_json(snapshot(), path, 0, 5, progress=fail)
    assert not path.exists()


def test_cancellation_during_encoding_removes_written_output(export_directory: Path) -> None:
    path = export_directory / "encoding.json"
    observed_output = False

    def cancel_after_write() -> bool:
        nonlocal observed_output
        observed_output = path.exists() and path.stat().st_size > 0
        return observed_output

    with pytest.raises(JsonExportCancelled):
        export_json(snapshot(count=600), path, 0, 599, cancelled=cancel_after_write)
    assert observed_output
    assert not path.exists()
