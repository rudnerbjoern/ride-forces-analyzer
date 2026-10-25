"""CSV and both JSON serializers retain their shared input rejection contracts."""

from pathlib import Path
from typing import cast

import pytest

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.exports.csv import export_csv
from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.exports.json import export_analyzer_json, export_json
from tests.exports.test_csv_export import snapshot


@pytest.mark.parametrize("format", list(DataExportFormat))
def test_shared_validation_preserves_format_errors_and_destination(
    export_directory: Path,
    format: DataExportFormat,
) -> None:
    exporter = {
        DataExportFormat.CSV: export_csv,
        DataExportFormat.JSON: export_json,
        DataExportFormat.ANALYZER_JSON: export_analyzer_json,
    }[format]
    suffix = "csv" if format is DataExportFormat.CSV else "json"
    label = suffix.upper()
    path = export_directory / f"output.{suffix}"
    analysis = snapshot()
    with pytest.raises(TypeError) as error:
        exporter(cast(RecordingAnalysis, object()), path, 0, 0)
    assert str(error.value) == f"{label} export requires RecordingAnalysis"
    with pytest.raises(TypeError) as error:
        exporter(analysis, path, True, 1)
    assert str(error.value) == f"{label} sample indices must be integers"
    for first, last in [(-1, 0), (2, 1), (0, len(analysis.time.source_indices))]:
        with pytest.raises(ValueError) as invalid:
            exporter(analysis, path, first, last)
        assert str(invalid.value) == f"{label} export requires a bounded inclusive sample range"
    wrong_suffix = path.with_suffix(".forces")
    wrong_suffix.write_bytes(b"preserve existing destination")
    with pytest.raises(ValueError) as invalid:
        exporter(analysis, wrong_suffix, 0, 0, overwrite=True)
    assert str(invalid.value) == f"{label} export requires a .{suffix} destination"
    assert wrong_suffix.read_bytes() == b"preserve existing destination"
    assert not path.exists()
    uppercase_suffix = path.with_suffix(f".{label}")
    assert exporter(analysis, uppercase_suffix, 0, 0) == 1
    assert uppercase_suffix.is_file()
