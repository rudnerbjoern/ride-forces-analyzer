"""FR-011–016: pure motion validation over an owned source tree, without decoding."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from math import isfinite
import re
from typing import Literal

from ride_forces_analyzer.domain import (
    MotionSequence,
    RecordingIndices,
    RecordingVectors,
    SampleRate,
    SourceEnvelope,
    SourceNumber,
    SourceValue,
    ValueOrigin,
    Vector3,
)
from ride_forces_analyzer.domain._validation import has_type

from ._diagnostic_budget import DiagnosticBudget, DiagnosticBudgetExceeded
from .diagnostics import ImportDiagnostic, Severity, json_pointer, ordered_diagnostics
from .limits import DEFAULT_LIMITS, ImportLimits
from .result import ImportFailure

_DECIMAL_STRING = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_VECTOR_FIELDS = (
    ("verticalDirectionVector", "vertical_direction"),
    ("lateralDirectionVector", "lateral_direction"),
    ("longitudinalDirectionVector", "longitudinal_direction"),
    ("xCalibrationVector", "x_calibration"),
    ("yCalibrationVector", "y_calibration"),
    ("zCalibrationVector", "z_calibration"),
)


@dataclass(frozen=True, slots=True)
class MotionParseSuccess:
    """Validated motion subset; never a complete recording/import success."""

    source: SourceEnvelope = field(repr=False)
    motion: MotionSequence = field(repr=False)
    indices: RecordingIndices
    vectors: RecordingVectors
    diagnostics: tuple[ImportDiagnostic, ...] = ()
    success: Literal[True] = field(default=True, init=False)

    def __post_init__(self) -> None:
        ordered = ordered_diagnostics(self.diagnostics)
        if any(item.severity is Severity.ERROR for item in ordered):
            raise ValueError("Motion success cannot contain error diagnostics")
        object.__setattr__(self, "diagnostics", ordered)


type MotionParseResult = MotionParseSuccess | ImportFailure
type _Path = tuple[str | int, ...]


def _number(value: SourceValue) -> float | None:
    numeric: Decimal | str
    if isinstance(value, SourceNumber):
        numeric = value.value
    elif isinstance(value, str) and _DECIMAL_STRING.fullmatch(value):
        numeric = value
    else:
        return None
    try:
        converted = float(numeric)
    except ValueError, OverflowError:
        return None
    return converted if isfinite(converted) else None


def _diagnose(
    diagnostics: DiagnosticBudget,
    code: str,
    path: _Path,
    message: str,
    *,
    severity: Severity = Severity.ERROR,
    sample_index: int | None = None,
) -> None:
    diagnostics.append(ImportDiagnostic(code, severity, json_pointer(*path), message, sample_index))


def _vector(
    value: SourceValue,
    path: _Path,
    diagnostics: DiagnosticBudget,
    *,
    severity: Severity = Severity.ERROR,
    sample_index: int | None = None,
) -> Vector3 | None:
    if not isinstance(value, Mapping):
        _diagnose(
            diagnostics,
            "INVALID_VECTOR",
            path,
            "Vector must be an object with x/y/z components",
            severity=severity,
            sample_index=sample_index,
        )
        return None
    components: list[float] = []
    for axis in ("x", "y", "z"):
        if axis not in value:
            _diagnose(
                diagnostics,
                "MISSING_VECTOR_COMPONENT",
                (*path, axis),
                "Required component is absent",
                severity=severity,
                sample_index=sample_index,
            )
            continue
        component = _number(value[axis])
        if component is None:
            _diagnose(
                diagnostics,
                "INVALID_NUMERIC_COMPONENT",
                (*path, axis),
                "Component must be a finite decimal string or JSON number",
                severity=severity,
                sample_index=sample_index,
            )
        else:
            components.append(component)
    return Vector3(*components) if len(components) == 3 else None


def _sequence(
    root: Mapping[str, SourceValue],
    key: str,
    diagnostics: DiagnosticBudget,
) -> tuple[Vector3, ...] | None:
    if key not in root:
        _diagnose(diagnostics, "MISSING_REQUIRED_FIELD", (key,), "Required sequence is absent")
        return None
    value = root[key]
    if not isinstance(value, tuple) or not value:
        _diagnose(
            diagnostics,
            "INVALID_MOTION_SEQUENCE",
            (key,),
            "Sequence must be a nonempty array",
        )
        return None
    samples: list[Vector3] = []
    for index, item in enumerate(value):
        vector = _vector(item, (key, index), diagnostics, sample_index=index)
        if vector is not None:
            samples.append(vector)
    # Never expose a shortened array when any original slot was invalid.
    return tuple(samples) if len(samples) == len(value) else None


def _rate(
    root: Mapping[str, SourceValue],
    diagnostics: DiagnosticBudget,
) -> SampleRate | None:
    if "sampleRate" not in root:
        return SampleRate()
    value = _number(root["sampleRate"])
    if value is None or value <= 0:
        _diagnose(
            diagnostics,
            "INVALID_SAMPLE_RATE",
            ("sampleRate",),
            "Present sample rate must be positive and finite; absence default does not apply",
        )
        return None
    return SampleRate(value, ValueOrigin.SOURCE)


def _index(
    root: Mapping[str, SourceValue],
    key: str,
    length: int | None,
    diagnostics: DiagnosticBudget,
    *,
    required: bool = False,
) -> int | None:
    if key not in root:
        if required:
            _diagnose(diagnostics, "MISSING_REQUIRED_FIELD", (key,), "Required index is absent")
        return None
    value = root[key]
    if not isinstance(value, SourceNumber) or value.value != value.value.to_integral_value():
        _diagnose(diagnostics, "INVALID_INDEX", (key,), "Index must be an integer JSON number")
        return None
    if value.value < 0 or (length is not None and value.value >= length):
        _diagnose(diagnostics, "INDEX_OUT_OF_RANGE", (key,), "Index is outside acceleration bounds")
        return None
    # No valid bounds exist for a malformed acceleration container. Avoid converting
    # potentially huge integers; that core error already prevents a successful result.
    return int(value.value) if length is not None else None


def validate_motion(source: SourceEnvelope, diagnostics: DiagnosticBudget) -> MotionParseResult:
    """Validate a caller-supplied 2.2.0 source tree; no I/O, dispatch, GPS or time math."""
    root = source.root
    if root is None:
        return ImportFailure(
            [
                ImportDiagnostic(
                    "INVALID_SOURCE_ROOT",
                    Severity.ERROR,
                    "",
                    "Source object is unavailable",
                ),
            ],
            source=source,
        )
    acceleration = _sequence(root, "accelerationSequence", diagnostics)
    original_acceleration = root.get("accelerationSequence")
    length = len(original_acceleration) if isinstance(original_acceleration, tuple) else None
    gravity = None
    device = root.get("device")
    if device not in ("iPhone", "Apple Watch"):
        _diagnose(
            diagnostics,
            "UNKNOWN_DEVICE_PROFILE",
            ("device",),
            "Device availability profile is unknown",
            severity=Severity.WARNING,
        )
    if "gravitySequence" in root:
        gravity = _sequence(root, "gravitySequence", diagnostics)
        original_gravity = root["gravitySequence"]
        if isinstance(original_gravity, tuple) and length is not None:
            if len(original_gravity) != length:
                _diagnose(
                    diagnostics,
                    "MOTION_LENGTH_MISMATCH",
                    ("gravitySequence",),
                    "Supplied gravity length must equal acceleration length",
                )
    elif device == "iPhone":
        _diagnose(
            diagnostics,
            "GRAVITY_UNAVAILABLE",
            ("gravitySequence",),
            "iPhone gravity sequence is absent",
            severity=Severity.WARNING,
        )
    sample_rate = _rate(root, diagnostics)
    start = _index(root, "startIndex", length, diagnostics)
    end = _index(root, "endIndex", length, diagnostics)
    for key in ("startIndex", "endIndex"):
        if key not in root:
            _diagnose(
                diagnostics,
                "INDEX_DEFAULTED",
                (key,),
                "Absent boundary uses the recording extent; source absence is preserved",
                severity=Severity.WARNING,
            )
    if "startIndex" not in root:
        start = 0
    if "endIndex" not in root and length:
        end = length - 1
    gravity_index = _index(root, "gravityIndex", length, diagnostics)
    incline_index = _index(root, "inclineIndex", length, diagnostics)
    if start is not None and end is not None and start > end:
        _diagnose(
            diagnostics,
            "INVALID_INDEX_ORDER",
            ("endIndex",),
            "Start index must not exceed end index",
        )
    vectors: dict[str, Vector3 | None] = {}
    for source_key, accessor in _VECTOR_FIELDS:
        vectors[accessor] = (
            _vector(root[source_key], (source_key,), diagnostics, severity=Severity.WARNING)
            if source_key in root
            else None
        )
    if any(item.severity is Severity.ERROR for item in diagnostics.records):
        version = root.get("schemaVersion")
        return ImportFailure(
            diagnostics.records,
            source=source,
            schema_version=version if isinstance(version, str) and version else None,
        )
    assert (
        acceleration is not None
        and sample_rate is not None
        and start is not None
        and end is not None
    )
    return MotionParseSuccess(
        source,
        MotionSequence(acceleration, gravity, sample_rate=sample_rate),
        RecordingIndices(start, end, gravity_index, incline_index),
        RecordingVectors(**vectors),
        ordered_diagnostics(diagnostics.records),
    )


def parse_motion(
    source: SourceEnvelope,
    *,
    limits: ImportLimits = DEFAULT_LIMITS,
) -> MotionParseResult:
    """Validate motion independently, with a bounded diagnostic list and no I/O."""
    if not has_type(limits, ImportLimits):
        raise ValueError("limits must be an ImportLimits instance")
    diagnostics = DiagnosticBudget(limits.max_diagnostics)
    try:
        return validate_motion(source, diagnostics)
    except DiagnosticBudgetExceeded:
        return diagnostics.failure(source)
