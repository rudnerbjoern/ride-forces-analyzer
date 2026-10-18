"""Small transactional SQLite store; no Qt, source recordings or rendered media.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words LOCALAPPDATA NOCASE

from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from .export_models import SavedBatch, SavedPreset, BatchJob


def default_database_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / "AppData" / "Local"
    return root / "Ride Forces Analyzer" / "exports.sqlite3"


class ExportStoreError(Exception):
    """A storage operation failed without replacing the database or user data."""


class ExportStore:
    def __init__(self, path: Path) -> None:
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
        with self._connection() as db:
            return tuple(
                SavedPreset.model_validate_json(row[0])
                for row in db.execute("SELECT payload FROM presets ORDER BY name COLLATE NOCASE")
            )

    def batches(self) -> tuple[SavedBatch, ...]:
        with self._connection() as db:
            return tuple(
                SavedBatch.model_validate_json(row[0])
                for row in db.execute("SELECT payload FROM batches ORDER BY name COLLATE NOCASE")
            )

    def save_preset(self, preset: SavedPreset, *, overwrite: bool = False) -> None:
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
        with self._connection() as db:
            db.execute("DELETE FROM presets WHERE name=?", (name,))

    def create_batch(self, name: str) -> SavedBatch:
        batch = SavedBatch(name=name)
        self.save_batch(batch)
        return batch

    def batch(self, name: str) -> SavedBatch:
        with self._connection() as db:
            row = db.execute("SELECT payload FROM batches WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ExportStoreError("The selected batch no longer exists")
            return SavedBatch.model_validate_json(row[0])

    def append_jobs(self, name: str, jobs: tuple[BatchJob, ...]) -> None:
        with self._connection() as db:
            row = db.execute("SELECT payload FROM batches WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ExportStoreError("Choose or create a batch first")
            batch = SavedBatch.model_validate_json(row[0])
            updated = SavedBatch(name=batch.name, jobs=(*batch.jobs, *jobs))
            db.execute(
                "UPDATE batches SET payload=? WHERE name=?",
                (updated.model_dump_json(), name),
            )

    def remove_jobs(self, name: str, indices: tuple[int, ...]) -> None:
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
        with self._connection() as db:
            db.execute("DELETE FROM batches WHERE name=?", (name,))
