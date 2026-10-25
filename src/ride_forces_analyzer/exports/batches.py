"""Reproducible sequential batch exports, independent of Qt and SQLite connections.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress

from collections.abc import Callable, Sequence
from datetime import datetime, UTC
from dataclasses import replace
from pathlib import Path
import re
from threading import Event
from uuid import uuid4
from typing import TypedDict

from pydantic import BaseModel

from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    RecordingAnalysis,
)
from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
)
from ride_forces_analyzer.analysis.service import AnalysisService
from ride_forces_analyzer.importers import ImportSuccess, import_forces
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.storage.export_models import BatchJob, RangeMode, SavedBatch, SavedPreset
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.rendering.encoding import ExportCancelled, export_video
from ride_forces_analyzer.rendering.model import VideoOutput, prepare_export


def _load_analysis(
    path: Path,
    configuration: AnalysisConfiguration,
    *,
    expected_sha256: str | None = None,
    restore_markers: bool = False,
) -> RecordingAnalysis:
    """Import losslessly, verify identity before analysis, then prepare the full recipe."""
    source = import_forces(path)
    if not isinstance(source, ImportSuccess):
        details = "; ".join(f"{item.code}: {item.message}" for item in source.diagnostics[:5])
        raise ValueError(f"{path.name}: {details}")
    if expected_sha256 is not None and source.source_sha256 != expected_sha256:
        raise ValueError("Recording bytes changed since this batch was saved")
    if restore_markers:
        configuration = Preferences().recording_configuration(
            source,
            configuration,
            calculation_time=datetime.now(UTC),
        )
    service = AnalysisService()
    try:
        service.request_analysis(source, configuration, calculation_time=datetime.now(UTC))
        state = service.get_state()
        if state.snapshot is None:
            raise ValueError(
                state.failure.message
                if state.failure
                else "Prepared recording analysis is unavailable",
            )
        return state.snapshot
    finally:
        service.close()


def make_job(
    analysis: RecordingAnalysis,
    preset: SavedPreset,
    *,
    range_mode: RangeMode | None = None,
    first: int | None = None,
    last: int | None = None,
) -> BatchJob:
    """Capture a source-bound immutable batch job from an analysis and preset.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        preset: Validated immutable export preset to store or apply.
        range_mode: Policy selecting the export sample interval.
        first: First included source sample index.
        last: Last included source sample index.

    Returns:
        Immutable export job bound to the source identity and selected preset.

    Raises:
        ValueError: Only file-backed recordings can be queued. A selection preset needs
            explicit bounds for this recording. Invalid export sample interval. If the
            supplied settings or operation state are invalid.
    """
    path = analysis.source.recording.source.provenance.path
    if path is None:
        raise ValueError("Only file-backed recordings can be queued")
    mode = range_mode or preset.range_mode
    if mode == "markers":
        first, last = analysis.ride_bounds
    elif mode == "entire":
        first, last = 0, len(analysis.time.source_indices) - 1
    if first is None or last is None:
        raise ValueError("A selection preset needs explicit bounds for this recording")
    count = len(analysis.time.source_indices)
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < count:
        raise ValueError("Invalid export sample interval")
    if analysis.forces.smoothed.channels is None:
        reason = analysis.forces.smoothed.availability.reason
        raise ValueError(reason.message if reason else "Calibrated forces are unavailable")
    return BatchJob(
        recording_path=path.resolve(),
        source_sha256=analysis.source.source_sha256,
        ride=analysis.source.recording.metadata.name or path.stem,
        preset=preset.model_copy(
            update={
                "analysis_configuration": replace(
                    preset.analysis_configuration,
                    ride_bounds=analysis.configuration.ride_bounds,
                    calibration=analysis.configuration.calibration,
                ),
            },
        ),
        range_mode=mode,
        first_sample=first,
        last_sample=last,
    )


def build_jobs(
    paths: Sequence[Path],
    presets: Sequence[SavedPreset],
    range_mode: RangeMode,
) -> tuple[BatchJob, ...]:
    """Build immutable jobs for the selected recordings and visual presets.

    Args:
        paths: Input paths to process.
        presets: Selected immutable export presets used to build jobs.
        range_mode: Policy selecting the export sample interval.

    Returns:
        Ordered export jobs for all selected recording/preset combinations.

    Raises:
        ValueError: Choose at least one recording and one preset.
    """
    if not paths or not presets:
        raise ValueError("Choose at least one recording and one preset")
    jobs: list[BatchJob] = []
    for path in paths:
        analysis = _load_analysis(path, source_app_configuration(), restore_markers=True)
        jobs.extend(make_job(analysis, preset, range_mode=range_mode) for preset in presets)
    return tuple(jobs)


class JobResult(BaseModel, frozen=True, strict=True):
    """Job result contract and owned data.

    Attributes:
        batch: Validated saved batch definition.
        job: Export job associated with this result.
        ride: Recording name or resolved recording for this export job.
        preset: Validated immutable export preset to store or apply.
        status: Optional callback receiving the current processing status.
        output: Output directory or path for generated artifacts.
        error: Failure to describe or transport.
    """

    batch: str
    job: int
    ride: str
    preset: str
    status: str
    output: Path | None = None
    error: str | None = None


class BatchReport(BaseModel, frozen=True, strict=True):
    """Batch report contract and owned data.

    Attributes:
        directory: Directory used by the operation.
        results: Completed job results in processing order.
    """

    directory: Path
    results: tuple[JobResult, ...]


class _JobInfo(TypedDict):
    """Job info contract and owned data.

    Attributes:
        batch: Validated saved batch definition.
        job: Export job associated with this result.
        ride: Recording name or resolved recording for this export job.
        preset: Validated immutable export preset to store or apply.
    """

    batch: str
    job: int
    ride: str
    preset: str


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name).strip(".-_")[:70] or "export"


def run_batches(
    batches: Sequence[SavedBatch],
    output_directory: Path,
    *,
    ffmpeg: Path | None = None,
    cancelled: Event | None = None,
    progress: Callable[[int, int, ExportProgress | None, str], None] | None = None,
    render_jobs: int = 1,
) -> BatchReport:
    """Run saved video jobs sequentially and retain a report and completed outputs.

    Args:
        batches: Selected saved batches in execution order.
        output_directory: Directory receiving completed outputs.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
        cancelled: Cancellation event checked during the operation.
        progress: Callback receiving job index/count, export status and label. None status
            marks a settled job, including failure, without fabricating frame progress.
        render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
            availability.

    Returns:
        Batch report containing per-job outcomes and completed output paths.

    Raises:
        ValueError: The selected batches contain no export jobs.
        OSError: If the required filesystem operation fails.
    """
    from ride_forces_analyzer.runtime.cpu_resources import effective_render_jobs

    render_jobs = effective_render_jobs(render_jobs)
    total = sum(len(batch.jobs) for batch in batches)
    if not total:
        raise ValueError("The selected batches contain no export jobs")
    cancel = cancelled if cancelled is not None else Event()
    directory = output_directory / (
        datetime.now(UTC).strftime("export-%Y%m%d-%H%M%S-") + uuid4().hex[:8]
    )
    directory.mkdir(parents=True)
    results: list[JobResult] = []
    ordinal = 0
    for batch_number, batch in enumerate(batches, 1):
        for job_number, job in enumerate(batch.jobs, 1):
            ordinal += 1
            label = f"{batch.name} · {job.ride} · {job.preset.name}"
            common: _JobInfo = {
                "batch": batch.name,
                "job": job_number,
                "ride": job.ride,
                "preset": job.preset.name,
            }
            if cancel.is_set():
                result = JobResult(
                    **common,
                    status="skipped",
                    error="Cancelled before this job started",
                )
            else:
                try:
                    if progress:
                        progress(ordinal, total, ExportProgress(ExportPhase.PREPARING), label)
                    analysis = _load_analysis(
                        job.recording_path,
                        job.preset.analysis_configuration,
                        expected_sha256=job.source_sha256,
                    )
                    timeline = prepare_export(
                        analysis,
                        job.preset.settings,
                        job.first_sample,
                        job.last_sample,
                    )
                    folder = directory / f"{batch_number:03d}-{_safe_name(batch.name)}"
                    folder.mkdir(exist_ok=True)
                    suffix = (
                        ".mov" if job.preset.settings.output == VideoOutput.TRANSPARENT else ".mp4"
                    )
                    target = (
                        folder
                        / f"{job_number:03d}-{_safe_name(job.ride)}--{_safe_name(job.preset.name)}{suffix}"
                    )

                    def on_progress(update: ExportProgress) -> None:
                        if progress:
                            progress(ordinal, total, update, label)

                    export_video(
                        timeline,
                        target,
                        ffmpeg=ffmpeg,
                        cancelled=cancel,
                        progress=on_progress,
                        render_jobs=render_jobs,
                    )
                    result = JobResult(**common, status="completed", output=target)
                except ExportCancelled:
                    cancel.set()
                    result = JobResult(**common, status="cancelled", error="Export cancelled")
                except Exception as error:
                    record_error("Batch export job", error)
                    result = JobResult(**common, status="failed", error=str(error))
            results.append(result)
            report = BatchReport(directory=directory, results=tuple(results))
            # The directory is unique to this run; persist completed work even after a later failure.
            (directory / "run-report.json").write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
            if progress and not cancel.is_set():
                progress(ordinal, total, None, label)
    return BatchReport(directory=directory, results=tuple(results))
