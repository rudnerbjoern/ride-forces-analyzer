"""Library schema, exact source storage, revision guards and transaction rollback."""

# cspell:words xinfo executemany Straße strasse

from contextlib import closing, contextmanager
from collections.abc import Generator
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
import sqlite3
from typing import Any

from alembic.operations import Operations
from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy.exc import SQLAlchemyError

from ride_forces_analyzer import __version__
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from ride_forces_analyzer.storage.library import (
    LibraryStore,
    LibraryStoreError,
    WORKFLOW_STATUSES,
    default_database_path,
)
from ride_forces_analyzer.storage.library_search import library_search_values

RAW = b' {"unknown":[1.000,true],"GPS":"retained"}\r\n'
DIGEST = sha256(RAW).hexdigest()


def insert_recording(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO recordings (source_sha256, source_bytes, source_filename, source_format, "
        "source_byte_count, imported_at_utc, first_sample, last_sample, "
        "calibration_algorithm_version, calibration_window_samples, search_text) "
        "VALUES (?, ?, 'ride.forces', 'forces', ?, '2026-11-01T10:00:00.000000Z', "
        "0, 10, 'source', 11, '')",
        (DIGEST, RAW, len(RAW)),
    )


def test_video_links_are_independent_recording_bound_and_offline(export_directory: Path) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    other = "b" * 64
    with store.connection() as connection:
        insert_recording(connection)
        connection.execute(
            "INSERT INTO recordings (source_sha256,source_bytes,source_filename,source_format,"
            "source_byte_count,imported_at_utc,first_sample,last_sample,"
            "calibration_algorithm_version,calibration_window_samples,search_text) "
            "SELECT ?,source_bytes,source_filename,source_format,source_byte_count,imported_at_utc,"
            "first_sample,last_sample,calibration_algorithm_version,calibration_window_samples,search_text "
            "FROM recordings WHERE source_sha256=?",
            (other, DIGEST),
        )
        before = connection.execute("SELECT * FROM recordings ORDER BY source_sha256").fetchall()
    first = store.save_video_link(DIGEST, "https://example.invalid/private?scheduled=1", "YouTube")
    second = store.save_video_link(DIGEST, "https://example.invalid/short", "Shorts")
    third = store.save_video_link(other, "http://other.invalid/video", "")
    reopened = LibraryStore(store.path)
    assert [link.id for link in reopened.video_links(DIGEST)] == [first, second]
    assert reopened.video_links(other)[0].id == third
    assert reopened.video_links(other)[0].label == ""
    store.save_video_link(
        DIGEST,
        "https://example.invalid/edited",
        "Old custom label",
        link_id=first,
    )
    assert store.video_links(DIGEST)[1].id == second
    for invalid in (
        "",
        "file:///video",
        "ftp://example.invalid/video",
        "https://",
        "https://a b/video",
    ):
        with pytest.raises(ValueError):
            store.save_video_link(DIGEST, invalid)
    with pytest.raises(LibraryStoreError):
        store.save_video_link(other, "https://other.invalid/changed", link_id=first)
    with pytest.raises(LibraryStoreError):
        store.remove_video_link(other, first)
    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_link BEFORE UPDATE ON video_links "
            "BEGIN SELECT RAISE(ABORT, 'injected link failure'); END",
        )
    with pytest.raises(LibraryStoreError, match="injected link failure"):
        store.save_video_link(DIGEST, "https://example.invalid/failure", link_id=first)
    assert store.video_links(DIGEST)[0].label == "Old custom label"
    store.remove_video_link(DIGEST, first)
    assert [link.id for link in LibraryStore(store.path).video_links(DIGEST)] == [second]
    assert LibraryStore(store.path).video_links(other)[0].id == third
    with store.connection() as connection:
        assert (
            connection.execute("SELECT * FROM recordings ORDER BY source_sha256").fetchall()
            == before
        )


