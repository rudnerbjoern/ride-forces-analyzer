"""Canonical immutable representations, without decoding or scientific inference.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite

from ride_forces_analyzer.validation.checks import has_type
from .source import SourceEnvelope, SourceNumber, SourceValue, freeze_source_value


def _finite(value: float, name: str) -> float:
    if has_type(value, bool) or not has_type(value, (int, float)):
        raise TypeError(f"{name} requires a numeric value, excluding booleans")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} requires a finite value") from error
    if not isfinite(number):
        raise ValueError(f"{name} requires a finite value")
    return number


def _index(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} requires a nonnegative integer index")


class ValueOrigin(StrEnum):
    """Value origin contract and owned data.

    Attributes:
        SOURCE: Named value for source (`source`).
        DEFAULT: Named value for default (`default`).
    """

    SOURCE = "source"
    DEFAULT = "default"


class RecordingFormat(StrEnum):
    """Recording format contract and owned data.

    Attributes:
        RIDE_FORCES: Named value for ride forces (`ride-forces`).
        RFDB: Named value for rfdb (`rfdb`).
    """

    RIDE_FORCES = "ride-forces"
    RFDB = "rfdb"


@dataclass(frozen=True, slots=True)
class SampleRate:
    """Sample rate contract and owned data.

    Attributes:
        value: Candidate value to validate, format or store.
        origin: Origin marker distinguishing retained source data from an admitted
            default.
    """

    value: float = 50.0
    origin: ValueOrigin = ValueOrigin.DEFAULT

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Sample rate must be positive. The owner-default sample rate is 50 Hz.
            TypeError: Sample rate origin must be a ValueOrigin.
        """
        value = _finite(self.value, "Sample rate")
        if value <= 0:
            raise ValueError("Sample rate must be positive")
        if not has_type(self.origin, ValueOrigin):
            raise TypeError("Sample rate origin must be a ValueOrigin")
        if self.origin is ValueOrigin.DEFAULT and value != 50.0:
            raise ValueError("The owner-default sample rate is 50 Hz")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class RidingPosition:
    """Riding position contract and owned data.

    Attributes:
        value: Candidate value to validate, format or store.
        origin: Origin marker distinguishing retained source data from an admitted
            default.
    """

    value: str = "Seated"
    origin: ValueOrigin = ValueOrigin.DEFAULT

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Riding position must be a nonempty string. The owner-default riding
                position is Seated.
            TypeError: Riding position origin must be a ValueOrigin.
        """
        if not has_type(self.value, str) or not self.value.strip():
            raise ValueError("Riding position must be a nonempty string")
        if not has_type(self.origin, ValueOrigin):
            raise TypeError("Riding position origin must be a ValueOrigin")
        if self.origin is ValueOrigin.DEFAULT and self.value != "Seated":
            raise ValueError("The owner-default riding position is Seated")


@dataclass(frozen=True, slots=True)
class Vector3:
    """Vector3 contract and owned data.

    Attributes:
        x: Horizontal coordinate or vector component in the declared coordinate system.
        y: Vertical coordinate or vector component in the declared coordinate system.
        z: Third vector component in the declared frame and units.
    """

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.
        """
        for name, value in (("x", self.x), ("y", self.y), ("z", self.z)):
            object.__setattr__(self, name, _finite(value, name))


