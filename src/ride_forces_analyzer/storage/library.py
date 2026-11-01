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
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.importers.library_metadata import project_library_metadata
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
    ) -> bool:
        """Insert a complete import once, preserving every existing entry on duplicates.

        Args:
            source: Successful import owning the exact original source bytes.
            filename: Original supported basename, not an external storage dependency.
            bounds: Valid inclusive bounds resolved from source/defaults and preferences.
            calibration: Reference choices admitted by the existing calibration service.

        Returns:
            True for a new entry; False for byte-identical input already archived.

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
        with self.connection() as connection:
            imported_at = (
                datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
            )
            cursor = connection.execute(
                "INSERT INTO recordings (source_sha256, source_bytes, source_filename, source_format, "
                "source_byte_count, source_ride_name, source_park_name, recorded_at_utc, recorded_day, "
                "day_timezone, imported_at_utc, first_sample, last_sample, gravity_index, incline_index, "
                "calibration_algorithm_version, calibration_window_samples, search_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '') "
                "ON CONFLICT(source_sha256) DO NOTHING",
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
                ),
            )
            return cursor.rowcount == 1

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
