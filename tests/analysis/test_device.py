"""Analytic synthetic device tests; no fixture unit or axis claims."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
import subprocess
import sys
from typing import cast

import numpy as np
import pytest

from ride_forces_analyzer.analysis import (
    AnalysisChannel,
    AnalysisResult,
    CapabilityState,
    EvidenceState,
    FrameLabel,
    QuantityKind,
    ResultValidity,
    SampleValues,
    SourceSequence,
    UnitAssignment,
    UnitLabel,
)
from ride_forces_analyzer.analysis.device import (
    DeviceAccelerationUnit,
    MotionUnitContract,
    analyze_device_vectors,
    convert_device_vectors,
    device_vector_norm,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


NOW = datetime(2026, 10, 14, tzinfo=UTC)
G0 = 9.80665


def _source(
    acceleration: tuple[float, float, float] = (3.0, 4.0, 0.0),
    gravity: tuple[float, float, float] | None = None,
) -> ImportSuccess:
    payload: dict[str, object] = {
        "schemaVersion": "2.2.0",
        "device": "Apple Watch",
        "accelerationSequence": [dict(zip(("x", "y", "z"), map(str, acceleration), strict=True))],
        "startIndex": 0,
        "endIndex": 0,
        "unknown": {"retain": "003.000"},
    }
    if gravity is not None:
        payload["gravitySequence"] = [dict(zip(("x", "y", "z"), map(str, gravity), strict=True))]
    result = import_forces_bytes(json.dumps(payload).encode())
    assert isinstance(result, ImportSuccess)
    return result


def _contract(
    source: ImportSuccess,
    unit: DeviceAccelerationUnit = DeviceAccelerationUnit.SI,
    sequence: SourceSequence = SourceSequence.ACCELERATION,
    quantity: QuantityKind = QuantityKind.SPECIFIC_FORCE,
) -> MotionUnitContract:
    return MotionUnitContract(
        source.source_sha256,
        sequence,
        unit,
        quantity,
        ("synthetic: common orthogonal DEVICE component units",),
        ("synthetic: explicitly simulated sensor quantity",),
    )


def _analyze(
    source: ImportSuccess,
    unit: DeviceAccelerationUnit = DeviceAccelerationUnit.SI,
) -> AnalysisResult:
    return analyze_device_vectors(
        source,
        calculation_time=NOW,
        acceleration_contract=_contract(source, unit),
    )


def test_installed_device_processing_uses_no_network_writes_or_qt() -> None:
    script = """
import builtins
import os
import socket
import sys
from tests.analysis.test_device import _source, _analyze
source = _source()
def deny(*args, **kwargs):
    raise AssertionError("Unexpected file or network access during calculation")
builtins.open = deny
os.open = deny
socket.socket = deny
result = _analyze(source)
assert result.channels[1].samples.values[0] == 5
assert not any(name.startswith("PySide6") for name in sys.modules)
print("Offline device processing passed")
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    assert b"Offline device processing passed" in completed.stdout


@pytest.mark.parametrize(
    "quantity",
    [QuantityKind.SPECIFIC_FORCE, QuantityKind.GRAVITY, QuantityKind.KINEMATIC_ACCELERATION],
)
def test_analytic_norm_preserves_quantity_binding(quantity: QuantityKind) -> None:
    source = _source((-3, 4, 12))
    result = analyze_device_vectors(
        source,
        calculation_time=NOW,
        acceleration_contract=_contract(source, quantity=quantity),
    )
    vector, magnitude = result.channels[:2]
    assert (
        vector.quantity is quantity and magnitude.quantity is QuantityKind.DEVICE_VECTOR_MAGNITUDE
    )
    assert vector.samples is not None and magnitude.samples is not None
    np.testing.assert_array_equal(vector.samples.values, [[-3, 4, 12]])
    np.testing.assert_array_equal(magnitude.samples.values, [13])
    assert magnitude.frame is FrameLabel.DEVICE and magnitude.source_indices == (0,)
    assert magnitude.unit.state is EvidenceState.VERIFIED
    assert result.profile.configuration["acceleration.quantity"] == quantity.value
    assert result.source is source and result.provenance.calculation_time == NOW


