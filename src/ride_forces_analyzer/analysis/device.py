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

from ride_forces_analyzer.domain._validation import has_type
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
    """Supported common component units; bare 'g' is deliberately excluded."""

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
    """

    source_sha256: str
    source_sequence: SourceSequence
    unit: DeviceAccelerationUnit
    quantity: QuantityKind
    unit_evidence: tuple[str, ...]
    quantity_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not has_type(self.source_sha256, str)
            or len(self.source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.source_sha256)
        ):
            raise ValueError("Contract requires a lowercase source SHA-256")
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
    @property
    def magnitude(self) -> object: ...

    def to(self, units: str) -> "_ConvertedQuantity": ...


class _Registry(Protocol):
    def Quantity(self, magnitude: float, units: str) -> _ConvertedQuantity: ...


# Narrow the dynamically generated upstream API without exposing it to callers.
# No disk cache, custom definitions, contexts or runtime registry mutation.
_REGISTRY = cast(_Registry, pint.UnitRegistry(cache_folder=None))


def convert_device_vectors(samples: SampleValues, contract: MotionUnitContract) -> SampleValues:
    """Convert declared common x/y/z units to SI, preserving validity and ownership.

    The import service checks the contract's source binding. This primitive checks
    the typed contract; it does not certify reference strings as empirical truth.
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
    """Euclidean DEVICE magnitude, never a rider axis or inferred force relationship."""
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