@dataclass(frozen=True, slots=True, init=False)
class MotionSequence:
    """Motion sequence contract and owned data.

    Attributes:
        acceleration: Retained source acceleration sequence; source semantics are not
            inferred.
        gravity: Retained optional gravity data or source marker, as declared by the field
            type.
        sample_rate: Effective source samples per second, retaining its origin separately.
    """

    acceleration: tuple[Vector3, ...] = field(repr=False)
    gravity: tuple[Vector3, ...] | None = field(repr=False)
    sample_rate: SampleRate

    def __init__(
        self,
        acceleration: Sequence[Vector3],
        gravity: Sequence[Vector3] | None = None,
        *,
        sample_rate: SampleRate = SampleRate(),
    ) -> None:
        """Initialize motion sequence and its owned state.

        Args:
            acceleration: Retained source acceleration values.
            gravity: Optional retained source gravity values.
            sample_rate: Effective source samples per second.

        Returns:
            None.

        Raises:
            ValueError: Acceleration requires nonempty Vector3 samples. Supplied gravity must
                contain paired Vector3 samples.
            TypeError: Motion sample rate must be a SampleRate.
        """
        owned = tuple(acceleration)
        paired = tuple(gravity) if gravity is not None else None
        if not owned or any(not has_type(item, Vector3) for item in owned):
            raise ValueError("Acceleration requires nonempty Vector3 samples")
        if paired is not None and (
            len(paired) != len(owned) or any(not has_type(item, Vector3) for item in paired)
        ):
            raise ValueError("Supplied gravity must contain paired Vector3 samples")
        if not has_type(sample_rate, SampleRate):
            raise TypeError("Motion sample rate must be a SampleRate")
        object.__setattr__(self, "acceleration", owned)
        object.__setattr__(self, "gravity", paired)
        object.__setattr__(self, "sample_rate", sample_rate)

    @property
    def paired_motion_available(self) -> bool:
        """Report whether acceleration and gravity have structurally paired samples.

        Returns:
            True when the requested check succeeds or the event is handled; otherwise False.
        """
        return self.gravity is not None


@dataclass(frozen=True, slots=True)
class RecordingIndices:
    """Recording indices contract and owned data.

    Attributes:
        start: Start marker or start-action control, as declared by this class.
        end: Inclusive source end marker retained by the model.
        gravity: Retained optional gravity data or source marker, as declared by the field
            type.
        incline: Optional source incline-reference sample index.
    """

    start: int
    end: int
    gravity: int | None = None
    incline: int | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Start index must not exceed end index.
        """
        for name, value in (
            ("start", self.start),
            ("end", self.end),
            ("gravity", self.gravity),
            ("incline", self.incline),
        ):
            if value is not None:
                _index(value, name)
        if self.start > self.end:
            raise ValueError("Start index must not exceed end index")


@dataclass(frozen=True, slots=True)
class RecordingVectors:
    """Recording vectors contract and owned data.

    Attributes:
        vertical_direction: Source or effective vertical projection direction.
        lateral_direction: Source or effective lateral projection direction.
        longitudinal_direction: Source or effective longitudinal projection direction.
        x_calibration: Retained source calibration vector for the x axis.
        y_calibration: Retained source calibration vector for the y axis.
        z_calibration: Retained source calibration vector for the z axis.
    """

    vertical_direction: Vector3 | None = None
    lateral_direction: Vector3 | None = None
    longitudinal_direction: Vector3 | None = None
    x_calibration: Vector3 | None = None
    y_calibration: Vector3 | None = None
    z_calibration: Vector3 | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Recording vectors must be Vector3 values or None.
        """
        values = (
            self.vertical_direction,
            self.lateral_direction,
            self.longitudinal_direction,
            self.x_calibration,
            self.y_calibration,
            self.z_calibration,
        )
        if any(value is not None and not has_type(value, Vector3) for value in values):
            raise TypeError("Recording vectors must be Vector3 values or None")


@dataclass(frozen=True, slots=True, init=False)
class Attribute:
    """Attribute contract and owned data.

    Attributes:
        id: Source identifier retained without interpretation.
        label: Human-readable label.
        value: Candidate value to validate, format or store.
    """

    id: str
    label: str
    value: SourceValue = field(repr=False)

    def __init__(self, id: str, label: str, value: object) -> None:
        """Initialize attribute and its owned state.

        Args:
            id: Source identifier retained without interpretation.
            label: Human-readable label.
            value: Candidate value to validate, format or store.

        Returns:
            None.

        Raises:
            TypeError: Attribute id and label must be strings.
        """
        if not has_type(id, str) or not has_type(label, str):
            raise TypeError("Attribute id and label must be strings")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "value", freeze_source_value(value))


