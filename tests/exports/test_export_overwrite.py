"""Confirmed replacement preserves existing output until successful completion."""

from pathlib import Path

import pytest

from ride_forces_analyzer.csv_export import CsvExportCancelled, export_csv
from ride_forces_analyzer.json_export import JsonExportCancelled, export_json, export_analyzer_json
from tests.exports.test_csv_export import snapshot


@pytest.mark.parametrize("format", ["csv", "json", "analyzer_json"])
def test_confirmed_overwrite_matches_new_export(export_directory: Path, format: str) -> None:
    exporter = {
        "csv": export_csv,
        "json": export_json,
        "analyzer_json": export_analyzer_json,
    }[format]
    suffix = "csv" if format == "csv" else "json"
    path = export_directory / f"existing.{suffix}"
    path.write_bytes(b"previous export")
    expected = export_directory / f"new.{suffix}"
    analysis = snapshot()
    exporter(analysis, expected, 1, 4)

    def progress(count: int) -> None:
        assert path.read_bytes() == b"previous export"

    assert exporter(analysis, path, 1, 4, overwrite=True, progress=progress) == 4
    assert path.read_bytes() == expected.read_bytes()
    assert set(export_directory.iterdir()) == {path, expected}


@pytest.mark.parametrize("format", ["csv", "json", "analyzer_json"])
@pytest.mark.parametrize("failure", ["cancel", "write"])
def test_failed_overwrite_keeps_previous_export(
    export_directory: Path,
    format: str,
    failure: str,
) -> None:
    exporter = {
        "csv": export_csv,
        "json": export_json,
        "analyzer_json": export_analyzer_json,
    }[format]
    suffix = "csv" if format == "csv" else "json"
    cancellation = JsonExportCancelled if format != "csv" else CsvExportCancelled
    path = export_directory / f"existing.{suffix}"
    path.write_bytes(b"previous export")
    cancel = False

    def progress(count: int) -> None:
        nonlocal cancel
        assert path.read_bytes() == b"previous export"
        if failure == "write":
            raise OSError("writing failed")
        cancel = True

    with pytest.raises(OSError if failure == "write" else cancellation):
        exporter(
            snapshot(),
            path,
            0,
            5,
            overwrite=True,
            cancelled=lambda: cancel,
            progress=progress,
        )
    assert path.read_bytes() == b"previous export"
    assert list(export_directory.iterdir()) == [path]


@pytest.mark.parametrize("format", ["csv", "json", "analyzer_json"])
def test_replacement_failure_keeps_previous_export(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    format: str,
) -> None:
    exporter = {
        "csv": export_csv,
        "json": export_json,
        "analyzer_json": export_analyzer_json,
    }[format]
    suffix = "csv" if format == "csv" else "json"
    path = export_directory / f"existing.{suffix}"
    path.write_bytes(b"previous export")

    def blocked_replace(source: Path, target: Path) -> Path:
        raise PermissionError("destination is locked")

    monkeypatch.setattr(Path, "replace", blocked_replace)
    with pytest.raises(PermissionError, match="destination is locked"):
        exporter(snapshot(), path, 0, 5, overwrite=True)
    assert path.read_bytes() == b"previous export"
    assert list(export_directory.iterdir()) == [path]
