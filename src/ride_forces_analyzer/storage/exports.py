"""Small transactional SQLite store; no Qt, source recordings or rendered media.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words LOCALAPPDATA NOCASE

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from .export_models import SavedBatch, SavedPreset, BatchJob
from ride_forces_analyzer.runtime_paths import data_directory


def default_database_path() -> Path:
    """Return the platform-local export-definition database path.

    Returns:
        The platform-local export-definition database path.
    """
    return data_directory() / "exports.sqlite3"


class ExportStoreError(Exception):
    """A storage operation failed without replacing the database or user data."""


class ExportStore:
    """Export store contract and owned data.

    Attributes:
        path: Filesystem path read or written by this operation.
    """

    def __init__(self, path: Path) -> None:
        """Initialize export store and its owned state.

        Args:
            path: Filesystem path read or written by this operation.

        Returns:
            None.
        """
        self.path = path.resolve()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5)
            try:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise ExportStoreError(
                        "This export database uses an unsupported schema version",
                    )
                with connection:
                    if version == 0:
                        tables = connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT GLOB 'sqlite_*'",
                        ).fetchall()
                        if tables:
                            raise ExportStoreError(
                                "This existing database has no recognized export schema version",
                            )
                        connection.execute(
                            "CREATE TABLE IF NOT EXISTS presets (name TEXT PRIMARY KEY COLLATE NOCASE, payload TEXT NOT NULL)",
                        )
                        connection.execute(
                            "CREATE TABLE IF NOT EXISTS batches (name TEXT PRIMARY KEY COLLATE NOCASE, payload TEXT NOT NULL)",
                        )
                        connection.execute("PRAGMA user_version = 1")
                    yield connection
            finally:
                connection.close()
        except sqlite3.IntegrityError as error:
            raise ExportStoreError(
                "This name already exists. Choose a new name or update the selected item.",
            ) from error
        except (sqlite3.Error, OSError, ValidationError) as error:
            raise ExportStoreError(f"Export database: {error}") from error

    def presets(self) -> tuple[SavedPreset, ...]:
        """Read saved visual export presets from the local database.

        Returns:
            Saved visual presets in repository order.
        """
        with self._connection() as db:
            return tuple(
                SavedPreset.model_validate_json(row[0])
                for row in db.execute("SELECT payload FROM presets ORDER BY name COLLATE NOCASE")
            )

    def batches(self) -> tuple[SavedBatch, ...]:
        """Read saved batch definitions from the local database.

        Returns:
            Saved batch definitions in repository order.
        """
        with self._connection() as db:
            return tuple(
                SavedBatch.model_validate_json(row[0])
                for row in db.execute("SELECT payload FROM batches ORDER BY name COLLATE NOCASE")
            )

    def save_preset(self, preset: SavedPreset, *, overwrite: bool = False) -> None:
        """Persist a validated preset with explicit replacement policy.

        Args:
            preset: Validated immutable export preset to store or apply.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.

        Returns:
            None.

        Raises:
            ExportStoreError: The selected preset no longer exists.
        """
        with self._connection() as db:
            if overwrite:
                if (
                    db.execute(
                        "UPDATE presets SET payload=? WHERE name=?",
                        (preset.model_dump_json(), preset.name),
                    ).rowcount
                    != 1
                ):
                    raise ExportStoreError("The selected preset no longer exists")
            else:
                db.execute(
                    "INSERT INTO presets VALUES (?, ?)",
                    (preset.name, preset.model_dump_json()),
                )

    def save_batch(self, batch: SavedBatch, *, overwrite: bool = False) -> None:
        """Persist a validated batch definition with explicit replacement policy.

        Args:
            batch: Validated saved batch definition.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.

        Returns:
            None.

        Raises:
            ExportStoreError: The selected batch no longer exists.
        """
        with self._connection() as db:
            if overwrite:
                if (
                    db.execute(
                        "UPDATE batches SET payload=? WHERE name=?",
                        (batch.model_dump_json(), batch.name),
                    ).rowcount
                    != 1
                ):
                    raise ExportStoreError("The selected batch no longer exists")
            else:
                db.execute(
                    "INSERT INTO batches VALUES (?, ?)",
                    (batch.name, batch.model_dump_json()),
                )

    def delete_preset(self, name: str) -> None:
        """Delete the named saved preset from local storage.

        Args:
            name: Display name or identifier used to select the requested item.

        Returns:
            None.
        """
        with self._connection() as db:
            db.execute("DELETE FROM presets WHERE name=?", (name,))

    def create_batch(self, name: str) -> SavedBatch:
        """Create and persist an empty named batch.

        Args:
            name: Display name or identifier used to select the requested item.

        Returns:
            The newly persisted empty batch.
        """
        batch = SavedBatch(name=name, schema_version=1, jobs=())
        self.save_batch(batch)
        return batch

    def batch(self, name: str) -> SavedBatch:
        """Read the named saved batch from local storage.

        Args:
            name: Display name or identifier used to select the requested item.

        Returns:
            The matching saved batch definition.

        Raises:
            ExportStoreError: The selected batch no longer exists.
        """
        with self._connection() as db:
            row = db.execute("SELECT payload FROM batches WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ExportStoreError("The selected batch no longer exists")
            return SavedBatch.model_validate_json(row[0])

    def append_jobs(self, name: str, jobs: tuple[BatchJob, ...]) -> None:
        """Append immutable jobs to the named stored batch.

        Args:
            name: Display name or identifier used to select the requested item.
            jobs: Immutable video jobs in their selected execution order.

        Returns:
            None.

        Raises:
            ExportStoreError: Choose or create a batch first.
        """
        with self._connection() as db:
            row = db.execute("SELECT payload FROM batches WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ExportStoreError("Choose or create a batch first")
            batch = SavedBatch.model_validate_json(row[0])
            updated = SavedBatch(name=batch.name, jobs=(*batch.jobs, *jobs), schema_version=1)
            db.execute(
                "UPDATE batches SET payload=? WHERE name=?",
                (updated.model_dump_json(), name),
            )

    def remove_jobs(self, name: str, indices: tuple[int, ...]) -> None:
        """Remove the selected job rows from the named stored batch.

        Args:
            name: Display name or identifier used to select the requested item.
            indices: Selected source or stored-row indices.

        Returns:
            None.

        Raises:
            ExportStoreError: The selected batch no longer exists.
            ValueError: Invalid batch row.
        """
        with self._connection() as db:
            row = db.execute("SELECT payload FROM batches WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ExportStoreError("The selected batch no longer exists")
            batch = SavedBatch.model_validate_json(row[0])
            if any(index < 0 or index >= len(batch.jobs) for index in indices):
                raise ValueError("Invalid batch row")
            updated = batch.model_copy(
                update={
                    "jobs": tuple(
                        job for index, job in enumerate(batch.jobs) if index not in indices
                    ),
                },
            )
            db.execute(
                "UPDATE batches SET payload=? WHERE name=?",
                (updated.model_dump_json(), name),
            )

    def delete_batch(self, name: str) -> None:
        """Delete the named batch definition from local storage.

        Args:
            name: Display name or identifier used to select the requested item.

        Returns:
            None.
        """
        with self._connection() as db:
            db.execute("DELETE FROM batches WHERE name=?", (name,))
