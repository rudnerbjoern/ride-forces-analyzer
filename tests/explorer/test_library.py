"""Archive originals once and reopen them independently of external paths."""

# cspell:words wbits Straße strasse Ｒｉｄｅ

from hashlib import sha256
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import json
import zlib

import pytest

from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.preparation import source_app_configuration
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer import load_recording
from ride_forces_analyzer.domain import SourceNumber, ValueOrigin
from ride_forces_analyzer.explorer.library import LibraryArchive, library_details, recording_clock
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


def test_marker_authority_validation_and_atomic_failure(archive: LibraryArchive) -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    data = load_recording(path)
    assert isinstance(data, ExplorerData)
    source = data.source
    digest = source.source_sha256
    archive.preferences.remember_recording_markers(source, (3000, 4000), CalibrationOverrides())
    assert archive.import_paths((path,))[0].status == "imported"
    assert archive.store.markers(source) == ((3000, 4000), CalibrationOverrides())
    archive.store.set_workflow_status(digest, "uploaded")
    before = archive.store.source(digest)
    entry = archive.store.entries()[0]
    indices = source.recording.indices
    assert indices.gravity is not None and indices.incline is not None
    calibration = CalibrationOverrides(gravity_index=indices.gravity, incline_index=indices.incline)
    assert indices.gravity < 5000 and indices.incline < 5000
    assert archive.remember_recording_markers(source, (5000, 6000), calibration)
    # Preferences deliberately disagree; byte identity makes the Library authoritative.
    configuration = archive.recording_configuration(
        source,
        source_app_configuration(),
        calculation_time=datetime.now(UTC),
    )
    assert configuration.ride_bounds == (5000, 6000)
    assert configuration.calibration == calibration
    reopened = archive.reopen(digest)
    assert isinstance(reopened, ExplorerData) and reopened.analysis is not None
    assert reopened.ride_bounds == (5000, 6000)
    assert reopened.analysis.configuration.calibration == calibration
    for bounds in ((-1, 5), (6, 5), (0, len(source.recording.motion.acceleration)), (True, 5)):
        with pytest.raises(ValueError):
            archive.store.update_markers(source, bounds, calibration)
    with pytest.raises(ValueError):
        archive.store.update_markers(
            source,
            (5000, 6000),
            CalibrationOverrides(gravity_index=len(source.recording.motion.acceleration)),
        )
    assert archive.store.markers(source) == ((5000, 6000), calibration)
    with archive.store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_markers BEFORE UPDATE OF first_sample ON recordings "
            "BEGIN SELECT RAISE(ABORT, 'injected marker failure'); END",
        )
    assert not archive.remember_recording_markers(source, None, CalibrationOverrides())
    assert archive.store.markers(source) == ((5000, 6000), calibration)
    assert archive.preferences.recording_bounds(digest) == (3000, 4000)
    with archive.store.connection() as connection:
        connection.execute("DROP TRIGGER reject_markers")
    assert archive.remember_recording_markers(source, None, CalibrationOverrides())
    assert archive.store.markers(source) == ((indices.start, indices.end), CalibrationOverrides())
    assert archive.store.source(digest) == replace(before, bounds=(indices.start, indices.end))
    assert archive.store.entries()[0] == entry


def test_reset_keeps_absent_source_markers_absent(archive: LibraryArchive) -> None:
    imported = synthetic_source(
        startIndex=None,
        endIndex=None,
        gravityIndex=None,
        inclineIndex=None,
    )
    indices = imported.recording.indices
    archive.store.archive(
        imported,
        "missing.forces",
        (indices.start, indices.end),
        CalibrationOverrides(),
    )
    assert archive.remember_recording_markers(imported, (1, 2), CalibrationOverrides())
    assert archive.remember_recording_markers(imported, None, CalibrationOverrides())
    reopened = archive.reopen(imported.source_sha256)
    assert isinstance(reopened, ExplorerData) and reopened.markers == ()
    configuration = archive.recording_configuration(
        imported,
        source_app_configuration(),
        calculation_time=datetime.now(UTC),
    )
    assert configuration.ride_bounds is None


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
    entry = archive.store.entries()[0]
    assert recording_clock(entry) == "10:17:41"
    details = library_details(entry, reopened)
    assert "Recording time: 2026-09-17 10:17" in details
    assert "Import time:" in details and entry.imported_at_utc not in details
    assert "America/New_York" not in details
    assert "Source date:" not in details and "UUID:" not in details
    assert "Row: 3" in details and "Seat: 3" in details
    assert "\n\n" not in details
    table = library_details(replace(entry, source_ride_name="<b>Manta</b>"), reopened, rich=True)
    assert "<table" in table and "&lt;b&gt;Manta&lt;/b&gt;" in table
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
    # Without a source UUID, only byte-identical input is considered the same recording.
    renamed.write_bytes(path.read_bytes() + b"\n")
    different = archive.import_paths((renamed,))[0]
    assert different.status == "imported" and different.source_sha256 != source.source_sha256
    unknown_entry = archive.store.entries()[0]
    assert unknown_entry.recorded_day is None
    assert recording_clock(unknown_entry) == "—"
    assert "Unknown date" in library_details(unknown_entry)


