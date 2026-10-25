"""Device-only mathematics with explicit source-specific unit/quantity contracts.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Protocol, cast

import numpy as np
import pint

from ride_forces_analyzer.validation.checks import has_type, validate_sha256
from ride_forces_analyzer.importers import ImportSuccess, Severity

from .models import (
    AnalysisChannel,
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    EvidenceState,
    FrameLabel,
    ProcessingKind,
    ProfileName,
    QuantityKind,
    SampleValues,
    SourceSequence,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)


class DeviceAccelerationUnit(StrEnum):
    """Supported common component units; bare 'g' is deliberately excluded.

    Attributes:
        SI: Named value for si (`meter / second ** 2`).
        CENTIMETERS: Named value for centimeters (`centimeter / second ** 2`).
        FEET: Named value for feet (`foot / second ** 2`).
        STANDARD_GRAVITY: Named value for standard gravity (`standard_gravity`).
    """

    SI = "meter / second ** 2"
    CENTIMETERS = "centimeter / second ** 2"
    FEET = "foot / second ** 2"
    STANDARD_GRAVITY = "standard_gravity"


_VECTOR_QUANTITIES = (
    QuantityKind.SPECIFIC_FORCE,
    QuantityKind.GRAVITY,
    QuantityKind.KINEMATIC_ACCELERATION,
)


@dataclass(frozen=True, slots=True)
class MotionUnitContract:
    """Caller-validated evidence, never inferred from a source field name.

    References attest the common component unit and quantity independently.
    Synthetic references qualify only their synthetic source, not real recordings.

    Attributes:
        source_sha256: SHA-256 identity of the original recording bytes.
        source_sequence: Source sequence from which the values originate.
        unit: Declared unit and its evidence; unknown source units remain unknown.
        quantity: Declared physical quantity, including an explicit unknown state.
        unit_evidence: Evidence supporting the unit assignment.
        quantity_evidence: Evidence supporting the quantity assignment.
    """

    source_sha256: str
    source_sequence: SourceSequence
    unit: DeviceAccelerationUnit
    quantity: QuantityKind
    unit_evidence: tuple[str, ...]
    quantity_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Contract requires a lowercase source SHA-256. Contract must identify a
                motion sequence. Contract must distinguish the vector's physical quantity.
                Validated units and quantities require independent references.
            TypeError: A supported explicit acceleration unit is required. Evidence must be a
                collection of reference strings.
        """
        validate_sha256(self.source_sha256, "Contract requires a lowercase source SHA-256")
        if not has_type(self.source_sequence, SourceSequence) or self.source_sequence not in (
            SourceSequence.ACCELERATION,
            SourceSequence.GRAVITY,
        ):
            raise ValueError("Contract must identify a motion sequence")
        if not has_type(self.unit, DeviceAccelerationUnit):
            raise TypeError("A supported explicit acceleration unit is required")
        if not has_type(self.quantity, QuantityKind) or self.quantity not in _VECTOR_QUANTITIES:
            raise ValueError("Contract must distinguish the vector's physical quantity")
        for name in ("unit_evidence", "quantity_evidence"):
            values: object = getattr(self, name)
            if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
                raise TypeError("Evidence must be a collection of reference strings")
            refs = tuple(cast(tuple[object, ...], values))
            if not refs or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                raise ValueError("Validated units and quantities require independent references")
            object.__setattr__(self, name, refs)


class _ConvertedQuantity(Protocol):
    """Typed subset of a converted unit quantity."""

    @property
    def magnitude(self) -> object:
        """Return the numeric magnitude of the represented quantity.

        Returns:
            Numeric magnitude in the quantity's current units.
        """
        ...

    def to(self, units: str) -> "_ConvertedQuantity":
        """Convert this quantity to the requested units.

        Args:
            units: Declared units associated with the values.

        Returns:
            A quantity expressed in the requested units.
        """
        ...


class _Registry(Protocol):
    """Typed subset of the unit registry used for explicit conversions."""

    def Quantity(self, magnitude: float, units: str) -> _ConvertedQuantity:
        """Construct a quantity with an explicit magnitude and units.

        Args:
            magnitude: Vector magnitude in the declared units.
            units: Declared units associated with the values.

        Returns:
            The quantity constructed from the supplied magnitude and units.
        """
        ...


# Narrow the dynamically generated upstream API without exposing it to callers.
# No disk cache, custom definitions, contexts or runtime registry mutation.
_REGISTRY = cast(_Registry, pint.UnitRegistry(cache_folder=None))


