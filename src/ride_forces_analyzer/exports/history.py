"""Best-effort history capture and repeat preparation using archived originals.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Literal

from ride_forces_analyzer.analysis.service import AnalysisService
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.explorer.loading import present_recording
from ride_forces_analyzer.explorer.model import ExplorerData
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes
from ride_forces_analyzer.rendering.model import ExportSnapshot, prepare_export
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.storage.library import LibraryStoreError
from ride_forces_analyzer.storage.library_history import ExportRequest, HistoryEntry, LibraryHistory


class ExportAttempt:
    """Capture history without turning history failures into failed or deleted exports.

    Attributes:
        history: Persistence boundary.
        id: Attempt identity, or None for non-archived input/write failure.
        warning: Explanation of a history failure, otherwise empty.
        started: Monotonic attempt start, before preparation.
    """

    def __init__(
        self,
        request: ExportRequest,
        *,
        origin: Literal["single", "batch"] = "single",
        history: LibraryHistory | None = None,
    ) -> None:
        """Start one actual attempt, leaving skipped jobs outside this lifecycle.

        Args:
            request: Frozen settings captured before preparation.
            origin: Single export or batch job.
            history: Explicit Library history, or the application default.
        """
        self.started = monotonic()
        self.history = history if history is not None else LibraryHistory()
        self.warning = ""
        self.id: int | None = None
        self._paused: float | None = None
        try:
            self.id = self.history.start(request, origin)
        except (LibraryStoreError, OSError, ValueError) as error:
            self._warn(error)

    def prepared(self, snapshot: ExportSnapshot | ExportRequest) -> None:
        """Retain the effective recipe when output preparation succeeds.

        Args:
            snapshot: Existing shared video snapshot or data recipe.
        """
        if self.id is not None:
            try:
                self.history.prepared(self.id, snapshot)
            except (LibraryStoreError, ValueError) as error:
                self._warn(error)

    def pause(self) -> None:
        """Exclude destination selection and worker queue waiting from measured duration."""
        if self._paused is None:
            self._paused = monotonic()

    def resume(self) -> None:
        """Resume measured attempt work when its worker starts executing."""
        if self._paused is not None:
            self.started += monotonic() - self._paused
            self._paused = None

    def finish(
        self,
        status: Literal["completed", "failed", "cancelled"],
        *,
        output: Path | None = None,
        gpu: bool | None = None,
        error: str | None = None,
    ) -> None:
        """Save an actual terminal result; never remove or replace an output here.

        Args:
            status: Actual exporter result.
            output: Successfully published file, absent for unsuccessful attempts.
            gpu: Observed GPU selection, or unknown.
            error: Failure/cancellation explanation.
        """
        self.resume()
        duration = monotonic() - self.started
        if self.id is None:
            return
        size: int | None = None
        if output is not None:
            try:
                size = output.stat().st_size
            except OSError as failure:
                self._warn(failure)
        try:
            self.history.finish(
                self.id,
                status,
                duration,
                output=output,
                file_size=size,
                gpu=gpu,
                error=error,
            )
        except (LibraryStoreError, OSError, ValueError) as failure:
            self._warn(failure)

    def _warn(self, error: Exception) -> None:
        record_error("Export history", error)
        self.warning = str(error)


@dataclass(frozen=True, slots=True)
class RepeatedExport:
    """Prepared saved recipe for the existing export review and destination flow.

    Attributes:
        data: Archived source with captured analysis and metadata, without current overrides.
        request: Saved format, bounds and requested values.
        video_snapshot: Shared effective video snapshot, absent for data exports.
    """

    data: ExplorerData
    request: ExportRequest
    video_snapshot: ExportSnapshot | None


def prepare_repeat(entry: HistoryEntry, history: LibraryHistory | None = None) -> RepeatedExport:
    """Reconstruct an export solely from archived bytes and its frozen recipe.

    Args:
        entry: Attempt selected for review; its old output need not exist.
        history: Owning Library, or the application-local default.

    Returns:
        Source-backed data and supported saved settings for an existing export review.

    Raises:
        ValueError: The recipe/version/algorithm is unsupported or the source changed.
        LibraryStoreError: Archived bytes cannot be read.
    """
    if entry.snapshot_json is None:
        raise ValueError("No effective export settings were saved for this attempt.")
    request = ExportRequest.model_validate_json(entry.request_json)
    video = (
        ExportSnapshot.model_validate_json(entry.snapshot_json) if entry.kind == "video" else None
    )
    effective = (
        request if video is not None else ExportRequest.model_validate_json(entry.snapshot_json)
    )
    digest = video.source_sha256 if video is not None else effective.source_sha256
    if (
        digest != entry.source_sha256
        or request.source_sha256 != digest
        or request.kind != entry.kind
    ):
        raise ValueError("Saved export source does not match the archived recording.")
    archive = (history if history is not None else LibraryHistory()).store.source(digest)
    decoded = import_forces_bytes(archive.data, compressed=archive.compressed)
    if not isinstance(decoded, ImportSuccess):
        raise ValueError("Archived recording cannot be decoded.")
    additions = effective.additions or RecordingAdditions()
    if video is not None and video.schema_version == 1:
        additions = RecordingAdditions()
    source = ImportSuccess(decoded.recording, decoded.diagnostics, additions=additions)
    configuration = (
        video.analysis_configuration if video is not None else effective.analysis_configuration
    )
    service = AnalysisService()
    try:
        service.request_analysis(source, configuration, calculation_time=datetime.now(UTC))
        state = service.get_state()
        if state.snapshot is None:
            raise ValueError(
                state.failure.message if state.failure else "Saved analysis recipe is unavailable.",
            )
        analysis = state.snapshot
    finally:
        service.close()
    if video is not None:
        timeline = prepare_export(
            analysis,
            video.settings,
            video.first_sample,
            video.last_sample_inclusive,
        )
        actual = timeline.snapshot.model_dump(
            exclude={"application_version", "schema_version", "recording_metadata"},
        )
        expected = video.model_dump(
            exclude={"application_version", "schema_version", "recording_metadata"},
        )
        if actual != expected or (
            video.schema_version == 2
            and timeline.snapshot.recording_metadata != video.recording_metadata
        ):
            raise ValueError("Saved export settings are not supported by this application version.")
        request = request.model_copy(
            update={
                "settings": video.settings,
                "analysis_configuration": configuration,
                "first_sample": video.first_sample,
                "last_sample": video.last_sample_inclusive,
                "additions": additions,
            },
        )
    else:
        request = effective
    return RepeatedExport(present_recording(source, analysis=analysis), request, video)