def test_all_real_exports_identify_manta_once(archive: LibraryArchive) -> None:
    paths = tuple(
        path
        for path in sorted(REAL_FIXTURE_DIRECTORY.iterdir())
        if path.suffix in {".forces", ".zforces"}
    )
    results = archive.import_paths(paths)
    assert [result.status for result in results].count("imported") == 5
    assert [result.status for result in results].count("duplicate") == 1
    manta = [result for result in results if result.path.stem.startswith("Manta")]
    assert manta[0].source_sha256 == manta[1].source_sha256
    assert len(archive.store.entries()) == 5
    assert sum(entry.source_ride_name == "Manta" for entry in archive.store.entries()) == 1
    assert all(result.status == "duplicate" for result in archive.import_paths(paths[::-1]))
    for entry in archive.store.entries():
        reopened = archive.reopen(entry.source_sha256)
        assert isinstance(reopened, ExplorerData)
        assert reopened.source.source_sha256 == entry.source_sha256


def test_metadata_edits_reload_reset_and_keep_originals_dates_and_history(
    archive: LibraryArchive,
) -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces"))
    result = archive.import_paths((path,))[0]
    assert result.source_sha256 is not None
    digest = result.source_sha256
    before = archive.store.source(digest)
    original = archive.reopen(digest)
    assert isinstance(original, ExplorerData)
    entry = archive.store.entries()[0]
    values: dict[str, object] = {
        "ride_name": "Edited ride",
        "park_name": "Edited park",
        "row": "Front",
        "seat": "Left",
        "train": "Blue",
        "riding_position": "Seated",
        "notes": "Keep these notes",
    }
    saved = archive.store.update_metadata(digest, values)
    assert archive.store.metadata(digest) == saved
    current = archive.reopen(digest)
    assert isinstance(current, ExplorerData)
    assert current.source.recording.metadata == original.source.recording.metadata
    assert current.source.recording.attributes == original.source.recording.attributes
    assert current.source.recording.motion == original.source.recording.motion
    assert current.source.source_sha256 == digest
    assert (
        current.source.effective_metadata.name == "Edited ride" and current.title == "Edited ride"
    )
    posture = current.source.effective_metadata.riding_position
    assert posture is not None and posture.value == "Seated" and posture.origin is ValueOrigin.USER
    assert dict(current.metadata_fields) == {
        "Ride": "Edited ride",
        "Park": "Edited park",
        "Train": "Blue",
        "Row": "Front",
        "Seat": "Left",
    }
    details = library_details(archive.store.entries()[0], current)
    assert "Ride: Manta" in details and "Row: 3" in details
    assert "Library additions:" in details and "Row: Front" in details
    assert current.source.additions.notes == "Keep these notes"
    assert (
        archive.store.entries(park="edited PARK", search="EDITED RIDE")[0].source_sha256 == digest
    )
    external = load_recording(path)
    assert isinstance(external, ExplorerData)
    applied = archive.apply_metadata(external)
    assert applied.title == "Edited ride" and applied.source.recording is external.source.recording
    assert applied.analysis is not None and external.analysis is not None
    assert applied.analysis.forces is external.analysis.forces
    assert external.source.additions.notes == ""
    with archive.store.connection() as connection:
        connection.execute(
            "UPDATE recordings SET workflow_status='completed',first_sample=100,last_sample=200",
        )
        connection.execute(
            "INSERT INTO video_links(recording_sha256,url) VALUES (?, 'https://example.com')",
            (digest,),
        )
        connection.execute(
            "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,status,"
            "application_version,request_json) VALUES (?, 'csv','single','now','completed','1.3.0','{}')",
            (digest,),
        )
    for invalid in (
        {"date": "changed"},
        {"recorded_day": "changed"},
        {"day_timezone": "UTC"},
        {"recorded_at_utc": "changed"},
        {"imported_at_utc": "changed"},
        {"source_sha256": "a" * 64},
        {"riding_position": "Standing"},
        {"row": 1},
        {"notes": None},
    ):
        with pytest.raises(ValueError):
            archive.store.update_metadata(digest, invalid)
        assert archive.store.metadata(digest) == saved
    assert archive.import_paths((path,))[0].status == "duplicate"
    assert archive.store.metadata(digest) == saved
    archive.store.update_metadata(digest, {})
    restored = archive.reopen(digest)
    assert isinstance(restored, ExplorerData)
    assert restored.source.effective_metadata == original.source.recording.metadata
    assert restored.source.effective_attributes == original.source.recording.attributes
    assert restored.source.additions.notes == ""
    assert restored.ride_bounds == (100, 200)
    after = archive.store.source(digest)
    assert after.data == before.data and sha256(after.data).hexdigest() == digest
    after_entry = archive.store.entries()[0]
    assert (
        after_entry.recorded_at_utc,
        after_entry.recorded_day,
        after_entry.day_timezone,
        after_entry.imported_at_utc,
    ) == (entry.recorded_at_utc, entry.recorded_day, entry.day_timezone, entry.imported_at_utc)
    assert after_entry.workflow_status == "completed" and after_entry.export_count == 1
    with archive.store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM video_links").fetchone() == (1,)


