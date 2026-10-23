"""Best-effort local UI preferences, separate from recordings and export presets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
import sqlite3
from pydantic import FiniteFloat, TypeAdapter

from .exports import default_database_path
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES, FrameRate
from ride_forces_analyzer.i18n import LANGUAGES, Language
from typing import Literal
from math import isfinite
import re

from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    CalibrationReferenceError,
    validate_calibration_references,
)
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.importers import ImportSuccess

_RECORDING_BOUNDS = TypeAdapter(tuple[int, int])


def _recording_hash(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected a source SHA-256")
    return value


def _recording_bounds(value: tuple[int, int]) -> tuple[int, int]:
    first, last = _RECORDING_BOUNDS.validate_python(value, strict=True)
    if not 0 <= first <= last:
        raise ValueError("Ride markers must be ordered and nonnegative")
    return first, last


def _save_recording_bounds(
    connection: sqlite3.Connection,
    identifier: str,
    bounds: tuple[int, int] | None,
) -> None:
    """Write admitted bounds within the caller's transaction."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS recording_bounds (source_sha256 TEXT PRIMARY KEY, "
        "first_sample INTEGER NOT NULL, last_sample INTEGER NOT NULL)",
    )
    if bounds is None:
        connection.execute("DELETE FROM recording_bounds WHERE source_sha256 = ?", (identifier,))
    else:
        connection.execute(
            "INSERT OR REPLACE INTO recording_bounds VALUES (?, ?, ?)",
            (identifier, *bounds),
        )


def _save_recording_calibration(
    connection: sqlite3.Connection,
    identifier: str,
    calibration: CalibrationOverrides,
) -> None:
    """Write an admitted reference recipe within the caller's transaction."""
    connection.execute(
        "CREATE TABLE IF NOT EXISTS recording_calibration (source_sha256 TEXT PRIMARY KEY, "
        "gravity_index INTEGER, incline_index INTEGER, algorithm_version TEXT NOT NULL, "
        "window_samples INTEGER NOT NULL)",
    )
    if not calibration.active:
        connection.execute(
            "DELETE FROM recording_calibration WHERE source_sha256 = ?",
            (identifier,),
        )
    else:
        connection.execute(
            "INSERT OR REPLACE INTO recording_calibration VALUES (?, ?, ?, ?, ?)",
            (
                identifier,
                calibration.gravity_index,
                calibration.incline_index,
                calibration.algorithm_version,
                calibration.window_samples,
            ),
        )


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
    def remember_recording_markers(
        self,
        source: ImportSuccess,
        bounds: tuple[int, int] | None,
        calibration: CalibrationOverrides,
    ) -> bool:
        """Atomically save/reset all marker choices after numerical admission.

        Invalid choices raise before writing; storage failure leaves the previous
        transaction intact and returns False. Original source evidence is retained.
        """
        if bounds is not None:
            bounds = _recording_bounds(bounds)
            if bounds[1] >= len(source.recording.motion.acceleration):
                raise ValueError("Ride markers outside recording")
        validate_calibration_references(source, calibration, calculation_time=datetime.now(UTC))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection, connection:
                _save_recording_bounds(connection, source.source_sha256, bounds)
                _save_recording_calibration(connection, source.source_sha256, calibration)
            return True
        except OSError, sqlite3.Error, ValueError:
            return False

    def recording_calibration(self, source_sha256: str) -> CalibrationOverrides | None:
        """Read a versioned reference recipe; corrupt/unsupported rows stay untouched."""
        identifier = _recording_hash(source_sha256)
        try:
            if not self.path.is_file():
                return None
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection:
                row = connection.execute(
                    "SELECT gravity_index, incline_index, algorithm_version, window_samples "
                    "FROM recording_calibration WHERE source_sha256 = ?",
                    (identifier,),
                ).fetchone()
            return CalibrationOverrides(*row) if row else None
        except OSError, sqlite3.Error, ValueError, TypeError:
            return None

    def remember_recording_calibration(
        self,
        source: ImportSuccess,
        calibration: CalibrationOverrides,
    ) -> bool:
        """Save admitted source-bound references or reset them, preserving ride bounds.

        Invalid references raise before any database write. Storage errors return
        False. No original recording data or direction vectors are written here.
        """
        validate_calibration_references(source, calibration, calculation_time=datetime.now(UTC))
        identifier = source.source_sha256
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection, connection:
                _save_recording_calibration(connection, identifier, calibration)
            return True
        except OSError, sqlite3.Error, ValueError:
            return False

    def recording_configuration(
        self,
        source: ImportSuccess,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> AnalysisConfiguration:
        """Resolve valid local markers for a fresh import, without changing source evidence.

        Invalid optional entries are ignored independently and never deleted.
        Numerical stages remain owned by the caller's analysis service/snapshot.
        Saved jobs must use their bound recipe instead of this local lookup.
        """
        bounds = self.recording_bounds(source.source_sha256)
        if bounds is None or bounds[1] >= len(source.recording.motion.acceleration):
            bounds = configuration.ride_bounds
        calibration = self.recording_calibration(source.source_sha256)
        if calibration is not None:
            try:
                validate_calibration_references(
                    source,
                    calibration,
                    calculation_time=calculation_time,
                )
            except CalibrationReferenceError:
                calibration = None
        return replace(
            configuration,
            ride_bounds=bounds,
            calibration=calibration if calibration is not None else configuration.calibration,
        )

    def recording_bounds(self, source_sha256: str) -> tuple[int, int] | None:
        """Read optional content-bound markers; missing/unreadable storage is ignored."""
        identifier = _recording_hash(source_sha256)
        try:
            if not self.path.is_file():
                return None
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection:
                row = connection.execute(
                    "SELECT first_sample, last_sample FROM recording_bounds WHERE source_sha256 = ?",
                    (identifier,),
                ).fetchone()
            return _recording_bounds(tuple(row)) if row else None
        except OSError, sqlite3.Error, ValueError:
            return None

    def remember_recording_bounds(
        self,
        source_sha256: str,
        bounds: tuple[int, int] | None,
    ) -> bool:
        """Save/reset local markers, returning False on storage failure; never write a source."""
        identifier = _recording_hash(source_sha256)
        if bounds is not None:
            bounds = _recording_bounds(bounds)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.1)) as connection, connection:
                _save_recording_bounds(connection, identifier, bounds)
            return True
        except OSError, sqlite3.Error, ValueError:
            return False

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
        for language in LANGUAGES:
            if value == language:
                return language
        return default

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
