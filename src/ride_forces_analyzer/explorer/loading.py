"""Load recordings and compose explorer data through existing analysis services.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import TYPE_CHECKING
from math import isfinite
from pathlib import Path
from ride_forces_analyzer.importers import ImportFailure, ImportSuccess, import_forces

from .model import ExplorerData
from .text import import_notes

if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.recording import RecordingAnalysis


def present_recording(
    source: ImportSuccess,
    *,
    analysis: "RecordingAnalysis | None" = None,
) -> ExplorerData:
    """Build explorer presentation data from a successful lossless import.

    Args:
        source: Input recording, retained source representation or source path to read.
        analysis: Prepared recording-analysis snapshot used by this operation.

    Returns:
        Explorer data retaining the original recording and prepared analysis.

    Raises:
        ValueError: Source values exceed the chart display range. Analysis belongs to
            another import.
    """
    recording = source.recording
    motion = recording.motion
    channels = (
        tuple(vector.x for vector in motion.acceleration),
        tuple(vector.y for vector in motion.acceleration),
        tuple(vector.z for vector in motion.acceleration),
    )
    name = source.effective_metadata.name
    path = recording.source.provenance.path
    title = name or (path.stem if path is not None else tr("Recording"))
    device = recording.metadata.device or tr("Unknown device")
    gravity = tr("available") if motion.gravity is not None else tr("absent")
    gps = tr(recording.gps_status.value)
    rate = motion.sample_rate
    summary = tr(
        "{0}  |  {1:,} samples  |  Sample rate {2:g} Hz ({3})  |  Time: INFERRED_UNIFORM  |  Gravity {4}  |  GPS {5}",
        device,
        len(motion.acceleration),
        rate.value,
        rate.origin.value,
        gravity,
        gps,
    )
    low = min(0.0, min(min(axis) for axis in channels))
    high = max(0.0, max(max(axis) for axis in channels))
    # Pad each signed extremum independently; keep zero visible for one-sided data.
    value_range = (low * 1.05, high * 1.05) if low < high else (-1.0, 1.0)
    if not all(isfinite(value) for value in value_range):
        raise ValueError("Source values exceed the chart display range")
    calibration_error = None
    if analysis is not None and analysis.source is not source:
        raise ValueError("Analysis belongs to another import")
    if find_spec("numpy") is not None:
        from ride_forces_analyzer.analysis.preparation import (
            source_app_configuration,
        )
        from ride_forces_analyzer.analysis.service import AnalysisService

        if analysis is None:
            service = AnalysisService()
            service.request_analysis(
                source,
                source_app_configuration(),
                calculation_time=datetime.now(UTC),
            )
            state = service.get_state()
            analysis = state.snapshot
            calibration_error = state.failure.message if state.failure is not None else None
            service.close()
        if analysis is not None:
            reason = analysis.forces.smoothed.availability.reason
            calibration_error = reason.message if reason is not None else None
    else:
        calibration_error = tr("The optional NumPy analysis package is not installed")
    notes = import_notes(source, calibration_error)
    return ExplorerData(
        source,
        channels,
        title,
        summary,
        notes,
        value_range,
        calibration_error=calibration_error,
        analysis=analysis,
    )


def load_recording(path: Path) -> ExplorerData | ImportFailure:
    """Read an original using M2; keep source ownership and all warnings intact.

    Args:
        path: Filesystem path read or written by this operation.

    Returns:
        Prepared explorer data on success, otherwise a structured import failure.
    """
    source = import_forces(path)
    return source if isinstance(source, ImportFailure) else present_recording(source)