def test_synthetic_stationarity_never_combines_independent_vectors() -> None:
    # Explicit synthetic f = +g0 z, gravity = -g0 z; not a .forces convention.
    source = _source((0, 0, G0), (0, 0, -G0))
    result = analyze_device_vectors(
        source,
        calculation_time=NOW,
        acceleration_contract=_contract(source),
        gravity_contract=_contract(
            source,
            sequence=SourceSequence.GRAVITY,
            quantity=QuantityKind.GRAVITY,
        ),
    )
    assert result.validity is ResultValidity.VALID
    for channel, expected in zip(
        result.channels,
        ([[0, 0, G0]], [G0], [[0, 0, -G0]], [G0]),
        strict=True,
    ):
        assert channel.samples is not None
        np.testing.assert_allclose(channel.samples.values, expected, rtol=1e-14)
    assert result.channels[0].quantity is QuantityKind.SPECIFIC_FORCE
    assert result.channels[2].quantity is QuantityKind.GRAVITY
    assert not any(c.quantity is QuantityKind.KINEMATIC_ACCELERATION for c in result.channels)


def test_zero_specific_force_is_finite_zero_not_missing_or_one_g() -> None:
    source = _source((0, 0, 0), (0, 0, -G0))
    result = _analyze(source)
    channel = result.channels[1]
    assert channel.samples is not None
    assert channel.samples.values[0] == 0 and channel.samples.valid_rows == (True,)
    assert (
        result.channels[2].state is CapabilityState.UNAVAILABLE
    )  # supplied but unqualified gravity
    assert source.recording.motion.gravity is not None
    assert source.recording.motion.gravity[0].z == -G0


@pytest.mark.parametrize(
    "unit,expected",
    [
        (DeviceAccelerationUnit.SI, 5),
        (DeviceAccelerationUnit.CENTIMETERS, 0.05),
        (DeviceAccelerationUnit.FEET, 1.524),
        (DeviceAccelerationUnit.STANDARD_GRAVITY, 5 * G0),
    ],
)
def test_explicit_pint_conversion(unit: DeviceAccelerationUnit, expected: float) -> None:
    source = _source()
    result = _analyze(source, unit)
    assert result.channels[1].samples is not None
    np.testing.assert_allclose(result.channels[1].samples.values, [expected], rtol=1e-14)
    assert result.channels[0].unit.label is UnitLabel.ACCELERATION_SI
    assert result.profile.configuration["acceleration.source_unit"] == unit.value
    assert source.recording.motion.acceleration[0].x == 3


@pytest.mark.parametrize(
    "bad_unit",
    ["g", "gram", "meter", "dimensionless", "unknown", "meter / second ** 2", None],
)
def test_unknown_or_dimensionally_wrong_units_are_rejected(bad_unit: object) -> None:
    with pytest.raises(TypeError, match="explicit acceleration unit"):
        replace(_contract(_source()), unit=cast(DeviceAccelerationUnit, bad_unit))


def test_contract_rejects_missing_evidence_and_wrong_binding() -> None:
    source = _source()
    contract = _contract(source)
    for name in ("unit_evidence", "quantity_evidence"):
        with pytest.raises(ValueError, match="references"):
            replace(contract, **{name: ()})
    with pytest.raises(FrozenInstanceError):
        setattr(contract, "unit", DeviceAccelerationUnit.FEET)
    for wrong in (
        replace(contract, source_sha256="0" * 64),
        replace(contract, source_sequence=SourceSequence.GRAVITY),
    ):
        with pytest.raises(ValueError, match="source and sequence"):
            analyze_device_vectors(source, calculation_time=NOW, acceleration_contract=wrong)
    with pytest.raises(ValueError, match="motion sequence"):
        replace(contract, source_sequence=SourceSequence.GPS)
    with pytest.raises(ValueError, match="physical quantity"):
        replace(contract, quantity=QuantityKind.SOURCE_VALUES)


def test_absent_contract_and_absent_sequence_are_distinct_and_deterministic() -> None:
    source = _source()
    result = analyze_device_vectors(source, calculation_time=NOW)
    assert result == analyze_device_vectors(source, calculation_time=NOW)
    assert result.validity is ResultValidity.RESTRICTED
    assert all(
        c.samples is None and c.state is CapabilityState.UNAVAILABLE for c in result.channels
    )
    assert [d.code for d in result.diagnostics] == ["SOURCE_UNIT_UNKNOWN"] * 2 + [
        "SOURCE_SEQUENCE_ABSENT",
    ] * 2
    with_contract = _analyze(source)
    assert all(c.samples is None for c in with_contract.channels[2:])
    # Even a caller declaration cannot synthesize a missing channel.
    absent = analyze_device_vectors(
        source,
        calculation_time=NOW,
        gravity_contract=_contract(
            source,
            sequence=SourceSequence.GRAVITY,
            quantity=QuantityKind.GRAVITY,
        ),
    )
    assert absent.channels[2].samples is None


