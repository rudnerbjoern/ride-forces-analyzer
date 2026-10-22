"""Best-effort SQLite raster tile cache, independent of recordings and analysis.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import closing, contextmanager
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from time import time

from ride_forces_analyzer.runtime_paths import data_directory

MAX_CACHE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class TileEntry:
    data: bytes
    expires: float
    etag: str
    modified: str


class TileCache:
    """Store tile bytes and HTTP validators; evict least recently used images.

    Each operation owns a short connection/transaction. Storage failures are cache
    misses or ignored writes, so an unavailable cache never prevents map loading.
    The byte limit covers PNG payloads; SQLite metadata adds a small overhead.
    """

    def __init__(self, path: Path | None = None, max_bytes: int = MAX_CACHE_BYTES) -> None:
        if max_bytes <= 0:
            raise ValueError("Cache limit must be positive")
        self.path = path if path is not None else data_directory() / "map-cache.sqlite3"
        self.max_bytes = max_bytes

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=0.1)) as connection:
            connection.execute("PRAGMA auto_vacuum = FULL")
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS tiles ("
                    "provider TEXT NOT NULL, zoom INTEGER NOT NULL, x INTEGER NOT NULL, "
                    "y INTEGER NOT NULL, data BLOB NOT NULL, expires REAL NOT NULL, "
                    "etag TEXT NOT NULL, modified TEXT NOT NULL, accessed REAL NOT NULL, "
                    "PRIMARY KEY (provider, zoom, x, y))",
                )
                yield connection

    def get(self, provider: str, zoom: int, x: int, y: int) -> TileEntry | None:
        """Read one tile and record its use, including expired entries for revalidation."""
        try:
            with self._connection() as connection:
                key = (provider, zoom, x, y)
                row = connection.execute(
                    "SELECT data, expires, etag, modified FROM tiles "
                    "WHERE provider=? AND zoom=? AND x=? AND y=?",
                    key,
                ).fetchone()
                if row is None:
                    return None
                connection.execute(
                    "UPDATE tiles SET accessed=? WHERE provider=? AND zoom=? AND x=? AND y=?",
                    (time(), *key),
                )
                return TileEntry(*row)
        except OSError, sqlite3.Error:
            return None

    def put(self, provider: str, zoom: int, x: int, y: int, entry: TileEntry) -> None:
        """Atomically replace a tile and trim oldest uses to the PNG byte budget."""
        if len(entry.data) > self.max_bytes:
            return
        try:
            with self._connection() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        provider,
                        zoom,
                        x,
                        y,
                        entry.data,
                        entry.expires,
                        entry.etag,
                        entry.modified,
                        time(),
                    ),
                )
                total: int = connection.execute(
                    "SELECT COALESCE(SUM(length(data)), 0) FROM tiles",
                ).fetchone()[0]
                if total > self.max_bytes:
                    for rowid, size in connection.execute(
                        "SELECT rowid, length(data) FROM tiles ORDER BY accessed, rowid",
                    ).fetchall():
                        connection.execute("DELETE FROM tiles WHERE rowid=?", (rowid,))
                        total -= size
                        if total <= self.max_bytes:
                            break
        except OSError, sqlite3.Error:
            pass

    def delete(self, provider: str, zoom: int, x: int, y: int) -> None:
        """Remove a tile when HTTP forbids storage."""
        try:
            with self._connection() as connection:
                connection.execute(
                    "DELETE FROM tiles WHERE provider=? AND zoom=? AND x=? AND y=?",
                    (provider, zoom, x, y),
                )
        except OSError, sqlite3.Error:
            pass

    def clear(self) -> bool:
        """Delete every tile and its HTTP metadata; report failure to the caller."""
        try:
            with self._connection() as connection:
                connection.execute("DELETE FROM tiles")
            return True
        except OSError, sqlite3.Error:
            return False
