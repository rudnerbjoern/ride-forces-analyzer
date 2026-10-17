"""Pure selected-range force extrema; raw use requires no optional analysis runtime."""

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import TYPE_CHECKING

from ride_forces_analyzer.domain import ValueOrigin
from ride_forces_analyzer.importers import ImportSuccess

if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.reference import AppReference


@dataclass(frozen=True, slots=True)
class Extremum:
    value: float
    index: int
    recording_seconds: float


@dataclass(frozen=True, slots=True)
class ChannelExtrema:
    name: str
    minimum: Extremum
    maximum: Extremum


@dataclass(frozen=True, slots=True)
class SelectionExtrema:
    source_sha256: str
    first: int
    last: int
    sample_rate: float
    rate_origin: ValueOrigin
    mode: str
    unit: str
    smoothing_window: int
    source_algorithm: str
    capability: str
    channels: tuple[ChannelExtrema, ...]
    calculation_time: datetime
    algorithm: str = "inclusive-three-channel-extrema-v1"
    time_basis: str = "INFERRED_UNIFORM"

    @property
    def count(self) -> int:
        return self.last - self.first + 1


def calculate_extrema(
    source: ImportSuccess,
    first: int,
    last: int,
    *,
    reference: "AppReference | None" = None,
    calculation_time: datetime | None = None,
) -> SelectionExtrema:
    """Use existing full channels, inclusive endpoints and earliest tied indices."""
    calculated = calculation_time if calculation_time is not None else datetime.now(UTC)
    if calculated.utcoffset() is None:
        raise ValueError("Extrema calculation time must be timezone-aware")
    recording = source.recording
    count = len(recording.motion.acceleration)
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < count:
        raise ValueError("Extrema require bounded, ordered sample indices")
    rate = recording.motion.sample_rate
    if reference is not None:
        if reference.source_sha256 != source.source_sha256 or reference.sample_rate != rate.value:
            raise ValueError("Reference must match the source and sample rate")
        channels = reference.channels
        names = ("Vertical", "Lateral", "Longitudinal")
    else:
        samples = recording.motion.acceleration
        channels = (
            tuple(v.x for v in samples),
            tuple(v.y for v in samples),
            tuple(v.z for v in samples),
        )
        names = ("x", "y", "z")
    if len(channels) != 3 or any(len(values) != count for values in channels):
        raise ValueError("Extrema require three complete source-length channels")
    results: list[ChannelExtrema] = []
    for name, values in zip(names, channels, strict=True):
        if not all(isfinite(value) for value in values[first : last + 1]):
            raise ValueError("Extrema require finite selected samples")
        minimum = min(range(first, last + 1), key=values.__getitem__)
        maximum = max(range(first, last + 1), key=values.__getitem__)
        results.append(
            ChannelExtrema(
                name,
                Extremum(values[minimum], minimum, minimum / rate.value),
                Extremum(values[maximum], maximum, maximum / rate.value),
            ),
        )
    return SelectionExtrema(
        source.source_sha256,
        first,
        last,
        rate.value,
        rate.origin,
        "calibrated" if reference is not None else "raw",
        reference.unit if reference is not None else "unknown",
        reference.smoothing_window if reference is not None else 1,
        reference.algorithm if reference is not None else "source-acceleration-v1",
        reference.capability if reference is not None else "VERIFIED",
        tuple(results),
        calculated,
    )