def test_metadata_reset_retains_unfamiliar_source_posture_and_numeric_attributes(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    source = synthetic_source(
        ridingPosition="Unfamiliar",
        attributes=[{"id": "row", "label": "Row", "value": 3}],
    )
    path = export_directory / "source.forces"
    path.write_bytes(source.recording.source.original_bytes)
    archive.import_paths((path,))
    digest = source.source_sha256
    archive.store.update_metadata(digest, {"riding_position": "Flying", "row": "Back"})
    edited = archive.reopen(digest)
    assert isinstance(edited, ExplorerData)
    assert edited.source.effective_attributes[0].value == "Back"
    archive.store.update_metadata(digest, {})
    reset = archive.reopen(digest)
    assert isinstance(reset, ExplorerData)
    assert (
        reset.source.effective_metadata.riding_position == source.recording.metadata.riding_position
    )
    assert reset.source.effective_metadata.riding_position is not None
    assert reset.source.effective_metadata.riding_position.value == "Unfamiliar"
    assert isinstance(reset.source.effective_attributes[0].value, SourceNumber)


def test_park_and_unicode_name_search_are_combined_and_literal(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    names = (
        ("Straße Ｒｉｄｅ", "Café Park"),
        ("100%_Fun\\O'Clock", "CAFE\u0301 PARK"),
        ("Unknown ride", None),
        ("Other ride", "Other park"),
    )
    for index, (ride, park) in enumerate(names):
        path = export_directory / f"source-{index}.forces"
        path.write_bytes(synthetic_source(name=ride, location=park).recording.source.original_bytes)
        assert archive.import_paths((path,))[0].status == "imported"
    store = archive.store
    assert len(store.entries()) == 4
    assert len(store.parks()) == 2
    assert {entry.ride_name for entry in store.entries(park="café PARK")} == {
        names[0][0],
        names[1][0],
    }
    assert [entry.ride_name for entry in store.entries(search=" STRASSE  cafe\u0301 \t ride ")] == [
        names[0][0],
    ]
    assert [entry.ride_name for entry in store.entries(park="", search="unknown")] == [names[2][0]]
    assert store.entries(park="", search="strasse") == ()
    assert store.entries(park="Other park", search="café") == ()
    for literal in ("%", "_", "\\", "'"):
        assert [entry.ride_name for entry in store.entries(search=literal)] == [names[1][0]]
    assert store.entries(search="' OR 1=1 --") == ()
    assert store.entries(search="strasse missing") == ()
    assert store.entries(search=" \t ") == store.entries()


def test_changed_uuid_export_updates_source_and_preserves_library_state(
    archive: LibraryArchive,
    export_directory: Path,
) -> None:
    identity = "be687591-84bb-4469-aac0-e5a16b0744f9"
    source = synthetic_source(uuid=identity, name="Before", location="Park")
    path = export_directory / "first.forces"
    path.write_bytes(source.recording.source.original_bytes)
    assert archive.import_paths((path,))[0].status == "imported"
    with archive.store.connection() as connection:
        connection.execute(
            "UPDATE recordings SET notes='keep',ride_name_override='My ride',"
            "workflow_status='uploaded',first_sample=1,last_sample=3,gravity_index=4",
        )
        connection.execute(
            "INSERT INTO video_links(recording_sha256,url) VALUES (?, 'https://example.com')",
            (source.source_sha256,),
        )
        connection.execute(
            "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,"
            "status,application_version,request_json) VALUES (?, 'csv','single','now',"
            "'completed','1.3.0','{\"original\":true}')",
            (source.source_sha256,),
        )
        imported_at = connection.execute("SELECT imported_at_utc FROM recordings").fetchone()[0]
    changed = synthetic_source(uuid=identity.upper(), name="After", location="New park", row=5)
    updated_path = export_directory / "changed.zforces"
    raw = zlib.compress(changed.recording.source.original_bytes, wbits=-15)
    updated_path.write_bytes(raw)
    result = archive.import_paths((updated_path,))[0]
    digest = sha256(raw).hexdigest()
    assert result.status == "updated" and result.source_sha256 == digest
    entries = archive.store.entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_uuid == identity
    assert entry.source_sha256 == digest and entry.imported_at_utc == imported_at
    assert entry.source_ride_name == "After" and entry.ride_name == "My ride"
    assert entry.park_name == "New park" and entry.workflow_status == "uploaded"
    assert archive.store.entries(park="NEW PARK", search="my RIDE") == entries
    assert archive.store.entries(search="Before") == ()
    assert archive.store.parks() == ("New park",)
    assert entry.export_count == 1
    reopened = archive.reopen(digest)
    assert isinstance(reopened, ExplorerData)
    assert reopened.source.recording.source.original_bytes == raw
    assert reopened.source.recording.metadata.name == "After"
    assert reopened.ride_bounds == (1, 3)
    with archive.store.connection() as connection:
        assert connection.execute("SELECT notes,gravity_index FROM recordings").fetchone() == (
            "keep",
            4,
        )
        assert connection.execute("SELECT recording_sha256 FROM video_links").fetchone() == (
            digest,
        )
        assert connection.execute(
            "SELECT recording_sha256,request_json FROM export_history",
        ).fetchone() == (digest, '{"original":true}')
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    # The new source remains unchanged when imported again in the other format.
    path.write_bytes(changed.recording.source.original_bytes)
    duplicate = archive.import_paths((path,))[0]
    assert duplicate.status == "duplicate" and duplicate.source_sha256 == digest
    assert archive.store.source(digest).data == raw
    shortened = synthetic_source(
        uuid=identity,
        startIndex=0,
        endIndex=2,
        accelerationSequence=[{"x": "0", "y": "0", "z": "1"}] * 3,
        gravitySequence=[{"x": "0", "y": "0", "z": "1"}] * 3,
    )
    path.write_bytes(shortened.recording.source.original_bytes)
    assert archive.import_paths((path,))[0].status == "failed"
    assert archive.store.entries() == entries
    assert archive.store.source(digest).data == raw
    # A failed replacement is atomic and does not remove the existing source/history.
    payload = json.loads(changed.recording.source.original_bytes)
    payload["name"] = "Rejected"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with archive.store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_update BEFORE UPDATE ON recordings "
            "BEGIN SELECT RAISE(ABORT, 'injected update failure'); END",
        )
    assert archive.import_paths((path,))[0].status == "failed"
    assert archive.store.entries() == entries
    assert archive.store.source(digest).data == raw


@pytest.mark.parametrize("identity", [None, "invalid", "00000000-0000-0000-0000-000000000000"])
def test_unusable_uuid_does_not_merge_distinct_sources(
    archive: LibraryArchive,
    export_directory: Path,
    identity: str | None,
) -> None:
    for number in range(2):
        path = export_directory / f"source-{number}.forces"
        path.write_bytes(
            synthetic_source(uuid=identity, name=f"Ride {number}").recording.source.original_bytes,
        )
        assert archive.import_paths((path,))[0].status == "imported"
    assert len(archive.store.entries()) == 2


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
