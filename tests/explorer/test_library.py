"""Archive originals once and reopen them independently of external paths."""

from hashlib import sha256
from pathlib import Path

import pytest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError
from ride_forces_analyzer.storage.preferences import Preferences
from tests.analysis.test_recording_preparation import synthetic_source
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


@pytest.fixture
def archive(export_directory: Path) -> LibraryArchive:
    return LibraryArchive(
        LibraryStore(export_directory / "library.sqlite3"),
        Preferences(export_directory / "preferences.sqlite3"),
    )


@pytest.mark.parametrize("extension", ["forces", "zforces"])
def test_authorized_originals_reopen_without_external_files(
    archive: LibraryArchive,
    export_directory: Path,
    extension: str,
) -> None:
    fixture = next(REAL_FIXTURE_DIRECTORY.glob(f"Manta-*.{extension}"))
    raw = fixture.read_bytes()
    modified = fixture.stat().st_mtime_ns
    original = import_forces_bytes(raw, compressed=extension == "zforces")
    assert isinstance(original, ImportSuccess)
    expected = (
        (91361, "005ce708ec946bcf4dbe0163fc2fb23c629b65c1ed11706000c130855c4ba1e5")
        if extension == "zforces"
        else REAL_FIXTURES[fixture.name]
    )
    assert (len(raw), sha256(raw).hexdigest()) == expected
    path = export_directory / f"original.{extension}"
    path.write_bytes(raw)
    result = archive.import_paths((path,))[0]
    assert result.status == "imported" and result.source_sha256 == expected[1]
    if extension == "forces":
        path.rename(path.with_name("moved.forces"))
    else:
        path.unlink()
    reopened = archive.reopen(expected[1])
    assert isinstance(reopened, ExplorerData)
    assert reopened.source.recording.source.original_bytes == raw
    assert reopened.source.recording.source.root == original.recording.source.root
    assert reopened.source.recording.gps == original.recording.gps
    assert reopened.source.recording.metadata == original.recording.metadata
    assert reopened.source.source_sha256 == expected[1]
    assert reopened.source.byte_count == expected[0]
    assert reopened.source.recording.source.provenance.path is None
    assert reopened.analysis is not None
    assert fixture.read_bytes() == raw and fixture.stat().st_mtime_ns == modified
    with archive.store.connection() as connection:
        row = connection.execute(
            "SELECT source_filename,source_format,source_byte_count,workflow_status FROM recordings",
        ).fetchone()
        assert row == (f"original.{extension}", extension, len(raw), "imported")


def test_duplicate_preserves_complete_entry_and_relationships(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 7)
    path = export_directory / "first.forces"
    path.write_bytes(source.recording.source.original_bytes)
    bounds = (1, 2)
    calibration = CalibrationOverrides(gravity_index=3)
    assert archive.preferences.remember_recording_markers(source, bounds, calibration)
    result = archive.import_paths((path,))[0]
    assert result.status == "imported"
    stored = archive.store.source(source.source_sha256)
    assert stored.bounds == bounds and stored.calibration == calibration
    reopened = archive.reopen(source.source_sha256)
    assert isinstance(reopened, ExplorerData)
    assert reopened.ride_bounds == bounds
    assert (
        reopened.analysis is not None and reopened.analysis.configuration.calibration == calibration
    )
    with archive.store.connection() as connection:
        connection.execute(
            "UPDATE recordings SET notes='keep',row_override='Front',ride_name_override='User ride',workflow_status='uploaded'",
        )
        connection.execute(
            "INSERT INTO video_links(recording_sha256,url,label) VALUES (?, 'https://example.com/video', 'Custom')",
            (source.source_sha256,),
        )
        connection.execute(
            "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,status,application_version,request_json) VALUES (?, 'csv','single','2026-11-01T10:00:00.000000Z','failed','1.3.0','{}')",
            (source.source_sha256,),
        )
        before = connection.execute("SELECT * FROM recordings").fetchone()
        history = connection.execute("SELECT * FROM export_history").fetchall()
        links = connection.execute("SELECT * FROM video_links").fetchall()
    archive.preferences.remember_recording_markers(source, None, CalibrationOverrides())
    renamed = export_directory / "other-name.forces"
    renamed.write_bytes(path.read_bytes())
    result = archive.import_paths((renamed,))[0]
    assert result.status == "duplicate" and result.source_sha256 == source.source_sha256
    with archive.store.connection() as connection:
        assert connection.execute("SELECT * FROM recordings").fetchone() == before
        assert connection.execute("SELECT * FROM export_history").fetchall() == history
        assert connection.execute("SELECT * FROM video_links").fetchall() == links
    # Identical parsed values, UUID and dates do not make different original bytes duplicates.
    renamed.write_bytes(path.read_bytes() + b"\n")
    different = archive.import_paths((renamed,))[0]
    assert different.status == "imported" and different.source_sha256 != source.source_sha256


def test_failed_files_and_failed_transaction_do_not_stop_other_imports(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    source = synthetic_source()
    bad = export_directory / "bad.forces"
    bad.write_bytes(b"invalid JSON")
    rejected = export_directory / "rejected.forces"
    good = export_directory / "good.forces"
    rejected.write_bytes(source.recording.source.original_bytes)
    good.write_bytes(source.recording.source.original_bytes)
    with archive.store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_selected BEFORE INSERT ON recordings WHEN NEW.source_filename='rejected.forces' BEGIN SELECT RAISE(ABORT, 'injected write failure'); END",
        )
    results = archive.import_paths((bad, rejected, good, good))
    assert [result.status for result in results] == ["failed", "failed", "imported", "duplicate"]
    assert results[0].error and results[1].error
    with archive.store.connection() as connection:
        assert connection.execute("SELECT source_filename FROM recordings").fetchall() == [
            ("good.forces",),
        ]


def test_invalid_saved_markers_fall_back_without_rewriting_preferences(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    source = synthetic_source()
    path = export_directory / "source.forces"
    path.write_bytes(source.recording.source.original_bytes)
    assert archive.preferences.remember_recording_bounds(source.source_sha256, (1, 99999))
    assert archive.import_paths((path,))[0].status == "imported"
    assert archive.store.source(source.source_sha256).bounds == (
        source.recording.indices.start,
        source.recording.indices.end,
    )
    assert archive.preferences.recording_bounds(source.source_sha256) == (1, 99999)


def test_corrupt_archived_bytes_are_rejected_without_replacing_entry(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    path = export_directory / "source.forces"
    source = synthetic_source()
    path.write_bytes(source.recording.source.original_bytes)
    assert archive.import_paths((path,))[0].status == "imported"
    with archive.store.connection() as connection:
        connection.execute("UPDATE recordings SET source_bytes=?", (b"x" * source.byte_count,))
    before = archive.store.path.read_bytes()
    with pytest.raises(LibraryStoreError, match="integrity"):
        archive.reopen(source.source_sha256)
    assert archive.store.path.read_bytes() == before
