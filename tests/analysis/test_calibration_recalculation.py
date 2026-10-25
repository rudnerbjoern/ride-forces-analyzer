"""Custom reference bases, stage ownership and service invalidation contracts."""

from dataclasses import replace
from datetime import timedelta
from math import sqrt
from typing import cast
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.analysis import preparation
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.recording import (
    AnalysisFailed,
    AnalysisInvalidated,
    AnalysisStage,
    AnalysisUpdated,
    AvailabilityState,
    EventEvaluationState,
    RequestStatus,
    StageConfiguration,
)
from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
)
from ride_forces_analyzer.analysis.service import AnalysisDelivery, AnalysisService
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess
from tests.analysis.test_recording_preparation import NOW, prepare_snapshot, synthetic_source

LATER = NOW + timedelta(seconds=1)


@pytest.fixture
def calibration_source() -> ImportSuccess:
    values = [(0, 1, 1)] * 5 + [(1, 0, 2)] * 3 + [(1, -1, 1)] * 5
    return synthetic_source(
        accelerationSequence=[
            dict(zip(("x", "y", "z"), map(str, row), strict=True)) for row in values
        ],
        gravitySequence=[{"x": "0", "y": "0", "z": "1"}] * len(values),
    )


def test_custom_basis_drives_forces_and_independent_tilt(calibration_source: ImportSuccess) -> None:
    source = calibration_source
    original = prepare_snapshot(source_app_configuration(), source)
    snapshot = original.with_configuration(
        replace(original.configuration, calibration=CalibrationOverrides(2, 10)),
        revision=4,
        calculation_time=LATER,
    )
    basis = snapshot.calibration
    assert basis is not None and snapshot.forces.projected.calibration is basis
    expected = (
        (0, 1 / sqrt(2), 1 / sqrt(2)),
        (2 / sqrt(6), 1 / sqrt(6), -1 / sqrt(6)),
        (-1 / sqrt(3), 1 / sqrt(3), -1 / sqrt(3)),
    )
    for axis, row in zip(basis.directions, expected, strict=True):
        assert (axis.x, axis.y, axis.z) == pytest.approx(row, abs=1e-14)
    assert basis.references.provenance.source is source.recording.source.provenance
    assert basis.references.provenance.calculation_time == LATER
    sample = snapshot.sample(2)
    assert sample.projected is not None
    assert (
        sample.projected.vertical,
        sample.projected.lateral,
        sample.projected.longitudinal,
    ) == pytest.approx(
        (sqrt(2), 0, 0),
        abs=1e-14,
    )
    assert sample.orientation_degrees == pytest.approx(45)
    assert sample.raw is source.recording.motion.acceleration[2]
    assert snapshot.source is original.source and snapshot.time is original.time
    assert source.recording.vectors.vertical_direction == Vector3(0, 0, 1)
    assert source.recording.indices.gravity is None and source.recording.indices.incline is None
    assert original.calibration is None and original.sample(2).orientation_degrees == 0
    assert snapshot.forces.smoothed.combined == original.forces.smoothed.combined
    snapshot.validate()


