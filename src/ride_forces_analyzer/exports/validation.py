"""Shared input validation for sample-aligned CSV and JSON exports.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.domain.models import SampleRate
from ride_forces_analyzer.validation.checks import has_type, validate_sample_range

from .formats import DataExportFormat


def validate_export(
    analysis: RecordingAnalysis,
    path: Path,
    first: int,
    last: int,
    format: DataExportFormat,
) -> SampleRate:
    """Validate a bound snapshot, inclusive interval and data-export destination.

    Args:
        analysis: Prepared snapshot to validate without recalculating its stages.
        path: Destination whose suffix must match the selected format.
        first: First included source sample index.
        last: Last included source sample index.
        format: CSV or either JSON format; both JSON formats use JSON errors
            and require a .json destination.

    Returns:
        The snapshot's existing sample rate for timestamp serialization.

    Raises:
        TypeError: The snapshot or interval indices have incompatible types.
        ValueError: The interval, destination suffix or snapshot is invalid,
            or the sample rate is unavailable.
    """
    suffix = "csv" if format is DataExportFormat.CSV else "json"
    label = suffix.upper()
    if not has_type(analysis, RecordingAnalysis):
        raise TypeError(f"{label} export requires RecordingAnalysis")
    validate_sample_range(
        first,
        last,
        len(analysis.time.source_indices),
        f"{label} export requires a bounded inclusive sample range",
        type_message=f"{label} sample indices must be integers",
    )
    if path.suffix.lower() != f".{suffix}":
        raise ValueError(f"{label} export requires a .{suffix} destination")
    analysis.validate()
    rate = analysis.time.basis.sample_rate
    if rate is None:
        raise ValueError(f"{label} sample times require a sample rate")
    return rate