def test_owned_conversion_and_missing_rows_survive_without_zero_fill() -> None:
    values = np.array([[3, 4, 0], [np.nan, np.nan, np.nan]], dtype=np.float64)
    samples = SampleValues(values, valid_rows=(True, False))
    converted = convert_device_vectors(
        samples,
        _contract(_source(), DeviceAccelerationUnit.CENTIMETERS),
    )
    channel = AnalysisChannel(
        "synthetic",
        QuantityKind.SPECIFIC_FORCE,
        CapabilityState.VERIFIED,
        SourceSequence.ACCELERATION,
        unit=UnitAssignment(UnitLabel.ACCELERATION_SI, EvidenceState.VERIFIED, ("synthetic",)),
        frame=FrameLabel.DEVICE,
        samples=converted,
        source_indices=(0, 1),
        columns=("x", "y", "z"),
    )
    norm = device_vector_norm(channel)
    assert norm.samples is not None and norm.samples.valid_rows == (True, False)
    assert norm.samples.values[0] == pytest.approx(0.05) and np.isnan(norm.samples.values[1])
    values[:] = 99
    assert samples.values[0, 0] == 3 and converted.values[0, 0] == 0.03
    with pytest.raises(ValueError):
        converted.values.setflags(write=True)
    with pytest.raises(ValueError, match="x/y/z"):
        convert_device_vectors(SampleValues(np.array([1.0])), _contract(_source()))
    with pytest.raises(ValueError, match="verified SI"):
        device_vector_norm(replace(channel, frame=FrameLabel.RIDER, frame_evidence=("synthetic",)))


@pytest.mark.parametrize("scale", [1e-300, 1e300])
def test_norm_avoids_intermediate_squaring_range_loss(scale: float) -> None:
    result = _analyze(_source((3 * scale, 4 * scale, 0)))
    assert result.channels[1].samples is not None
    assert result.channels[1].samples.values[0] / scale == pytest.approx(5)


@pytest.mark.parametrize(
    "vector,unit,code",
    [
        ((1e308, 0.0, 0.0), DeviceAccelerationUnit.STANDARD_GRAVITY, "UNIT_CONVERSION_RANGE"),
        ((1.5e308, 1.5e308, 0.0), DeviceAccelerationUnit.SI, "DEVICE_NORM_RANGE"),
    ],
)
def test_out_of_range_math_returns_structured_errors(
    vector: tuple[float, float, float],
    unit: DeviceAccelerationUnit,
    code: str,
) -> None:
    result = _analyze(_source(vector), unit)
    assert result.validity is ResultValidity.INVALID
    assert result.channels[1].samples is None
    assert result.diagnostics[0].code == code
    if code == "DEVICE_NORM_RANGE":
        assert result.channels[0].samples is not None  # independent usable converted vectors


@pytest.mark.parametrize("name", REAL_FIXTURES)
def test_all_originals_fail_closed_without_units_and_retain_bytes(
    name: str,
) -> None:
    expected_size, expected_hash = REAL_FIXTURES[name]
    path = REAL_FIXTURE_DIRECTORY / name
    before = path.stat().st_mtime_ns
    source = import_forces(path)
    assert isinstance(source, ImportSuccess)
    result = analyze_device_vectors(source, calculation_time=NOW)
    assert result == analyze_device_vectors(source, calculation_time=NOW)
    assert result.source is source and result.validity is ResultValidity.RESTRICTED
    assert all(
        c.state is CapabilityState.UNAVAILABLE and c.samples is None for c in result.channels
    )
    raw = source.recording.source.original_bytes
    assert (
        raw == path.read_bytes()
        and len(raw) == expected_size
        and sha256(raw).hexdigest() == expected_hash
    )
    assert path.stat().st_mtime_ns == before
    if name.startswith("IronGwazi"):
        assert source.recording.motion.gravity is None
        assert result.diagnostics[-1].code == "SOURCE_SEQUENCE_ABSENT"
    else:
        assert source.recording.motion.gravity is not None
        assert all(d.code == "SOURCE_UNIT_UNKNOWN" for d in result.diagnostics)
