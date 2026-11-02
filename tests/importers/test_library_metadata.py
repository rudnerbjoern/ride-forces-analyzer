"""Source-evidenced Library names, dates and original-byte preservation."""

# cspell:words Seaworld Phantasialand Bobbejaanland tzset

from dataclasses import replace
from pathlib import Path
import time

import pytest

from ride_forces_analyzer.domain import Recording, RecordingMetadata, SourceNumber
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from ride_forces_analyzer.importers.library_metadata import (
    LibraryMetadata,
    project_library_metadata,
)
from tests.support.recordings import (
    REAL_FIXTURE_DIRECTORY,
    REAL_FIXTURES,
    RFDB_FIXTURE_DIRECTORY,
    RFDB_FIXTURES,
)

EXPECTED = {
    "IronGwazi": ("Iron Gwazi", "Busch Gardens Tampa", "2026-09-25"),
    "Kraken": ("Kraken", "SeaWorld Orlando", "2026-09-17"),
    "Manta": ("Manta", "Seaworld Orlando", "2026-09-17"),
    "Taron": ("Taron", "Phantasialand", "2024-09-27"),
    "VoltronNevera": ("Voltron Nevera", "Europa-Park", "2025-03-20"),
    "Typhoon": ("Typhoon", "Bobbejaanland", None),
}


@pytest.mark.parametrize(
    ("directory", "filename", "identity"),
    [
        (directory, filename, identity)
        for directory, fixtures in (
            (REAL_FIXTURE_DIRECTORY, REAL_FIXTURES),
            (RFDB_FIXTURE_DIRECTORY, RFDB_FIXTURES),
        )
        for filename, identity in fixtures.items()
    ],
)
def test_authorized_source_projection(
    directory: Path,
    filename: str,
    identity: tuple[int, str],
) -> None:
    path = directory / filename
    original = path.read_bytes()
    modified = path.stat().st_mtime_ns
    imported = import_forces(path)
    assert isinstance(imported, ImportSuccess)
    projected = project_library_metadata(imported.recording)
    name, park, day = EXPECTED[filename.split("-", 1)[0]]
    assert (projected.source_ride_name, projected.source_park_name) == (name, park)
    assert projected.recorded_day == day
    assert projected.source_date is imported.recording.metadata.date
    assert projected.source_timezone == imported.recording.metadata.timezone
    assert imported.recording.source.original_bytes == path.read_bytes() == original
    assert (imported.byte_count, imported.source_sha256) == identity
    assert path.stat().st_mtime_ns == modified


def test_manta_original_app_date_and_compressed_projection() -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    results = [import_forces(path), import_forces(path.with_suffix(".zforces"))]
    assert all(isinstance(result, ImportSuccess) for result in results)
    projections = [
        project_library_metadata(result.recording)
        for result in results
        if isinstance(result, ImportSuccess)
    ]
    assert projections[0] == projections[1]
    projected = projections[0]
    assert projected.recorded_at_utc == "2026-09-17T14:17:41.330959Z"
    assert projected.day_timezone == "America/New_York"
    assert projected.source_date == SourceNumber("811347461.3309591")
    # Owner's original-app display: 2026-09-17 10:18, precision one minute.
    # The projected local instant is 10:17:41, within that observation's precision.


@pytest.mark.parametrize("name,park", [(None, None), ("", ""), (" Ride ", " Park ")])
def test_names_keep_missing_empty_and_original_spelling(
    synthetic_recording: Recording,
    name: str | None,
    park: str | None,
) -> None:
    recording = replace(synthetic_recording, metadata=RecordingMetadata(name=name, location=park))
    projected = project_library_metadata(recording)
    assert (projected.source_ride_name, projected.source_park_name) == (name, park)


@pytest.mark.parametrize("date", [None, "1e999", "-1e999", "252423993600", "-63113904001"])
def test_missing_or_unrepresentable_dates_stay_unknown(
    synthetic_recording: Recording,
    date: str | None,
) -> None:
    metadata = RecordingMetadata(date=SourceNumber(date) if date else None)
    projected = project_library_metadata(replace(synthetic_recording, metadata=metadata))
    assert (projected.recorded_at_utc, projected.recorded_day, projected.day_timezone) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("timezone", [None, "", "invalid", "/invalid", "Europe/Berlin"])
def test_day_preserves_recording_location_independently_of_host_zone(
    synthetic_recording: Recording,
    timezone: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_localtime(seconds: float | None = None) -> time.struct_time:
        pytest.fail("Host zone consulted")

    # 2001-01-01 23:30 UTC is already January 2 at the recording location in Berlin.
    metadata = RecordingMetadata(date=SourceNumber("84600.0000000"), timezone=timezone)
    recording = replace(synthetic_recording, metadata=metadata)
    projections: list[LibraryMetadata] = []
    for host_zone in ("Pacific/Honolulu", "Asia/Tokyo"):
        monkeypatch.setenv("TZ", host_zone)
        # Windows has no tzset; rejecting localtime also catches accidental host-zone use.
        monkeypatch.setattr(time, "localtime", reject_localtime)
        projections.append(project_library_metadata(recording))
    assert projections[0] == projections[1]
    projected = projections[0]
    assert projected.recorded_at_utc == "2001-01-01T23:30:00.000000Z"
    assert projected.recorded_day == ("2001-01-02" if timezone == "Europe/Berlin" else "2001-01-01")
    assert projected.day_timezone == ("Europe/Berlin" if timezone == "Europe/Berlin" else "UTC")


@pytest.mark.parametrize("date", [b'"invalid"', b"null", b"true"])
def test_invalid_optional_date_does_not_prevent_projection(date: bytes) -> None:
    raw = (
        b'{"schemaVersion":"2.2.0","accelerationSequence":[{"x":"0","y":"0","z":"1"}],'
        b'"date":' + date + b',"unknown":{"kept":true}}'
    )
    imported = import_forces_bytes(raw)
    assert isinstance(imported, ImportSuccess)
    projected = project_library_metadata(imported.recording)
    assert projected.source_date is None
    assert projected.recorded_day is None
    assert imported.recording.source.original_bytes == raw
