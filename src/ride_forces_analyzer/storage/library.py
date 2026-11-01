"""Transactional Library schema upgrades and ordinary SQLite connections.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words sqlalchemy autocommit poolclass timespec

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import as_file, files
from pathlib import Path
import sqlite3
from typing import Literal

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from ride_forces_analyzer.runtime.paths import data_directory
from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    validate_calibration_references,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes
from ride_forces_analyzer.importers.library_metadata import project_library_metadata, recording_uuid
from ride_forces_analyzer.validation.checks import validate_sample_range, validate_sha256


class LibraryStoreError(Exception):
    """Library access failed without replacing the database or discarding its data."""


@dataclass(frozen=True, slots=True)
class ArchivedSource:
    """Original archive bytes and current marker recipe for reopening.

    Attributes:
        data: Complete original bytes, including compression and unknown fields.
        filename: Original basename, independent of the previous external path.
        compressed: Whether bytes are in the zforces format.
        bounds: Current inclusive recording bounds.
        calibration: Current source/default or validated custom reference choices.
    """

    data: bytes
    filename: str
    compressed: bool
    bounds: tuple[int, int]
    calibration: CalibrationOverrides


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    """Lightweight recording-list metadata without original source BLOBs.

    Attributes:
        source_sha256: Stable original-byte recording identity.
        filename: Original basename.
        source_ride_name: Verbatim source ride name, if available.
        source_park_name: Verbatim source park name, if available.
        ride_name: Effective ride name, using an override when set.
        park_name: Effective park name, using an override when set.
        recorded_at_utc: Normalized recording instant, or None when unknown.
        recorded_day: Recording-local grouping date, or None when unknown.
        day_timezone: Source zone or explicit UTC fallback used for the day.
        imported_at_utc: First successful archive import time in UTC.
        export_count: Number of associated export attempts.
        workflow_status: Current manually assigned recording workflow state.
        source_uuid: Source recording identity across exports, if valid.
    """

    source_sha256: str
    filename: str
    source_ride_name: str | None
    source_park_name: str | None
    ride_name: str | None
    park_name: str | None
    recorded_at_utc: str | None
    recorded_day: str | None
    day_timezone: str | None
    imported_at_utc: str
    export_count: int
    workflow_status: str
    source_uuid: str | None = None


def default_database_path() -> Path:
    """Return the Library database location without creating it.

    Returns:
        The existing application data directory's library.sqlite3 path.
    """
    return data_directory() / "library.sqlite3"


class LibraryStore:
    """Own schema initialization and transactional SQLite access to the Library.

    Attributes:
        path: Database path; existing preferences and export stores are independent.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Select the database without opening it.

        Args:
            path: Explicit database path, or the application-local default.
        """
        self.path = (path if path is not None else default_database_path()).resolve()

    def archive(
        self,
        source: ImportSuccess,
        filename: str,
        bounds: tuple[int, int],
        calibration: CalibrationOverrides,
    ) -> tuple[Literal["imported", "updated", "duplicate"], str]:
        """Archive one recording by UUID, updating its source on a changed export.

        Args:
            source: Successful import owning the exact original source bytes.
            filename: Original supported basename, not an external storage dependency.
            bounds: Valid inclusive bounds resolved from source/defaults and preferences.
            calibration: Reference choices admitted by the existing calibration service.

        Returns:
            Outcome and current archived digest. Equivalent exports retain the first
            original; changed exports replace source bytes and source projections,
            preserving Library additions, valid markers and related history.

        Raises:
            ValueError: The filename or bounds are invalid.
            LibraryStoreError: The transaction could not be committed.
        """
        source_format = Path(filename).suffix.lower().removeprefix(".")
        if Path(filename).name != filename or source_format not in {"forces", "zforces"}:
            raise ValueError("Expected a forces or zforces basename")
        validate_sample_range(
            *bounds,
            len(source.recording.motion.acceleration),
            "Invalid Library bounds",
        )
        metadata = project_library_metadata(source.recording)
        source_uuid = recording_uuid(source.recording)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT source_sha256, source_bytes, source_format, first_sample, last_sample, "
                "gravity_index, incline_index, calibration_algorithm_version, "
                "calibration_window_samples FROM recordings "
                "WHERE source_sha256=? OR (source_uuid IS NOT NULL AND source_uuid=?)",
                (source.source_sha256, source_uuid),
            ).fetchone()
            if existing is not None:
                digest = existing[0]
                if digest == source.source_sha256:
                    return "duplicate", digest
                archived = import_forces_bytes(existing[1], compressed=existing[2] == "zforces")
                if not isinstance(archived, ImportSuccess):
                    raise LibraryStoreError("Cannot update an unreadable archived recording")
                if archived.recording.source.root == source.recording.source.root:
                    return "duplicate", digest
                validate_sample_range(
                    existing[3],
                    existing[4],
                    len(source.recording.motion.acceleration),
                    "Existing Library bounds are incompatible with this export",
                )
                validate_calibration_references(
                    source,
                    CalibrationOverrides(*existing[5:9]),
                    calculation_time=datetime.now(UTC),
                )
                # Keep relationships valid while replacing the byte-based primary key.
                connection.execute("PRAGMA defer_foreign_keys = ON")
                connection.execute(
                    "UPDATE recordings SET source_sha256=?, source_bytes=?, source_filename=?, "
                    "source_format=?, source_byte_count=?, source_ride_name=?, source_park_name=?, "
                    "recorded_at_utc=?, recorded_day=?, day_timezone=? WHERE source_sha256=?",
                    (
                        source.source_sha256,
                        source.recording.source.original_bytes,
                        filename,
                        source_format,
                        source.byte_count,
                        metadata.source_ride_name,
                        metadata.source_park_name,
                        metadata.recorded_at_utc,
                        metadata.recorded_day,
                        metadata.day_timezone,
                        digest,
                    ),
                )
                for table in ("export_history", "video_links"):
                    connection.execute(
                        f"UPDATE {table} SET recording_sha256=? WHERE recording_sha256=?",
                        (source.source_sha256, digest),
                    )
                return "updated", source.source_sha256
            imported_at = (
                datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
            )
            connection.execute(
                "INSERT INTO recordings (source_sha256, source_bytes, source_filename, source_format, "
                "source_byte_count, source_ride_name, source_park_name, recorded_at_utc, recorded_day, "
                "day_timezone, imported_at_utc, first_sample, last_sample, gravity_index, incline_index, "
                "calibration_algorithm_version, calibration_window_samples, source_uuid, search_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')",
                (
                    source.source_sha256,
                    source.recording.source.original_bytes,
                    filename,
                    source_format,
                    source.byte_count,
                    metadata.source_ride_name,
                    metadata.source_park_name,
                    metadata.recorded_at_utc,
                    metadata.recorded_day,
                    metadata.day_timezone,
                    imported_at,
                    *bounds,
                    calibration.gravity_index,
                    calibration.incline_index,
                    calibration.algorithm_version,
                    calibration.window_samples,
                    source_uuid,
                ),
            )
            return "imported", source.source_sha256

    def entries(self) -> tuple[LibraryEntry, ...]:
        """Read only list metadata in deterministic newest-first day/instant order.

        Unknown dates come last. Import time descending and source digest ascending
        resolve ties; the query never selects source BLOBs or parses recordings.

        Returns:
            Effective names, source/date/import details and export counts.

        Raises:
            LibraryStoreError: Library metadata could not be read.
        """
        with self.connection() as connection:
            return tuple(
                LibraryEntry(*row)
                for row in connection.execute(
                    "SELECT r.source_sha256, r.source_filename, r.source_ride_name, r.source_park_name, "
                    "COALESCE(r.ride_name_override, r.source_ride_name), "
                    "COALESCE(r.park_name_override, r.source_park_name), "
                    "r.recorded_at_utc, r.recorded_day, r.day_timezone, r.imported_at_utc, "
                    "(SELECT count(*) FROM export_history h WHERE h.recording_sha256=r.source_sha256), "
                    "r.workflow_status, r.source_uuid "
                    "FROM recordings r ORDER BY r.recorded_day DESC, r.recorded_at_utc DESC, "
                    "r.imported_at_utc DESC, r.source_sha256",
                )
            )

    def source(self, source_sha256: str) -> ArchivedSource:
        """Read one archived original, verifying its stored identity before decoding.

        Args:
            source_sha256: Exact original-byte recording identity.

        Returns:
            Original bytes, format and current marker choices for one recording.

        Raises:
            ValueError: The requested digest is invalid.
            LibraryStoreError: The entry is missing, corrupt or unreadable.
        """
        validate_sha256(source_sha256, "Expected a source SHA-256")
        with self.connection() as connection:
            row = connection.execute(
                "SELECT source_bytes, source_filename, source_format, source_byte_count, "
                "first_sample, last_sample, gravity_index, incline_index, "
                "calibration_algorithm_version, calibration_window_samples "
                "FROM recordings WHERE source_sha256=?",
                (source_sha256,),
            ).fetchone()
        if row is None:
            raise LibraryStoreError("Recording is not in the Library")
        if not isinstance(row[0], bytes):
            raise LibraryStoreError("Archived source integrity check failed")
        data = row[0]
        if len(data) != row[3] or sha256(data).hexdigest() != source_sha256:
            raise LibraryStoreError("Archived source integrity check failed")
        try:
            calibration = CalibrationOverrides(row[6], row[7], row[8], row[9])
        except (ValueError, TypeError) as error:
            raise LibraryStoreError("Invalid archived calibration recipe") from error
        if row[2] not in {"forces", "zforces"}:
            raise LibraryStoreError("Unsupported archived source format")
        return ArchivedSource(data, row[1], row[2] == "zforces", (row[4], row[5]), calibration)

    def initialize(self) -> None:
        """Apply packaged Alembic revisions in one explicit SQLite transaction.

        Current databases are read without rewriting schema or data. Unknown
        revisions and unversioned existing tables are rejected without replacement.
        A failed upgrade rolls back both DDL and data, including the revision row.

        Raises:
            LibraryStoreError: Database access or migration failed.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with as_file(files("ride_forces_analyzer.storage.library_migrations")) as location:
                config = Config()
                config.set_main_option("script_location", str(location).replace("%", "%%"))
                scripts = ScriptDirectory.from_config(config)
                engine = create_engine(
                    URL.create("sqlite", database=str(self.path)),
                    connect_args={"isolation_level": None},
                    poolclass=NullPool,
                )
                try:
                    with engine.connect() as connection:
                        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
                        connection.exec_driver_sql("BEGIN IMMEDIATE")
                        try:
                            current = MigrationContext.configure(connection).get_current_heads()
                            known = {revision.revision for revision in scripts.walk_revisions()}
                            if len(current) > 1 or any(item not in known for item in current):
                                raise LibraryStoreError("Unsupported Library schema revision")
                            tables = connection.exec_driver_sql(
                                "SELECT name FROM sqlite_master WHERE type='table' "
                                "AND name NOT GLOB 'sqlite_*'",
                            ).fetchall()
                            if not current and tables:
                                raise LibraryStoreError("Existing Library has no schema revision")
                            if current != (scripts.get_current_head(),):
                                config.attributes["connection"] = connection
                                command.upgrade(config, "head")
                            connection.commit()
                        except Exception:
                            connection.rollback()
                            raise
                finally:
                    engine.dispose()
        except (OSError, sqlite3.Error, SQLAlchemyError, CommandError) as error:
            raise LibraryStoreError(f"Library database: {error}") from error

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Open a foreign-key-enabled SQLite transaction after applying migrations.

        Yields:
            Standard-library connection for ordinary parameterized reads/writes.

        Raises:
            LibraryStoreError: Initialization or database access failed; writes roll back.
        """
        self.initialize()
        try:
            connection = sqlite3.connect(self.path, isolation_level=None, timeout=5)
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("BEGIN")
                try:
                    yield connection
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
            finally:
                connection.close()
        except (sqlite3.Error, OSError) as error:
            raise LibraryStoreError(f"Library database: {error}") from error
