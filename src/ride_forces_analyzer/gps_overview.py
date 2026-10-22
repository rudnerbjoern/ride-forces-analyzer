"""Independent approximate GPS geometry for spatial reference, never force analysis.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from math import cos, radians, sin, sqrt

from ride_forces_analyzer.domain import Recording


@dataclass(frozen=True, slots=True)
class GpsOverview:
    """North-up local WGS84 approximation, with unavailable slots/gaps disconnected."""

    segments: tuple[tuple[tuple[float, float], ...], ...]
    count: int
    total: int
    geographic_segments: tuple[tuple[tuple[float, float], ...], ...] = ()

    @property
    def points(self) -> tuple[tuple[float, float], ...]:
        return tuple(point for segment in self.segments for point in segment)


def prepare_gps_overview(recording: Recording) -> GpsOverview | None:
    """Preserve source order; omit unusable positions without bridging missing fixes."""
    gps = recording.gps
    if gps is None:
        return None
    valid = [
        entry.fix
        for entry in gps.entries
        if entry.fix is not None
        and abs(entry.fix.latitude) <= 90
        and abs(entry.fix.longitude) <= 180
    ]
    if not valid:
        return None
    origin = valid[0]
    phi = radians(origin.latitude)
    eccentricity = 6.6943799901413165e-3
    denominator = 1 - eccentricity * sin(phi) ** 2
    east_radius = 6378137 / sqrt(denominator) * cos(phi)
    north_radius = 6378137 * (1 - eccentricity) / denominator**1.5
    segments: list[tuple[tuple[float, float], ...]] = []
    current: list[tuple[float, float]] = []
    previous_time: float | None = None
    geographic: list[tuple[tuple[float, float], ...]] = []
    coordinates: list[tuple[float, float]] = []
    for entry in gps.entries:
        fix = entry.fix
        if fix is None or abs(fix.latitude) > 90 or abs(fix.longitude) > 180:
            if current:
                segments.append(tuple(current))
                geographic.append(tuple(coordinates))
                current = []
                coordinates = []
            previous_time = None
            continue
        if current and (
            fix.timestamp is None
            or previous_time is None
            or not 0 < fix.timestamp - previous_time <= 2
            or abs(fix.longitude - origin.longitude) > 180
        ):
            segments.append(tuple(current))
            geographic.append(tuple(coordinates))
            current = []
            coordinates = []
        current.append(
            (
                radians(fix.longitude - origin.longitude) * east_radius,
                -radians(fix.latitude - origin.latitude) * north_radius,
            ),
        )
        previous_time = fix.timestamp
        coordinates.append((fix.latitude, fix.longitude))
    if current:
        segments.append(tuple(current))
        geographic.append(tuple(coordinates))
    return GpsOverview(tuple(segments), len(valid), len(gps.entries), tuple(geographic))
