"""FR-009–010, FR-017–022, FR-025: five originals and optional defects."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from hashlib import sha256
from math import copysign
from typing import cast

import pytest

from ride_forces_analyzer.domain import (
    GpsStatus,
    SourceEnvelope,
    SourceNumber,
    ValueOrigin,
)
from ride_forces_analyzer.importers import (
    DecodeSuccess,
    ImportFailure,
    ImportLimits,
    ImportSuccess,
    import_forces,
    MotionParseSuccess,
    OptionalParseSuccess,
    Severity,
    decode_forces_bytes,
    ordered_diagnostics,
    parse_motion,
    parse_optional_data,
)
from test_project import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

TEXT_FIELDS = {
    "name": "name",
    "uuid": "uuid",
    "device": "device",
    "timezone": "timezone",
    "location": "location",
    "weatherConditions": "weather_conditions",
}
NUMBER_FIELDS = {
    "latitude": "latitude",
    "longitude": "longitude",
    "temperature": "temperature",
    "windDirection": "wind_direction",
    "windSpeed": "wind_speed",
    "windGust": "wind_gust",
}
GPS_FIELDS = {
    "latitude": "latitude",
    "longitude": "longitude",
    "timestamp": "timestamp",
    "altitude": "altitude",
    "speed": "speed",
    "course": "course",
    "horizontalAccuracy": "horizontal_accuracy",
    "verticalAccuracy": "vertical_accuracy",
    "speedAccuracy": "speed_accuracy",
    "courseAccuracy": "course_accuracy",
}
NEGATIVE_FIELDS = [
    "speed",
    "course",
    "horizontalAccuracy",
    "verticalAccuracy",
    "speedAccuracy",
    "courseAccuracy",
]
EXPECTED_GPS = {"IronGwazi": None, "Kraken": 174, "Manta": 193, "Taron": 182, "VoltronNevera": 149}


def _root() -> dict[str, object]:
    return {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "accelerationSequence": [{"x": "0", "y": "0", "z": "1"}],
        "startIndex": SourceNumber("0"),
        "endIndex": SourceNumber("0"),
    }


def _fix() -> dict[str, object]:
    return {
        "latitude": SourceNumber("1.00000000000000000001"),
        "longitude": SourceNumber("2.00"),
        "timestamp": SourceNumber("10.00"),
    }


def _parse(root: dict[str, object]) -> OptionalParseSuccess:
    result = parse_optional_data(SourceEnvelope(b"retained synthetic bytes", root))
    assert isinstance(result, OptionalParseSuccess)
    return result


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_all_original_optional_data_and_gps_fixes_survive(filename: str) -> None:
    """AC-02/04/07 subset: complete fields/fixes, ordered attributes, source integrity."""
    path = REAL_FIXTURE_DIRECTORY / filename
    modified = path.stat().st_mtime_ns
    raw = path.read_bytes()
    assert (len(raw), sha256(raw).hexdigest()) == REAL_FIXTURES[filename]
    decoded = decode_forces_bytes(raw)
    assert isinstance(decoded, DecodeSuccess)
    source = decoded.source
    root = source.root
    assert root is not None
    result = parse_optional_data(source)
    assert isinstance(result, OptionalParseSuccess)
    assert result.source is source and source.original_bytes == raw
    assert parse_optional_data(source) == result
    for key, accessor in TEXT_FIELDS.items():
        assert getattr(result.metadata, accessor) == root.get(key)
    for key, accessor in NUMBER_FIELDS.items():
        original = root.get(key)
        assert getattr(result.metadata, accessor) == (
            float(original.value) if isinstance(original, SourceNumber) else None
        )
    assert result.metadata.date is root["date"]
    assert result.metadata.advanced_recording is root["advancedRecording"]
    for key, accessor in (
        ("smoothingFactor", "smoothing_factor"),
        ("maxForce", "max_force"),
        ("minForce", "min_force"),
    ):
        assert getattr(result, accessor) is root[key]
    position = result.metadata.riding_position
    assert position is not None
    present = "ridingPosition" in root
    assert position.value == (root["ridingPosition"] if present else "Seated")
    assert position.origin is (ValueOrigin.SOURCE if present else ValueOrigin.DEFAULT)
    original_attributes = root["attributes"]
    assert isinstance(original_attributes, tuple) and result.attributes is not None
    assert len(result.attributes) == len(original_attributes)
    for original, attribute in zip(original_attributes, result.attributes, strict=True):
        assert isinstance(original, Mapping)
        assert (attribute.id, attribute.label, attribute.value) == (
            original["id"],
            original["label"],
            original["value"],
        )
    recording = filename.split("-", 1)[0]
    if recording == "Manta":
        assert result.metadata.location is None and "location" not in root
        for key in ("temperature", "weatherConditions", "windDirection", "windSpeed", "windGust"):
            assert key not in root
        assert result.metadata.temperature is None and result.metadata.weather_conditions is None
        assert (
            result.metadata.wind_direction
            is result.metadata.wind_speed
            is result.metadata.wind_gust
            is None
        )
    if recording in ("Taron", "VoltronNevera"):
        assert not present and position.origin is ValueOrigin.DEFAULT
    if recording == "Taron":
        assert [(item.label, item.value) for item in result.attributes] == [
            ("Row", "2"),
            ("Seat", "1"),
        ]
    expected = EXPECTED_GPS[recording]
    if expected is None:
        assert result.gps is None and result.gps_status is GpsStatus.ABSENT
        assert "locationSequence" not in root and "gravitySequence" not in root
        assert result.metadata.latitude is result.metadata.longitude is None
        assert not result.diagnostics
    else:
        original_gps = root["locationSequence"]
        assert isinstance(original_gps, tuple) and result.gps is not None
        assert len(result.gps.entries) == len(original_gps) == expected
        assert result.gps_status is GpsStatus.PRESENT
        acceleration = root["accelerationSequence"]
        assert isinstance(acceleration, tuple) and len(acceleration) != expected
        negatives: set[tuple[int, str]] = set()
        for index, (original, entry) in enumerate(
            zip(original_gps, result.gps.entries, strict=True),
        ):
            assert isinstance(original, Mapping) and entry.fix is not None and entry.index == index
            for key, accessor in GPS_FIELDS.items():
                value = original[key]
                assert isinstance(value, SourceNumber)
                assert getattr(entry.fix, accessor) == float(value.value)
                if key in NEGATIVE_FIELDS and value.value < 0:
                    negatives.add((index, f"/locationSequence/{index}/{key}"))
        assert {
            (d.sample_index, d.json_path)
            for d in result.diagnostics
            if d.code == "GPS_NEGATIVE_VALUE"
        } == negatives
    assert all(item.severity is not Severity.ERROR for item in result.diagnostics)
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    motion = parse_motion(source)
    assert isinstance(motion, MotionParseSuccess)
    if recording == "IronGwazi":
        assert motion.motion.gravity is None and not motion.motion.paired_motion_available
    assert path.stat().st_mtime_ns == modified
    after = path.read_bytes()
    assert after == raw and (len(after), sha256(after).hexdigest()) == REAL_FIXTURES[filename]


@pytest.mark.parametrize("field", [*TEXT_FIELDS, "ridingPosition"])
@pytest.mark.parametrize("value", [None, True, SourceNumber("0"), [], {}])
def test_invalid_present_optional_text_warns_and_never_defaults(field: str, value: object) -> None:
    root = _root()
    root[field] = value
    result = _parse(root)
    accessor = TEXT_FIELDS.get(field, "riding_position")
    assert getattr(result.metadata, accessor) is None
    assert any(
        d.code == "INVALID_OPTIONAL_METADATA" and d.json_path == "/" + field
        for d in result.diagnostics
    )
    assert result.source.root is not None and field in result.source.root


@pytest.mark.parametrize("position", ["Seated", "Flying", "Standing", "Future posture", " Flying "])
def test_valid_present_riding_position_is_not_trimmed_or_overridden(position: str) -> None:
    root = _root()
    root["ridingPosition"] = position
    result = _parse(root)
    assert result.metadata.riding_position is not None
    assert result.metadata.riding_position.value == position
    assert result.metadata.riding_position.origin is ValueOrigin.SOURCE
    assert not result.diagnostics


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_blank_present_riding_position_is_unavailable(value: str) -> None:
    root = _root()
    root["ridingPosition"] = value
    result = _parse(root)
    assert result.metadata.riding_position is None and len(result.diagnostics) == 1


@pytest.mark.parametrize("field", NUMBER_FIELDS)
@pytest.mark.parametrize("value", [None, True, "0", SourceNumber("1e9999"), [], {}])
def test_invalid_metadata_numeric_values_warn_without_zero_filling(
    field: str,
    value: object,
) -> None:
    root = _root()
    root[field] = value
    result = _parse(root)
    assert getattr(result.metadata, NUMBER_FIELDS[field]) is None
    assert len(result.diagnostics) == 1 and result.diagnostics[0].json_path == "/" + field


def test_metadata_absence_zero_false_and_exact_date_have_distinct_meanings() -> None:
    absent = _parse(_root())
    assert (
        absent.metadata.temperature
        is absent.metadata.advanced_recording
        is absent.metadata.date
        is None
    )
    assert absent.attributes is None and absent.gps_status is GpsStatus.ABSENT
    assert absent.metadata.riding_position is not None
    assert absent.metadata.riding_position.origin is ValueOrigin.DEFAULT
    assert absent.source.root is not None and "ridingPosition" not in absent.source.root
    root = _root()
    root.update(
        temperature=SourceNumber("-0.00"),
        advancedRecording=False,
        date=SourceNumber("1e9999"),
        timezone="Custom/timezone",
        location="",
        maxForce=SourceNumber("1.00000000000000000001"),
    )
    result = _parse(root)
    assert result.metadata.temperature == 0 and copysign(1, result.metadata.temperature) < 0
    assert result.metadata.advanced_recording is False
    assert result.metadata.date == root["date"] and result.max_force == root["maxForce"]
    assert result.metadata.location == "" and result.metadata.timezone == "Custom/timezone"
    assert not result.diagnostics


@pytest.mark.parametrize(
    "field",
    ["date", "smoothingFactor", "maxForce", "minForce", "advancedRecording"],
)
@pytest.mark.parametrize("value", [None, "0", [], {}])
def test_exact_number_and_boolean_metadata_reject_wrong_types(field: str, value: object) -> None:
    root = _root()
    root[field] = value
    result = _parse(root)
    assert (
        len(result.diagnostics) == 1 and result.diagnostics[0].code == "INVALID_OPTIONAL_METADATA"
    )


@pytest.mark.parametrize("value", [SourceNumber("0"), SourceNumber("1")])
def test_advanced_recording_never_coerces_numbers_to_boolean(value: SourceNumber) -> None:
    root = _root()
    root["advancedRecording"] = value
    result = _parse(root)
    assert result.metadata.advanced_recording is None and len(result.diagnostics) == 1


@pytest.mark.parametrize("value", [None, True, "[]", {}, SourceNumber("0")])
@pytest.mark.parametrize("field", ["locationSequence", "attributes"])
def test_defective_optional_containers_are_unavailable_not_core_errors(
    field: str,
    value: object,
) -> None:
    root = _root()
    root[field] = value
    result = _parse(root)
    assert len(result.diagnostics) == 1 and result.diagnostics[0].severity is Severity.WARNING
    assert result.diagnostics[0].json_path == "/" + field
    if field == "locationSequence":
        assert result.gps is None and result.gps_status is GpsStatus.INVALID
        assert result.diagnostics[0].code == "INVALID_OPTIONAL_GPS"
    else:
        assert (
            result.attributes is None
            and result.diagnostics[0].code == "INVALID_OPTIONAL_ATTRIBUTES"
        )
    assert isinstance(parse_motion(result.source), MotionParseSuccess)


@pytest.mark.parametrize("count", [0, 1, 2, 11])
def test_gps_counts_are_independent_and_empty_containers_are_present(count: int) -> None:
    root = _root()
    root.update(locationSequence=[_fix() for _ in range(count)], attributes=[])
    result = _parse(root)
    assert result.gps is not None and result.gps_status is GpsStatus.PRESENT
    assert len(result.gps.entries) == count and result.attributes == ()
    assert all(entry.index == index for index, entry in enumerate(result.gps.entries))
    assert isinstance(parse_motion(result.source), MotionParseSuccess)


@pytest.mark.parametrize(
    "device, informational",
    [("Apple Watch", False), ("iPhone", True), ("Future", False), (None, False)],
)
def test_missing_gps_device_policy_preserves_absence(
    device: str | None,
    informational: bool,
) -> None:
    root = _root()
    if device is None:
        del root["device"]
    else:
        root["device"] = device
    result = _parse(root)
    assert result.gps is None and result.gps_status is GpsStatus.ABSENT
    assert len(result.diagnostics) == int(informational)
    if informational:
        assert result.diagnostics[0].code == "GPS_UNAVAILABLE"
        assert result.diagnostics[0].severity is Severity.INFO


@pytest.mark.parametrize("field", ["latitude", "longitude"])
@pytest.mark.parametrize("value", [None, True, "1", SourceNumber("1e9999"), [], {}])
def test_bad_coordinates_disable_only_their_original_fix_slot(field: str, value: object) -> None:
    root = _root()
    broken = _fix()
    broken[field] = value
    root["locationSequence"] = [_fix(), broken, _fix()]
    result = _parse(root)
    assert result.gps is not None
    assert [entry.fix is not None for entry in result.gps.entries] == [True, False, True]
    diagnostic = next(d for d in result.diagnostics if d.code == "INVALID_GPS_FIX")
    assert diagnostic.json_path == f"/locationSequence/1/{field}" and diagnostic.sample_index == 1
    assert diagnostic.severity is Severity.WARNING


@pytest.mark.parametrize("value", [None, True, "fix", SourceNumber("0"), []])
def test_non_object_fixes_retain_unavailable_slots(value: object) -> None:
    root = _root()
    root["locationSequence"] = [value]
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is None
    assert len(result.diagnostics) == 1 and result.diagnostics[0].json_path == "/locationSequence/0"


@pytest.mark.parametrize(
    "field",
    [key for key in GPS_FIELDS if key not in ("latitude", "longitude")],
)
@pytest.mark.parametrize("value", [None, False, "0", SourceNumber("1e9999"), [], {}])
def test_bad_optional_gps_members_leave_valid_fix_and_siblings_available(
    field: str,
    value: object,
) -> None:
    root = _root()
    fix = _fix()
    fix[field] = value
    root["locationSequence"] = [fix]
    result = _parse(root)
    assert result.gps is not None
    parsed = result.gps.entries[0].fix
    assert parsed is not None and parsed.latitude == 1 and parsed.longitude == 2
    assert getattr(parsed, GPS_FIELDS[field]) is None
    assert (
        len(result.diagnostics) == 1 and result.diagnostics[0].code == "INVALID_OPTIONAL_GPS_FIELD"
    )
    assert result.diagnostics[0].json_path == f"/locationSequence/0/{field}"


def test_missing_gps_coordinates_and_optional_members_are_never_borrowed_or_zero_filled() -> None:
    root = _root()
    root.update(
        latitude=SourceNumber("1"),
        longitude=SourceNumber("2"),
        locationSequence=[{}, {"latitude": SourceNumber("1"), "longitude": SourceNumber("2")}],
    )
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is None
    fix = result.gps.entries[1].fix
    assert fix is not None
    assert all(
        getattr(fix, accessor) is None
        for key, accessor in GPS_FIELDS.items()
        if key not in ("latitude", "longitude")
    )
    assert {d.json_path for d in result.diagnostics} == {
        "/locationSequence/0/latitude",
        "/locationSequence/0/longitude",
    }


@pytest.mark.parametrize("field", NEGATIVE_FIELDS)
@pytest.mark.parametrize("token", ["-1", "-12.345", "-1e-9999"])
def test_any_negative_speed_course_or_accuracy_is_preserved_with_warning(
    field: str,
    token: str,
) -> None:
    root = _root()
    fix = _fix()
    fix[field] = SourceNumber(token)
    root["locationSequence"] = [fix]
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is not None
    assert getattr(result.gps.entries[0].fix, GPS_FIELDS[field]) == float(token)
    assert len(result.diagnostics) == 1 and result.diagnostics[0].code == "GPS_NEGATIVE_VALUE"
    assert result.diagnostics[0].json_path == f"/locationSequence/0/{field}"
    assert result.source.root is not None
    original = result.source.root["locationSequence"]
    assert isinstance(original, tuple) and isinstance(original[0], Mapping)
    assert original[0][field] == SourceNumber(token)


@pytest.mark.parametrize("token", ["0", "-0.00", "1000000"])
def test_finite_accuracy_is_never_rejected_by_an_invented_threshold(token: str) -> None:
    root = _root()
    root["locationSequence"] = [{**_fix(), **{key: SourceNumber(token) for key in NEGATIVE_FIELDS}}]
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is not None
    assert not result.diagnostics


@pytest.mark.parametrize("field", NEGATIVE_FIELDS)
def test_negative_float_overflow_keeps_exact_value_and_both_defect_and_negative_warnings(
    field: str,
) -> None:
    root = _root()
    root["locationSequence"] = [{**_fix(), field: SourceNumber("-1e9999")}]
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is not None
    assert getattr(result.gps.entries[0].fix, GPS_FIELDS[field]) is None
    assert {d.code for d in result.diagnostics} == {
        "INVALID_OPTIONAL_GPS_FIELD",
        "GPS_NEGATIVE_VALUE",
    }
    assert result.source.root is not None
    raw = result.source.root["locationSequence"]
    assert isinstance(raw, tuple) and isinstance(raw[0], Mapping)
    assert raw[0][field] == SourceNumber("-1e9999")


@pytest.mark.parametrize(
    "field, token",
    [
        ("latitude", "90.00000000000000000000000000001"),
        ("latitude", "-91"),
        ("longitude", "181"),
        ("longitude", "-181"),
    ],
)
def test_suspicious_finite_coordinates_warn_and_remain_available(field: str, token: str) -> None:
    root = _root()
    root["locationSequence"] = [{**_fix(), field: SourceNumber(token)}]
    result = _parse(root)
    assert result.gps is not None and result.gps.entries[0].fix is not None
    assert len(result.diagnostics) == 1 and result.diagnostics[0].code == "GPS_SUSPICIOUS_VALUE"


def test_timestamp_order_uses_exact_source_numbers_across_unavailable_gaps_without_epoch_conversion() -> (
    None
):
    root = _root()
    tokens = ["10.00000000000000000001", "10.00000000000000000002", "10.00000000000000000002", "9"]
    root["locationSequence"] = [{**_fix(), "timestamp": SourceNumber(token)} for token in tokens]
    result = _parse(root)
    assert {d.sample_index for d in result.diagnostics} == {2, 3}
    assert all(d.code == "GPS_SUSPICIOUS_VALUE" for d in result.diagnostics)
    root["locationSequence"] = [
        _fix(),
        None,
        {"latitude": SourceNumber("1"), "longitude": SourceNumber("2")},
        {**_fix(), "timestamp": SourceNumber("9")},
    ]
    result = _parse(root)
    assert any(d.code == "GPS_SUSPICIOUS_VALUE" and d.sample_index == 3 for d in result.diagnostics)
    assert result.gps is not None and len(result.gps.entries) == 4


def test_arbitrary_attribute_values_labels_counts_and_extensions_keep_order_and_ownership() -> None:
    payload: dict[str, object] = {"unknown/key~": [SourceNumber("1.00"), "1.00", False, None]}
    records = [
        {"id": "same", "label": "Any label", "value": value, "extension": payload}
        for value in (payload, None, True, SourceNumber("0"), "", ["x"])
    ]
    root = _root()
    root.update(
        attributes=records,
        unknown={"nested": payload},
        locationSequence=[{**_fix(), "extension": payload}],
    )
    source = SourceEnvelope(b"retained synthetic bytes", root)
    result = parse_optional_data(source)
    assert isinstance(result, OptionalParseSuccess) and result.attributes is not None
    assert len(result.attributes) == 6
    assert [item.value for item in result.attributes[1:5]] == [None, True, SourceNumber("0"), ""]
    assert result.attributes[-1].value == ("x",)
    assert isinstance(result.attributes[0].value, Mapping)
    owned = result.attributes[0].value["unknown/key~"]
    assert owned == (SourceNumber("1.00"), "1.00", False, None)
    root.clear()
    records.clear()
    payload.clear()
    assert (
        isinstance(result.attributes[0].value, Mapping)
        and result.attributes[0].value["unknown/key~"] == owned
    )
    assert source.root is not None and "unknown" in source.root
    gps = source.root["locationSequence"]
    assert isinstance(gps, tuple) and isinstance(gps[0], Mapping) and "extension" in gps[0]
    with pytest.raises(FrozenInstanceError):
        setattr(result, "gps", None)
    with pytest.raises(TypeError):
        cast(dict[str, object], result.attributes[0].value)["new"] = True
    assert not result.diagnostics and not hasattr(result, "recording")


@pytest.mark.parametrize(
    "broken",
    [
        None,
        [],
        "entry",
        {},
        {"id": None, "label": "label", "value": "value"},
        {"id": "id", "label": True, "value": "value"},
        {"id": "id", "label": "label"},
    ],
)
def test_malformed_attributes_warn_at_source_index_without_corrupting_siblings(
    broken: object,
) -> None:
    root = _root()
    root["attributes"] = [
        {"id": "b", "label": "Seat", "value": "2"},
        broken,
        {"id": "a", "label": "Row", "value": "1"},
    ]
    result = _parse(root)
    assert result.attributes is not None
    assert [item.id for item in result.attributes] == ["b", "a"]
    assert all(
        d.code == "INVALID_ATTRIBUTE"
        and d.sample_index == 1
        and d.json_path.startswith("/attributes/1")
        for d in result.diagnostics
    )


def test_diagnostics_are_ordered_safe_and_independent_of_object_member_order() -> None:
    root = _root()
    root.update(
        device="iPhone",
        location=None,
        ridingPosition=None,
        attributes=[None],
        locationSequence=[{**_fix(), "speed": SourceNumber("-123.456")}, None],
    )
    source = SourceEnvelope(b"retained bytes", root)
    result = parse_optional_data(source)
    shuffled = dict(reversed(list(root.items())))
    fixes = cast(list[object], shuffled["locationSequence"])
    fixes[0] = dict(reversed(list(cast(dict[str, object], fixes[0]).items())))
    assert result == parse_optional_data(SourceEnvelope(b"retained bytes", shuffled))
    assert isinstance(result, OptionalParseSuccess)
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    assert all("123.456" not in d.message for d in result.diagnostics)
    assert all(d.severity is Severity.WARNING for d in result.diagnostics)


@pytest.mark.parametrize("budget", [1, 2, 4])
def test_optional_diagnostic_budget_accepts_boundary_and_fails_on_overflow(budget: int) -> None:
    root = _root()
    root["attributes"] = [None] * budget
    source = SourceEnvelope(b"retained bytes", root)
    limits = ImportLimits(max_diagnostics=budget)
    result = parse_optional_data(source, limits=limits)
    assert isinstance(result, OptionalParseSuccess) and len(result.diagnostics) == budget
    root["attributes"] = [None] * (budget + 1)
    source = SourceEnvelope(b"retained bytes", root)
    result = parse_optional_data(source, limits=limits)
    assert (
        isinstance(result, ImportFailure) and result.recording is None and result.source is source
    )
    assert len(result.diagnostics) == budget and result.schema_version == "2.2.0"
    fatal = result.diagnostics[0]
    assert fatal.code == "RESOURCE_LIMIT_EXCEEDED" and fatal.severity is Severity.ERROR
    assert fatal.json_path == f"/attributes/{budget}"
    assert result == parse_optional_data(source, limits=limits)


def test_missing_source_root_is_failure_and_optional_success_never_validates_core() -> None:
    result = parse_optional_data(SourceEnvelope(b"invalid"))
    assert isinstance(result, ImportFailure) and result.diagnostics[0].code == "INVALID_SOURCE_ROOT"
    subset = _parse({})
    assert not hasattr(subset, "recording")
    assert isinstance(parse_motion(subset.source), ImportFailure)
    with pytest.raises(ValueError, match="limits"):
        parse_optional_data(subset.source, limits=cast(ImportLimits, None))


def test_voltron_weather_metadata_matches_source_app() -> None:
    path = next(REAL_FIXTURE_DIRECTORY.glob("VoltronNevera-*.forces"))
    original = path.read_bytes()
    result = import_forces(path)
    assert isinstance(result, ImportSuccess)
    metadata = result.recording.metadata
    assert metadata.weather_conditions == "Mostly Clear"
    assert metadata.temperature == 17.786710739135742
    assert metadata.wind_direction == 195.0
    assert metadata.wind_speed == 0.9936420124626161
    assert metadata.wind_gust == 3.874126195764542
    assert metadata.temperature is not None and metadata.wind_direction is not None
    assert metadata.wind_speed is not None and metadata.wind_gust is not None
    assert round(metadata.temperature, 1) == 17.8
    assert round(metadata.wind_speed * 3.6) == 4
    assert round(metadata.wind_gust * 3.6) == 14
    assert 191.25 <= metadata.wind_direction < 213.75  # SSW sector, centered at 202.5 degrees.
    assert result.recording.source.original_bytes == original
    assert path.read_bytes() == original