def test_fresh_schema_resources_relationships_and_reopen(export_directory: Path) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    assert not store.path.exists()
    resources = files("ride_forces_analyzer.storage.library_migrations")
    assert resources.joinpath("env.py").is_file()
    assert resources.joinpath("versions/v1_3.py").is_file()
    with store.connection() as connection:
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert revision == "1_3_search"
        assert tuple(map(int, revision.split("_")[:2])) <= tuple(
            map(int, __version__.split(".")[:2]),
        )
        assert {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        } == {
            "recordings",
            "export_history",
            "video_links",
            "alembic_version",
        }
        expected = {
            "recordings": "source_sha256 source_bytes source_filename source_format source_byte_count "
            "source_ride_name source_park_name recorded_at_utc recorded_day day_timezone imported_at_utc "
            "first_sample last_sample gravity_index incline_index calibration_algorithm_version "
            "calibration_window_samples ride_name_override park_name_override row_override seat_override "
            "train_override riding_position_override notes workflow_status park_key search_text source_uuid",
            "export_history": "id recording_sha256 export_kind origin started_at_utc finished_at_utc "
            "duration_seconds status application_version request_json export_snapshot_json output_path "
            "file_size_bytes gpu_encoding error",
            "video_links": "id recording_sha256 url label",
        }
        for table, columns in expected.items():
            assert [
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            ] == columns.split()
        indexes = {
            "idx_recordings_uuid": [("source_uuid", 0)],
            "idx_recordings_day": [
                ("recorded_day", 1),
                ("recorded_at_utc", 1),
                ("imported_at_utc", 1),
                ("source_sha256", 0),
            ],
            "idx_recordings_park_day": [
                ("park_key", 0),
                ("recorded_day", 1),
                ("recorded_at_utc", 1),
                ("imported_at_utc", 1),
                ("source_sha256", 0),
            ],
            "idx_export_history_recording": [
                ("recording_sha256", 0),
                ("started_at_utc", 1),
                ("id", 1),
            ],
            "idx_video_links_recording": [("recording_sha256", 0), ("id", 0)],
        }
        assert {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT GLOB 'sqlite_*'",
            )
        } == indexes.keys()
        for name, columns in indexes.items():
            assert [
                (row[2], row[3])
                for row in connection.execute(f"PRAGMA index_xinfo({name})")
                if row[5]
            ] == columns
        for table in ("export_history", "video_links"):
            foreign_key = connection.execute(f"PRAGMA foreign_key_list({table})").fetchone()
            assert foreign_key[2:5] == ("recordings", "recording_sha256", "source_sha256")
        insert_recording(connection)
        connection.execute(
            "UPDATE recordings SET notes='kept', row_override='Front', gravity_index=20",
        )
        connection.execute(
            "INSERT INTO video_links (recording_sha256,url,label) VALUES (?, ?, ?)",
            (DIGEST, "https://example.com/video", "Custom"),
        )
        connection.execute(
            "INSERT INTO export_history (recording_sha256, export_kind, origin, started_at_utc, "
            "status, application_version, request_json, export_snapshot_json) "
            "VALUES (?, 'video', 'single', '2026-11-01T10:00:00.000000Z', 'failed', '1.3.0', ?, ?)",
            (DIGEST, '{"unknown":{"saved":true}}', '{"recipe":"kept"}'),
        )
    before = store.path.read_bytes()
    modified = store.path.stat().st_mtime_ns
    with LibraryStore(store.path).connection() as connection:
        assert connection.execute(
            "SELECT source_bytes, notes, row_override, workflow_status, gravity_index FROM recordings",
        ).fetchone() == (
            RAW,
            "kept",
            "Front",
            "imported",
            20,
        )
        assert connection.execute(
            "SELECT request_json,export_snapshot_json FROM export_history",
        ).fetchone() == ('{"unknown":{"saved":true}}', '{"recipe":"kept"}')
        assert connection.execute("SELECT label FROM video_links").fetchone() == ("Custom",)
    assert store.path.read_bytes() == before
    assert store.path.stat().st_mtime_ns == modified


@pytest.mark.parametrize("revisions", [("99_0",), ("unknown",), ("1",), ("1_3", "99_0"), ()])
def test_unrecognized_database_is_refused_without_changes(
    export_directory: Path,
    revisions: tuple[str, ...],
) -> None:
    path = export_directory / "library.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE preserved (payload BLOB)")
        connection.execute("INSERT INTO preserved VALUES (?)", (RAW,))
        if revisions:
            connection.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
            connection.executemany(
                "INSERT INTO alembic_version VALUES (?)",
                [(item,) for item in revisions],
            )
    before = path.read_bytes()
    modified = path.stat().st_mtime_ns
    with pytest.raises(LibraryStoreError, match="revision"):
        LibraryStore(path).initialize()
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == modified


