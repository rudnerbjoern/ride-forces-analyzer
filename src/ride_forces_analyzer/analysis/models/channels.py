"""Measurement channels with explicit quantities, units, frames and time bases.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, field
from enum import StrEnum


from ride_forces_analyzer.domain import SampleRate
from ride_forces_analyzer.domain._validation import has_type

from ._validation import validate_text as _text, text_values as _texts, validate_enum as _enum
from .samples import SampleValues


class CapabilityState(StrEnum):
    """Capability state contract and owned data.

    Attributes:
        VERIFIED: Named value for verified (`verified`).
        PROVISIONAL: Named value for provisional (`provisional`).
        UNAVAILABLE: Named value for unavailable (`unavailable`).
        INVALID: Named value for invalid (`invalid`).
    """

    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class QuantityKind(StrEnum):
    """Quantity kind contract and owned data.

    Attributes:
        SOURCE_VALUES: Named value for source values (`source_values`).
        SPECIFIC_FORCE: Named value for specific force (`specific_force`).
        GRAVITY: Named value for gravity (`gravity`).
        KINEMATIC_ACCELERATION: Named value for kinematic acceleration
            (`kinematic_acceleration`).
        DEVICE_VECTOR_MAGNITUDE: Named value for device vector magnitude
            (`device_vector_magnitude`).
        LOAD_FACTOR: Named value for load factor (`load_factor`).
        DISTANCE: Named value for distance (`distance`).
        SPEED: Named value for speed (`speed`).
        ALTITUDE: Named value for altitude (`altitude`).
        ANGLE: Named value for angle (`angle`).
    """

    SOURCE_VALUES = "source_values"
    SPECIFIC_FORCE = "specific_force"
    GRAVITY = "gravity"
    KINEMATIC_ACCELERATION = "kinematic_acceleration"
    DEVICE_VECTOR_MAGNITUDE = "device_vector_magnitude"
    LOAD_FACTOR = "load_factor"
    DISTANCE = "distance"
    SPEED = "speed"
    ALTITUDE = "altitude"
    ANGLE = "angle"


class UnitLabel(StrEnum):
    """Unit label contract and owned data.

    Attributes:
        UNKNOWN: Named value for unknown (`unknown`).
        ACCELERATION_SI: Named value for acceleration si (`m/s^2`).
        DIMENSIONLESS: Named value for dimensionless (`dimensionless`).
        METERS: Named value for meters (`m`).
        METERS_PER_SECOND: Named value for meters per second (`m/s`).
        DEGREES: Named value for degrees (`deg`).
    """

    UNKNOWN = "unknown"
    ACCELERATION_SI = "m/s^2"
    DIMENSIONLESS = "dimensionless"
    METERS = "m"
    METERS_PER_SECOND = "m/s"
    DEGREES = "deg"


class EvidenceState(StrEnum):
    """Evidence state contract and owned data.

    Attributes:
        UNKNOWN: Named value for unknown (`unknown`).
        ASSUMED: Named value for assumed (`assumed`).
        VERIFIED: Named value for verified (`verified`).
    """

    UNKNOWN = "unknown"
    ASSUMED = "assumed"
    VERIFIED = "verified"


class FrameLabel(StrEnum):
    """Frame label contract and owned data.

    Attributes:
        UNKNOWN: Named value for unknown (`unknown`).
        DEVICE: Named value for device (`device`).
        WORLD_GRAVITY: Named value for world gravity (`world_gravity`).
        RIDER: Named value for rider (`rider`).
    """

    UNKNOWN = "unknown"
    DEVICE = "device"
    WORLD_GRAVITY = "world_gravity"
    RIDER = "rider"


class SourceSequence(StrEnum):
    """Source sequence contract and owned data.

    Attributes:
        ACCELERATION: Named value for acceleration (`acceleration`).
        GRAVITY: Named value for gravity (`gravity`).
        GPS: Named value for gps (`gps`).
    """

    ACCELERATION = "acceleration"
    GRAVITY = "gravity"
    GPS = "gps"


class ProcessingKind(StrEnum):
    """Processing kind contract and owned data.

    Attributes:
        RAW: Named value for raw (`raw`).
        FILTERED: Named value for filtered (`filtered`).
    """

    RAW = "raw"
    FILTERED = "filtered"


class TimeBasisKind(StrEnum):
    """Time basis kind contract and owned data.

    Attributes:
        SAMPLE_INDEX: Named value for sample index (`sample_index`).
        INFERRED_UNIFORM: Named value for inferred uniform (`inferred_uniform`).
        SOURCE_UNVERIFIED: Named value for source unverified (`source_unverified`).
        VERIFIED_SECONDS: Named value for verified seconds (`verified_seconds`).
    """

    SAMPLE_INDEX = "sample_index"
    INFERRED_UNIFORM = "inferred_uniform"
    SOURCE_UNVERIFIED = "source_unverified"
    VERIFIED_SECONDS = "verified_seconds"


@dataclass(frozen=True, slots=True)
class UnitAssignment:
    """Unit assignment contract and owned data.

    Attributes:
        label: Human-readable label.
        state: Declared capability, request or parsing state for this object.
        evidence: Evidence supporting the declared value.
    """

    label: UnitLabel = UnitLabel.UNKNOWN
    state: EvidenceState = EvidenceState.UNKNOWN
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Unknown units and unknown evidence state must agree. Assigned units
                require explicit evidence or assumption references.
        """
        _enum(self.label, UnitLabel)
        _enum(self.state, EvidenceState)
        object.__setattr__(self, "evidence", _texts(self.evidence, "Unit evidence"))
        if (self.label is UnitLabel.UNKNOWN) != (self.state is EvidenceState.UNKNOWN):
            raise ValueError("Unknown units and unknown evidence state must agree")
        if self.state is not EvidenceState.UNKNOWN and not self.evidence:
            raise ValueError("Assigned units require explicit evidence or assumption references")


