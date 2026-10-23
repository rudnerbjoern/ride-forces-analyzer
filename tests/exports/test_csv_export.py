"""CSV output preserves prepared samples, missingness and quality."""

import csv
from dataclasses import replace
from datetime import UTC, datetime
import json
from math import hypot
from pathlib import Path
from threading import Event
from typing import cast

import pytest

from ride_forces_analyzer.analysis.recording import (
    RecordingAnalysis,
    StageConfiguration,
    prepare_recording_analysis,
    source_app_configuration,
)
from ride_forces_analyzer.csv_export import CSV_COLUMNS, CsvExportCancelled, export_csv
from ride_forces_analyzer.i18n import get_language, set_language
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


def test_user_start_marker_defines_csv_replay_zero(export_directory: Path) -> None:
    original = snapshot()
    analysis = original.with_configuration(
        replace(original.configuration, ride_bounds=(1, 3)),
        revision=1,
        calculation_time=datetime.now(UTC),
    )
    destination = export_directory / "markers.csv"
    export_csv(analysis, destination, 1, 3)
    exported = rows(destination)
    assert exported[0]["Timestamp"] == "00:00.00"
    assert float(exported[0]["replay_seconds"]) == 0
    assert analysis.source.recording.indices.start == 2


def test_shared_measurement_headers_match_the_source_app_csv() -> None:
    reference = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.csv"))
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        app_columns = next(csv.reader(stream))
    assert CSV_COLUMNS[: len(app_columns)] == tuple(app_columns)


def test_manta_timestamps_match_every_source_app_csv_row(export_directory: Path) -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    imported = import_forces(path)
    assert isinstance(imported, ImportSuccess)
    analysis = prepare_recording_analysis(
        imported,
        source_app_configuration(),
        revision=0,
        calculation_time=datetime(2026, 10, 21, tzinfo=UTC),
    )
    output = export_directory / "manta.csv"
    export_csv(analysis, output, imported.recording.indices.start, imported.recording.indices.end)
    with path.with_suffix(".csv").open(encoding="utf-8-sig", newline="") as stream:
        expected = [row["Timestamp"] for row in csv.DictReader(stream)]
    assert [row["Timestamp"] for row in rows(output)] == expected


@pytest.mark.parametrize(
    "rate,first,last,expected",
    [
        (50.0, 0, 2, ["-00:00.02", "-00:00.01", "00:00.00"]),
        (50.0, 51, 53, ["00:00.49", "00:01.00", "00:01.01"]),
        (25.0, 26, 28, ["00:00.24", "00:01.00", "00:01.01"]),
        (59.94, 1, 3, ["-0.017 s", "0.000 s", "0.017 s"]),
    ],
)
def test_timestamp_retains_replay_origin_and_sample_counter(
    export_directory: Path,
    rate: float,
    first: int,
    last: int,
    expected: list[str],
) -> None:
    output = export_directory / "time.csv"
    export_csv(snapshot(count=last + 1, rate=rate), output, first, last)
    assert [row["Timestamp"] for row in rows(output)] == expected


def snapshot(*, calibrated: bool = True, count: int = 6, rate: float = 50) -> RecordingAnalysis:
    values = (1.0, 0.5, 0.0, -0.5, 0.0, 1.0)
    payload: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "iPhone",
        "sampleRate": rate,
        "startIndex": 2,
        "accelerationSequence": [
            {"x": 0, "y": -0.3, "z": values[index % len(values)]} for index in range(count)
        ],
        "preservedUnknownField": {"value": "original"},
    }
    if calibrated:
        payload.update(
            gravitySequence=[
                {"x": 0, "y": 0, "z": 0 if index == 2 else 1} for index in range(count)
            ],
            verticalDirectionVector={"x": 0, "y": 0, "z": 1},
            lateralDirectionVector={"x": 1, "y": 0, "z": 0},
            longitudinalDirectionVector={"x": 0, "y": 1, "z": 0},
        )
    imported = import_forces_bytes(json.dumps(payload).encode())
    assert isinstance(imported, ImportSuccess)
    configuration = replace(
        source_app_configuration(),
        smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 3),)),
    )
    return prepare_recording_analysis(
        imported,
        configuration,
        revision=0,
        calculation_time=datetime(2026, 10, 21, tzinfo=UTC),
    )


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == list(CSV_COLUMNS)
        return list(reader)


