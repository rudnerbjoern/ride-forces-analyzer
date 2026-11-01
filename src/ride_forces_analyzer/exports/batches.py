"""Reproducible sequential batch exports, independent of Qt and SQLite connections.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.validation.checks import validate_sample_range

from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress

from collections.abc import Callable, Sequence
from datetime import datetime, UTC
from dataclasses import replace
from fractions import Fraction
from math import ceil
from pathlib import Path
import re
from threading import Event
from time import monotonic
from uuid import uuid4
from typing import TypedDict

from pydantic import BaseModel

from ride_forces_analyzer import __version__
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
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.rendering.encoding import ExportCancelled, export_video
from ride_forces_analyzer.rendering.model import ExportSnapshot, VideoOutput, prepare_export


def _load_analysis(
    path: Path,
    configuration: AnalysisConfiguration,
    *,
    expected_sha256: str | None = None,
    restore_markers: bool = False,
    additions: RecordingAdditions | None = None,
) -> RecordingAnalysis:
    """Import losslessly, verify identity before analysis, then prepare the full recipe."""
    source = import_forces(path)
    if not isinstance(source, ImportSuccess):
        details = "; ".join(f"{item.code}: {item.message}" for item in source.diagnostics[:5])
        raise ValueError(f"{path.name}: {details}")
    if expected_sha256 is not None and source.source_sha256 != expected_sha256:
        raise ValueError("Recording bytes changed since this batch was saved")
    if restore_markers:
        additions = LibraryStore().metadata(source.source_sha256)
        configuration = LibraryArchive().recording_configuration(
            source,
            configuration,
            calculation_time=datetime.now(UTC),
        )
    if additions is not None:
        source = ImportSuccess(source.recording, source.diagnostics, additions=additions)
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
    validate_sample_range(first, last, count, "Invalid export sample interval")
    if analysis.forces.smoothed.channels is None:
        reason = analysis.forces.smoothed.availability.reason
        raise ValueError(reason.message if reason else "Calibrated forces are unavailable")
    return BatchJob(
        recording_path=path.resolve(),
        source_sha256=analysis.source.source_sha256,
        ride=analysis.source.effective_metadata.name or path.stem,
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
        metadata_additions=analysis.source.additions,
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
        batch: Saved batch display name.
        job: One-based job number within the batch.
        ride: Recording title captured by the saved job.
        preset: Saved preset display name.
        job_snapshot: Requested saved job, retained even if preparation never starts.
        export_snapshot: Export-owned effective settings and analysis recipe from the
            prepared timeline, or None when preparation did not complete.
        gpu_encoding: Actual encoder GPU selection, or None before it is reported.
        file_size_bytes: Completed output length, or None without a completed file.
        duration_seconds: Elapsed job-attempt time from preparation through completion,
            failure or cancellation. Excludes queue waiting and report writes; None
            when the job was skipped.
        status: Completed, failed, cancelled or skipped outcome.
        output: Path of the successfully completed video, if available.
        error: Explanation of an unsuccessful outcome, if available.
    """

    batch: str
    job: int
    ride: str
    preset: str
    job_snapshot: BatchJob | None = None
    export_snapshot: ExportSnapshot | None = None
    gpu_encoding: bool | None = None
    file_size_bytes: int | None = None
    duration_seconds: float | None = None
    status: str
    output: Path | None = None
    error: str | None = None


class BatchReport(BaseModel, frozen=True, strict=True):
    """Batch report contract and owned data.

    Attributes:
        directory: User-selected directory containing numbered batch folders.
        report_path: Unique report file reserved for this run in the selected directory.
        application_version: Analyzer version producing the report.
        render_jobs: Effective concurrent frame-renderer setting used for this run.
        requested_ffmpeg: Supplied encoder path, or None for automatic discovery.
        results: Completed job results in processing order.
    """

    directory: Path
    report_path: Path
    application_version: str = __version__
    render_jobs: int = 1
    requested_ffmpeg: Path | None = None
    results: tuple[JobResult, ...]


class _JobInfo(TypedDict):
    """Job info contract and owned data.

    Attributes:
        batch: Saved batch display name.
        job: One-based job number within the batch.
        ride: Recording title captured by the saved job.
        preset: Saved preset display name.
        job_snapshot: Complete immutable saved job captured before execution.
        export_snapshot: Export-owned effective snapshot, or None before preparation.
        gpu_encoding: Reported encoder selection, or None while unavailable.
        file_size_bytes: Completed file length, or None without a completed file.
    """

    batch: str
    job: int
    ride: str
    preset: str
    job_snapshot: BatchJob
    export_snapshot: ExportSnapshot | None
    gpu_encoding: bool | None
    file_size_bytes: int | None


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name).strip(".-_")[:70] or "export"


