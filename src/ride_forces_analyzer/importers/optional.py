"""FR-009–010, FR-017–022, FR-025: optional source accessors, without full import."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from math import isfinite
from typing import Literal

from ride_forces_analyzer.domain import (
    Attribute,
    GpsEntry,
    GpsFix,
    GpsSequence,
    GpsStatus,
    RecordingMetadata,
    RidingPosition,
    SourceEnvelope,
    SourceNumber,
    SourceValue,
    ValueOrigin,
)
from ride_forces_analyzer.domain._validation import has_type

from ._diagnostic_budget import DiagnosticBudget, DiagnosticBudgetExceeded
from .diagnostics import ImportDiagnostic, Severity, ordered_diagnostics
from .limits import DEFAULT_LIMITS, ImportLimits
from .result import ImportFailure

_GPS_FIELDS = (
    ("timestamp", "timestamp"),
    ("altitude", "altitude"),
    ("speed", "speed"),
    ("course", "course"),
    ("horizontalAccuracy", "horizontal_accuracy"),
    ("verticalAccuracy", "vertical_accuracy"),
    ("speedAccuracy", "speed_accuracy"),
    ("courseAccuracy", "course_accuracy"),
)
_NEGATIVE_FIELDS = frozenset(
    {
        "speed",
        "course",
        "horizontalAccuracy",
        "verticalAccuracy",
        "speedAccuracy",
        "courseAccuracy",
    },
)


@dataclass(frozen=True, slots=True)
class OptionalParseSuccess:
    """Optional-data subset only; success does not validate core motion or schema."""

    source: SourceEnvelope = field(repr=False)
    metadata: RecordingMetadata = field(repr=False)
    attributes: tuple[Attribute, ...] | None = field(repr=False)
    gps: GpsSequence | None = field(repr=False)
    gps_status: GpsStatus
    smoothing_factor: SourceNumber | None = None
    max_force: SourceNumber | None = None
    min_force: SourceNumber | None = None
    diagnostics: tuple[ImportDiagnostic, ...] = ()
    success: Literal[True] = field(default=True, init=False)

    def __post_init__(self) -> None:
        ordered = ordered_diagnostics(self.diagnostics)
        if any(item.severity is Severity.ERROR for item in ordered):
            raise ValueError("Optional success cannot contain error diagnostics")
        if (self.gps_status is GpsStatus.PRESENT) != (self.gps is not None):
            raise ValueError("GPS status must agree with sequence availability")
        attributes = tuple(self.attributes) if self.attributes is not None else None
        if attributes is not None and any(not has_type(item, Attribute) for item in attributes):
            raise TypeError("Optional attributes must contain Attribute values")
        object.__setattr__(self, "attributes", attributes)
        object.__setattr__(self, "diagnostics", ordered)


type OptionalParseResult = OptionalParseSuccess | ImportFailure


def _finite_number(value: SourceValue) -> float | None:
    # GPS/metadata require JSON numbers, not the numeric strings accepted for motion.
    if not isinstance(value, SourceNumber):
        return None
    converted = float(value.value)
    return converted if isfinite(converted) else None


def _text(root: Mapping[str, SourceValue], key: str, diagnostics: DiagnosticBudget) -> str | None:
    if key not in root:
        return None
    value = root[key]
    if isinstance(value, str):
        return value
    diagnostics.add("INVALID_OPTIONAL_METADATA", (key,), "Optional text must be a JSON string")
    return None


def _source_number(
    root: Mapping[str, SourceValue],
    key: str,
    diagnostics: DiagnosticBudget,
) -> SourceNumber | None:
    if key not in root:
        return None
    value = root[key]
    if isinstance(value, SourceNumber):
        return value
    diagnostics.add("INVALID_OPTIONAL_METADATA", (key,), "Optional value must be a JSON number")
    return None


def _metadata_number(
    root: Mapping[str, SourceValue],
    key: str,
    diagnostics: DiagnosticBudget,
) -> float | None:
    if key not in root:
        return None
    value = _finite_number(root[key])
    if value is None:
        diagnostics.add(
            "INVALID_OPTIONAL_METADATA",
            (key,),
            "Optional numeric accessor requires a finite JSON number",
        )
    return value


def _riding_position(
    root: Mapping[str, SourceValue],
    diagnostics: DiagnosticBudget,
) -> RidingPosition | None:
    if "ridingPosition" not in root:
        return RidingPosition()
    value = root["ridingPosition"]
    if isinstance(value, str) and value.strip():
        return RidingPosition(value, ValueOrigin.SOURCE)
    diagnostics.add(
        "INVALID_OPTIONAL_METADATA",
        ("ridingPosition",),
        "Present riding position must be a nonempty string; absence default does not apply",
    )
    return None


def _metadata(root: Mapping[str, SourceValue], diagnostics: DiagnosticBudget) -> RecordingMetadata:
    advanced: bool | None = None
    if "advancedRecording" in root:
        raw = root["advancedRecording"]
        if isinstance(raw, bool):
            advanced = raw
        else:
            diagnostics.add(
                "INVALID_OPTIONAL_METADATA",
                ("advancedRecording",),
                "Advanced recording must be a JSON boolean",
            )
    return RecordingMetadata(
        name=_text(root, "name", diagnostics),
        uuid=_text(root, "uuid", diagnostics),
        device=_text(root, "device", diagnostics),
        advanced_recording=advanced,
        date=_source_number(root, "date", diagnostics),
        timezone=_text(root, "timezone", diagnostics),
        location=_text(root, "location", diagnostics),
        riding_position=_riding_position(root, diagnostics),
        latitude=_metadata_number(root, "latitude", diagnostics),
        longitude=_metadata_number(root, "longitude", diagnostics),
        temperature=_metadata_number(root, "temperature", diagnostics),
        weather_conditions=_text(root, "weatherConditions", diagnostics),
        wind_direction=_metadata_number(root, "windDirection", diagnostics),
        wind_speed=_metadata_number(root, "windSpeed", diagnostics),
        wind_gust=_metadata_number(root, "windGust", diagnostics),
    )


def _attributes(
    root: Mapping[str, SourceValue],
    diagnostics: DiagnosticBudget,
) -> tuple[Attribute, ...] | None:
    if "attributes" not in root:
        return None
    raw = root["attributes"]
    if not isinstance(raw, tuple):
        diagnostics.add(
            "INVALID_OPTIONAL_ATTRIBUTES",
            ("attributes",),
            "Attributes must be an array",
        )
        return None
    attributes: list[Attribute] = []
    for index, item in enumerate(raw):
        path = ("attributes", index)
        if not isinstance(item, Mapping):
            diagnostics.add("INVALID_ATTRIBUTE", path, "Attribute must be an object", index=index)
            continue
        valid = True
        for key in ("id", "label", "value"):
            if key not in item or (key != "value" and not isinstance(item[key], str)):
                diagnostics.add(
                    "INVALID_ATTRIBUTE",
                    (*path, key),
                    "Attribute requires string id/label and a present source-valued value",
                    index=index,
                )
                valid = False
        if valid:
            identifier, label = item["id"], item["label"]
            assert isinstance(identifier, str) and isinstance(label, str)
            attributes.append(Attribute(identifier, label, item["value"]))
    return tuple(attributes)


def _gps_fix(value: SourceValue, index: int, diagnostics: DiagnosticBudget) -> GpsFix | None:
    path = ("locationSequence", index)
    if not isinstance(value, Mapping):
        diagnostics.add("INVALID_GPS_FIX", path, "GPS fix must be an object", index=index)
        return None
    coordinates: dict[str, float | None] = {}
    for key, bound in (("latitude", 90), ("longitude", 180)):
        coordinate = _finite_number(value.get(key))
        coordinates[key] = coordinate
        if coordinate is None:
            diagnostics.add(
                "INVALID_GPS_FIX",
                (*path, key),
                "GPS coordinates require present finite JSON numbers; fix is unavailable",
                index=index,
            )
        elif isinstance(raw := value[key], SourceNumber) and raw.value.copy_abs() > bound:
            diagnostics.add(
                "GPS_SUSPICIOUS_VALUE",
                (*path, key),
                "Coordinate exceeds conventional GPS bounds; units remain unverified",
                index=index,
            )
    members: dict[str, float | None] = {}
    for key, accessor in _GPS_FIELDS:
        number = _finite_number(value[key]) if key in value else None
        members[accessor] = number
        if key in value and number is None:
            diagnostics.add(
                "INVALID_OPTIONAL_GPS_FIELD",
                (*path, key),
                "Optional GPS accessor requires a finite JSON number; member is unavailable",
                index=index,
            )
        raw_member = value.get(key)
        if (
            key in _NEGATIVE_FIELDS
            and isinstance(raw_member, SourceNumber)
            and raw_member.value < 0
        ):
            diagnostics.add(
                "GPS_NEGATIVE_VALUE",
                (*path, key),
                "Negative GPS source value retained; units and sentinel meaning are unverified",
                index=index,
            )
    latitude, longitude = coordinates["latitude"], coordinates["longitude"]
    if latitude is None or longitude is None:
        return None
    return GpsFix(latitude, longitude, **members)


def _gps(
    root: Mapping[str, SourceValue],
    diagnostics: DiagnosticBudget,
) -> tuple[GpsSequence | None, GpsStatus]:
    if "locationSequence" not in root:
        if root.get("device") == "iPhone":
            diagnostics.add(
                "GPS_UNAVAILABLE",
                ("locationSequence",),
                "iPhone GPS sequence is absent",
                severity=Severity.INFO,
            )
        return None, GpsStatus.ABSENT
    raw = root["locationSequence"]
    if not isinstance(raw, tuple):
        diagnostics.add(
            "INVALID_OPTIONAL_GPS",
            ("locationSequence",),
            "Optional GPS sequence must be an array; container is unavailable",
        )
        return None, GpsStatus.INVALID
    entries: list[GpsEntry] = []
    previous_timestamp: Decimal | None = None
    for index, value in enumerate(raw):
        fix = _gps_fix(value, index, diagnostics)
        entries.append(GpsEntry(index, fix))
        if fix is not None and fix.timestamp is not None:
            assert isinstance(value, Mapping)
            timestamp = value["timestamp"]
            assert isinstance(timestamp, SourceNumber)
            if previous_timestamp is not None and timestamp.value <= previous_timestamp:
                diagnostics.add(
                    "GPS_SUSPICIOUS_VALUE",
                    ("locationSequence", index, "timestamp"),
                    "GPS timestamp is not increasing relative to the previous usable timestamp",
                    index=index,
                )
            previous_timestamp = timestamp.value
    return GpsSequence(entries), GpsStatus.PRESENT


def validate_optional_data(
    source: SourceEnvelope,
    diagnostics: DiagnosticBudget,
) -> OptionalParseResult:
    """Parse a decoded 2.2.0 envelope; no I/O, motion validation or scientific conversion."""
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
    metadata = _metadata(root, diagnostics)
    attributes = _attributes(root, diagnostics)
    smoothing = _source_number(root, "smoothingFactor", diagnostics)
    maximum = _source_number(root, "maxForce", diagnostics)
    minimum = _source_number(root, "minForce", diagnostics)
    gps, status = _gps(root, diagnostics)
    return OptionalParseSuccess(
        source,
        metadata,
        attributes,
        gps,
        status,
        smoothing,
        maximum,
        minimum,
        ordered_diagnostics(diagnostics.records),
    )


def parse_optional_data(
    source: SourceEnvelope,
    *,
    limits: ImportLimits = DEFAULT_LIMITS,
) -> OptionalParseResult:
    """Parse optional accessors independently with a bounded diagnostic list and no I/O."""
    if not has_type(limits, ImportLimits):
        raise ValueError("limits must be an ImportLimits instance")
    diagnostics = DiagnosticBudget(limits.max_diagnostics)
    try:
        return validate_optional_data(source, diagnostics)
    except DiagnosticBudgetExceeded:
        return diagnostics.failure(source)
