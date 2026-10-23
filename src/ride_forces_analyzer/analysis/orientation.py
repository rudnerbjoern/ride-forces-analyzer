"""Source-app tilt: angle between current gravity and stored vertical direction.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import acos, degrees, hypot

from ride_forces_analyzer.domain import Recording, Vector3

from .projection import source_directions


def orientation_degrees(
    recording: Recording,
    *,
    vertical_direction: Vector3 | None = None,
) -> tuple[float | None, ...]:
    """Calculate tilt to an explicit vertical axis or the original source direction.

    Absent/zero gravity remains gaps; this is never yaw or track heading.
    The optional effective axis changes no source data or force processing.
    """
    gravity = recording.motion.gravity
    vertical = vertical_direction or source_directions(recording)[0]
    count = len(recording.motion.acceleration)
    if gravity is None or vertical is None:
        return (None,) * count
    length = hypot(vertical.x, vertical.y, vertical.z)
    if length == 0:
        return (None,) * count
    axis = (vertical.x / length, vertical.y / length, vertical.z / length)
    values: list[float | None] = []
    for vector in gravity:
        norm = hypot(vector.x, vector.y, vector.z)
        if norm == 0:
            values.append(None)
        else:
            cosine = sum(a * b / norm for a, b in zip(axis, (vector.x, vector.y, vector.z)))
            values.append(degrees(acos(max(-1.0, min(1.0, cosine)))))
    return tuple(values)
