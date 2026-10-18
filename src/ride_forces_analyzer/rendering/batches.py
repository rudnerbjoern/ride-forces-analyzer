"""Reproducible sequential batch exports, independent of Qt and SQLite connections.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Sequence
from datetime import datetime, UTC
from pathlib import Path
import re
from threading import Event
from uuid import uuid4
from typing import TypedDict

from pydantic import BaseModel

from ride_forces_analyzer.explorer import ExplorerData, failure_text, load_recording
from ride_forces_analyzer.storage.export_models import BatchJob, RangeMode, SavedBatch, SavedPreset
from .encoding import ExportCancelled, export_video
from .model import prepare_export


def make_job(
    data: ExplorerData,
    preset: SavedPreset,
    *,
    range_mode: RangeMode | None = None,
    first: int | None = None,
    last: int | None = None,
) -> BatchJob:
    path = data.source.recording.source.provenance.path
    if path is None:
        raise ValueError("Only file-backed recordings can be queued")
    mode = range_mode or preset.range_mode
    indices = data.source.recording.indices
    if mode == "markers":
        first, last = indices.start, indices.end
    elif mode == "entire":
        first, last = 0, data.count - 1
    if first is None or last is None:
        raise ValueError("A selection preset needs explicit bounds for this recording")
    data.select(first, last)
    if data.reference is None:
        raise ValueError(data.reference_error or "Calibrated forces are unavailable")
    return BatchJob(
        recording_path=path.resolve(),
        source_sha256=data.source.source_sha256,
        ride=data.title,
        preset=preset,
        range_mode=mode,
        first_sample=first,
        last_sample=last,
    )


def build_jobs(
    paths: Sequence[Path],
    presets: Sequence[SavedPreset],
    range_mode: RangeMode,
) -> tuple[BatchJob, ...]:
    if not paths or not presets:
        raise ValueError("Choose at least one recording and one preset")
    jobs: list[BatchJob] = []
    for path in paths:
        data = load_recording(path)
        if not isinstance(data, ExplorerData):
            raise ValueError(f"{path.name}: {failure_text(data)}")
        jobs.extend(make_job(data, preset, range_mode=range_mode) for preset in presets)
    return tuple(jobs)


class JobResult(BaseModel, frozen=True, strict=True):
    batch: str
    job: int
    ride: str
    preset: str
    status: str
    output: Path | None = None
    error: str | None = None


class BatchReport(BaseModel, frozen=True, strict=True):
    directory: Path
    results: tuple[JobResult, ...]


class _JobInfo(TypedDict):
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
    progress: Callable[[int, int, int, int, str], None] | None = None,
    status: Callable[[str], None] | None = None,
) -> BatchReport:
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
                    if status:
                        status(f"Job {ordinal}/{total}: {label}")
                    data = load_recording(job.recording_path)
                    if not isinstance(data, ExplorerData):
                        raise ValueError(failure_text(data))
                    if data.source.source_sha256 != job.source_sha256:
                        raise ValueError("Recording bytes changed since this batch was saved")
                    data = data.with_smoothing(job.preset.smoothing_window)
                    timeline = prepare_export(
                        data,
                        job.preset.settings,
                        job.first_sample,
                        job.last_sample,
                    )
                    folder = directory / f"{batch_number:03d}-{_safe_name(batch.name)}"
                    folder.mkdir(exist_ok=True)
                    suffix = ".mov" if job.preset.settings.output == "transparent" else ".mp4"
                    target = (
                        folder
                        / f"{job_number:03d}-{_safe_name(job.ride)}--{_safe_name(job.preset.name)}{suffix}"
                    )

                    def on_progress(frame: int, frames: int) -> None:
                        if progress:
                            progress(ordinal, total, frame, frames, label)

                    export_video(
                        timeline,
                        target,
                        ffmpeg=ffmpeg,
                        cancelled=cancel,
                        progress=on_progress,
                        status=status,
                    )
                    result = JobResult(**common, status="completed", output=target)
                except ExportCancelled:
                    cancel.set()
                    result = JobResult(**common, status="cancelled", error="Export cancelled")
                except Exception as error:
                    result = JobResult(**common, status="failed", error=str(error))
            results.append(result)
            report = BatchReport(directory=directory, results=tuple(results))
            # The directory is unique to this run; persist completed work even after a later failure.
            (directory / "run-report.json").write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
            if progress and not cancel.is_set():
                progress(ordinal, total, 1, 1, label)
    return BatchReport(directory=directory, results=tuple(results))