def convert_device_vectors(samples: SampleValues, contract: MotionUnitContract) -> SampleValues:
    """Convert declared common x/y/z units to SI, preserving validity and ownership.

    The import service checks the contract's source binding. This primitive checks
    the typed contract; it does not certify reference strings as empirical truth.

    Args:
        samples: Sample values in the declared source or analysis representation.
        contract: Declared source-unit contract.

    Returns:
        Owned SI acceleration vectors with source-row validity preserved.

    Raises:
        TypeError: Conversion requires owned samples and a validated unit contract.
        ValueError: Device conversion requires x/y/z rows. Pint returned an invalid
            conversion factor. Unit conversion exceeded finite float64 range.
    """
    if not has_type(samples, SampleValues) or not has_type(contract, MotionUnitContract):
        raise TypeError("Conversion requires owned samples and a validated unit contract")
    if len(samples.shape) != 2 or samples.shape[1] != 3:
        raise ValueError("Device conversion requires x/y/z rows")
    factor = (
        _REGISTRY.Quantity(1.0, contract.unit.value).to(DeviceAccelerationUnit.SI.value).magnitude
    )
    if not isinstance(factor, (int, float)) or not isfinite(factor) or factor <= 0:
        raise ValueError("Pint returned an invalid conversion factor")
    # One Pint conversion per channel, then vectorized arithmetic, no per-row quantities.
    with np.errstate(over="ignore", invalid="ignore"):
        values = samples.values * factor
    if not np.isfinite(values[np.asarray(samples.valid_rows)]).all():
        raise ValueError("Unit conversion exceeded finite float64 range")
    return SampleValues(values, valid_rows=samples.valid_rows)


def device_vector_norm(channel: AnalysisChannel) -> AnalysisChannel:
    """Euclidean DEVICE magnitude, never a rider axis or inferred force relationship.

    Args:
        channel: Prepared channel whose units, bounds and availability govern the result.

    Returns:
        Device-vector magnitude channel with its unit and evidence metadata.

    Raises:
        TypeError: Norm requires a typed channel.
        ValueError: Norm requires verified SI raw DEVICE x/y/z vectors. Device magnitude
            exceeded finite float64 range.
    """
    if not has_type(channel, AnalysisChannel):
        raise TypeError("Norm requires a typed channel")
    if (
        channel.state is not CapabilityState.VERIFIED
        or channel.quantity not in _VECTOR_QUANTITIES
        or channel.unit.state is not EvidenceState.VERIFIED
        or channel.unit.label is not UnitLabel.ACCELERATION_SI
        or channel.frame is not FrameLabel.DEVICE
        or channel.processing is not ProcessingKind.RAW
        or channel.columns != ("x", "y", "z")
        or channel.samples is None
        or len(channel.samples.shape) != 2
        or channel.samples.shape[1] != 3
    ):
        raise ValueError("Norm requires verified SI raw DEVICE x/y/z vectors")
    # hypot avoids intermediate squared-component overflow/underflow.
    with np.errstate(over="ignore", invalid="ignore"):
        norm = np.hypot.reduce(channel.samples.values, axis=1)
    if not np.isfinite(norm[np.asarray(channel.samples.valid_rows)]).all():
        raise ValueError("Device magnitude exceeded finite float64 range")
    return replace(
        channel,
        identifier=f"{channel.identifier}-norm",
        quantity=QuantityKind.DEVICE_VECTOR_MAGNITUDE,
        samples=SampleValues(norm, valid_rows=channel.samples.valid_rows),
        columns=("magnitude",),
    )


