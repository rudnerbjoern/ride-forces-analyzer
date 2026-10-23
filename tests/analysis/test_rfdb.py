"""RFDB axis interpretation uses the supported normalized source-app policy."""

# cspell:words linalg

from dataclasses import replace
from datetime import UTC, datetime
import json

import numpy as np
import pytest

from ride_forces_analyzer.analysis.models import AnalysisProfile, ProfileName
from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AvailabilityState,
    StageConfiguration,
    prepare_recording_analysis,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces, import_forces_bytes
from tests.importers.test_rfdb import document
from tests.support.recordings import (
    REAL_FIXTURE_DIRECTORY,
    REAL_FIXTURES,
    RFDB_FIXTURE_DIRECTORY,
    RFDB_FIXTURES,
)


def configuration() -> AnalysisConfiguration:
    return AnalysisConfiguration(
        AnalysisProfile(
            ProfileName.RIDER_CALIBRATED,
            policy_references=("Source-app normalized projection",),
            assumptions=("Provisional source-app policy",),
            allow_provisional=True,
        ),
        StageConfiguration("source-direction-unit-projection", "1"),
        StageConfiguration("centered-mean", "1", (("window_samples", 1),)),
        StageConfiguration("source-gravity-tilt", "1"),
        StageConfiguration("vertical-context", "1"),
    )


@pytest.mark.parametrize("filename", REAL_FIXTURES)
def test_app_sources_independently_confirm_calibration_axis_mapping(filename: str) -> None:
    result = import_forces(REAL_FIXTURE_DIRECTORY / filename)
    assert isinstance(result, ImportSuccess)
    vectors = result.recording.vectors
    assert vectors.vertical_direction == vectors.y_calibration
    assert vectors.lateral_direction == vectors.x_calibration
    assert vectors.longitudinal_direction == vectors.z_calibration


@pytest.mark.parametrize("with_gravity", [False, True])
def test_rfdb_mapping_matches_equivalent_app_directions_and_keeps_source_missingness(
    with_gravity: bool,
) -> None:
    root = json.loads(document())
    if with_gravity:
        root["gravitySequence"] = [{"x": 0, "y": 0, "z": 1}] * 3
    rfdb = import_forces_bytes(json.dumps(root).encode())
    assert isinstance(rfdb, ImportSuccess)
    root.update(
        schemaVersion="2.2.0",
        verticalDirectionVector=root["yCalibrationVector"],
        lateralDirectionVector=root["xCalibrationVector"],
        longitudinalDirectionVector=root["zCalibrationVector"],
    )
    app = import_forces_bytes(json.dumps(root).encode())
    assert isinstance(app, ImportSuccess)
    now = datetime.now(UTC)
    snapshot = prepare_recording_analysis(rfdb, configuration(), revision=0, calculation_time=now)
    equivalent = prepare_recording_analysis(app, configuration(), revision=0, calculation_time=now)
    expected = [(1, 0, 0), (-0.5, 0.4, 0.6), (2, -0.3, -0.2)]
    for index, (vertical, lateral, longitudinal) in enumerate(expected):
        sample = snapshot.sample(index)
        assert sample.projected is not None
        assert (
            sample.projected.vertical,
            sample.projected.lateral,
            sample.projected.longitudinal,
        ) == (vertical, lateral, longitudinal)
        assert sample.smoothed == equivalent.sample(index).smoothed
        assert sample.context == equivalent.sample(index).context
        assert sample.orientation_degrees == equivalent.sample(index).orientation_degrees
        assert (sample.orientation_degrees is not None) is with_gravity
    assert rfdb.recording.vectors.vertical_direction is None
    assert orientation_degrees(rfdb.recording) == orientation_degrees(app.recording)
    changed = snapshot.with_smoothing(3, revision=1, calculation_time=now)
    assert changed.forces.projected is snapshot.forces.projected
    assert changed.orientation is snapshot.orientation


def test_real_rfdb_normalizes_rounded_axes_without_fabricating_gravity() -> None:
    result = import_forces(RFDB_FIXTURE_DIRECTORY / next(iter(RFDB_FIXTURES)))
    assert isinstance(result, ImportSuccess)
    snapshot = prepare_recording_analysis(
        result,
        configuration(),
        revision=0,
        calculation_time=datetime.now(UTC),
    )
    vector = result.recording.vectors.y_calibration
    assert vector is not None
    direction = np.array([vector.x, vector.y, vector.z])
    direction /= np.linalg.norm(direction)
    expected = np.array([(v.x, v.y, v.z) for v in result.recording.motion.acceleration]) @ direction
    assert snapshot.forces.projected.channels is not None
    np.testing.assert_allclose(
        snapshot.forces.projected.channels[0].values,
        expected,
        rtol=1e-14,
        atol=1e-14,
    )
    assert snapshot.orientation.availability.state is AvailabilityState.UNAVAILABLE
    assert snapshot.sample(4109).context is not None
    raw = prepare_recording_analysis(
        result,
        replace(configuration(), profile=AnalysisProfile(ProfileName.RAW_DEVICE_ONLY)),
        revision=1,
        calculation_time=datetime.now(UTC),
    )
    assert raw.sample(0).projected is None
    assert raw.sample(0).raw == result.recording.motion.acceleration[0]
