"""Recording-bound export attempts, independent of exporters and Qt.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words timespec lastrowid

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from ride_forces_analyzer import __version__
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration, RecordingAnalysis
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.rendering.model import (
    ExportRecordingMetadata,
    ExportSettings,
    ExportSnapshot,
    analysis_configuration_metadata,
)
from ride_forces_analyzer.validation.checks import validate_sha256
from .library import LibraryStore, LibraryStoreError

ExportKind = Literal["video", "csv", "json", "analyzer_json"]
ExportStatus = Literal["running", "completed", "failed", "cancelled", "interrupted"]


class ExportRequest(BaseModel, frozen=True, strict=True, extra="forbid"):
    """Freeze requested settings; data exports also use this as their effective snapshot.

    Attributes:
        schema_version: Version of this requested/data-export recipe.
        kind: Existing video or data format identifier.
        source_sha256: Exact original-byte identity.
        analysis_configuration: Captured markers, calibration and numerical recipe.
        first_sample: First included source sample.
        last_sample: Last included source sample.
        settings: Requested video settings; absent for data exports.
        additions: Captured additions, or None for legacy original-source semantics.
        recording_metadata: Effective labels when analysis was available.
    """

    schema_version: Literal[1] = 1
    kind: ExportKind
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_configuration: AnalysisConfiguration
    first_sample: int
    last_sample: int
    settings: ExportSettings | None = None
    additions: RecordingAdditions | None = None
    recording_metadata: ExportRecordingMetadata | None = None

    @field_serializer("analysis_configuration")
    def serialize_configuration(self, value: AnalysisConfiguration) -> dict[str, object]:
        """Use the shared analysis recipe representation.

        Args:
            value: Captured immutable configuration.

        Returns:
            JSON-compatible recipe without computed arrays.
        """
        return analysis_configuration_metadata(value)

    @classmethod
    def capture(
        cls,
        analysis: RecordingAnalysis,
        kind: ExportKind,
        first: int,
        last: int,
        settings: ExportSettings | None = None,
    ) -> "ExportRequest":
        """Capture requested values before preparing an output.

        Args:
            analysis: Bound source and current immutable analysis.
            kind: Output format.
            first: Inclusive first sample.
            last: Inclusive last sample.
            settings: Video settings, absent for data exports.

        Returns:
            Frozen source-bound request.
        """
        return cls(
            kind=kind,
            source_sha256=analysis.source.source_sha256,
            analysis_configuration=analysis.configuration,
            first_sample=first,
            last_sample=last,
            settings=settings,
            additions=analysis.source.additions,
            recording_metadata=ExportRecordingMetadata.from_source(analysis.source),
        )


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One persisted attempt, retaining unsupported recipes without rewriting them.

    Attributes:
        id: Local attempt identity.
        source_sha256: Recording foreign key.
        kind: Output format identifier.
        origin: Single export or batch job.
        started_at: UTC attempt start.
        finished_at: UTC finish when known.
        duration: Monotonic elapsed attempt seconds, excluding queue waiting.
        status: Stored running or terminal outcome.
        application_version: Application creating the attempt.
        request_json: Frozen requested settings.
        snapshot_json: Effective shared video snapshot or data recipe, when prepared.
        output_path: Destination, without requiring the output to remain present.
        file_size: Successfully published file length, when known.
        gpu_encoding: Observed backend selection, otherwise None.
        error: Failure, cancellation or interruption explanation.
    """

    id: int
    source_sha256: str
    kind: str
    origin: str
    started_at: str
    finished_at: str | None
    duration: float | None
    status: str
    application_version: str
    request_json: str
    snapshot_json: str | None
    output_path: str | None
    file_size: int | None
    gpu_encoding: bool | None
    error: str | None


