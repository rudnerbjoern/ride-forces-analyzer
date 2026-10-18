"""FR-011–016: all five motion fixtures and synthetic structural defects."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from math import copysign
from typing import cast

import pytest

from ride_forces_analyzer.domain import (
    SourceEnvelope,
    SourceNumber,
    SourceValue,
    ValueOrigin,
    Vector3,
)
from ride_forces_analyzer.importers import (
    ImportFailure,
    MotionParseSuccess,
    Severity,
    ordered_diagnostics,
    parse_motion,
)
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

VECTORS = (
    ("verticalDirectionVector", "vertical_direction"),
    ("lateralDirectionVector", "lateral_direction"),
    ("longitudinalDirectionVector", "longitudinal_direction"),
    ("xCalibrationVector", "x_calibration"),
    ("yCalibrationVector", "y_calibration"),
    ("zCalibrationVector", "z_calibration"),
)
EXPECTED = {
    "IronGwazi": (8712, None, 1720, 8179, 7382, 3121, ValueOrigin.SOURCE),
    "Kraken": (10084, 10084, 913, 9138, 1028, 2928, ValueOrigin.SOURCE),
    "Manta": (9640, 9640, 1214, 9639, 2013, 3370, ValueOrigin.SOURCE),
    "Taron": (9089, 9089, 2284, 6639, 1513, 2852, ValueOrigin.DEFAULT),
    "VoltronNevera": (10504, 10504, 1571, 10374, 6894, 7368, ValueOrigin.DEFAULT),
}


def _root() -> dict[str, object]:
    return {
        "schemaVersion": "2.2.0",
        "device": "iPhone",
        "accelerationSequence": [{"x": "-0.000", "y": "0", "z": "1.00"}] * 3,
        "gravitySequence": [{"x": "0", "y": "0", "z": "1.00"}] * 3,
        "sampleRate": SourceNumber("50"),
        "startIndex": SourceNumber("1"),
        "endIndex": SourceNumber("2"),
        "gravityIndex": SourceNumber("0"),
        "inclineIndex": SourceNumber("2"),
        **{key: {"x": "2.00", "y": "0", "z": "0"} for key, _ in VECTORS},
    }


def _source(root: dict[str, object]) -> SourceEnvelope:
    # Programmatic source-tree boundary, not the future production document decoder.
    return SourceEnvelope(b"retained synthetic source bytes", root)


def _vector_at(root: dict[str, object], field: str, index: int = 0) -> dict[str, object]:
    if field.endswith("Sequence"):
        return cast(list[dict[str, object]], root[field])[index]
    return cast(dict[str, object], root[field])


def _assert_original_vector(raw: SourceValue, vector: Vector3) -> None:
    assert isinstance(raw, Mapping)
    for axis in ("x", "y", "z"):
        component = raw[axis]
        assert isinstance(component, str)
        assert getattr(vector, axis) == float(component)


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_every_original_motion_sample_and_vector_survives(filename: str) -> None:
    """AC-02/06: exact retained bytes, all samples/components, markers and rate origin."""
    path = REAL_FIXTURE_DIRECTORY / filename
    modified = path.stat().st_mtime_ns
    raw = path.read_bytes()
    assert (len(raw), sha256(raw).hexdigest()) == REAL_FIXTURES[filename]
    tree = cast(
        dict[str, object],
        json.loads(raw, parse_int=SourceNumber, parse_float=SourceNumber),
    )
    source = SourceEnvelope(raw, tree, source_path=path)
    result = parse_motion(source)
    assert isinstance(result, MotionParseSuccess)
    assert result.diagnostics == ()
    acceleration_count, gravity_count, start, end, gravity, incline, origin = EXPECTED[
        filename.split("-", 1)[0]
    ]
    assert len(result.motion.acceleration) == acceleration_count
    assert (result.indices.start, result.indices.end) == (start, end)
    assert (result.indices.gravity, result.indices.incline) == (gravity, incline)
    assert result.motion.sample_rate.value == 50 and result.motion.sample_rate.origin is origin
    assert source.root is not None
    for key, parsed in (
        ("accelerationSequence", result.motion.acceleration),
        ("gravitySequence", result.motion.gravity),
    ):
        if parsed is None:
            assert gravity_count is None and key not in source.root
            assert not result.motion.paired_motion_available
            continue
        originals = source.root[key]
        assert isinstance(originals, tuple) and len(parsed) == len(originals)
        for original, vector in zip(originals, parsed, strict=True):
            _assert_original_vector(original, vector)
    for key, accessor in VECTORS:
        _assert_original_vector(source.root[key], getattr(result.vectors, accessor))
    if filename.startswith("Taron-"):
        assert result.indices.gravity == 1513 < result.indices.start == 2284
    assert result.source is source and source.original_bytes == raw
    assert parse_motion(source) == result
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == modified


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0", 0.0),
        ("-0", -0.0),
        ("+01.50", 1.5),
        (".5", 0.5),
        ("1.", 1.0),
        ("-1.25e+2", -125.0),
        ("1e-9999", 0.0),
        (SourceNumber("1.00"), 1.0),
        (SourceNumber("1e2"), 100.0),
        (SourceNumber("-0"), -0.0),
    ],
)
def test_finite_decimal_values_keep_original_type_and_spelling(
    value: SourceValue,
    expected: float,
) -> None:
    root = _root()
    _vector_at(root, "accelerationSequence")["x"] = value
    source = _source(root)
    result = parse_motion(source)
    assert isinstance(result, MotionParseSuccess)
    actual = result.motion.acceleration[0].x
    assert actual == expected and copysign(1, actual) == copysign(1, expected)
    assert source.root is not None
    samples = source.root["accelerationSequence"]
    assert isinstance(samples, tuple) and isinstance(samples[0], Mapping)
    assert samples[0]["x"] == value and type(samples[0]["x"]) is type(value)


@pytest.mark.parametrize(
    "field",
    ["accelerationSequence", "gravitySequence", *(k for k, _ in VECTORS)],
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        "",
        " ",
        " 1",
        "1 ",
        "NaN",
        "Infinity",
        "-inf",
        "1_000",
        "0x10",
        "one",
        "١",
        "1e9999",
        SourceNumber("1e9999"),
        [],
        {},
    ],
)
def test_invalid_components_are_targeted_and_never_zero_filled(field: str, value: object) -> None:
    root = _root()
    _vector_at(root, field)["x"] = value
    result = parse_motion(_source(root))
    core = field.endswith("Sequence")
    assert isinstance(result, ImportFailure if core else MotionParseSuccess)
    pointer = f"/{field}/0/x" if core else f"/{field}/x"
    diagnostic = next(item for item in result.diagnostics if item.json_path == pointer)
    assert diagnostic.code == "INVALID_NUMERIC_COMPONENT"
    assert diagnostic.severity is (Severity.ERROR if core else Severity.WARNING)
    assert diagnostic.sample_index == (0 if core else None)
    if isinstance(result, ImportFailure):
        assert result.recording is None and result.source is not None
    else:
        accessor = dict(VECTORS)[field]
        assert getattr(result.vectors, accessor) is None
        assert len(result.motion.acceleration) == 3


@pytest.mark.parametrize("field", ["accelerationSequence", "gravitySequence", "xCalibrationVector"])
@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_each_missing_component_is_reported(field: str, axis: str) -> None:
    root = _root()
    del _vector_at(root, field)[axis]
    result = parse_motion(_source(root))
    assert any(
        item.code == "MISSING_VECTOR_COMPONENT" and item.json_path.endswith("/" + axis)
        for item in result.diagnostics
    )


@pytest.mark.parametrize(
    "field",
    ["accelerationSequence", "gravitySequence", "verticalDirectionVector"],
)
@pytest.mark.parametrize("value", [None, True, "0", [], SourceNumber("0")])
def test_non_object_vectors_are_rejected(field: str, value: object) -> None:
    root = _root()
    if field.endswith("Sequence"):
        root[field] = [value]
    else:
        root[field] = value
    result = parse_motion(_source(root))
    assert any(item.code == "INVALID_VECTOR" for item in result.diagnostics)


@pytest.mark.parametrize("field", ["accelerationSequence", "gravitySequence"])
@pytest.mark.parametrize("value", [None, True, {}, "[]", SourceNumber("0"), []])
def test_invalid_or_empty_motion_array_is_fatal(field: str, value: object) -> None:
    root = _root()
    root[field] = value
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert any(
        item.code == "INVALID_MOTION_SEQUENCE" and item.json_path == "/" + field
        for item in result.diagnostics
    )


@pytest.mark.parametrize("count", [1, 2, 4])
def test_unequal_gravity_lengths_are_fatal_without_padding_or_truncation(count: int) -> None:
    root = _root()
    root["gravitySequence"] = [{"x": "0", "y": "0", "z": "1"}] * count
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert any(item.code == "MOTION_LENGTH_MISMATCH" for item in result.diagnostics)


@pytest.mark.parametrize("field", ["accelerationSequence", "gravitySequence"])
@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_every_component_of_the_final_sample_is_validated(field: str, axis: str) -> None:
    root = _root()
    for sequence in ("accelerationSequence", "gravitySequence"):
        root[sequence] = [{"x": "0", "y": "0", "z": "1"} for _ in range(1001)]
    _vector_at(root, field, 1000)[axis] = "Infinity"
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].json_path == f"/{field}/1000/{axis}"
    assert result.diagnostics[0].sample_index == 1000


@pytest.mark.parametrize("invalid", [False, True])
def test_apple_watch_supplied_gravity_is_validated_without_device_override(invalid: bool) -> None:
    root = _root()
    root.update(device="Apple Watch", advancedRecording=False)
    if invalid:
        _vector_at(root, "gravitySequence")["z"] = None
    result = parse_motion(_source(root))
    if invalid:
        assert isinstance(result, ImportFailure)
    else:
        assert isinstance(result, MotionParseSuccess)
        assert result.motion.gravity is not None and result.motion.paired_motion_available
        assert len(result.motion.gravity) == 3


@pytest.mark.parametrize("start, end", [(0, 0), (0, 2), (2, 2)])
def test_start_end_boundary_indices_are_preserved_without_slicing(start: int, end: int) -> None:
    root = _root()
    root.update(startIndex=SourceNumber(str(start)), endIndex=SourceNumber(str(end)))
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert (result.indices.start, result.indices.end) == (start, end)
    assert len(result.motion.acceleration) == 3


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        "NaN",
        "Infinity",
        "1e9999",
        SourceNumber("1e9999"),
        SourceNumber("0"),
        SourceNumber("-1"),
        "-0",
        "1e-9999",
        [],
        {},
    ],
)
def test_present_invalid_rate_never_receives_the_absence_default(value: object) -> None:
    root = _root()
    root["sampleRate"] = value
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert any(item.code == "INVALID_SAMPLE_RATE" for item in result.diagnostics)
    assert result.source is not None and result.source.root is not None
    assert "sampleRate" in result.source.root


@pytest.mark.parametrize("value", [SourceNumber("50"), SourceNumber("100.5"), "+25.0"])
def test_valid_present_rate_wins_and_has_source_provenance(value: SourceValue) -> None:
    root = _root()
    root["sampleRate"] = value
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert result.motion.sample_rate.origin is ValueOrigin.SOURCE
    assert result.motion.sample_rate.value == float(
        value.value if isinstance(value, SourceNumber) else cast(str, value),
    )


def test_only_absent_rate_defaults_and_optional_vectors_remain_unavailable() -> None:
    root = _root()
    del root["sampleRate"]
    for key, _ in VECTORS:
        del root[key]
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert (
        result.motion.sample_rate.value == 50
        and result.motion.sample_rate.origin is ValueOrigin.DEFAULT
    )
    assert result.source.root is not None and "sampleRate" not in result.source.root
    assert all(getattr(result.vectors, accessor) is None for _, accessor in VECTORS)


@pytest.mark.parametrize(
    "device, expected",
    [
        ("Apple Watch", None),
        ("iPhone", "GRAVITY_UNAVAILABLE"),
        ("Future device", "UNKNOWN_DEVICE_PROFILE"),
        (None, "UNKNOWN_DEVICE_PROFILE"),
    ],
)
def test_absent_gravity_policy_never_fabricates_samples(
    device: str | None,
    expected: str | None,
) -> None:
    root = _root()
    del root["gravitySequence"]
    if device is None:
        del root["device"]
    else:
        root["device"] = device
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert result.motion.gravity is None and not result.motion.paired_motion_available
    assert result.source.root is not None and "gravitySequence" not in result.source.root
    assert tuple(item.code for item in result.diagnostics) == ((expected,) if expected else ())


@pytest.mark.parametrize("field", ["startIndex", "endIndex", "gravityIndex", "inclineIndex"])
@pytest.mark.parametrize(
    "value, code",
    [
        (True, "INVALID_INDEX"),
        (None, "INVALID_INDEX"),
        ("1", "INVALID_INDEX"),
        (SourceNumber("1.5"), "INVALID_INDEX"),
        (SourceNumber("-1"), "INDEX_OUT_OF_RANGE"),
        (SourceNumber("3"), "INDEX_OUT_OF_RANGE"),
        (SourceNumber("1e9999"), "INDEX_OUT_OF_RANGE"),
    ],
)
def test_every_supplied_index_is_independently_validated(
    field: str,
    value: object,
    code: str,
) -> None:
    root = _root()
    root[field] = value
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert any(item.code == code and item.json_path == "/" + field for item in result.diagnostics)


def test_bounds_order_and_missing_required_fields() -> None:
    root = _root()
    root.update(startIndex=SourceNumber("2"), endIndex=SourceNumber("1"))
    result = parse_motion(_source(root))
    assert isinstance(result, ImportFailure)
    assert any(item.code == "INVALID_INDEX_ORDER" for item in result.diagnostics)
    for key in ("accelerationSequence",):
        missing = _root()
        del missing[key]
        result = parse_motion(_source(missing))
        assert isinstance(result, ImportFailure)
        assert any(
            item.code == "MISSING_REQUIRED_FIELD" and item.json_path == "/" + key
            for item in result.diagnostics
        )
    assert isinstance(parse_motion(SourceEnvelope(b"retained bytes")), ImportFailure)


def test_marker_bounds_ignore_start_end_interval_and_chronology() -> None:
    root = _root()
    root.update(
        gravityIndex=SourceNumber("2.0"),
        inclineIndex=SourceNumber("0e0"),
        startIndex=SourceNumber("1"),
        endIndex=SourceNumber("1"),
    )
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert (result.indices.gravity, result.indices.incline) == (2, 0)
    del root["gravityIndex"]
    del root["inclineIndex"]
    result = parse_motion(_source(root))
    assert isinstance(result, MotionParseSuccess)
    assert result.indices.gravity is None and result.indices.incline is None


def test_extensions_member_order_immutability_and_no_scientific_transformations() -> None:
    root = _root()
    vector = _vector_at(root, "accelerationSequence")
    vector.update(x="2.50", y="-3.0", z="4.00", extension={"flag": True})
    root["locationSequence"] = ["outside this stage"]
    source = _source(root)
    result = parse_motion(source)
    shuffled = parse_motion(_source(dict(reversed(list(root.items())))))
    assert isinstance(result, MotionParseSuccess) and result == shuffled
    assert result.motion.acceleration[0] == Vector3(2.5, -3, 4)
    assert result.vectors.x_calibration == Vector3(2, 0, 0)
    vector.clear()
    root.clear()
    assert result.motion.acceleration[0] == Vector3(2.5, -3, 4)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "motion", None)
    assert source.root is not None and "locationSequence" in source.root
    assert not hasattr(result, "recording")


def test_all_bad_slots_produce_deterministic_safe_diagnostics_and_no_partial_success() -> None:
    root = _root()
    root["accelerationSequence"] = [{"x": "bad", "y": False}, None, {"x": "1", "y": "2", "z": "3"}]
    root["gravitySequence"] = [{"x": "0", "y": "0", "z": "1"}] * 2
    root["startIndex"] = True
    root["sampleRate"] = None
    source = _source(root)
    result = parse_motion(source)
    assert isinstance(result, ImportFailure) and result.recording is None
    assert result == parse_motion(source)
    assert result.diagnostics == ordered_diagnostics(result.diagnostics)
    assert {item.json_path for item in result.diagnostics} == {
        "/accelerationSequence/0/x",
        "/accelerationSequence/0/y",
        "/accelerationSequence/0/z",
        "/accelerationSequence/1",
        "/gravitySequence",
        "/startIndex",
        "/sampleRate",
    }
    assert all("bad" not in item.message for item in result.diagnostics)
