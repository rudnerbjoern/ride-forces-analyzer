"""Typed inputs, admission and basis construction for provisional calibration.

Source axes remain unchanged; custom references use fixed acceleration means.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from datetime import datetime
from math import fsum, hypot, isfinite

from ride_forces_analyzer import __version__
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.importers import ImportSuccess, Severity

from .models import AnalysisDiagnostic, AnalysisProvenance, CapabilityState

# Centered acceleration means recover the five fixtures' rounded source axes.
REFERENCE_WINDOW_SAMPLES = 5
# Dimensionless numerical admission, not physical or sensor-accuracy thresholds.
MIN_REFERENCE_SINE = 1e-6
MIN_POLARITY_COSINE = 1e-6


@dataclass(frozen=True, slots=True)
class CalibrationOverrides:
    """Select original acceleration indices; None retains that source axis.

    Indices need no relationship to ride bounds or each other. Construction checks
    integer/nonnegative values; validation against a source checks upper bounds.
    Both None means no custom calibration and preserves the original basis.

    Raises:
        TypeError: An index is not an integer, including booleans.
        ValueError: An index is negative.
    """

    gravity_index: int | None = None
    incline_index: int | None = None

    def __post_init__(self) -> None:
        for index in (self.gravity_index, self.incline_index):
            if index is not None:
                if type(index) is not int:
                    raise TypeError("Calibration indices must be integers, not booleans")
                if index < 0:
                    raise ValueError("Calibration indices must be nonnegative")

    @property
    def active(self) -> bool:
        """Whether at least one reference replaces a source direction."""
        return self.gravity_index is not None or self.incline_index is not None


class CalibrationReferenceError(ValueError):
    """Reject a reference with a stable diagnostic rather than guessed axes."""

    def __init__(self, code: str, message: str) -> None:
        self.diagnostic = AnalysisDiagnostic(code, Severity.ERROR, message, "calibration")
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CalibrationReferences:
    """Immutable validated inputs for the reference-basis calculation.

    Vectors are original source axes or unnormalized reference means, all in
    device coordinates. Intervals are inclusive original indices; None identifies
    a retained source axis. Provenance retains the source hash and explicit UTC
    validation time. Factory validation establishes geometry only, not physical
    calibration, source-app equivalence or safe rider loading.
    """

    overrides: CalibrationOverrides
    vertical_reference: Vector3
    longitudinal_reference: Vector3
    polarity_reference: Vector3
    gravity_interval: tuple[int, int] | None
    incline_interval: tuple[int, int] | None
    provenance: AnalysisProvenance
    algorithm_version: str = field(default="1", init=False)
    window_samples: int = field(default=REFERENCE_WINDOW_SAMPLES, init=False)
    capability: CapabilityState = field(default=CapabilityState.PROVISIONAL, init=False)


@dataclass(frozen=True, slots=True)
class CalibrationBasis:
    """Retain effective device axes and the exact reference provenance.

    Construct through prepare_calibration_basis for validated, orthonormal axes.
    Constructors store references; no source vectors or sensor buffers are changed.

    Attributes:
        references: Source-bound means, overrides, support, version and UTC time.
        vertical_direction: Unit axis from Gravity, or normalized source vertical.
        lateral_direction: Unit longitudinal cross vertical, positive right.
        longitudinal_direction: Unit axis with original longitudinal polarity.
    """

    references: CalibrationReferences
    vertical_direction: Vector3
    lateral_direction: Vector3
    longitudinal_direction: Vector3

    @property
    def directions(self) -> tuple[Vector3, Vector3, Vector3]:
        """Return vertical/lateral/longitudinal rows for direct projection."""
        return self.vertical_direction, self.lateral_direction, self.longitudinal_direction


def prepare_calibration_basis(
    source: ImportSuccess,
    overrides: CalibrationOverrides,
    *,
    calculation_time: datetime,
) -> CalibrationBasis | None:
    """Prepare an orthonormal, right-handed basis from admitted references.

    Args:
        source: Complete original import with source axes and acceleration.
        overrides: Custom reference indices; inactive choices retain source policy.
        calculation_time: Explicit aware UTC calculation time for provenance.

    Returns:
        Immutable full-precision axes and references, or None when inactive.
        No force projection, orientation or source mutation occurs here.

    Raises:
        TypeError: Input types are incompatible.
        ValueError: Calculation time is not explicit UTC.
        CalibrationReferenceError: Reference admission fails.
    """
    references = validate_calibration_references(
        source,
        overrides,
        calculation_time=calculation_time,
    )
    if references is None:
        return None
    return CalibrationBasis(
        references,
        *_reference_directions(
            references.vertical_reference,
            references.longitudinal_reference,
            references.polarity_reference,
        ),
    )


def _unit(vector: Vector3, name: str) -> Vector3:
    """Check finite, nonzero geometry without inventing a physical unit scale."""
    length = hypot(vector.x, vector.y, vector.z)
    if not all(isfinite(value) for value in (vector.x, vector.y, vector.z, length)):
        raise CalibrationReferenceError(
            "CALIBRATION_NON_FINITE_REFERENCE",
            f"{name} requires a finite vector and norm",
        )
    if length == 0:
        raise CalibrationReferenceError(
            "CALIBRATION_ZERO_REFERENCE",
            f"{name} has no direction",
        )
    return Vector3(vector.x / length, vector.y / length, vector.z / length)


def _mean(
    samples: tuple[Vector3, ...],
    index: int,
) -> tuple[Vector3, tuple[int, int]]:
    """Use fixed centered support, shortened/renormalized at recording edges."""
    radius = REFERENCE_WINDOW_SAMPLES // 2
    first, last = max(0, index - radius), min(len(samples) - 1, index + radius)
    window = samples[first : last + 1]
    try:
        # Divide before summation to avoid artificial overflow of a finite mean.
        mean = Vector3(
            *(
                fsum(getattr(value, axis) / len(window) for value in window)
                for axis in ("x", "y", "z")
            ),
        )
    except (OverflowError, ValueError) as error:
        raise CalibrationReferenceError(
            "CALIBRATION_NON_FINITE_REFERENCE",
            "Reference mean is not finite",
        ) from error
    return mean, (first, last)


def validate_calibration_references(
    source: ImportSuccess,
    overrides: CalibrationOverrides,
    *,
    calculation_time: datetime,
) -> CalibrationReferences | None:
    """Admit reference inputs without changing forces or original source axes.

    Args:
        source: Complete immutable import, retaining original bytes and axes.
        overrides: Typed Gravity/Incline choices on the full acceleration axis.
        calculation_time: Explicit timezone-aware UTC time for provenance.

    Returns:
        Validated means/source references and provenance, or None when inactive.
        Gravity sensor data is not required for these acceleration-based references.

    Raises:
        TypeError: Source or overrides have incompatible types.
        ValueError: Provenance time is not explicit UTC.
        CalibrationReferenceError: Out-of-range indices, missing source axes,
            non-finite/zero vectors, parallel references or ambiguous polarity.
    """
    if not has_type(source, ImportSuccess) or not has_type(overrides, CalibrationOverrides):
        raise TypeError("Calibration validation requires an import and typed overrides")
    provenance = AnalysisProvenance(
        source.recording.source.provenance,
        __version__,
        "user-reference-calibration",
        calculation_time,
    )
    samples = source.recording.motion.acceleration
    for index in (overrides.gravity_index, overrides.incline_index):
        if index is not None and index >= len(samples):
            raise CalibrationReferenceError(
                "CALIBRATION_INDEX_OUT_OF_RANGE",
                "Calibration index is outside the recording",
            )
    if not overrides.active:
        return None
    axes = source.recording.vectors
    vertical, lateral, longitudinal = (
        axes.vertical_direction,
        axes.lateral_direction,
        axes.longitudinal_direction,
    )
    if vertical is None or lateral is None or longitudinal is None:
        raise CalibrationReferenceError(
            "CALIBRATION_SOURCE_AXES_UNAVAILABLE",
            "Calibration requires the original source directions",
        )
    polarity_reference = longitudinal
    for axis in (vertical, lateral, longitudinal):
        _unit(axis, "Source axis")
    gravity_interval = incline_interval = None
    if overrides.gravity_index is not None:
        vertical, gravity_interval = _mean(samples, overrides.gravity_index)
    if overrides.incline_index is not None:
        longitudinal, incline_interval = _mean(samples, overrides.incline_index)
    _reference_directions(vertical, longitudinal, polarity_reference)
    return CalibrationReferences(
        overrides,
        vertical,
        longitudinal,
        polarity_reference,
        gravity_interval,
        incline_interval,
        provenance,
    )


def _reference_directions(
    vertical: Vector3,
    longitudinal: Vector3,
    polarity_reference: Vector3,
) -> tuple[Vector3, Vector3, Vector3]:
    """Admit geometry and derive one consistently signed right-handed basis."""
    unit_vertical = _unit(vertical, "Gravity reference")
    unit_longitudinal = _unit(longitudinal, "Incline reference")
    cosine = fsum(
        a * b
        for a, b in zip(
            (unit_vertical.x, unit_vertical.y, unit_vertical.z),
            (unit_longitudinal.x, unit_longitudinal.y, unit_longitudinal.z),
            strict=True,
        )
    )
    candidate = Vector3(
        unit_longitudinal.x - cosine * unit_vertical.x,
        unit_longitudinal.y - cosine * unit_vertical.y,
        unit_longitudinal.z - cosine * unit_vertical.z,
    )
    if hypot(candidate.x, candidate.y, candidate.z) <= MIN_REFERENCE_SINE:
        raise CalibrationReferenceError(
            "CALIBRATION_PARALLEL_REFERENCES",
            "Gravity and Incline do not define distinct directions",
        )
    unit_candidate = _unit(candidate, "Longitudinal candidate")
    polarity = _unit(polarity_reference, "Source longitudinal axis")
    agreement = fsum(
        a * b
        for a, b in zip(
            (unit_candidate.x, unit_candidate.y, unit_candidate.z),
            (polarity.x, polarity.y, polarity.z),
            strict=True,
        )
    )
    if abs(agreement) <= MIN_POLARITY_COSINE:
        raise CalibrationReferenceError(
            "CALIBRATION_POLARITY_AMBIGUOUS",
            "Incline does not resolve the original longitudinal polarity",
        )
    if agreement < 0:
        unit_candidate = Vector3(-unit_candidate.x, -unit_candidate.y, -unit_candidate.z)
    lateral = _unit(
        Vector3(
            unit_candidate.y * unit_vertical.z - unit_candidate.z * unit_vertical.y,
            unit_candidate.z * unit_vertical.x - unit_candidate.x * unit_vertical.z,
            unit_candidate.x * unit_vertical.y - unit_candidate.y * unit_vertical.x,
        ),
        "Lateral axis",
    )
    return unit_vertical, lateral, unit_candidate