@dataclass(frozen=True, slots=True)
class GpsFix:
    """Finite source numbers; units, epoch and negative sentinels are unverified.

    Attributes:
        latitude: Retained latitude scalar; it does not qualify GPS accuracy or force
            analysis.
        longitude: Retained longitude scalar; it does not qualify GPS accuracy or force
            analysis.
        timestamp: Retained source timestamp.
        altitude: Retained source altitude.
        speed: Retained source speed.
        course: Retained source course.
        horizontal_accuracy: Retained source horizontal-accuracy estimate.
        vertical_accuracy: Retained source vertical-accuracy estimate.
        speed_accuracy: Retained source speed-accuracy estimate.
        course_accuracy: Retained source course-accuracy estimate.
    """

    latitude: float = field(repr=False)
    longitude: float = field(repr=False)
    timestamp: float | None = field(default=None, repr=False)
    altitude: float | None = field(default=None, repr=False)
    speed: float | None = field(default=None, repr=False)
    course: float | None = field(default=None, repr=False)
    horizontal_accuracy: float | None = field(default=None, repr=False)
    vertical_accuracy: float | None = field(default=None, repr=False)
    speed_accuracy: float | None = field(default=None, repr=False)
    course_accuracy: float | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.
        """
        for name, value in (("latitude", self.latitude), ("longitude", self.longitude)):
            object.__setattr__(self, name, _finite(value, name))
        for optional_name, optional_value in (
            ("timestamp", self.timestamp),
            ("altitude", self.altitude),
            ("speed", self.speed),
            ("course", self.course),
            ("horizontal_accuracy", self.horizontal_accuracy),
            ("vertical_accuracy", self.vertical_accuracy),
            ("speed_accuracy", self.speed_accuracy),
            ("course_accuracy", self.course_accuracy),
        ):
            if optional_value is not None:
                object.__setattr__(self, optional_name, _finite(optional_value, optional_name))


@dataclass(frozen=True, slots=True)
class GpsEntry:
    """Gps entry contract and owned data.

    Attributes:
        index: Source or collection index selected for this operation.
        fix: Optional retained geographic fix for this sample.
    """

    index: int
    fix: GpsFix | None = field(repr=False)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: GPS entry must contain a GpsFix or an unavailable slot.
        """
        _index(self.index, "GPS source index")
        if self.fix is not None and not has_type(self.fix, GpsFix):
            raise TypeError("GPS entry must contain a GpsFix or an unavailable slot")


@dataclass(frozen=True, slots=True, init=False)
class GpsSequence:
    """Gps sequence contract and owned data.

    Attributes:
        entries: Ordered entries to retain.
    """

    entries: tuple[GpsEntry, ...] = field(repr=False)

    def __init__(self, entries: Sequence[GpsEntry]) -> None:
        """Initialize gps sequence and its owned state.

        Args:
            entries: Ordered entries to retain.

        Returns:
            None.

        Raises:
            ValueError: GPS entries must retain every original sequential slot.
        """
        owned = tuple(entries)
        if any(
            not has_type(item, GpsEntry) or item.index != index for index, item in enumerate(owned)
        ):
            raise ValueError("GPS entries must retain every original sequential slot")
        object.__setattr__(self, "entries", owned)


