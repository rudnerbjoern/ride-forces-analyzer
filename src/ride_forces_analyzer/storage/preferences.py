"""Best-effort local UI preferences, separate from recordings and export presets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import closing
from enum import StrEnum
from pathlib import Path
import sqlite3
from pydantic import FiniteFloat, TypeAdapter

from .exports import default_database_path
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES, FrameRate
from ride_forces_analyzer.i18n import Language
from typing import Literal
from math import isfinite


class Appearance(StrEnum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"
    VERBOLTEN = "verbolten"
    MANTA = "manta"
    FALCONS_FLIGHT = "falcons_flight"
    TARON = "taron"
    RED_FORCE = "red_force"
    LOCH_NESS = "loch_ness"
    SLINKY_DOG_DASH = "slinky_dog_dash"
    TOP_THRILL_2 = "top_thrill_2"


DirectoryKey = Literal["recording_directory", "export_directory"]
PreferenceKey = Literal[
    DirectoryKey,
    "language",
    "appearance",
    "export_fps",
    "automatic_updates",
    "restore_last_file",
    "last_recording_path",
    "update_checked_at",
    "skipped_update",
]

_LANGUAGE = TypeAdapter(Language)
_APPEARANCE = TypeAdapter(Appearance)
_BOOLEAN = TypeAdapter(bool)
_TEXT = TypeAdapter(str)
_PATH = TypeAdapter(Path)
_TIMESTAMP = TypeAdapter(FiniteFloat)


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        self.path = _PATH.validate_python(
            path if path is not None else default_database_path().with_name("preferences.sqlite3"),
            strict=True,
        )

    def recording_directory(self) -> str:
        return self._directory("recording_directory")

    def export_directory(self) -> str:
        return self._directory("export_directory")

    def restore_last_file(self) -> bool:
        return self._read("restore_last_file") == "true"

    def remember_restore_last_file(self, enabled: bool) -> None:
        enabled = _BOOLEAN.validate_python(enabled, strict=True)
        self._write("restore_last_file", "true" if enabled else "false")

    def last_recording(self) -> Path | None:
        value = self._read("last_recording_path")
        if value:
            try:
                path = Path(value)
                if path.is_absolute() and path.is_file():
                    return path
            except OSError, ValueError:
                pass
        return None

    def _directory(self, key: DirectoryKey) -> str:
        value = self._read(key)
        try:
            return value if value and Path(value).is_dir() else ""
        except OSError, ValueError:
            return ""

    def language(self, default: Language = "en") -> Language:
        default = _LANGUAGE.validate_python(default, strict=True)
        value = self._read("language")
        return "de" if value == "de" else "en" if value == "en" else default

    def appearance(self) -> Appearance:
        value = self._read("appearance")
        try:
            return Appearance(value)
        except ValueError:
            return Appearance.SYSTEM

    def remember_language(self, value: Language) -> None:
        self._write("language", _LANGUAGE.validate_python(value, strict=True))

    def remember_appearance(self, value: Appearance) -> None:
        self._write("appearance", _APPEARANCE.validate_python(value, strict=True).value)

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
        enabled = _BOOLEAN.validate_python(enabled, strict=True)
        self._write("automatic_updates", "true" if enabled else "false")

    def update_check_due(self, now: float) -> bool:
        now = _TIMESTAMP.validate_python(now, strict=True)
        if not self.automatic_updates():
            return False
        try:
            last = float(self._read("update_checked_at"))
        except ValueError:
            return True
        return not isfinite(last) or now < last or now - last >= 86400

    def remember_update_check(self, now: float) -> None:
        self._write("update_checked_at", str(_TIMESTAMP.validate_python(now, strict=True)))

    def skipped_update(self) -> str:
        return self._read("skipped_update")

    def skip_update(self, tag: str) -> None:
        self._write("skipped_update", _TEXT.validate_python(tag, strict=True))

    def _read(self, key: PreferenceKey) -> str:
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

    def _remember(self, key: DirectoryKey, path: Path) -> None:
        path = _PATH.validate_python(path, strict=True)
        try:
            resolved = path.resolve()
            directory = resolved.parent
            if not directory.is_dir():
                return
            self._write(key, str(directory))
            if key == "recording_directory":
                self._write("last_recording_path", str(resolved))
        except OSError, ValueError:
            return

    def _write(self, key: PreferenceKey, value: str) -> None:
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