@dataclass(frozen=True, slots=True)
class TimeBasis:
    """Time basis contract and owned data.

    Attributes:
        kind: Discriminator identifying the represented variant.
        sample_rate: Effective source samples per second, retaining its origin separately.
        epoch: Optional epoch associated with the time representation.
        evidence: Evidence supporting the declared value.
    """

    kind: TimeBasisKind = TimeBasisKind.SAMPLE_INDEX
    sample_rate: SampleRate | None = None
    epoch: str | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Time sample rate must retain the M2 value and origin.
            ValueError: Inferred uniform time requires the effective sample rate. Verified
                seconds require independent time evidence. An unverified or inferred time
                basis cannot assign an epoch.
        """
        _enum(self.kind, TimeBasisKind)
        object.__setattr__(self, "evidence", _texts(self.evidence, "Time evidence"))
        if self.sample_rate is not None and not has_type(self.sample_rate, SampleRate):
            raise TypeError("Time sample rate must retain the M2 value and origin")
        if self.kind is TimeBasisKind.INFERRED_UNIFORM and self.sample_rate is None:
            raise ValueError("Inferred uniform time requires the effective sample rate")
        if self.kind is TimeBasisKind.VERIFIED_SECONDS and not self.evidence:
            raise ValueError("Verified seconds require independent time evidence")
        if self.epoch is not None:
            _text(self.epoch, "Time epoch")
            if self.kind is not TimeBasisKind.VERIFIED_SECONDS:
                raise ValueError("An unverified or inferred time basis cannot assign an epoch")


@dataclass(frozen=True, slots=True)
class AnalysisChannel:
    """Analysis channel contract and owned data.

    Attributes:
        identifier: Stable identifier of this channel or subscription.
        quantity: Declared physical quantity, including an explicit unknown state.
        state: Declared capability, request or parsing state for this object.
        source_sequence: Source sequence from which the values originate.
        unit: Declared unit and its evidence; unknown source units remain unknown.
        frame: Declared coordinate frame, separate from physical mounting qualification.
        frame_evidence: Evidence supporting the declared coordinate frame.
        time_basis: Time representation and evidence associated with this data product.
        processing: Whether the channel represents retained or filtered values.
        samples: Owned sample buffer and validity information in the declared units.
        source_indices: Original indices identifying rows in the source sequence.
        columns: Names identifying the columns of the sample buffer.
        reason: Explanation for a restricted, unavailable or invalid result.
    """

    identifier: str
    quantity: QuantityKind
    state: CapabilityState
    source_sequence: SourceSequence
    unit: UnitAssignment = UnitAssignment()
    frame: FrameLabel = FrameLabel.UNKNOWN
    frame_evidence: tuple[str, ...] = ()
    time_basis: TimeBasis = TimeBasis()
    processing: ProcessingKind = ProcessingKind.RAW
    samples: SampleValues | None = field(default=None, repr=False)
    source_indices: tuple[int, ...] = ()
    columns: tuple[str, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Channels require typed unit and time assignments.
            ValueError: Source indices must be nonnegative integers. Excluded channels require
                a reason and no fabricated samples. Available channels require samples and one
                source index per row. Every sample column requires a distinct label. Raw
                source values cannot assign physical units or rider/world frames. Physical
                quantities require an explicit compatible canonical unit. Verified physical
                values require verified unit evidence. Interpreted frames require explicit
                independent evidence.
        """
        _text(self.identifier, "Channel identifier")
        for value, kind in (
            (self.quantity, QuantityKind),
            (self.state, CapabilityState),
            (self.source_sequence, SourceSequence),
            (self.frame, FrameLabel),
            (self.processing, ProcessingKind),
        ):
            _enum(value, kind)
        if not has_type(self.unit, UnitAssignment) or not has_type(self.time_basis, TimeBasis):
            raise TypeError("Channels require typed unit and time assignments")
        object.__setattr__(self, "frame_evidence", _texts(self.frame_evidence, "Frame evidence"))
        object.__setattr__(self, "columns", _texts(self.columns, "Column labels"))
        indices = tuple(self.source_indices)
        if any(type(index) is not int or index < 0 for index in indices):
            raise ValueError("Source indices must be nonnegative integers")
        object.__setattr__(self, "source_indices", indices)
        if self.reason is not None:
            _text(self.reason, "Channel reason")
        if self.state in (CapabilityState.UNAVAILABLE, CapabilityState.INVALID):
            if self.samples is not None or indices or not self.reason:
                raise ValueError("Excluded channels require a reason and no fabricated samples")
            return
        if (
            self.samples is None
            or not has_type(self.samples, SampleValues)
            or len(indices) != self.samples.shape[0]
        ):
            raise ValueError("Available channels require samples and one source index per row")
        count = self.samples.shape[1] if len(self.samples.shape) == 2 else 1
        if len(self.columns) != count or len(set(self.columns)) != count:
            raise ValueError("Every sample column requires a distinct label")
        if self.quantity is QuantityKind.SOURCE_VALUES:
            if self.unit.label is not UnitLabel.UNKNOWN or self.frame not in (
                FrameLabel.UNKNOWN,
                FrameLabel.DEVICE,
            ):
                raise ValueError(
                    "Raw source values cannot assign physical units or rider/world frames",
                )
        else:
            expected = {
                QuantityKind.SPECIFIC_FORCE: UnitLabel.ACCELERATION_SI,
                QuantityKind.GRAVITY: UnitLabel.ACCELERATION_SI,
                QuantityKind.KINEMATIC_ACCELERATION: UnitLabel.ACCELERATION_SI,
                QuantityKind.DEVICE_VECTOR_MAGNITUDE: UnitLabel.ACCELERATION_SI,
                QuantityKind.LOAD_FACTOR: UnitLabel.DIMENSIONLESS,
                QuantityKind.DISTANCE: UnitLabel.METERS,
                QuantityKind.SPEED: UnitLabel.METERS_PER_SECOND,
                QuantityKind.ALTITUDE: UnitLabel.METERS,
                QuantityKind.ANGLE: UnitLabel.DEGREES,
            }[self.quantity]
            if self.unit.label is not expected:
                raise ValueError(
                    "Physical quantities require an explicit compatible canonical unit",
                )
            if (
                self.state is CapabilityState.VERIFIED
                and self.unit.state is not EvidenceState.VERIFIED
            ):
                raise ValueError("Verified physical values require verified unit evidence")
        if self.frame in (FrameLabel.WORLD_GRAVITY, FrameLabel.RIDER) and not self.frame_evidence:
            raise ValueError("Interpreted frames require explicit independent evidence")
