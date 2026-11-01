"""App-shaped and structured JSON serialization of a bound analysis snapshot.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable, Mapping
from dataclasses import asdict
import json
from pathlib import Path
from typing import TextIO

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.exports._file import export_file
from ride_forces_analyzer.formatting.time import format_sample_time
from ride_forces_analyzer.domain.source import SourceNumber, SourceValue

from .formats import DataExportFormat
from .validation import validate_export


JSON_SAMPLE_KEYS = (
    "Vertical Forces (g)",
    "Lateral Forces (g)",
    "Longitudinal Forces (g)",
    "Combined Forces (g)",
    "Tilt Angle Orientation (degrees)",
    "Timestamp",
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
    "capabilities",
    "diagnostic_codes",
)


class JsonExportCancelled(Exception):
    """Cancellation requested; the newly created incomplete file is removed."""


def _recording_metadata(analysis: RecordingAnalysis) -> dict[str, object]:
    metadata = analysis.source.effective_metadata
    result = asdict(metadata)
    result["date"] = metadata.date.token if metadata.date is not None else None
    if analysis.source.additions.notes:
        result["notes"] = analysis.source.additions.notes
    if any(
        value is not None
        for value in (
            analysis.source.additions.row,
            analysis.source.additions.seat,
            analysis.source.additions.train,
        )
    ):
        result["attributes"] = [
            {"id": item.id, "label": item.label, "value": _attribute_value(item.value)}
            for item in analysis.source.effective_attributes
        ]
    return result


def _write_document(
    stream: TextIO,
    content: dict[str, object],
    cancelled: Callable[[], bool],
) -> None:
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    stream.write("{\n")
    for position, (key, value) in enumerate(content.items()):
        stream.write(f"\t{encoder.encode(key)}: ")
        for chunk in encoder.iterencode(value):
            if cancelled():
                raise JsonExportCancelled()
            stream.write(chunk)
        stream.write(",\n" if position < len(content) - 1 else "\n")
    stream.write("}")
    if cancelled():
        raise JsonExportCancelled()


def _calibration_metadata(analysis: RecordingAnalysis) -> dict[str, object]:
    """Retain original directions beside the bound recipe and effective basis."""
    source = analysis.source.recording.vectors
    basis = analysis.calibration
    references = basis.references if basis is not None else None
    original = (source.vertical_direction, source.lateral_direction, source.longitudinal_direction)
    effective = basis.directions if basis is not None else original
    return {
        "recipe": asdict(analysis.configuration.calibration),
        "source_directions": {
            name: asdict(vector) if vector is not None else None
            for name, vector in zip(("vertical", "lateral", "longitudinal"), original, strict=True)
        },
        "effective_directions": {
            name: asdict(vector) if vector is not None else None
            for name, vector in zip(("vertical", "lateral", "longitudinal"), effective, strict=True)
        },
        "reference_support": {
            "gravity": references.gravity_interval if references is not None else None,
            "incline": references.incline_interval if references is not None else None,
        },
        "provenance": {
            "source_sha256": references.provenance.source.sha256,
            "algorithm": references.provenance.algorithm,
            "engine_version": references.provenance.engine_version,
            "calculation_time": references.provenance.calculation_time.isoformat(),
            "capability": references.capability.value,
        }
        if references is not None
        else None,
    }


def export_json(
    analysis: RecordingAnalysis,
    path: Path,
    first: int,
    last: int,
    *,
    overwrite: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int], None] = lambda count: None,
) -> int:
    """Write parallel sample arrays and metadata; return the inclusive sample count.

    Read prepared values without recalculation or rounding. Unavailable values
    become null. Output uses UTF-8 without BOM, LF, tab-indented root keys and
    compact arrays, matching the app's layout without its two-decimal truncation.

    Raises:
        TypeError: Snapshot or index types are invalid.
        ValueError: Snapshot, interval, suffix or JSON numeric values are invalid.
        FileExistsError: Destination exists and overwrite is not enabled.
        OSError: Writing failed.
        JsonExportCancelled: Cancellation requested before completion.

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
    rate = validate_export(analysis, path, first, last, DataExportFormat.JSON)
    arrays: dict[str, list[object]] = {key: [] for key in JSON_SAMPLE_KEYS}
    count = last - first + 1
    if cancelled():
        raise JsonExportCancelled()
    with export_file(path, encoding="utf-8", newline="\n", overwrite=overwrite) as stream:
        for written, index in enumerate(range(first, last + 1), 1):
            if cancelled():
                raise JsonExportCancelled()
            sample = analysis.sample(index)
            smoothed, projected = sample.smoothed, sample.projected
            values: tuple[object, ...] = (
                smoothed.vertical if smoothed else None,
                smoothed.lateral if smoothed else None,
                smoothed.longitudinal if smoothed else None,
                sample.combined_g,
                sample.orientation_degrees,
                format_sample_time(index - analysis.replay_origin, rate.value),
                sample.index,
                sample.recording_seconds,
                sample.replay_seconds,
                sample.raw.x,
                sample.raw.y,
                sample.raw.z,
                projected.vertical if projected else None,
                projected.lateral if projected else None,
                projected.longitudinal if projected else None,
                sample.context.value if sample.context is not None else None,
                {name: state.value for name, state in sample.quality.capabilities},
                [item.code for item in sample.quality.diagnostics],
            )
            for key, value in zip(JSON_SAMPLE_KEYS, values, strict=True):
                arrays[key].append(value)
            if written % 250 == 0 or written == count:
                progress(written)
        recording = analysis.source.recording
        content: dict[str, object] = dict(arrays)
        content["metadata"] = {
            "sample_rate_hz": rate.value,
            "sample_rate_origin": rate.origin.value,
            "time_basis": analysis.time.basis.kind.value,
            "smoothing_window_samples": dict(analysis.configuration.smoothing.parameters).get(
                "window_samples",
                11,
            ),
            "first_sample": first,
            "last_sample": last,
            "source_indices": asdict(recording.indices),
            "effective_ride_bounds": analysis.ride_bounds,
            "calibration": _calibration_metadata(analysis),
            "recording": _recording_metadata(analysis),
            "stages": {
                name: asdict(getattr(analysis.configuration, name))
                for name in ("projection", "smoothing", "orientation", "context")
            },
        }
        _write_document(stream, content, cancelled)
    return count