_COLUMNS = (
    "id,recording_sha256,export_kind,origin,started_at_utc,finished_at_utc,duration_seconds,"
    "status,application_version,request_json,export_snapshot_json,output_path,file_size_bytes,"
    "gpu_encoding,error"
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class LibraryHistory:
    """Persist attempt states in the existing Library table.

    Attributes:
        store: Library owning connections and transactions.
    """

    def __init__(self, store: LibraryStore | None = None) -> None:
        """Select persistence without creating an attempt.

        Args:
            store: Explicit Library, or the application-local default.
        """
        self.store = store if store is not None else LibraryStore()

    def entries(self, source_sha256: str) -> tuple[HistoryEntry, ...]:
        """List attempts newest first, without reading source BLOBs.

        Args:
            source_sha256: Recording identity.

        Returns:
            Distinct attempts including unsupported saved recipe versions.

        Raises:
            ValueError: Invalid source identity.
            LibraryStoreError: Reading fails.
        """
        validate_sha256(source_sha256, "Expected a source SHA-256")
        with self.store.connection() as connection:
            return tuple(
                HistoryEntry(*row)
                for row in connection.execute(
                    f"SELECT {_COLUMNS} FROM export_history WHERE recording_sha256=? "
                    "ORDER BY started_at_utc DESC,id DESC",
                    (source_sha256,),
                )
            )

    def start(self, request: ExportRequest, origin: Literal["single", "batch"]) -> int | None:
        """Start one attempt only if its exact-byte source is archived.

        Args:
            request: Validated frozen requested settings.
            origin: Existing single/batch execution path.

        Returns:
            Attempt identity, or None for non-archived input.

        Raises:
            LibraryStoreError: Saving fails.
        """
        with self.store.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO export_history(recording_sha256,export_kind,origin,started_at_utc,"
                "status,application_version,request_json) SELECT source_sha256,?,?,?,'running',?,? "
                "FROM recordings WHERE source_sha256=?",
                (
                    request.kind,
                    origin,
                    _utc_now(),
                    __version__,
                    request.model_dump_json(),
                    request.source_sha256,
                ),
            )
            return cursor.lastrowid if cursor.rowcount == 1 else None

    def prepared(self, attempt_id: int, snapshot: ExportSnapshot | ExportRequest) -> None:
        """Attach effective settings without modifying the requested recipe.

        Args:
            attempt_id: Running attempt identity.
            snapshot: Shared video snapshot or admitted data-export recipe.

        Raises:
            LibraryStoreError: Attempt/source mismatch, terminal attempt or write failure.
        """
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE export_history SET export_snapshot_json=? "
                "WHERE id=? AND recording_sha256=? AND export_kind=? AND status='running'",
                (
                    snapshot.model_dump_json(),
                    attempt_id,
                    snapshot.source_sha256,
                    "video" if isinstance(snapshot, ExportSnapshot) else snapshot.kind,
                ),
            )
            if cursor.rowcount != 1:
                raise LibraryStoreError("Export attempt is not running for this source")

    def finish(
        self,
        attempt_id: int,
        status: Literal["completed", "failed", "cancelled"],
        duration: float,
        *,
        output: Path | None = None,
        file_size: int | None = None,
        gpu: bool | None = None,
        error: str | None = None,
    ) -> None:
        """Commit a terminal result only after publication or a known failure/cancellation.

        Args:
            attempt_id: Running attempt identity.
            status: Actual terminal result.
            duration: Monotonic time from attempt start through its terminal result.
            output: Published destination for completed attempts.
            file_size: Completed byte count when available.
            gpu: Observed encoder backend, otherwise unknown.
            error: Failure/cancellation explanation.

        Raises:
            ValueError: Invalid duration or completed-file information.
            LibraryStoreError: The running attempt cannot be finalized.
        """
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("Invalid terminal export status")
        if not isfinite(duration) or duration < 0 or (file_size is not None and file_size < 0):
            raise ValueError("Invalid export result measurements")
        if status == "completed" and output is None:
            raise ValueError("Completed exports require a published destination")
        if status != "completed" and (output is not None or file_size is not None):
            raise ValueError("Only completed exports have published-file information")
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE export_history SET status=?,finished_at_utc=?,duration_seconds=?,"
                "output_path=?,file_size_bytes=?,gpu_encoding=?,error=? "
                "WHERE id=? AND status='running' "
                "AND (? != 'completed' OR export_snapshot_json IS NOT NULL)",
                (
                    status,
                    _utc_now(),
                    duration,
                    str(output.resolve()) if output else None,
                    file_size,
                    gpu,
                    error,
                    attempt_id,
                    status,
                ),
            )
            if cursor.rowcount != 1:
                raise LibraryStoreError("Export attempt cannot be finalized")

    def interrupt_running(self) -> None:
        """Mark leftover attempts interrupted at application startup, preserving unknown results.

        Raises:
            LibraryStoreError: Recovery cannot be saved.
        """
        with self.store.connection() as connection:
            connection.execute(
                "UPDATE export_history SET status='interrupted',error='Application stopped before a result was saved' "
                "WHERE status='running'",
            )