def analyze_device_vectors(
    source: ImportSuccess,
    *,
    calculation_time: datetime,
    acceleration_contract: MotionUnitContract | None = None,
    gravity_contract: MotionUnitContract | None = None,
) -> AnalysisResult:
    """Return independent SI vectors/norms or structured capability exclusions.

    No source contracts are assigned automatically. No source timeline, calibration,
    GPS, load factor, sequence relationship or rider/world mapping is calculated.

    Args:
        source: Input recording, retained source representation or source path to read.
        calculation_time: Aware timestamp recorded in calculation provenance.
        acceleration_contract: Unit and quantity evidence for source acceleration.
        gravity_contract: Unit and quantity evidence for source gravity.

    Returns:
        Independent si vectors/norms or structured capability exclusions.

    Raises:
        TypeError: Device analysis requires full M2 ImportSuccess. Motion contracts must
            be typed or absent.
        ValueError: Motion contract does not match this source and sequence.
        AssertionError: If a required internal invariant does not hold.
    """
    if not has_type(source, ImportSuccess):
        raise TypeError("Device analysis requires full M2 ImportSuccess")
    provenance = AnalysisProvenance(
        source.recording.source.provenance,
        "0.1.0",
        "device-si-hypot-v1",
        calculation_time,
    )
    channels: list[AnalysisChannel] = []
    diagnostics: list[AnalysisDiagnostic] = []
    configuration: dict[str, str] = {
        "numpy_version": np.__version__,
        "pint_version": pint.__version__,
    }
    motion = source.recording.motion
    for sequence, vectors, contract in (
        (SourceSequence.ACCELERATION, motion.acceleration, acceleration_contract),
        (SourceSequence.GRAVITY, motion.gravity, gravity_contract),
    ):
        identifier = f"{sequence.value}-device"
        if contract is not None:
            if not has_type(contract, MotionUnitContract):
                raise TypeError("Motion contracts must be typed or absent")
            if (
                contract.source_sha256 != source.source_sha256
                or contract.source_sequence != sequence
            ):
                raise ValueError("Motion contract does not match this source and sequence")
            configuration[f"{sequence.value}.source_unit"] = contract.unit.value
            configuration[f"{sequence.value}.quantity"] = contract.quantity.value
        reason = None
        code = "SOURCE_UNIT_UNKNOWN"
        if vectors is None:
            reason, code = "Source motion sequence is absent", "SOURCE_SEQUENCE_ABSENT"
        elif contract is None:
            reason = "No validated source unit and quantity contract"
        if reason is not None:
            for name, quantity in (
                (identifier, contract.quantity if contract else QuantityKind.SOURCE_VALUES),
                (f"{identifier}-norm", QuantityKind.DEVICE_VECTOR_MAGNITUDE),
            ):
                channels.append(
                    AnalysisChannel(
                        name,
                        quantity,
                        CapabilityState.UNAVAILABLE,
                        sequence,
                        reason=reason,
                    ),
                )
                diagnostics.append(AnalysisDiagnostic(code, Severity.WARNING, reason, name))
            continue
        # The absent paths above cannot establish either data or units.
        assert contract is not None and vectors is not None
        unit = UnitAssignment(
            UnitLabel.ACCELERATION_SI,
            EvidenceState.VERIFIED,
            contract.unit_evidence + contract.quantity_evidence,
        )
        source_samples = SampleValues(
            np.array([(v.x, v.y, v.z) for v in vectors], dtype=np.float64),
        )
        channel = AnalysisChannel(
            identifier,
            contract.quantity,
            CapabilityState.VERIFIED,
            sequence,
            unit=unit,
            frame=FrameLabel.DEVICE,
            time_basis=TimeBasis(TimeBasisKind.SAMPLE_INDEX, sample_rate=motion.sample_rate),
            samples=source_samples,
            source_indices=tuple(range(len(vectors))),
            columns=("x", "y", "z"),
        )
        try:
            channel = replace(channel, samples=convert_device_vectors(source_samples, contract))
        except ValueError as error:
            for name, quantity in (
                (identifier, contract.quantity),
                (f"{identifier}-norm", QuantityKind.DEVICE_VECTOR_MAGNITUDE),
            ):
                channels.append(
                    AnalysisChannel(
                        name,
                        quantity,
                        CapabilityState.INVALID,
                        sequence,
                        reason=str(error),
                    ),
                )
                diagnostics.append(
                    AnalysisDiagnostic("UNIT_CONVERSION_RANGE", Severity.ERROR, str(error), name),
                )
            continue
        channels.append(channel)
        try:
            channels.append(device_vector_norm(channel))
        except ValueError as error:
            name = f"{identifier}-norm"
            channels.append(
                AnalysisChannel(
                    name,
                    QuantityKind.DEVICE_VECTOR_MAGNITUDE,
                    CapabilityState.INVALID,
                    sequence,
                    reason=str(error),
                ),
            )
            diagnostics.append(
                AnalysisDiagnostic("DEVICE_NORM_RANGE", Severity.ERROR, str(error), name),
            )
    profile = AnalysisProfile(
        ProfileName.DEVICE_VECTORS,
        configuration=configuration,
        policy_references=("ADR-0003: device-only qualification", "ADR-0004: immutable quantities"),
    )
    return AnalysisResult(source, profile, provenance, tuple(channels), tuple(diagnostics))
