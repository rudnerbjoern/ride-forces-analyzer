"""Pure selected-range force extrema; raw use requires no optional analysis runtime.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import TYPE_CHECKING
from collections.abc import Sequence

from ride_forces_analyzer.domain import ValueOrigin
from ride_forces_analyzer.importers import ImportSuccess

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

    from ride_forces_analyzer.analysis.models import AnalysisProvenance
    from ride_forces_analyzer.analysis.recording import AnalysisQuality, SmoothedForces


@dataclass(frozen=True, slots=True)
class Extremum:
    """Extremum contract and owned data.

    Attributes:
        value: Candidate value to validate, format or store.
        index: Source or collection index selected for this operation.
        recording_seconds: Time since the recording origin, in seconds.
    """

    value: float
    index: int
    recording_seconds: float


@dataclass(frozen=True, slots=True)
class ChannelExtrema:
    """Channel extrema contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        minimum: Minimum retained value or extremum in the declared interval and units.
        maximum: Maximum retained value or configured resource limit.
    """

    name: str
    minimum: Extremum
    maximum: Extremum


@dataclass(frozen=True, slots=True)
class SelectionExtrema:
    """Selection extrema contract and owned data.

    Attributes:
        source_sha256: SHA-256 identity of the original recording bytes.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        sample_rate: Effective source samples per second, retaining its origin separately.
        rate_origin: Evidence identifying the sample-rate source.
        mode: Selected operation mode.
        unit: Declared unit and its evidence; unknown source units remain unknown.
        smoothing_window: Odd number of source samples used for smoothing.
        source_algorithm: Algorithm associated with the original retained values.
        capability: Scientific capability status limited to the declared evidence scope.
        channels: Prepared channels to inspect or display.
        calculation_time: Aware timestamp recorded in calculation provenance.
        algorithm: Identifier of the algorithm used by the stage.
        time_basis: Time representation and evidence associated with this data product.
        quality: Quality and availability information accompanying the prepared values.
        provenance: Source identity, processing configuration and calculation evidence.
    """

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

    quality: "AnalysisQuality | None" = None
    provenance: "AnalysisProvenance | None" = None

    @property
    def count(self) -> int:
        """Return the number of retained samples or items represented by this object.

        Returns:
            The number of retained samples or items represented by this object.
        """
        return self.last - self.first + 1


def calculate_extrema(
    source: ImportSuccess,
    first: int,
    last: int,
    *,
    forces: "SmoothedForces | None" = None,
    calculation_time: datetime | None = None,
) -> SelectionExtrema:
    """Read full source/stage buffers with inclusive bounds and earliest tied indices.

    Args:
        source: Original lossless import, also retained by the optional force stage.
        first: First included source sample index.
        last: Last included source sample index.
        forces: Prepared smoothed stage for calibrated mode; None selects raw axes.
        calculation_time: Aware result time, defaulting to the current UTC time.

    Returns:
        Immutable extrema with source/time identity and the force stage's quality
        and calculation provenance. No numerical preparation is performed.

    Raises:
        ValueError: Invalid interval/time, mismatched or unavailable stage,
            incomplete channels or missing/non-finite selected samples.
        AssertionError: If a required internal invariant does not hold.
    """
    calculated = calculation_time if calculation_time is not None else datetime.now(UTC)
    if calculated.utcoffset() is None:
        raise ValueError("Extrema calculation time must be timezone-aware")
    recording = source.recording
    count = len(recording.motion.acceleration)
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < count:
        raise ValueError("Extrema require bounded, ordered sample indices")
    rate = recording.motion.sample_rate
    channels: "tuple[Sequence[float] | NDArray[np.float64], ...]"
    if forces is not None:
        projection = forces.projection
        if projection.source is not source or projection.time.basis.sample_rate != rate:
            raise ValueError("Force stage must match the source and sample rate")
        if projection.time.source_indices != tuple(range(count)):
            raise ValueError("Force stage must preserve source sample correspondence")
        if forces.availability.state.value != "available" or forces.channels is None:
            raise ValueError("Calibrated force stage is unavailable")
        if forces.provenance is None:
            raise ValueError("Calibrated force stage requires provenance")
        if any(len(axis.valid_rows) != count for axis in forces.channels):
            raise ValueError("Extrema require source-length validity masks")
        if any(not all(axis.valid_rows[first : last + 1]) for axis in forces.channels):
            raise ValueError("Extrema require valid selected samples")
        channels = (forces.channels[0].values, forces.channels[1].values, forces.channels[2].values)
        names = ("Vertical", "Lateral", "Longitudinal")
    else:
        samples = recording.motion.acceleration
        channels = (
            tuple(v.x for v in samples),
            tuple(v.y for v in samples),
            tuple(v.z for v in samples),
        )
        names = ("x", "y", "z")
    if any(len(values) != count for values in channels):
        raise ValueError("Extrema require three complete source-length channels")
    results: list[ChannelExtrema] = []
    for axis, name in enumerate(names):
        values = channels[axis]
        if not all(isfinite(value) for value in values[first : last + 1]):
            raise ValueError("Extrema require finite selected samples")
        minimum = min(range(first, last + 1), key=values.__getitem__)
        maximum = max(range(first, last + 1), key=values.__getitem__)
        results.append(
            ChannelExtrema(
                name,
                Extremum(float(values[minimum]), minimum, minimum / rate.value),
                Extremum(float(values[maximum]), maximum, maximum / rate.value),
            ),
        )
    window = dict(forces.configuration.parameters).get("window_samples", 11) if forces else 1
    assert type(window) is int
    return SelectionExtrema(
        source.source_sha256,
        first,
        last,
        rate.value,
        rate.origin,
        "calibrated" if forces is not None else "raw",
        "g" if forces is not None else "unknown",
        window,
        f"{forces.projection.configuration.algorithm}-{forces.configuration.algorithm}-{window}-v{forces.configuration.version}"
        if forces is not None
        else "source-acceleration-v1",
        next(
            (
                state.value.upper()
                for name, state in forces.quality.capabilities
                if name == "smoothing"
            ),
            "UNAVAILABLE",
        )
        if forces is not None
        else "VERIFIED",
        tuple(results),
        calculated,
        quality=forces.quality if forces is not None else None,
        provenance=forces.provenance if forces is not None else None,
    )
