"""Explicit Library archive import and source-backed reopening without Qt widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    CalibrationReferenceError,
    validate_calibration_references,
)
from ride_forces_analyzer.importers import (
    ImportFailure,
    ImportSuccess,
    import_forces,
    import_forces_bytes,
)
from ride_forces_analyzer.storage.library import LibraryEntry, LibraryStore, LibraryStoreError
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.domain import ValueOrigin
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.validation.checks import validate_sample_range

from .loading import present_recording
from .model import ExplorerData
from .text import failure_text, metadata_fields


def recording_clock(entry: LibraryEntry) -> str:
    """Format a recording's clock time at its source location, independently of the host.

    Args:
        entry: Lightweight Library metadata with an optional recording instant.

    Returns:
        HH:MM:SS at the recording location, or an em dash for an unknown instant.
    """
    if entry.recorded_at_utc is None:
        return "—"
    try:
        instant = datetime.fromisoformat(entry.recorded_at_utc)
        if instant.tzinfo is None:
            return "—"
        zone = ZoneInfo(entry.day_timezone) if entry.day_timezone else UTC
        return instant.astimezone(zone).strftime("%H:%M:%S")
    except ValueError, OverflowError, ZoneInfoNotFoundError:
        return "—"


def library_details(entry: LibraryEntry, data: ExplorerData | None = None) -> str:
    """Format read-only source/date/import details inside the Library panel.

    Args:
        entry: Selected list entry, retaining original and effective source names.
        data: Successfully reopened recording supplying additional original metadata.

    Returns:
        Plain text suitable for a read-only, wrapping detail view.
    """
    recorded = (
        f"{entry.recorded_day} {recording_clock(entry)} ({entry.day_timezone})"
        if entry.recorded_day is not None
        else tr("Unknown date")
    )
    lines = [
        f"{tr('Source file')}: {entry.filename}",
        f"{tr('Recording time')}: {recorded}",
        f"{tr('Import time (UTC)')}: {entry.imported_at_utc}",
        f"{tr('Ride')}: {entry.source_ride_name or '—'}",
        f"{tr('Park')}: {entry.source_park_name or '—'}",
    ]
    if data is not None:
        metadata = data.source.recording.metadata
        for label, value in (
            ("Device", metadata.device),
            ("UUID", metadata.uuid),
            ("Source date", metadata.date.token if metadata.date is not None else None),
            ("Source time zone", metadata.timezone),
            (
                "Riding position",
                metadata.riding_position.value
                if metadata.riding_position is not None
                and metadata.riding_position.origin is ValueOrigin.SOURCE
                else None,
            ),
        ):
            if value is not None:
                lines.append(f"{tr(label)}: {value}")
        lines.extend(
            f"{tr(label)}: {value}"
            for label, value in metadata_fields(data, original=True)
            if label not in {"Ride", "Park"}
        )
        additions = data.source.additions
        if additions != RecordingAdditions():
            lines.append(f"{tr('Library additions')}:")
            for label, value in (
                ("Ride", additions.ride_name),
                ("Park", additions.park_name),
                ("Row", additions.row),
                ("Seat", additions.seat),
                ("Train", additions.train),
                ("Riding position", additions.riding_position),
                ("Notes", additions.notes or None),
            ):
                if value is not None:
                    lines.append(f"{tr(label)}: {value or '—'}")
    return "\n".join(lines)


def library_row_text(entry: LibraryEntry) -> str:
    """Format a compact recording entry without table columns.

    Args:
        entry: Lightweight recording metadata and export count.

    Returns:
        Three lines containing ride, park and source-local clock/export summary.
    """
    exports = (
        tr("{0} export", entry.export_count)
        if entry.export_count == 1
        else tr("{0} exports", entry.export_count)
    )
    return "\n".join(
        (
            entry.ride_name or tr("Unknown ride"),
            entry.park_name or tr("Unknown park"),
            f"{recording_clock(entry)[:5]} · {exports}",
        ),
    )


@dataclass(frozen=True, slots=True)
class ArchiveImportResult:
    """One independent archive-import outcome without retained measurement arrays.

    Attributes:
        path: Selected original file path, never modified by import.
        status: New entry, updated source, unchanged duplicate, or failed file.
        source_sha256: Current archived original-byte identity on success, otherwise None.
        error: Explanation for a failed file, otherwise None.
    """

    path: Path
    status: Literal["imported", "updated", "duplicate", "failed"]
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
        """Archive files independently, updating changed exports of known recording UUIDs.

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
                status, digest = self.store.archive(source, path.name, bounds, calibration)
                results.append(
                    ArchiveImportResult(
                        path,
                        status,
                        digest,
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
        source = ImportSuccess(source.recording, source.diagnostics, additions=archived.additions)
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
                ride_bounds=None
                if archived.bounds == (source.recording.indices.start, source.recording.indices.end)
                else archived.bounds,
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

    def recording_configuration(
        self,
        source: ImportSuccess,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> AnalysisConfiguration:
        """Resolve Library markers first, retaining preferences for non-archived input.

        Args:
            source: Lossless import identified by its original-byte hash.
            configuration: Fresh analysis configuration, never a saved job recipe.
            calculation_time: Timestamp for preference reference validation.

        Returns:
            Configuration using the authoritative current marker choices.

        Raises:
            ValueError: Archived choices are invalid.
            LibraryStoreError: The Library cannot be read.
        """
        markers = self.store.markers(source)
        if markers is None:
            return self.preferences.recording_configuration(
                source,
                configuration,
                calculation_time=calculation_time,
            )
        bounds, calibration = markers
        indices = source.recording.indices
        return replace(
            configuration,
            ride_bounds=None if bounds == (indices.start, indices.end) else bounds,
            calibration=calibration,
        )

    def remember_recording_markers(
        self,
        source: ImportSuccess,
        bounds: tuple[int, int] | None,
        calibration: CalibrationOverrides,
    ) -> bool:
        """Save admitted marker choices to their owning Library or preference store.

        Args:
            source: Import identifying the recording and original defaults.
            bounds: Inclusive bounds, or None to reset to source defaults.
            calibration: Admitted calibration reference recipe.

        Returns:
            True on success; False on storage failure without fallback writes.

        Raises:
            ValueError: Marker choices are invalid.
        """
        try:
            if self.store.update_markers(source, bounds, calibration):
                return True
        except LibraryStoreError:
            return False
        return self.preferences.remember_recording_markers(source, bounds, calibration)

    def apply_metadata(self, data: ExplorerData) -> ExplorerData:
        """Apply Library additions to an external open without repeating numerical analysis.

        Args:
            data: Successfully loaded external recording and optional prepared analysis.

        Returns:
            Data with current Library additions, or unchanged data for external sources.

        Raises:
            LibraryStoreError: Library metadata cannot be read.
            ValueError: Stored additions are invalid.
        """
        additions = self.store.metadata(data.source.source_sha256)
        if additions is None or additions == data.source.additions:
            return data
        source = ImportSuccess(data.source.recording, data.source.diagnostics, additions=additions)
        analysis = replace(data.analysis, source=source) if data.analysis is not None else None
        return replace(
            data,
            source=source,
            analysis=analysis,
            title=source.effective_metadata.name or data.title,
        )