@pytest.mark.parametrize(
    "change",
    ("gravity", "incline", "smoothing", "bounds", "reset_gravity", "reset_incline", "reset_all"),
)
def test_service_rebuilds_only_affected_calibration_dependencies(
    calibration_source: ImportSuccess,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    configuration = replace(
        source_app_configuration(),
        calibration=CalibrationOverrides(2, 10),
        events=StageConfiguration("airtime-events", "1"),
    )
    original = prepare_snapshot(configuration, calibration_source)
    service = AnalysisService(original)
    deliveries: list[AnalysisDelivery] = []
    orientation_deliveries: list[AnalysisDelivery] = []
    service.subscribe(deliveries.append)
    service.subscribe(orientation_deliveries.append, stages=frozenset((AnalysisStage.ORIENTATION,)))
    calls: list[Mock] = []
    for name in ("prepare_calibration_basis", "project_directions", "orientation_degrees"):
        spy = Mock(wraps=getattr(preparation, name))
        monkeypatch.setattr(preparation, name, spy)
        calls.append(spy)
    overrides = {
        "gravity": CalibrationOverrides(6, 10),
        "incline": CalibrationOverrides(2, 6),
        "reset_gravity": CalibrationOverrides(None, 10),
        "reset_incline": CalibrationOverrides(2, None),
        "reset_all": CalibrationOverrides(),
    }
    if change == "smoothing":
        service.request_smoothing(5, calculation_time=LATER)
    else:
        changed = (
            replace(configuration, ride_bounds=(0, 12))
            if change == "bounds"
            else replace(configuration, calibration=overrides[change])
        )
        service.request_configuration(changed, calculation_time=LATER)
    state = service.get_state()
    assert state.status is RequestStatus.READY
    snapshot = state.snapshot
    assert snapshot is not None and snapshot is not original
    gravity_changed = change in ("gravity", "reset_gravity", "reset_all")
    basis_changed = change not in ("smoothing", "bounds")
    assert tuple(call.call_count for call in calls) == (
        int(basis_changed),
        int(basis_changed),
        int(gravity_changed),
    )
    expected = set[AnalysisStage]()
    if basis_changed:
        expected.update((AnalysisStage.CALIBRATION, AnalysisStage.PROJECTION))
    if basis_changed or change == "smoothing":
        expected.update((AnalysisStage.SMOOTHING, AnalysisStage.CONTEXT, AnalysisStage.EVENTS))
    if gravity_changed:
        expected.add(AnalysisStage.ORIENTATION)
    assert len(deliveries) == 3
    pending, updated = deliveries[1:]
    assert isinstance(pending, AnalysisInvalidated) and isinstance(updated, AnalysisUpdated)
    assert pending.dirty_stages == updated.replaced_stages == frozenset(expected)
    assert len(orientation_deliveries) == (3 if gravity_changed else 1)
    assert (snapshot.calibration is original.calibration) == (not basis_changed)
    assert (snapshot.forces.projected is original.forces.projected) == (not basis_changed)
    assert (snapshot.forces.smoothed is original.forces.smoothed) == (change == "bounds")
    assert (snapshot.orientation is original.orientation) == (not gravity_changed)
    assert (snapshot.context is original.context) == (change == "bounds")
    assert (snapshot.events is original.events) == (change == "bounds")
    assert snapshot.source is original.source and snapshot.time is original.time
    assert snapshot.events.status is EventEvaluationState.EVALUATED
    fresh = prepare_snapshot(snapshot.configuration, calibration_source)
    assert snapshot.forces.smoothed.channels == fresh.forces.smoothed.channels
    assert snapshot.orientation.values == fresh.orientation.values
    assert snapshot.context.labels == fresh.context.labels
    assert snapshot.events.events == fresh.events.events
    if snapshot.calibration is not None:
        assert fresh.calibration is not None
        assert snapshot.calibration.directions == fresh.calibration.directions
    snapshot.validate()


@pytest.mark.parametrize(
    "overrides,code",
    (
        (CalibrationOverrides(gravity_index=13), "CALIBRATION_INDEX_OUT_OF_RANGE"),
        (CalibrationOverrides(incline_index=0), "CALIBRATION_PARALLEL_REFERENCES"),
        (cast(CalibrationOverrides, None), "ANALYSIS_FAILED"),
    ),
)
def test_failed_calibration_retains_last_snapshot_and_can_reset(
    overrides: CalibrationOverrides,
    code: str,
) -> None:
    source = synthetic_source(
        gravitySequence=None,
        accelerationSequence=[{"x": "0", "y": "0", "z": "1"}] * 13,
    )
    original = prepare_snapshot(source_app_configuration(), source)
    service = AnalysisService(original)
    deliveries: list[AnalysisDelivery] = []
    service.subscribe(deliveries.append)
    revision = service.request_configuration(
        replace(original.configuration, calibration=overrides),
        calculation_time=LATER,
    )
    state = service.get_state()
    assert state.status is RequestStatus.FAILED and state.snapshot is original
    failure = deliveries[-1]
    assert isinstance(failure, AnalysisFailed)
    assert failure.revision == revision and failure.source_sha256 == source.source_sha256
    assert failure.failure is state.failure and failure.failure.code == code
    service.request_configuration(original.configuration, calculation_time=LATER)
    recovered = service.get_state()
    assert recovered.status is RequestStatus.READY and recovered.failure is None
    assert recovered.snapshot is not None and recovered.snapshot.forces is original.forces


def test_custom_calibration_keeps_missing_gravity_unavailable() -> None:
    source = synthetic_source(
        gravitySequence=None,
        accelerationSequence=[{"x": "1", "y": "1", "z": "1"}] * 7,
    )
    snapshot = prepare_snapshot(
        replace(source_app_configuration(), calibration=CalibrationOverrides(incline_index=3)),
        source,
    )
    assert snapshot.calibration is not None and snapshot.sample(0).projected is not None
    assert snapshot.orientation.availability.state is AvailabilityState.UNAVAILABLE
    assert snapshot.sample(0).orientation_degrees is None


@pytest.mark.parametrize("mismatch", ("basis", "projection", "orientation"))
def test_snapshot_rejects_mixed_calibration_dependencies(
    calibration_source: ImportSuccess,
    mismatch: str,
) -> None:
    original = prepare_snapshot(source_app_configuration(), calibration_source)
    changed = original.with_configuration(
        replace(original.configuration, calibration=CalibrationOverrides(2, 10)),
        revision=4,
        calculation_time=LATER,
    )
    if mismatch == "basis":
        changed = replace(changed, calibration=None)
    elif mismatch == "projection":
        changed = replace(changed, forces=original.forces)
    else:
        changed = replace(changed, orientation=original.orientation)
    with pytest.raises((TypeError, ValueError)):
        changed.validate()
