"""Sample-aligned CSV serialization of an existing immutable analysis snapshot.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
import csv
from pathlib import Path

from ride_forces_analyzer.analysis.recording import ForceSample, RecordingAnalysis
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.explorer import format_sample_time


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
        FileExistsError: Destination already exists; no file is overwritten.
        OSError: Destination cannot be written.
        CsvExportCancelled: Cancellation requested before completion.

    Writing/callback failures remove only the newly created incomplete file.
    """
    if not has_type(analysis, RecordingAnalysis):
        raise TypeError("CSV export requires RecordingAnalysis")
    if type(first) is not int or type(last) is not int:
        raise TypeError("CSV sample indices must be integers")
    if not 0 <= first <= last < len(analysis.time.source_indices):
        raise ValueError("CSV export requires a bounded inclusive sample range")
    if path.suffix.lower() != ".csv":
        raise ValueError("CSV export requires a .csv destination")
    analysis.validate()
    rate = analysis.time.basis.sample_rate
    if rate is None:
        raise ValueError("CSV sample times require a sample rate")
    window = dict(analysis.configuration.smoothing.parameters).get("window_samples", 11)
    count = last - first + 1
    created = False
    try:
        if cancelled():
            raise CsvExportCancelled()
        with path.open("x", encoding="utf-8-sig", newline="") as stream:
            created = True
            writer = csv.writer(stream)
            writer.writerow(CSV_COLUMNS)
            for written, index in enumerate(range(first, last + 1), 1):
                if cancelled():
                    raise CsvExportCancelled()
                sample = analysis.sample(index)
                writer.writerow(
                    (
                        format_sample_time(index - analysis.time.replay_origin, rate.value),
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
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
    return count