def _attribute_value(value: SourceValue) -> object:
    """Retain exact source-number tokens and nested attribute values."""
    if isinstance(value, SourceNumber):
        return {"number_token": value.token}
    if isinstance(value, Mapping):
        return {key: _attribute_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_attribute_value(item) for item in value]
    return value


def export_analyzer_json(
    analysis: RecordingAnalysis,
    path: Path,
    first: int,
    last: int,
    *,
    overwrite: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int], None] = lambda count: None,
) -> int:
    """Export schema 1 with grouped arrays, inferred time and shared quality.

    Sample values retain full precision and null missingness. Time is represented
    by the source index range, rate and replay origin; quality capabilities and
    common diagnostics occur once, with indexed sample diagnostics separately.
    Metadata retains source markers, attributes, recipe and scientific limits.

    Returns:
        Number of exported samples, including both interval endpoints.

    Raises:
        TypeError: Snapshot or index types are invalid.
        ValueError: Snapshot, range, suffix or JSON values are invalid.
        FileExistsError: Destination exists without overwrite permission.
        OSError: Writing or replacement failed.
        JsonExportCancelled: Cancel requested; existing output remains intact.

    Uses the same progress, cancellation and atomic overwrite contract as
    export_json. No calculation, interpolation or GPS alignment is performed.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        path: Filesystem path read or written by this operation.
        first: First included source sample index.
        last: Last included source sample index.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.
        cancelled: Predicate returning True when cancellation has been requested.
        progress: Callback receiving the number of source rows written.
    """
    rate = validate_export(analysis, path, first, last, DataExportFormat.ANALYZER_JSON)
    count = last - first + 1
    axes = ("vertical", "lateral", "longitudinal")
    raw: dict[str, list[float | None]] = {axis: [] for axis in ("x", "y", "z")}
    projected: dict[str, list[float | None]] = {axis: [] for axis in axes}
    smoothed: dict[str, list[float | None]] = {axis: [] for axis in (*axes, "combined")}
    orientation: list[float | None] = []
    context: list[str | None] = []
    if cancelled():
        raise JsonExportCancelled()
    with export_file(path, encoding="utf-8", newline="\n", overwrite=overwrite) as stream:
        for written, index in enumerate(range(first, last + 1), 1):
            if cancelled():
                raise JsonExportCancelled()
            sample = analysis.sample(index)
            for axis in raw:
                raw[axis].append(getattr(sample.raw, axis))
            for axis in axes:
                projected[axis].append(
                    getattr(sample.projected, axis) if sample.projected else None,
                )
                smoothed[axis].append(getattr(sample.smoothed, axis) if sample.smoothed else None)
            smoothed["combined"].append(sample.combined_g)
            orientation.append(sample.orientation_degrees)
            context.append(sample.context.value if sample.context is not None else None)
            if written % 250 == 0 or written == count:
                progress(written)
        recording = _recording_metadata(analysis)
        recording["indices"] = asdict(analysis.source.recording.indices)
        recording["effective_ride_bounds"] = analysis.ride_bounds
        recording["attributes"] = [
            {"id": item.id, "label": item.label, "value": _attribute_value(item.value)}
            for item in analysis.source.effective_attributes
        ]
        configuration = analysis.configuration
        profile = configuration.profile
        sample_diagnostics: dict[str, list[object]] = {}
        common_diagnostics: list[object] = []
        for diagnostic in analysis.quality.diagnostics:
            if diagnostic.source_index is None:
                common_diagnostics.append(asdict(diagnostic))
            elif first <= diagnostic.source_index <= last:
                sample_diagnostics.setdefault(str(diagnostic.source_index), []).append(
                    asdict(diagnostic),
                )
        content: dict[str, object] = {
            "schema_version": 1,
            "recording": recording,
            "analysis": {
                "profile": {
                    "name": profile.name.value,
                    "schema_version": profile.schema_version,
                    "configuration": dict(profile.configuration),
                    "policy_references": profile.policy_references,
                    "assumptions": profile.assumptions,
                    "allow_provisional": profile.allow_provisional,
                },
                "stages": {
                    name: asdict(getattr(configuration, name))
                    for name in ("projection", "smoothing", "orientation", "context")
                },
                "events": asdict(configuration.events)
                if configuration.events is not None
                else None,
                "context_input": configuration.context_input.value,
                "events_input": configuration.events_input.value,
                "ride_bounds": configuration.ride_bounds,
                "calibration": _calibration_metadata(analysis),
                "units": {"raw": "unknown", "forces": "g", "orientation": "deg"},
                "force_unit_assignment": asdict(analysis.forces.projected.unit),
                "availability": {
                    "projection": asdict(analysis.forces.projected.availability),
                    "smoothing": asdict(analysis.forces.smoothed.availability),
                    "orientation": asdict(analysis.orientation.availability),
                    "context": asdict(analysis.context.availability),
                },
            },
            "time": {
                "basis": analysis.time.basis.kind.value,
                "sample_rate_hz": rate.value,
                "sample_rate_origin": rate.origin.value,
                "first_sample": first,
                "sample_count": count,
                "replay_origin": analysis.replay_origin,
                "epoch": analysis.time.basis.epoch,
                "evidence": analysis.time.basis.evidence,
            },
            "samples": {
                "raw": raw,
                "projected": projected,
                "smoothed": smoothed,
                "orientation": orientation,
                "vertical_context": context,
            },
            "quality": {
                "capabilities": {
                    name: state.value for name, state in analysis.quality.capabilities
                },
                "diagnostics": common_diagnostics,
                "sample_diagnostics": sample_diagnostics,
            },
        }
        _write_document(stream, content, cancelled)
    return count
