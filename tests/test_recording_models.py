"""FR-002/006/027: canonical typed data without decoding or force mathematics."""

from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from ride_forces_analyzer.domain import (
    Attribute,
    GpsEntry,
    GpsFix,
    GpsSequence,
    GpsStatus,
    MotionSequence,
    Recording,
    RecordingIndices,
    RecordingMetadata,
    RecordingVectors,
    RidingPosition,
    SampleRate,
    SourceNumber,
    ValueOrigin,
    Vector3,
)


def test_motion_copies_inputs_and_keeps_order() -> None:
    acceleration = [Vector3(1, 2, 3), Vector3(4, 5, 6)]
    gravity = [Vector3(0, 0, 1), Vector3(0, 1, 0)]
    motion = MotionSequence(acceleration, gravity)
    acceleration.reverse()
    gravity.clear()
    assert motion.acceleration == (Vector3(1, 2, 3), Vector3(4, 5, 6))
    assert motion.gravity == (Vector3(0, 0, 1), Vector3(0, 1, 0))
    assert motion.paired_motion_available
    with pytest.raises(FrozenInstanceError):
        setattr(motion.acceleration[0], "x", 9)


def test_unavailable_gravity_is_not_a_zero_vector(synthetic_recording: Recording) -> None:
    assert synthetic_recording.motion.gravity is None
    assert not synthetic_recording.motion.paired_motion_available
    assert synthetic_recording.motion.acceleration[0].x == 0.0
    assert synthetic_recording.metadata.advanced_recording is False


def test_defaults_keep_origin_and_source_absence(synthetic_recording: Recording) -> None:
    source = synthetic_recording.source.root
    assert source is not None and "sampleRate" not in source and "ridingPosition" not in source
    assert synthetic_recording.motion.sample_rate == SampleRate(50, ValueOrigin.DEFAULT)
    assert synthetic_recording.metadata.riding_position == RidingPosition(
        "Seated",
        ValueOrigin.DEFAULT,
    )
    assert SampleRate(50, ValueOrigin.SOURCE) != SampleRate()
    assert RidingPosition("Seated", ValueOrigin.SOURCE) != RidingPosition()
    assert SampleRate(100, ValueOrigin.SOURCE).value == 100.0
    assert RidingPosition("Flying", ValueOrigin.SOURCE).value == "Flying"
    assert RecordingMetadata(riding_position=None).riding_position is None


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), True])
def test_invalid_sample_rate_cannot_become_an_absence_default(value: float) -> None:
    with pytest.raises((ValueError, TypeError)):
        SampleRate(value, ValueOrigin.SOURCE)


def test_default_values_cannot_be_mislabeled() -> None:
    with pytest.raises(ValueError):
        SampleRate(100, ValueOrigin.DEFAULT)
    with pytest.raises(ValueError):
        RidingPosition("Flying", ValueOrigin.DEFAULT)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "1"])
def test_vector_does_not_accept_non_finite_or_untyped_components(value: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        Vector3(cast(float, value), 0, 0)


def test_present_empty_or_unpaired_motion_is_rejected() -> None:
    with pytest.raises(ValueError):
        MotionSequence([])
    with pytest.raises(ValueError):
        MotionSequence([Vector3(0, 0, 0)], [])
    with pytest.raises(ValueError):
        MotionSequence([Vector3(0, 0, 0)], [Vector3(0, 0, 0)] * 2)


def test_metadata_absent_false_and_zero_stay_distinct() -> None:
    absent = RecordingMetadata()
    zero = RecordingMetadata(
        advanced_recording=False,
        temperature=0,
        wind_speed=0,
        latitude=0,
        longitude=0,
    )
    assert absent.temperature is None and zero.temperature == 0.0
    assert absent.advanced_recording is None and zero.advanced_recording is False
    assert absent.latitude is None and zero.latitude == 0.0
    assert absent.wind_speed is None and zero.wind_speed == 0.0
    date = SourceNumber("0.000")
    assert RecordingMetadata(date=date).date == date


def test_attributes_copy_nested_values_and_recording_order(synthetic_recording: Recording) -> None:
    value = {"extension": [SourceNumber("0"), "0", False, None]}
    attribute = Attribute("id", "Any future label", value)
    attributes = [attribute, Attribute("second", "Seat", "1")]
    recording = replace(synthetic_recording, attributes=attributes)
    value.clear()
    attributes.reverse()
    assert recording.attributes[0].label == "Any future label"
    assert recording.attributes[1].label == "Seat"
    assert recording.attributes[0].value != {}
    with pytest.raises(FrozenInstanceError):
        setattr(recording, "attributes", ())


def test_markers_and_original_extrema_are_not_reinterpreted(synthetic_recording: Recording) -> None:
    indices = RecordingIndices(1, 1, gravity=0, incline=1)
    vectors = RecordingVectors(x_calibration=Vector3(2, 0, 0))
    recording = replace(
        synthetic_recording,
        indices=indices,
        vectors=vectors,
        max_force=SourceNumber("1.000"),
        min_force=SourceNumber("-0"),
        smoothing_factor=SourceNumber("0"),
    )
    assert recording.indices.gravity == 0 < recording.indices.start
    assert recording.vectors.x_calibration == Vector3(2, 0, 0)
    assert recording.max_force == SourceNumber("1.000")
    assert recording.min_force == SourceNumber("-0")
    assert recording.smoothing_factor == SourceNumber("0")
    with pytest.raises(ValueError):
        replace(recording, indices=RecordingIndices(0, 2))


def test_gps_keeps_zero_negative_and_unavailable_original_slots(
    synthetic_recording: Recording,
) -> None:
    fix = GpsFix(0, 0, timestamp=0, speed=-1, course=-1, speed_accuracy=-1, course_accuracy=-1)
    entries = [GpsEntry(0, fix), GpsEntry(1, None), GpsEntry(2, None)]
    sequence = GpsSequence(entries)
    entries.clear()
    recording = replace(synthetic_recording, gps=sequence, gps_status=GpsStatus.PRESENT)
    assert recording.gps is not None and len(recording.gps.entries) == 3
    assert len(recording.motion.acceleration) == 2
    assert recording.gps.entries[0].fix == fix
    assert recording.gps.entries[1].fix is None
    assert fix.latitude == 0.0 and fix.speed == -1.0 and fix.timestamp == 0.0
    assert fix.altitude is None
    assert repr(fix) == "GpsFix()"
    with pytest.raises(FrozenInstanceError):
        setattr(fix, "latitude", 1)


def test_gps_missing_empty_and_invalid_are_explicit(synthetic_recording: Recording) -> None:
    assert synthetic_recording.gps_status is GpsStatus.ABSENT
    empty = replace(synthetic_recording, gps=GpsSequence([]), gps_status=GpsStatus.PRESENT)
    assert empty.gps is not None and empty.gps.entries == ()
    invalid = replace(synthetic_recording, gps_status=GpsStatus.INVALID)
    assert invalid.gps is None and invalid.gps_status is GpsStatus.INVALID
    with pytest.raises(ValueError):
        replace(synthetic_recording, gps_status=GpsStatus.PRESENT)
    with pytest.raises(ValueError):
        GpsSequence([GpsEntry(1, None)])


def test_gps_finite_heuristics_are_not_scientific_rejection() -> None:
    assert GpsFix(100, 200, timestamp=-1, horizontal_accuracy=-1).latitude == 100.0
    with pytest.raises(TypeError):
        GpsFix(True, 0)
    with pytest.raises(ValueError):
        GpsFix(0, 0, timestamp=float("nan"))
