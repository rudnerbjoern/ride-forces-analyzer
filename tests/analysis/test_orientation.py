"""Orientation gaps remain explicit for a degenerate effective reference axis."""

from ride_forces_analyzer.analysis.orientation import orientation_degrees
from ride_forces_analyzer.domain import Vector3
from tests.analysis.test_recording_preparation import synthetic_source


def test_zero_effective_vertical_axis_leaves_orientation_unavailable() -> None:
    source = synthetic_source()
    values = orientation_degrees(source.recording, vertical_direction=Vector3(0, 0, 0))
    assert values == (None,) * len(source.recording.motion.acceleration)
