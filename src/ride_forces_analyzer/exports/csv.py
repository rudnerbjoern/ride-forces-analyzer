"""Sample-aligned CSV serialization of an existing immutable analysis snapshot.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
import csv
from pathlib import Path

from ride_forces_analyzer.analysis.recording import ForceSample, RecordingAnalysis
from ride_forces_analyzer.exports._file import export_file
from ride_forces_analyzer.formatting.time import format_sample_time

from .formats import DataExportFormat
from .validation import validate_export


CSV_COLUMNS = (
    "Timestamp",
    "Vertical Forces (g)",
    "Lateral Forces (g)",
    "Longitudinal Forces (g)",
    "Combined Forces (g)",
    "Tilt Angle Orientation (degrees)",
    "sample_index",
    "recording_seconds",
    "replay_seconds",
    "raw_x_source",
    "raw_y_source",
    "raw_z_source",
    "projected_vertical_g",
    "projected_lateral_g",
    "projected_longitudinal_g",
    "vertical_context",
    "sample_rate_hz",
    "time_basis",
    "smoothing_window_samples",
    "capabilities",
    "diagnostic_codes",
)


class CsvExportCancelled(Exception):
    """CSV writing was cancelled; the incomplete destination is removed."""


def _forces(value: ForceSample | None) -> tuple[float | None, ...]:
    return (value.vertical, value.lateral, value.longitudinal) if value else (None, None, None)


def export_csv(
    analysis: RecordingAnalysis,
    path: Path,
    first: int,
    last: int,
    *,
    overwrite: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int], None] = lambda count: None,
) -> int:
    """Write one row per original sample in an inclusive interval; return row count.

    The snapshot supplies all values without preparation or interpolation. Source
    axes have unknown units; derived g values retain the source-app policy's
    provisional status. Missing derived values are empty CSV fields. English
    headers, comma separators, decimal points and UTF-8 BOM are locale-independent.

    Raises:
        TypeError: Input is not a snapshot or interval indices are not integers.
        ValueError: Snapshot, range or destination suffix is invalid.
        FileExistsError: Destination exists and overwrite is not enabled.
        OSError: Destination cannot be written.
        CsvExportCancelled: Cancellation requested before completion.

    Overwrite requires explicit opt-in and replaces the destination only after
    successful writing. Cancellation/failure preserves existing output.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        path: Filesystem path read or written by this operation.
        first: First included source sample index.
        last: Last included source sample index.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.
        cancelled: Predicate returning True when cancellation has been requested.
        progress: Callback receiving the number of source rows written.

    Returns:
        Number of exported source sample rows.
    """
    rate = validate_export(analysis, path, first, last, DataExportFormat.CSV)
    window = dict(analysis.configuration.smoothing.parameters).get("window_samples", 11)
    count = last - first + 1
    if cancelled():
        raise CsvExportCancelled()
    with export_file(path, encoding="utf-8-sig", newline="", overwrite=overwrite) as stream:
        writer = csv.writer(stream)
        writer.writerow(CSV_COLUMNS)
        for written, index in enumerate(range(first, last + 1), 1):
            if cancelled():
                raise CsvExportCancelled()
            sample = analysis.sample(index)
            writer.writerow(
                (
                    format_sample_time(index - analysis.replay_origin, rate.value),
                    *_forces(sample.smoothed),
                    sample.combined_g,
                    sample.orientation_degrees,
                    sample.index,
                    sample.recording_seconds,
                    sample.replay_seconds,
                    sample.raw.x,
                    sample.raw.y,
                    sample.raw.z,
                    *_forces(sample.projected),
                    sample.context.value if sample.context is not None else None,
                    rate.value,
                    analysis.time.basis.kind.value,
                    window,
                    ";".join(
                        f"{name}={state.value}" for name, state in sample.quality.capabilities
                    ),
                    ";".join(item.code for item in sample.quality.diagnostics),
                ),
            )
            if written % 250 == 0 or written == count:
                progress(written)
        if cancelled():
            raise CsvExportCancelled()
    return count
