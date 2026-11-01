"""Explicit Library archive import and source-backed reopening without Qt widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    CalibrationReferenceError,
    validate_calibration_references,
)
from ride_forces_analyzer.importers import ImportFailure, import_forces, import_forces_bytes
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.validation.checks import validate_sample_range

from .loading import present_recording
from .model import ExplorerData
from .text import failure_text


@dataclass(frozen=True, slots=True)
class ArchiveImportResult:
    """One independent archive-import outcome without retained measurement arrays.

    Attributes:
        path: Selected original file path, never modified by import.
        status: New entry, unchanged duplicate, or failed file.
        source_sha256: Original-byte identity on success, otherwise None.
        error: Explanation for a failed file, otherwise None.
    """

    path: Path
    status: Literal["imported", "duplicate", "failed"]
    source_sha256: str | None = None
    error: str | None = None


class LibraryArchive:
    """Compose archive persistence with existing importer and analysis services.

    Attributes:
        store: Library persistence boundary.
        preferences: Existing marker choices used only when first archiving a source.
    """

    def __init__(
        self,
        store: LibraryStore | None = None,
        preferences: Preferences | None = None,
    ) -> None:
        """Select the archive and existing marker preferences without opening files.

        Args:
            store: Explicit Library store, or the application-local store.
            preferences: Existing preferences, or their application-local default.
        """
        self.store = store if store is not None else LibraryStore()
        self.preferences = preferences if preferences is not None else Preferences()

    def import_paths(self, paths: Sequence[Path]) -> tuple[ArchiveImportResult, ...]:
        """Archive successful files independently, keeping duplicates completely unchanged.

        Args:
            paths: Explicitly selected files; ordinary file opening never calls this.

        Returns:
            One ordered result per file; an expected failure does not stop later files.
        """
        results: list[ArchiveImportResult] = []
        for path in paths:
            try:
                source = import_forces(path)
                if isinstance(source, ImportFailure):
                    results.append(ArchiveImportResult(path, "failed", error=failure_text(source)))
                    continue
                indices = source.recording.indices
                bounds = self.preferences.recording_bounds(source.source_sha256)
                if bounds is None or bounds[1] >= len(source.recording.motion.acceleration):
                    bounds = (indices.start, indices.end)
                calibration = self.preferences.recording_calibration(source.source_sha256)
                if calibration is None:
                    calibration = CalibrationOverrides()
                try:
                    validate_calibration_references(
                        source,
                        calibration,
                        calculation_time=datetime.now(UTC),
                    )
                except CalibrationReferenceError:
                    calibration = CalibrationOverrides()
                added = self.store.archive(source, path.name, bounds, calibration)
                results.append(
                    ArchiveImportResult(
                        path,
                        "imported" if added else "duplicate",
                        source.source_sha256,
                    ),
                )
            except (LibraryStoreError, OSError, ValueError) as error:
                results.append(ArchiveImportResult(path, "failed", error=str(error)))
        return tuple(results)

    def reopen(self, source_sha256: str) -> ExplorerData | ImportFailure:
        """Reopen exact archived bytes through existing decoding and analysis services.

        Args:
            source_sha256: Original-byte identity of the selected archived recording.

        Returns:
            Explorer presentation with archived markers, or a structured decoding failure.

        Raises:
            LibraryStoreError: The entry or stored marker recipe is missing or invalid.
            ValueError: The requested digest is invalid or source values cannot be displayed.
        """
        archived = self.store.source(source_sha256)
        source = import_forces_bytes(archived.data, compressed=archived.compressed)
        if isinstance(source, ImportFailure):
            return source
        now = datetime.now(UTC)
        try:
            validate_sample_range(
                *archived.bounds,
                len(source.recording.motion.acceleration),
                "Invalid Library bounds",
            )
            validate_calibration_references(source, archived.calibration, calculation_time=now)
        except (ValueError, TypeError) as error:
            raise LibraryStoreError("Invalid archived recording markers") from error
        data = present_recording(source)
        if data.analysis is not None:
            snapshot = data.analysis
            configuration = replace(
                snapshot.configuration,
                ride_bounds=archived.bounds,
                calibration=archived.calibration,
            )
            if configuration != snapshot.configuration:
                data = data.with_analysis(
                    snapshot.with_configuration(
                        configuration,
                        revision=snapshot.revision + 1,
                        calculation_time=now,
                    ),
                )
        return data
