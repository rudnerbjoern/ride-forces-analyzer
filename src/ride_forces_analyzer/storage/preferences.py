"""Best-effort local UI preferences, separate from recordings and export presets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import closing
from pathlib import Path
import sqlite3

from .exports import default_database_path
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES, FrameRate
from ride_forces_analyzer.i18n import Language
from typing import Literal
from math import isfinite


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        self.path = (
            path if path is not None else default_database_path().with_name("preferences.sqlite3")
        )

    def recording_directory(self) -> str:
        return self._directory("recording_directory")

    def export_directory(self) -> str:
        return self._directory("export_directory")

    def _directory(self, key: str) -> str:
        value = self._read(key)
        try:
            return value if value and Path(value).is_dir() else ""
        except OSError, ValueError:
            return ""

    def language(self, default: Language = "en") -> Language:
        value = self._read("language")
        return "de" if value == "de" else "en" if value == "en" else default

    def appearance(self) -> Literal["dark", "light", "system"]:
        value = self._read("appearance")
        return "light" if value == "light" else "dark" if value == "dark" else "system"

    def remember_language(self, value: Language) -> None:
        self._write("language", value)

    def remember_appearance(self, value: Literal["dark", "light", "system"]) -> None:
        self._write("appearance", value)

    def export_fps(self) -> FrameRate:
        value = self._read("export_fps")
        for rate in EXPORT_FRAME_RATES:
            if str(rate) == value:
                return rate
        return 50

    def remember_export_fps(self, value: FrameRate) -> None:
        if type(value) not in (int, str) or value not in EXPORT_FRAME_RATES:
            raise ValueError("Unsupported default export frame rate")
        self._write("export_fps", str(value))

    def automatic_updates(self) -> bool:
        return self._read("automatic_updates") == "true"

    def remember_automatic_updates(self, enabled: bool) -> None:
        self._write("automatic_updates", "true" if enabled else "false")

    def update_check_due(self, now: float) -> bool:
        if not self.automatic_updates():
            return False
        try:
            last = float(self._read("update_checked_at"))
        except ValueError:
            return True
        return not isfinite(last) or now < last or now - last >= 86400

    def remember_update_check(self, now: float) -> None:
        self._write("update_checked_at", str(now))

    def skipped_update(self) -> str:
        return self._read("skipped_update")

    def skip_update(self, tag: str) -> None:
        self._write("skipped_update", tag)

    def _read(self, key: str) -> str:
        try:
            if not self.path.is_file():
                return ""
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection:
                row = connection.execute(
                    "SELECT value FROM preferences WHERE key = ?",
                    (key,),
                ).fetchone()
            return row[0] if row and isinstance(row[0], str) else ""
        except OSError, sqlite3.Error, ValueError:
            return ""

    def remember_recording(self, path: Path) -> None:
        self._remember("recording_directory", path)

    def remember_export(self, path: Path) -> None:
        self._remember("export_directory", path)

    def _remember(self, key: str, path: Path) -> None:
        try:
            directory = path.resolve().parent
            if not directory.is_dir():
                return
            self._write(key, str(directory))
        except OSError, ValueError:
            return

    def _write(self, key: str, value: str) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection, connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                )
                connection.execute(
                    "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                    (key, value),
                )
        except OSError, sqlite3.Error, ValueError:
            # Optional preferences must never prevent opening a recording.
            return