def test_failed_initial_migration_rolls_back_schema_data_and_revision(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = export_directory / "library.sqlite3"

    def fail(operation: Operations, *args: Any, **kwargs: Any) -> None:
        operation.execute("CREATE TABLE partial_data (payload BLOB)")
        operation.execute("INSERT INTO partial_data VALUES (X'0001')")
        raise SQLAlchemyError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "create_index", fail)
        with pytest.raises(LibraryStoreError, match="injected migration failure"):
            LibraryStore(path).initialize()
    with closing(sqlite3.connect(path)) as connection, connection:
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
        )
    LibraryStore(path).initialize()
    with closing(sqlite3.connect(path)) as connection, connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "1_3_search",
        )


def test_uuid_upgrade_merges_existing_formats_preserves_relationships_and_rolls_back(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    upgrade = command.upgrade
    sources: list[ImportSuccess] = []

    def old_upgrade(config: Config, target: str) -> None:
        upgrade(config, "1_3")

    with monkeypatch.context() as patch:
        patch.setattr(command, "upgrade", old_upgrade)
        with store.connection() as connection:
            for number, extension in enumerate(("forces", "zforces")):
                path = next(REAL_FIXTURE_DIRECTORY.glob(f"Manta-*.{extension}"))
                source = import_forces(path)
                assert isinstance(source, ImportSuccess)
                sources.append(source)
                insert_recording(connection)
                connection.execute(
                    "UPDATE recordings SET source_sha256=?,source_bytes=?,source_filename=?,"
                    "source_format=?,source_byte_count=?,imported_at_utc=?,notes=? "
                    "WHERE source_sha256=?",
                    (
                        source.source_sha256,
                        source.recording.source.original_bytes,
                        path.name,
                        extension,
                        source.byte_count,
                        f"2026-11-01T10:0{number}:00Z",
                        f"notes-{number}",
                        DIGEST,
                    ),
                )
                calibration = CalibrationOverrides()
                connection.execute(
                    "UPDATE recordings SET calibration_algorithm_version=?,calibration_window_samples=?",
                    (calibration.algorithm_version, calibration.window_samples),
                )
                connection.execute(
                    "INSERT INTO video_links(recording_sha256,url) VALUES (?, 'https://example.com')",
                    (source.source_sha256,),
                )
                connection.execute(
                    "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,"
                    "status,application_version,request_json) VALUES (?, 'csv','single','now',"
                    "'completed','1.3.0','{}')",
                    (source.source_sha256,),
                )
    before = store.path.read_bytes()
    create_index = Operations.create_index

    def fail_index(operation: Operations, name: str, *args: Any, **kwargs: Any) -> None:
        if name == "idx_recordings_uuid":
            raise SQLAlchemyError("injected UUID migration failure")
        create_index(operation, name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "create_index", fail_index)
        with pytest.raises(LibraryStoreError, match="injected UUID migration failure"):
            store.initialize()
    assert store.path.read_bytes() == before
    store.initialize()
    entries = store.entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.source_uuid == "be687591-84bb-4469-aac0-e5a16b0744f9"
    assert entry.source_sha256 == sources[0].source_sha256
    assert entry.export_count == 2
    assert store.source(entry.source_sha256).data == sources[0].recording.source.original_bytes
    with store.connection() as connection:
        assert connection.execute("SELECT notes FROM recordings").fetchone() == ("notes-0",)
        assert connection.execute("SELECT count(*) FROM video_links").fetchone() == (2,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    current = store.path.read_bytes()
    store.initialize()
    assert store.path.read_bytes() == current


def test_ordinary_writes_enforce_constraints_and_rollback(export_directory: Path) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    with store.connection() as connection:
        insert_recording(connection)
    for column, value in (
        ("source_format", "other"),
        ("source_byte_count", -1),
        ("source_byte_count", 0),
        ("first_sample", -1),
        ("last_sample", -1),
        ("gravity_index", -1),
        ("riding_position_override", "Standing"),
        ("workflow_status", "automatic"),
        ("source_sha256", "Z" * 64),
    ):
        with pytest.raises(LibraryStoreError):
            with store.connection() as connection:
                connection.execute("UPDATE recordings SET notes='must roll back'")
                connection.execute(f"UPDATE recordings SET {column}=?", (value,))
    with pytest.raises(LibraryStoreError):
        with store.connection() as connection:
            connection.execute(
                "INSERT INTO video_links (recording_sha256,url) VALUES ('missing','https://example.com')",
            )
    with pytest.raises(LibraryStoreError):
        with store.connection() as connection:
            connection.execute(
                "INSERT INTO export_history (recording_sha256,export_kind,origin,started_at_utc,status,application_version,request_json) VALUES ('missing','video','single','now','running','1.3.0','{}')",
            )
    with store.connection() as connection:
        assert connection.execute("SELECT notes FROM recordings").fetchone() == ("",)
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "1_3_search",
        )


def test_default_path_and_io_failure(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(export_directory))
    assert default_database_path() == export_directory / "Ride Forces Analyzer" / "library.sqlite3"
    assert LibraryStore().path == default_database_path().resolve()
    parent = export_directory / "not-a-directory"
    parent.write_text("preserved", encoding="utf-8")
    with pytest.raises(LibraryStoreError):
        LibraryStore(parent / "library.sqlite3").initialize()
    assert parent.read_text(encoding="utf-8") == "preserved"


def test_manual_workflow_accepts_all_transitions_and_preserves_other_data(
    export_directory: Path,
) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    with store.connection() as connection:
        insert_recording(connection)
        connection.execute("UPDATE recordings SET notes='kept',row_override='Front'")
        connection.execute(
            "INSERT INTO video_links(recording_sha256,url) VALUES (?, 'https://example.com')",
            (DIGEST,),
        )
        connection.execute(
            "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,status,"
            "application_version,request_json) VALUES (?, 'csv','single','now','completed','1.3.0','{}')",
            (DIGEST,),
        )
        connection.row_factory = sqlite3.Row
        before = dict(connection.execute("SELECT * FROM recordings").fetchone())
        before.pop("workflow_status")
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for status in (*WORKFLOW_STATUSES, *reversed(WORKFLOW_STATUSES), "completed", "imported"):
        store.set_workflow_status(DIGEST, status)
        with LibraryStore(store.path).connection() as connection:
            connection.row_factory = sqlite3.Row
            current = dict(connection.execute("SELECT * FROM recordings").fetchone())
            assert current.pop("workflow_status") == status
            assert current == before
            assert connection.execute("SELECT count(*) FROM video_links").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM export_history").fetchone()[0] == 1
            assert (
                connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                == tables
            )
    for invalid in ("", "automatic", "COMPLETED"):
        with pytest.raises(ValueError, match="workflow status"):
            store.set_workflow_status(DIGEST, invalid)
    with pytest.raises(ValueError):
        store.set_workflow_status("invalid", "completed")
    with pytest.raises(LibraryStoreError, match="not in the Library"):
        store.set_workflow_status("f" * 64, "completed")
    with store.connection() as connection:
        connection.execute(
            "CREATE TRIGGER reject_status BEFORE UPDATE OF workflow_status ON recordings "
            "WHEN NEW.workflow_status='uploaded' BEGIN SELECT RAISE(ABORT, 'injected status failure'); END",
        )
    with pytest.raises(LibraryStoreError, match="injected status failure"):
        store.set_workflow_status(DIGEST, "uploaded")
    assert LibraryStore(store.path).entries()[0].workflow_status == "imported"


def test_list_order_counts_effective_names_and_no_source_blob_reads(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    rows = [
        ("a", "2026-11-01", "2026-11-01T14:00:00.000000Z", "2026-11-01T18:00:00.000000Z"),
        ("b", "2026-11-01", "2026-11-01T14:00:00.000000Z", "2026-11-01T19:00:00.000000Z"),
        ("c", "2026-11-01", "2026-11-01T14:00:00.000000Z", "2026-11-01T19:00:00.000000Z"),
        ("d", "2026-11-01", "2026-11-01T15:00:00.000000Z", "2026-11-01T17:00:00.000000Z"),
        ("e", "2026-10-31", "2026-10-31T20:00:00.000000Z", "2026-11-01T20:00:00.000000Z"),
        ("f", None, None, "2026-11-01T20:00:00.000000Z"),
        ("0", None, None, "2026-11-01T21:00:00.000000Z"),
        ("1", None, None, "2026-11-01T21:00:00.000000Z"),
    ]
    with store.connection() as connection:
        for key, day, instant, imported in rows:
            connection.execute(
                "INSERT INTO recordings (source_sha256,source_bytes,source_filename,source_format,"
                "source_byte_count,source_ride_name,source_park_name,recorded_day,recorded_at_utc,"
                "day_timezone,imported_at_utc,first_sample,last_sample,calibration_algorithm_version,"
                "calibration_window_samples,search_text) VALUES (?, X'00', ?, 'forces', 1, ?, 'Park',"
                "?,?, 'UTC', ?, 0,0,'1',5,'')",
                (key * 64, f"{key}.forces", f"Ride {key}", day, instant, imported),
            )
        connection.execute(
            "UPDATE recordings SET ride_name_override='Effective ride',park_name_override='Effective park' WHERE source_sha256=?",
            ("e" * 64,),
        )
        for key, *_ in rows:
            ride = "Effective ride" if key == "e" else f"Ride {key}"
            park = "Effective park" if key == "e" else "Park"
            connection.execute(
                "UPDATE recordings SET park_key=?,search_text=? WHERE source_sha256=?",
                (*library_search_values(ride, park), key * 64),
            )
        for _ in range(2):
            connection.execute(
                "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,status,application_version,request_json) VALUES (?, 'csv','single','2026-11-01T10:00:00.000000Z','failed','1.3.0','{}')",
                ("b" * 64,),
            )
    original_connection = store.connection

    def authorize(
        action: int,
        table: str | None,
        column: str | None,
        database: str | None,
        trigger: str | None,
    ) -> int:
        if action == sqlite3.SQLITE_READ and table == "recordings" and column == "source_bytes":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    @contextmanager
    def metadata_only() -> Generator[sqlite3.Connection, None, None]:
        with original_connection() as connection:
            connection.set_authorizer(authorize)
            yield connection

    monkeypatch.setattr(store, "connection", metadata_only)
    entries = store.entries()
    assert [entry.source_sha256[0] for entry in entries] == ["d", "b", "c", "a", "e", "0", "1", "f"]
    assert [entry.export_count for entry in entries] == [0, 2, 0, 0, 0, 0, 0, 0]
    assert all(entry.workflow_status == "imported" for entry in entries)
    corrected = entries[4]
    assert (corrected.ride_name, corrected.park_name) == ("Effective ride", "Effective park")
    assert (corrected.source_ride_name, corrected.source_park_name) == ("Ride e", "Park")
    assert store.entries(park="effective PARK", search="RIDE") == (corrected,)
    assert store.parks() == ("Effective park", "Park")
    assert store.entries(search="absent") == ()
    assert store.entries() == entries


def test_search_projection_upgrade_uses_effective_names_and_rolls_back(
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LibraryStore(export_directory / "library.sqlite3")
    upgrade = command.upgrade

    def old_upgrade(config: Config, target: str) -> None:
        upgrade(config, "1_3_identity")

    with monkeypatch.context() as patch:
        patch.setattr(command, "upgrade", old_upgrade)
        with store.connection() as connection:
            insert_recording(connection)
            connection.execute(
                "UPDATE recordings SET source_ride_name='Original',source_park_name='Old park',"
                "ride_name_override='Straße',park_name_override='Café Park',notes='kept'",
            )
    before = store.path.read_bytes()
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute(
            "CREATE TRIGGER reject_projection BEFORE UPDATE OF search_text ON recordings "
            "BEGIN SELECT RAISE(ABORT, 'injected projection failure'); END",
        )
    rejected = store.path.read_bytes()
    with pytest.raises(LibraryStoreError, match="injected projection failure"):
        store.initialize()
    assert store.path.read_bytes() == rejected
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute("DROP TRIGGER reject_projection")
    store.initialize()
    assert store.path.read_bytes() != before
    entry = store.entries(park="CAFÉ PARK", search="strasse")[0]
    assert entry.source_ride_name == "Original" and entry.ride_name == "Straße"
    assert store.parks() == ("Café Park",)
    with store.connection() as connection:
        assert connection.execute("SELECT source_bytes,notes FROM recordings").fetchone() == (
            RAW,
            "kept",
        )
    current = store.path.read_bytes()
    store.initialize()
    assert store.path.read_bytes() == current