@pytest.mark.parametrize("rate", [25.0, 50.0, 59.94])
def test_inclusive_csv_retains_full_history_smoothing_time_context_and_provenance(
    export_directory: Path,
    rate: float,
) -> None:
    analysis = snapshot(rate=rate)
    original = analysis.source.recording.source.original_bytes
    path = export_directory / "selection.csv"
    assert export_csv(analysis, path, 1, 4) == 4
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    result = rows(path)
    assert [int(row["sample_index"]) for row in result] == [1, 2, 3, 4]
    for row, expected in zip(result, (0.5, 0.0, -1 / 6, 1 / 6), strict=True):
        index = int(row["sample_index"])
        assert float(row["recording_seconds"]) == index / rate
        assert float(row["replay_seconds"]) == (index - 2) / rate
        assert float(row["Vertical Forces (g)"]) == pytest.approx(expected)
        assert float(row["Lateral Forces (g)"]) == 0.0
        assert float(row["projected_vertical_g"]) == (0.5, 0.0, -0.5, 0.0)[index - 1]
        assert float(row["raw_x_source"]) == 0.0
        assert float(row["Longitudinal Forces (g)"]) == pytest.approx(-0.3)
        assert float(row["Combined Forces (g)"]) == pytest.approx(hypot(expected, -0.3))
        assert row["smoothing_window_samples"] == "3"
        assert row["time_basis"] == "inferred_uniform"
        assert float(row["sample_rate_hz"]) == rate
        assert "projection=provisional" in row["capabilities"]
        context = analysis.sample(index).context
        assert context is not None and row["vertical_context"] == context.value
    assert result[1]["Tilt Angle Orientation (degrees)"] == ""
    assert result[1]["diagnostic_codes"]
    assert result[0]["Tilt Angle Orientation (degrees)"] == "0.0"
    assert analysis.source.recording.source.original_bytes == original


def test_raw_export_keeps_zero_and_leaves_unavailable_results_empty(export_directory: Path) -> None:
    path = export_directory / "raw.csv"
    export_csv(snapshot(calibrated=False), path, 0, 0)
    row = rows(path)[0]
    assert float(row["raw_x_source"]) == 0.0
    assert float(row["raw_z_source"]) == 1.0
    for column in (
        "projected_vertical_g",
        "Vertical Forces (g)",
        "Combined Forces (g)",
        "Tilt Angle Orientation (degrees)",
        "vertical_context",
    ):
        assert row[column] == ""
    assert "projection=unavailable" in row["capabilities"]
    assert row["diagnostic_codes"]


def test_csv_is_locale_independent_and_retains_the_bound_snapshot(export_directory: Path) -> None:
    analysis = snapshot()
    updated = analysis.with_configuration(
        replace(
            analysis.configuration,
            smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 1),)),
        ),
        revision=1,
        calculation_time=datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert updated.forces.smoothed is not analysis.forces.smoothed
    english, german = export_directory / "english.csv", export_directory / "german.csv"
    language = get_language()
    try:
        set_language("en")
        export_csv(analysis, english, 0, 5)
        set_language("de")
        export_csv(analysis, german, 0, 5)
    finally:
        set_language(language)
    assert english.read_bytes() == german.read_bytes()
    assert rows(german)[1]["smoothing_window_samples"] == "3"


@pytest.mark.parametrize("first,last", [(-1, 1), (2, 1), (0, 6)])
def test_invalid_ranges_do_not_create_a_file(export_directory: Path, first: int, last: int) -> None:
    path = export_directory / "invalid.csv"
    with pytest.raises(ValueError, match="range"):
        export_csv(snapshot(), path, first, last)
    assert not path.exists()


def test_invalid_destination_and_existing_files_are_preserved(export_directory: Path) -> None:
    analysis = snapshot()
    for name, exception in (("original.forces", ValueError), ("existing.csv", FileExistsError)):
        path = export_directory / name
        path.write_bytes(b"preserve exact bytes")
        with pytest.raises(exception):
            export_csv(analysis, path, 0, 5)
        assert path.read_bytes() == b"preserve exact bytes"
    with pytest.raises(TypeError, match="integers"):
        export_csv(analysis, export_directory / "bool.csv", True, 5)
    with pytest.raises(TypeError, match="RecordingAnalysis"):
        export_csv(cast(RecordingAnalysis, object()), export_directory / "wrong.csv", 0, 0)


@pytest.mark.parametrize("before_start", [False, True])
def test_cancellation_removes_only_the_incomplete_file(
    export_directory: Path,
    before_start: bool,
) -> None:
    path = export_directory / "cancelled.csv"
    cancelled = Event()
    if before_start:
        cancelled.set()
    progress: list[int] = []

    def stop(count: int) -> None:
        progress.append(count)
        cancelled.set()

    with pytest.raises(CsvExportCancelled):
        export_csv(snapshot(count=600), path, 0, 599, cancelled=cancelled.is_set, progress=stop)
    assert progress == ([] if before_start else [250])
    assert not path.exists()


def test_failed_write_removes_partial_output(export_directory: Path) -> None:
    path = export_directory / "failed.csv"

    def fail(count: int) -> None:
        raise OSError("Simulated write failure")

    with pytest.raises(OSError, match="Simulated"):
        export_csv(snapshot(), path, 0, 5, progress=fail)
    assert not path.exists()
