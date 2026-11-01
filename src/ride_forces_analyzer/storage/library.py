"""Transactional Library schema upgrades and ordinary SQLite connections.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words sqlalchemy autocommit poolclass

from collections.abc import Generator
from contextlib import contextmanager
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


class LibraryStoreError(Exception):
    """Library access failed without replacing the database or discarding its data."""


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
