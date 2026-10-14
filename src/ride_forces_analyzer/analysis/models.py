"""Stage 1 immutable contracts; no scientific calculations or source interpretation."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
import re
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from ride_forces_analyzer.domain import SampleRate, SourceProvenance
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.importers import ImportSuccess, Severity


def _text(value: str, name: str) -> None:
    if not has_type(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def _texts(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} requires a sequence of text values")
    owned = tuple(values)
    for value in owned:
        _text(value, name)
    return owned


def _enum(value: object, kind: type[StrEnum]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


class CapabilityState(StrEnum):
    VERIFIED = "verified"
    PROVISIONAL = "provisional"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class QuantityKind(StrEnum):
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
    UNKNOWN = "unknown"
    ACCELERATION_SI = "m/s^2"
    DIMENSIONLESS = "dimensionless"
    METERS = "m"
    METERS_PER_SECOND = "m/s"
    DEGREES = "deg"


class EvidenceState(StrEnum):
    UNKNOWN = "unknown"
    ASSUMED = "assumed"
    VERIFIED = "verified"


class FrameLabel(StrEnum):
    UNKNOWN = "unknown"
    DEVICE = "device"
    WORLD_GRAVITY = "world_gravity"
    RIDER = "rider"


class SourceSequence(StrEnum):
    ACCELERATION = "acceleration"
    GRAVITY = "gravity"
    GPS = "gps"


class ProcessingKind(StrEnum):
    RAW = "raw"
    FILTERED = "filtered"


class TimeBasisKind(StrEnum):
    SAMPLE_INDEX = "sample_index"
    INFERRED_UNIFORM = "inferred_uniform"
    SOURCE_UNVERIFIED = "source_unverified"
    VERIFIED_SECONDS = "verified_seconds"


@dataclass(frozen=True, slots=True)
class UnitAssignment:
    label: UnitLabel = UnitLabel.UNKNOWN
    state: EvidenceState = EvidenceState.UNKNOWN
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _enum(self.label, UnitLabel)
        _enum(self.state, EvidenceState)
        object.__setattr__(self, "evidence", _texts(self.evidence, "Unit evidence"))
        if (self.label is UnitLabel.UNKNOWN) != (self.state is EvidenceState.UNKNOWN):
            raise ValueError("Unknown units and unknown evidence state must agree")
        if self.state is not EvidenceState.UNKNOWN and not self.evidence:
            raise ValueError("Assigned units require explicit evidence or assumption references")


@dataclass(frozen=True, slots=True)
class TimeBasis:
    kind: TimeBasisKind = TimeBasisKind.SAMPLE_INDEX
    sample_rate: SampleRate | None = None
    epoch: str | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
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


@dataclass(frozen=True, slots=True, init=False)
class SampleValues:
    """Own float64 bytes and explicit row validity; expose fresh read-only NumPy views."""

    _data: bytes = field(repr=False)
    shape: tuple[int, ...]
    valid_rows: tuple[bool, ...]

    def __init__(
        self,
        values: NDArray[np.generic],
        *,
        valid_rows: Sequence[bool] | None = None,
    ) -> None:
        if not has_type(values, np.ndarray) or values.dtype.kind not in "iuf":
            raise TypeError("Samples require a real numeric NumPy array, excluding booleans")
        if values.ndim not in (1, 2) or values.shape[0] == 0:
            raise ValueError("Samples require a nonempty scalar or column array")
        if values.ndim == 2 and values.shape[1] == 0:
            raise ValueError("Sample columns cannot be empty")
        owned = np.array(values, dtype="<f8", order="C", copy=True)
        validity = tuple(valid_rows) if valid_rows is not None else (True,) * len(owned)
        if len(validity) != len(owned) or any(type(item) is not bool for item in validity):
            raise ValueError("Validity must contain one explicit boolean per source row")
        for row, valid in zip(owned, validity, strict=True):
            if valid and not bool(np.all(np.isfinite(row))):
                raise ValueError("Valid rows must contain only finite numbers")
            if not valid and not bool(np.all(np.isnan(row))):
                raise ValueError("Missing rows require explicit NaN, never zero or hidden values")
        object.__setattr__(self, "_data", owned.tobytes(order="C"))
        object.__setattr__(self, "shape", tuple(owned.shape))
        object.__setattr__(self, "valid_rows", validity)

    @property
    def values(self) -> NDArray[np.float64]:
        """Metadata edits to this fresh view cannot change the owned model or data."""
        return np.frombuffer(self._data, dtype="<f8").reshape(self.shape)


type ParameterValue = None | bool | str | int | float


class ProfileName(StrEnum):
    RAW_DEVICE_ONLY = "raw_device_only"
    DEVICE_VECTORS = "device_vectors"
    RIDER_CALIBRATED = "rider_calibrated"
    GPS_EXPLORATORY = "gps_exploratory"
    GPS_STRICT = "gps_strict"


@dataclass(frozen=True, slots=True)
class AnalysisProfile:
    name: ProfileName = ProfileName.RAW_DEVICE_ONLY
    schema_version: str = "1"
    configuration: Mapping[str, ParameterValue] = field(default_factory=dict[str, ParameterValue])
    policy_references: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    allow_provisional: bool = False

    def __post_init__(self) -> None:
        _enum(self.name, ProfileName)
        _text(self.schema_version, "Profile schema")
        if type(self.allow_provisional) is not bool:
            raise TypeError("Provisional permission must be explicit boolean")
        if not has_type(self.configuration, Mapping):
            raise TypeError("Profile configuration must be a scalar-valued mapping")
        copied: dict[str, ParameterValue] = {}
        for key, value in self.configuration.items():
            _text(key, "Configuration key")
            if value is not None and type(value) not in (bool, str, int, float):
                raise TypeError("Configuration values must be immutable scalars")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError("Configuration numbers must be finite")
            copied[key] = value
        object.__setattr__(self, "configuration", MappingProxyType(dict(sorted(copied.items()))))
        for name in ("policy_references", "assumptions"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        if self.name is ProfileName.RAW_DEVICE_ONLY:
            if self.allow_provisional or self.assumptions or self.configuration:
                raise ValueError("The raw default cannot enable assumptions or processing settings")
        elif not self.policy_references:
            raise ValueError("Non-default profiles require explicit reviewed-policy references")
        if self.allow_provisional and not self.assumptions:
            raise ValueError("Provisional profiles require named assumptions")


@dataclass(frozen=True, slots=True)
class AnalysisDiagnostic:
    code: str
    severity: Severity
    message: str
    channel_id: str | None = None
    source_index: int | None = None

    def __post_init__(self) -> None:
        if not has_type(self.code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.code):
            raise ValueError("Diagnostic code must be a stable uppercase identifier")
        _enum(self.severity, Severity)
        _text(self.message, "Diagnostic message")
        if self.channel_id is not None:
            _text(self.channel_id, "Diagnostic channel")
        if self.source_index is not None:
            if type(self.source_index) is not int or self.source_index < 0:
                raise ValueError("Diagnostic index must be a nonnegative integer")
            if self.channel_id is None:
                raise ValueError("Indexed diagnostics require a channel/sequence reference")


@dataclass(frozen=True, slots=True)
class AnalysisChannel:
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


@dataclass(frozen=True, slots=True)
class AnalysisProvenance:
    source: SourceProvenance
    engine_version: str
    algorithm: str
    calculation_time: datetime

    def __post_init__(self) -> None:
        if not has_type(self.source, SourceProvenance):
            raise TypeError("Analysis requires retained M2 source provenance")
        _text(self.engine_version, "Engine version")
        _text(self.algorithm, "Algorithm identifier")
        if not has_type(
            self.calculation_time,
            datetime,
        ) or self.calculation_time.utcoffset() != timedelta(0):
            raise ValueError("Calculation time must be explicit timezone-aware UTC")


class ResultValidity(StrEnum):
    VALID = "valid"
    RESTRICTED = "restricted"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    source: ImportSuccess = field(repr=False)
    profile: AnalysisProfile
    provenance: AnalysisProvenance
    channels: tuple[AnalysisChannel, ...]
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not has_type(self.source, ImportSuccess):
            raise TypeError(
                "Analysis results require full M2 import success, not a subset or failure",
            )
        if not has_type(self.profile, AnalysisProfile) or not has_type(
            self.provenance,
            AnalysisProvenance,
        ):
            raise TypeError("Analysis results require typed profile and provenance")
        if self.provenance.source != self.source.recording.source.provenance:
            raise ValueError("Analysis provenance must match the complete M2 source")
        _text(self.schema_version, "Result schema")
        channels = tuple(self.channels)
        if not channels or any(not has_type(channel, AnalysisChannel) for channel in channels):
            raise ValueError("Result requires nonempty typed channels")
        by_id = {channel.identifier: channel for channel in channels}
        if len(by_id) != len(channels):
            raise ValueError("Channel identifiers must be unique")
        recording = self.source.recording
        lengths = {
            SourceSequence.ACCELERATION: len(recording.motion.acceleration),
            SourceSequence.GRAVITY: len(recording.motion.gravity)
            if recording.motion.gravity is not None
            else 0,
            SourceSequence.GPS: len(recording.gps.entries) if recording.gps is not None else 0,
        }
        for channel in channels:
            if any(index >= lengths[channel.source_sequence] for index in channel.source_indices):
                raise ValueError(
                    "Channel indices must be bounded independently by their source sequence",
                )
            if self.profile.name is ProfileName.RAW_DEVICE_ONLY and (
                channel.quantity is not QuantityKind.SOURCE_VALUES
                or channel.processing is not ProcessingKind.RAW
            ):
                raise ValueError("The raw default cannot expose physical or filtered channels")
            if channel.state is CapabilityState.PROVISIONAL and not self.profile.allow_provisional:
                raise ValueError(
                    "Provisional channels require explicit profile permission and assumptions",
                )
        diagnostics = tuple(self.diagnostics)
        if any(not has_type(item, AnalysisDiagnostic) for item in diagnostics):
            raise TypeError("Analysis diagnostics must be typed values")
        for item in diagnostics:
            if item.channel_id is not None:
                if item.channel_id not in by_id:
                    raise ValueError("Diagnostic channel must exist in the result")
                if (
                    item.source_index is not None
                    and item.source_index >= lengths[by_id[item.channel_id].source_sequence]
                ):
                    raise ValueError("Diagnostic index exceeds its independent source sequence")
        ranks = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
        ordered = tuple(
            sorted(
                diagnostics,
                key=lambda item: (
                    ranks[item.severity],
                    item.channel_id or "",
                    item.source_index if item.source_index is not None else -1,
                    item.code,
                ),
            ),
        )
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "diagnostics", ordered)

    @property
    def validity(self) -> ResultValidity:
        """Structural result status, never blanket scientific certification."""
        if any(item.severity is Severity.ERROR for item in self.diagnostics) or any(
            channel.state is CapabilityState.INVALID for channel in self.channels
        ):
            return ResultValidity.INVALID
        if any(channel.state is not CapabilityState.VERIFIED for channel in self.channels):
            return ResultValidity.RESTRICTED
        return ResultValidity.VALID
