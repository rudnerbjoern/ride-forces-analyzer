"""Analytic passive transforms and fail-closed real-recording frame gates."""

# cspell:words linalg

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
import subprocess
import sys

import numpy as np
import pytest

from ride_forces_analyzer.analysis import (
    AnalysisProfile,
    CapabilityState,
    FrameLabel,
    ProfileName,
    QuantityKind,
    ResultValidity,
    SampleValues,
    SourceSequence,
)
from ride_forces_analyzer.analysis.device import DeviceAccelerationUnit, MotionUnitContract
from ride_forces_analyzer.analysis.frames import (
    FRAME_ATOL,
    OrthonormalFrame,
    RiderCalibration,
    analyze_rider_frame,
    rotate_vectors,
)
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES

NOW = datetime(2026, 10, 17, tzinfo=UTC)
IDENTITY = OrthonormalFrame((Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)))
TURN = OrthonormalFrame((Vector3(0, 1, 0), Vector3(-1, 0, 0), Vector3(0, 0, 1)))
EXPLORATORY = AnalysisProfile(
    ProfileName.RIDER_CALIBRATED,
    policy_references=("synthetic: explicit passive convention",),
    assumptions=("synthetic rider basis only, no real-source qualification",),
    allow_provisional=True,
)


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


@pytest.mark.parametrize(
    "frame,expected",
    [
        (IDENTITY, [[1, 2, 3], [-4, -5, -6]]),
        (TURN, [[2, -1, 3], [-5, 4, -6]]),
        (
            OrthonormalFrame((Vector3(-1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1))),
            [[-1, 2, -3], [4, -5, 6]],
        ),
    ],
)
def test_passive_signed_projection_and_inverse(
    frame: OrthonormalFrame,
    expected: list[list[int]],
) -> None:
    values = SampleValues(np.array([[1, 2, 3], [-4, -5, -6]], dtype=np.float64))
    projected = rotate_vectors(values, frame)
    np.testing.assert_allclose(projected.values, expected, rtol=0, atol=1e-14)
    np.testing.assert_allclose(
        rotate_vectors(projected, frame, inverse=True).values,
        values.values,
        rtol=0,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        np.linalg.norm(projected.values, axis=1),
        np.linalg.norm(values.values, axis=1),
        rtol=1e-14,
    )


def test_non_axis_aligned_passive_transform_detects_transpose_and_preserves_norm() -> None:
    c = float(np.sqrt(0.5))
    frame = OrthonormalFrame((Vector3(c, c, 0), Vector3(-c, c, 0), Vector3(0, 0, 1)))
    samples = SampleValues(np.array([[2, 0, 3]], dtype=np.float64))
    actual = rotate_vectors(samples, frame)
    np.testing.assert_allclose(actual.values, [[2 * c, -2 * c, 3]], rtol=1e-14, atol=1e-14)
    np.testing.assert_allclose(
        rotate_vectors(actual, frame, inverse=True).values,
        samples.values,
        rtol=1e-14,
        atol=1e-14,
    )


@pytest.mark.parametrize(
    "rows",
    [
        (Vector3(0, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)),
        (Vector3(2, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)),
        (Vector3(1, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1)),
        (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1)),
        (Vector3(1, 0, 0), Vector3(0.01, 1, 0), Vector3(0, 0, 1)),
        (Vector3(1 + 10 * FRAME_ATOL, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)),
    ],
    ids=["zero", "scaled", "parallel", "reflection", "skew", "tolerance"],
)
def test_invalid_bases_are_rejected_instead_of_scipy_repair(
    rows: tuple[Vector3, Vector3, Vector3],
) -> None:
    with pytest.raises(ValueError):
        OrthonormalFrame(rows)


def test_missing_rows_zero_and_owned_data() -> None:
    array = np.array([[0, 0, 0], [np.nan, np.nan, np.nan], [3, 4, 5]])
    samples = SampleValues(array, valid_rows=(True, False, True))
    output = rotate_vectors(samples, TURN)
    array[0] = 9
    frame_view = TURN.matrix
    frame_view[:] = 0
    np.testing.assert_allclose(output.values, [[0, 0, 0], [np.nan] * 3, [4, -3, 5]], atol=1e-14)
    assert output.valid_rows == (True, False, True)
    assert not output.values.flags.writeable
    np.testing.assert_array_equal(TURN.matrix, [[0, 1, 0], [-1, 0, 0], [0, 0, 1]])
    with pytest.raises(FrozenInstanceError):
        setattr(TURN, "rows", IDENTITY.rows)
    missing = SampleValues(np.full((1, 3), np.nan), valid_rows=(False,))
    assert rotate_vectors(missing, TURN).valid_rows == (False,)


def test_projection_requires_three_components_and_does_not_invent_yaw() -> None:
    with pytest.raises(ValueError):
        rotate_vectors(SampleValues(np.array([1.0])), TURN)
    # A gravity-only pair cannot supply the three explicit axes required here.
    with pytest.raises(ValueError):
        OrthonormalFrame((Vector3(0, 0, 1), Vector3(0, 0, 1), Vector3(0, 0, 1)))