def _planned_frame_counts(batches: Sequence[SavedBatch], cancelled: Event) -> tuple[int, ...]:
    """Count output frames from saved intervals, importing each source once.

    Args:
        batches: Batches in execution order.
        cancelled: Event stopping additional source reads.

    Returns:
        Frame budgets per job; unreadable sources have no known frame budget.
    """
    rates: dict[Path, float | None] = {}
    counts: list[int] = []
    for batch in batches:
        for job in batch.jobs:
            if job.recording_path not in rates and not cancelled.is_set():
                try:
                    source = import_forces(job.recording_path)
                    rates[job.recording_path] = (
                        source.recording.motion.sample_rate.value
                        if isinstance(source, ImportSuccess)
                        else None
                    )
                except OSError, ValueError:
                    rates[job.recording_path] = None
            rate = rates.get(job.recording_path)
            counts.append(
                ceil(
                    Fraction(job.last_sample - job.first_sample + 1)
                    * job.preset.settings.frame_rate
                    / Fraction(str(rate)),
                )
                if rate is not None
                else 0,
            )
    return tuple(counts)


def run_batches(
    batches: Sequence[SavedBatch],
    output_directory: Path,
    *,
    ffmpeg: Path | None = None,
    cancelled: Event | None = None,
    progress: Callable[[int, int, ExportProgress | None, str], None] | None = None,
    overall_progress: Callable[[int, int], None] | None = None,
    render_jobs: int = 1,
) -> BatchReport:
    """Run saved video jobs sequentially and retain a report and completed outputs.

    Args:
        batches: Selected saved batches in execution order.
        output_directory: Selected directory receiving batch folders directly.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
        cancelled: Cancellation event checked during the operation.
        progress: Callback receiving job index/count, export status and label. None status
            marks a settled job, including failure, without fabricating frame progress.
        overall_progress: Callback receiving settled/submitted frame budgets and total
            planned frames across all batches. Failed jobs settle their planned budget;
            unreadable sources have no known frame budget. Cancellation retains progress.
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
    frame_counts = _planned_frame_counts(batches, cancel) if overall_progress else ()
    total_frames = sum(frame_counts)
    settled_frames = 0
    if overall_progress:
        overall_progress(0, total_frames)
    directory = output_directory
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / "run-report.json"
    try:
        report_path.touch(exist_ok=False)
    except FileExistsError:
        report_path = directory / f"run-report-{uuid4().hex[:8]}.json"
        report_path.touch(exist_ok=False)
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
                "job_snapshot": job,
                "export_snapshot": None,
                "gpu_encoding": None,
                "file_size_bytes": None,
            }
            if cancel.is_set():
                result = JobResult(
                    **common,
                    status="skipped",
                    error="Cancelled before this job started",
                )
            else:
                started = monotonic()
                try:
                    if progress:
                        progress(ordinal, total, ExportProgress(ExportPhase.PREPARING), label)
                    analysis = _load_analysis(
                        job.recording_path,
                        job.preset.analysis_configuration,
                        expected_sha256=job.source_sha256,
                        additions=job.metadata_additions,
                    )
                    timeline = prepare_export(
                        analysis,
                        job.preset.settings,
                        job.first_sample,
                        job.last_sample,
                    )
                    common["export_snapshot"] = timeline.snapshot
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
                        if update.use_gpu is not None:
                            common["gpu_encoding"] = update.use_gpu
                        if progress:
                            progress(ordinal, total, update, label)
                        if overall_progress:
                            overall_progress(
                                settled_frames
                                + min(update.completed_frames, frame_counts[ordinal - 1]),
                                total_frames,
                            )

                    export_video(
                        timeline,
                        target,
                        ffmpeg=ffmpeg,
                        cancelled=cancel,
                        progress=on_progress,
                        render_jobs=render_jobs,
                    )
                    common["file_size_bytes"] = target.stat().st_size
                    result = JobResult(**common, status="completed", output=target)
                except ExportCancelled:
                    cancel.set()
                    result = JobResult(**common, status="cancelled", error="Export cancelled")
                except Exception as error:
                    record_error("Batch export job", error)
                    result = JobResult(**common, status="failed", error=str(error))
                result = result.model_copy(update={"duration_seconds": monotonic() - started})
            results.append(result)
            report = BatchReport(
                directory=directory,
                report_path=report_path,
                render_jobs=render_jobs,
                requested_ffmpeg=ffmpeg,
                results=tuple(results),
            )
            # Only this run's reserved report is updated; earlier reports stay intact.
            report_path.write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
            if progress and not cancel.is_set():
                progress(ordinal, total, None, label)
            if overall_progress and not cancel.is_set():
                settled_frames += frame_counts[ordinal - 1]
                overall_progress(settled_frames, total_frames)
    return BatchReport(
        directory=directory,
        report_path=report_path,
        render_jobs=render_jobs,
        requested_ffmpeg=ffmpeg,
        results=tuple(results),
    )
