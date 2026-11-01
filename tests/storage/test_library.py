"""Library schema, exact source storage, revision guards and transaction rollback."""

# cspell:words xinfo executemany

from contextlib import closing
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
import sqlite3
from typing import Any

from alembic.operations import Operations
import pytest
from sqlalchemy.exc import SQLAlchemyError

from ride_forces_analyzer import __version__
from ride_forces_analyzer.storage.library import (
    LibraryStore,
    LibraryStoreError,
    default_database_path,
)

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
        assert revision == "1_3"
        assert tuple(map(int, revision.split("_"))) <= tuple(map(int, __version__.split(".")[:2]))
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
            "train_override riding_position_override notes workflow_status park_key search_text",
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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("1_3",)


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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("1_3",)


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