def test_exploratory_frame_preserves_units_source_profile_and_independent_channels() -> None:
    source = _source((3, 4, 0), (0, 0, -9.80665))
    calibration = RiderCalibration(source.source_sha256, TURN, ("synthetic basis",))
    result = analyze_rider_frame(
        source,
        calculation_time=NOW,
        calibration=calibration,
        profile=EXPLORATORY,
        acceleration_contract=_contract(source),
    )
    channel, gravity = result.channels
    assert channel.state is CapabilityState.PROVISIONAL
    assert channel.frame is FrameLabel.RIDER and channel.quantity is QuantityKind.SPECIFIC_FORCE
    assert channel.samples is not None
    np.testing.assert_allclose(channel.samples.values, [[4, -3, 0]], atol=1e-14)
    assert channel.columns == ("longitudinal", "lateral", "vertical")
    assert channel.frame_evidence == calibration.references
    assert channel.source_indices == (0,)
    assert gravity.state is CapabilityState.UNAVAILABLE and gravity.samples is None
    assert result.validity is ResultValidity.RESTRICTED
    assert result.source is source and result.profile.assumptions == EXPLORATORY.assumptions
    assert result.profile.configuration["rider_basis.row_0"] == "(0.0, 1.0, 0.0)"
    assert result.profile.configuration["acceleration.source_unit"] == _contract(source).unit.value
    assert result == analyze_rider_frame(
        source,
        calculation_time=NOW,
        calibration=calibration,
        profile=EXPLORATORY,
        acceleration_contract=_contract(source),
    )


def test_no_frame_no_units_wrong_source_and_missing_opt_in_fail_closed() -> None:
    source = _source()
    calibration = RiderCalibration(source.source_sha256, IDENTITY, ("synthetic basis",))
    no_frame = analyze_rider_frame(
        source,
        calculation_time=NOW,
        acceleration_contract=_contract(source),
    )
    assert all(c.state is CapabilityState.UNAVAILABLE for c in no_frame.channels)
    assert any(d.code == "RIDER_FRAME_UNQUALIFIED" for d in no_frame.diagnostics)
    no_units = analyze_rider_frame(
        source,
        calculation_time=NOW,
        calibration=calibration,
        profile=EXPLORATORY,
    )
    assert all(c.samples is None for c in no_units.channels)
    with pytest.raises(ValueError, match="provisional"):
        analyze_rider_frame(source, calculation_time=NOW, calibration=calibration)
    with pytest.raises(ValueError, match="source"):
        analyze_rider_frame(
            source,
            calculation_time=NOW,
            calibration=replace(calibration, source_sha256="0" * 64),
            profile=EXPLORATORY,
        )
    with pytest.raises(ValueError, match="profile"):
        analyze_rider_frame(source, calculation_time=NOW, profile=AnalysisProfile())
    with pytest.raises(ValueError):
        RiderCalibration(source.source_sha256, IDENTITY, ())
    with pytest.raises(ValueError):
        analyze_rider_frame(source, calculation_time=datetime(2026, 10, 17))


def test_rotation_overflow_is_invalid_and_never_zero_filled() -> None:
    c = float(np.sqrt(0.5))
    basis = OrthonormalFrame((Vector3(c, c, 0), Vector3(-c, c, 0), Vector3(0, 0, 1)))
    samples = SampleValues(np.array([[1.7e308, 1.7e308, 0]]))
    with pytest.raises(ValueError, match="float64"):
        rotate_vectors(samples, basis)
    source = _source((1.7e308, 1.7e308, 0))
    result = analyze_rider_frame(
        source,
        calculation_time=NOW,
        calibration=RiderCalibration(source.source_sha256, basis, ("synthetic",)),
        profile=EXPLORATORY,
        acceleration_contract=_contract(source),
    )
    assert result.channels[0].state is CapabilityState.INVALID
    assert result.channels[0].samples is None
    assert any(d.code == "FRAME_TRANSFORM_RANGE" for d in result.diagnostics)


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_originals_never_receive_implicit_rider_frames(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    original = path.read_bytes()
    modified = path.stat().st_mtime_ns
    source = import_forces(path)
    assert isinstance(source, ImportSuccess)
    result = analyze_rider_frame(source, calculation_time=NOW)
    assert all(
        c.state is CapabilityState.UNAVAILABLE and c.samples is None for c in result.channels
    )
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified
    expected_size, expected_hash = REAL_FIXTURES[filename]
    assert len(original) == expected_size and sha256(original).hexdigest() == expected_hash


def test_installed_rotation_uses_no_network_files_or_qt() -> None:
    script = """
import builtins, os, socket, sys
from tests.analysis.test_frames import _source, _contract, NOW, TURN, EXPLORATORY
from ride_forces_analyzer.analysis.frames import RiderCalibration, analyze_rider_frame
source = _source()
calibration = RiderCalibration(source.source_sha256, TURN, ('synthetic',))
def deny(*args, **kwargs):
    raise AssertionError('Unexpected file or network access')
builtins.open = os.open = socket.socket = deny
result = analyze_rider_frame(source, calculation_time=NOW, calibration=calibration,
    profile=EXPLORATORY, acceleration_contract=_contract(source))
assert result.channels[0].samples is not None
assert not any(name.startswith('PySide6') for name in sys.modules)
print('Offline passive frame processing passed')
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert b"Offline passive frame processing passed" in result.stdout