class GpsStatus(StrEnum):
    """Gps status contract and owned data.

    Attributes:
        ABSENT: Named value for absent (`absent`).
        PRESENT: Named value for present (`present`).
        INVALID: Named value for invalid (`invalid`).
    """

    ABSENT = "absent"
    PRESENT = "present"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RecordingMetadata:
    """Recording metadata contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        uuid: Opaque recording identifier retained from the source.
        device: Retained source device description.
        advanced_recording: Retained source advanced-recording setting.
        date: Retained source recording date.
        timezone: Retained source time-zone metadata.
        location: Retained source location metadata.
        riding_position: Declared or explicitly defaulted riding position.
        latitude: Retained latitude scalar; it does not qualify GPS accuracy or force
            analysis.
        longitude: Retained longitude scalar; it does not qualify GPS accuracy or force
            analysis.
        temperature: Retained source temperature metadata.
        weather_conditions: Retained source weather description.
        wind_direction: Retained source wind direction.
        wind_speed: Retained source wind speed.
        wind_gust: Retained source wind-gust metadata.
    """

    name: str | None = None
    uuid: str | None = None
    device: str | None = None
    advanced_recording: bool | None = None
    date: SourceNumber | None = None
    timezone: str | None = None
    location: str | None = None
    riding_position: RidingPosition | None = RidingPosition()
    latitude: float | None = field(default=None, repr=False)
    longitude: float | None = field(default=None, repr=False)
    temperature: float | None = None
    weather_conditions: str | None = None
    wind_direction: float | None = None
    wind_speed: float | None = None
    wind_gust: float | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Metadata text must be a string or None. Advanced recording must be bool
                or None. Date requires a source number without epoch conversion. Riding
                position must expose its effective value and origin.
        """
        strings = (
            self.name,
            self.uuid,
            self.device,
            self.timezone,
            self.location,
            self.weather_conditions,
        )
        if any(value is not None and not has_type(value, str) for value in strings):
            raise TypeError("Metadata text must be a string or None")
        if self.advanced_recording is not None and type(self.advanced_recording) is not bool:
            raise TypeError("Advanced recording must be bool or None")
        if self.date is not None and not has_type(self.date, SourceNumber):
            raise TypeError("Date requires a source number without epoch conversion")
        if self.riding_position is not None and not has_type(
            self.riding_position,
            RidingPosition,
        ):
            raise TypeError("Riding position must expose its effective value and origin")
        for name, value in (
            ("latitude", self.latitude),
            ("longitude", self.longitude),
            ("temperature", self.temperature),
            ("wind_direction", self.wind_direction),
            ("wind_speed", self.wind_speed),
            ("wind_gust", self.wind_gust),
        ):
            if value is not None:
                object.__setattr__(self, name, _finite(value, name))


@dataclass(frozen=True, slots=True, init=False)
class Recording:
    """Recording contract and owned data.

    Attributes:
        schema_version: Version identifying the admitted source or stored document
            contract.
        source_format: Admitted recording profile, kept separate from scientific
            qualification.
        source: Retained input identity or image; its original representation remains
            owned.
        motion: Validated source acceleration and optional gravity sequences.
        indices: Source or effective sample markers associated with the recording.
        metadata: Retained recording metadata without reconstruction of absent fields.
        attributes: Source attribute records, including retained labels and opaque values.
        vectors: Retained source direction or calibration vectors.
        gps: Independent optional GPS sequence retained for spatial context.
        gps_status: Availability status of the admitted optional GPS data.
        smoothing_factor: Source smoothing setting retained as metadata.
        max_force: Source maximum-force metadata.
        min_force: Source minimum-force metadata.
    """

    schema_version: str | None
    source_format: RecordingFormat
    source: SourceEnvelope = field(repr=False)
    motion: MotionSequence = field(repr=False)
    indices: RecordingIndices
    metadata: RecordingMetadata = field(repr=False)
    attributes: tuple[Attribute, ...] = field(repr=False)
    vectors: RecordingVectors
    gps: GpsSequence | None = field(repr=False)
    gps_status: GpsStatus
    smoothing_factor: SourceNumber | None
    max_force: SourceNumber | None
    min_force: SourceNumber | None

    def __init__(
        self,
        schema_version: str | None,
        source: SourceEnvelope,
        motion: MotionSequence,
        indices: RecordingIndices,
        *,
        source_format: RecordingFormat = RecordingFormat.RIDE_FORCES,
        metadata: RecordingMetadata = RecordingMetadata(),
        attributes: Sequence[Attribute] = (),
        vectors: RecordingVectors = RecordingVectors(),
        gps: GpsSequence | None = None,
        gps_status: GpsStatus | None = None,
        smoothing_factor: SourceNumber | None = None,
        max_force: SourceNumber | None = None,
        min_force: SourceNumber | None = None,
    ) -> None:
        """Initialize recording and its owned state.

        Args:
            schema_version: Admitted document schema version.
            source: Input recording, retained source representation or source path to read.
            motion: Validated acceleration and optional gravity data.
            indices: Selected source or stored-row indices.
            source_format: Identifier of the admitted source format.
            metadata: Retained recording metadata.
            attributes: Source attribute records to preserve.
            vectors: Vectors in the declared coordinate frame.
            gps: Optional GPS context retained separately from force analysis.
            gps_status: Availability of optional GPS data.
            smoothing_factor: Source smoothing setting retained as metadata.
            max_force: Source maximum-force metadata.
            min_force: Source minimum-force metadata.

        Returns:
            None.

        Raises:
            TypeError: Recording format must be a RecordingFormat. Recording requires typed
                motion and indices. Recording requires typed metadata and vectors. Recording
                attributes must contain Attribute values. Recording GPS must be a GpsSequence
                or None. Source extrema and smoothing require exact source numbers.
            ValueError: Unversioned RFDB recordings have no declared schema version. Recording
                schema version must be a nonempty string. A recording requires retained source
                bytes and a source object. Recording indices must be bounded by acceleration
                length. GPS status must agree with sequence availability.
        """
        if not has_type(source_format, RecordingFormat):
            raise TypeError("Recording format must be a RecordingFormat")
        if source_format is RecordingFormat.RFDB:
            if schema_version is not None:
                raise ValueError("Unversioned RFDB recordings have no declared schema version")
        elif not has_type(schema_version, str) or not schema_version:
            raise ValueError("Recording schema version must be a nonempty string")
        if (
            not has_type(source, SourceEnvelope)
            or source.root is None
            or source.provenance.byte_count == 0
        ):
            raise ValueError("A recording requires retained source bytes and a source object")
        if not has_type(motion, MotionSequence) or not has_type(indices, RecordingIndices):
            raise TypeError("Recording requires typed motion and indices")
        if any(
            index is not None and index >= len(motion.acceleration)
            for index in (indices.start, indices.end, indices.gravity, indices.incline)
        ):
            raise ValueError("Recording indices must be bounded by acceleration length")
        if not has_type(metadata, RecordingMetadata) or not has_type(vectors, RecordingVectors):
            raise TypeError("Recording requires typed metadata and vectors")
        owned_attributes = tuple(attributes)
        if any(not has_type(item, Attribute) for item in owned_attributes):
            raise TypeError("Recording attributes must contain Attribute values")
        if gps is not None and not has_type(gps, GpsSequence):
            raise TypeError("Recording GPS must be a GpsSequence or None")
        status = (
            gps_status
            if gps_status is not None
            else GpsStatus.ABSENT
            if gps is None
            else GpsStatus.PRESENT
        )
        if not has_type(status, GpsStatus) or (status is GpsStatus.PRESENT) != (gps is not None):
            raise ValueError("GPS status must agree with sequence availability")
        for name, value in (
            ("smoothing_factor", smoothing_factor),
            ("max_force", max_force),
            ("min_force", min_force),
        ):
            if value is not None and not has_type(value, SourceNumber):
                raise TypeError("Source extrema and smoothing require exact source numbers")
            object.__setattr__(self, name, value)
        for model_name, model_value in (
            ("schema_version", schema_version),
            ("source_format", source_format),
            ("source", source),
            ("motion", motion),
            ("indices", indices),
            ("metadata", metadata),
            ("attributes", owned_attributes),
            ("vectors", vectors),
            ("gps", gps),
            ("gps_status", status),
        ):
            object.__setattr__(self, model_name, model_value)
