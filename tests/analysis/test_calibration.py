"""Reference admission, basis geometry and source-app comparison evidence."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from typing import cast

import pytest

from ride_forces_analyzer.analysis.calibration import (
    CalibrationOverrides,
    CalibrationReferenceError,
    MIN_POLARITY_COSINE,
    MIN_REFERENCE_SINE,
    prepare_calibration_basis,
    validate_calibration_references,
)
from ride_forces_analyzer.analysis.models import CapabilityState
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess, Severity, import_forces
from tests.analysis.test_recording_preparation import NOW, synthetic_source
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def test_reference_windows_and_provenance_retain_original_source() -> None:
    values = [(0, 0, 2)] * 6 + [(99, 99, 99)] + [(0, 2, 2)] * 6
    source = synthetic_source(
        startIndex=10,
        gravitySequence=None,
        accelerationSequence=[
            dict(zip(("x", "y", "z"), map(str, row), strict=True)) for row in values
        ],
    )
    before = source.recording.source.original_bytes
    overrides = CalibrationOverrides(gravity_index=0, incline_index=12)
    result = validate_calibration_references(source, overrides, calculation_time=NOW)
    assert result is not None
    assert result.overrides is overrides
    assert result.gravity_interval == (0, 2) and result.incline_interval == (10, 12)
    assert result.vertical_reference == Vector3(0, 0, 2)
    assert result.longitudinal_reference == Vector3(0, 2, 2)
    assert result.polarity_reference is source.recording.vectors.longitudinal_direction
    assert result.provenance.source is source.recording.source.provenance
    assert result.provenance.source.sha256 == source.source_sha256
    assert result.provenance.calculation_time == NOW
    assert result.provenance.algorithm == "user-reference-calibration"
    assert result.algorithm_version == "1" and result.window_samples == 5
    assert result.capability is CapabilityState.PROVISIONAL
    assert source.recording.source.original_bytes == before
    assert source.recording.indices.gravity is None and source.recording.indices.incline is None
    with pytest.raises(FrozenInstanceError):
        setattr(result, "window_samples", 3)


@pytest.mark.parametrize("custom_gravity", (True, False))
def test_unselected_reference_retains_its_original_source_axis(custom_gravity: bool) -> None:
    source = synthetic_source(
        gravitySequence=None,
        accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 13,
    )
    selected = (
        CalibrationOverrides(gravity_index=6)
        if custom_gravity
        else CalibrationOverrides(incline_index=6)
    )
    result = validate_calibration_references(source, selected, calculation_time=NOW)
    assert result is not None
    if custom_gravity:
        assert result.gravity_interval == (4, 8) and result.incline_interval is None
        assert result.longitudinal_reference is source.recording.vectors.longitudinal_direction
    else:
        assert result.incline_interval == (4, 8) and result.gravity_interval is None
        assert result.vertical_reference is source.recording.vectors.vertical_direction


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_original_reference_basis_recovers_stored_axes_at_export_precision(filename: str) -> None:
    """Compare the implemented basis to all 45 stored components, not physical validity."""
    source = import_forces(REAL_FIXTURE_DIRECTORY / filename)
    assert isinstance(source, ImportSuccess)
    indices = source.recording.indices
    assert indices.gravity is not None and indices.incline is not None
    basis = prepare_calibration_basis(
        source,
        CalibrationOverrides(indices.gravity, indices.incline),
        calculation_time=NOW,
    )
    assert basis is not None
    original = source.recording.vectors
    for actual, expected in zip(
        basis.directions,
        (original.vertical_direction, original.lateral_direction, original.longitudinal_direction),
        strict=True,
    ):
        assert expected is not None
        # Source axes are stored at three decimals; do not round production means.
        assert tuple(round(component, 3) for component in (actual.x, actual.y, actual.z)) == (
            expected.x,
            expected.y,
            expected.z,
        )


def test_inactive_overrides_do_not_reconstruct_the_original_basis() -> None:
    source = synthetic_source(verticalDirectionVector=None, lateralDirectionVector=None)
    assert (
        validate_calibration_references(source, CalibrationOverrides(), calculation_time=NOW)
        is None
    )
    assert prepare_calibration_basis(source, CalibrationOverrides(), calculation_time=NOW) is None


@pytest.mark.parametrize("value", (True, 1.5, "2", -1))
@pytest.mark.parametrize("field", ("gravity_index", "incline_index"))
def test_override_indices_require_nonnegative_integers(value: object, field: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        if field == "gravity_index":
            CalibrationOverrides(gravity_index=cast(int, value))
        else:
            CalibrationOverrides(incline_index=cast(int, value))


@pytest.mark.parametrize("field", ("gravity_index", "incline_index"))
def test_reference_indices_are_bounded_by_the_full_source_axis(field: str) -> None:
    with pytest.raises(CalibrationReferenceError) as failure:
        validate_calibration_references(
            synthetic_source(),
            CalibrationOverrides(gravity_index=7)
            if field == "gravity_index"
            else CalibrationOverrides(incline_index=7),
            calculation_time=NOW,
        )
    assert failure.value.diagnostic.code == "CALIBRATION_INDEX_OUT_OF_RANGE"
    assert failure.value.diagnostic.severity is Severity.ERROR


@pytest.mark.parametrize(
    "value,overrides,code",
    (
        ((0, 0, 0), CalibrationOverrides(gravity_index=0), "CALIBRATION_ZERO_REFERENCE"),
        (
            (1.5e308, 1.5e308, 1.5e308),
            CalibrationOverrides(gravity_index=0),
            "CALIBRATION_NON_FINITE_REFERENCE",
        ),
        ((0, 0, 1), CalibrationOverrides(incline_index=0), "CALIBRATION_PARALLEL_REFERENCES"),
        (
            (0, MIN_REFERENCE_SINE / 2, 1),
            CalibrationOverrides(incline_index=0),
            "CALIBRATION_PARALLEL_REFERENCES",
        ),
        ((1, 0, 1), CalibrationOverrides(incline_index=0), "CALIBRATION_POLARITY_AMBIGUOUS"),
        (
            (1, MIN_POLARITY_COSINE / 2, 1),
            CalibrationOverrides(incline_index=0),
            "CALIBRATION_POLARITY_AMBIGUOUS",
        ),
    ),
)
def test_non_finite_and_degenerate_references_report_diagnostics(
    value: tuple[float, float, float],
    overrides: CalibrationOverrides,
    code: str,
) -> None:
    source = synthetic_source(
        gravitySequence=None,
        accelerationSequence=[dict(zip(("x", "y", "z"), map(str, value), strict=True))] * 11,
    )
    with pytest.raises(CalibrationReferenceError) as failure:
        validate_calibration_references(source, overrides, calculation_time=NOW)
    assert failure.value.diagnostic.code == code


def test_negative_incline_preserves_the_sign_reference_for_later_basis_construction() -> None:
    source = synthetic_source(
        gravitySequence=None,
        accelerationSequence=[{"x": "0", "y": "-1", "z": "1"}] * 11,
    )
    result = validate_calibration_references(
        source,
        CalibrationOverrides(incline_index=0),
        calculation_time=NOW,
    )
    assert result is not None and result.longitudinal_reference.y < 0
    assert result.polarity_reference.y > 0
    basis = prepare_calibration_basis(source, result.overrides, calculation_time=NOW)
    assert basis is not None
    assert basis.directions == (Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))


def test_missing_source_axes_and_naive_time_are_rejected() -> None:
    with pytest.raises(CalibrationReferenceError) as failure:
        validate_calibration_references(
            synthetic_source(verticalDirectionVector=None),
            CalibrationOverrides(gravity_index=0),
            calculation_time=NOW,
        )
    assert failure.value.diagnostic.code == "CALIBRATION_SOURCE_AXES_UNAVAILABLE"
    with pytest.raises(ValueError, match="UTC"):
        validate_calibration_references(
            synthetic_source(),
            CalibrationOverrides(gravity_index=0),
            calculation_time=datetime(2026, 10, 23),
        )
