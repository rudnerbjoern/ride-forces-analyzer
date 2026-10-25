"""Immutable recording snapshot and access to existing prepared sample values.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from datetime import datetime

from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess

from ..calibration import (
    CalibrationBasis,
)

from .configuration import (
    AnalysisConfiguration,
)
from .stages import (
    AnalysisQuality,
    AnalysisTime,
    EventAnalysis,
    ForceChannels,
    ForceSeries,
    OrientationSeries,
    SampleContext,
    StageAvailability,
    VerticalContext,
)
from .validation import validate_snapshot


@dataclass(frozen=True, slots=True)
class ForceSample:
    """Name the three force values of one sample, in the parent stage's units.

    Attributes:
        vertical: Signed vertical load.
        lateral: Signed lateral load; positive means right in the source-app policy.
        longitudinal: Signed longitudinal load; positive means acceleration under
            that same policy.
    """

    vertical: float
    lateral: float
    longitudinal: float


@dataclass(frozen=True, slots=True)
class AnalyzedSample:
    """Bundle one sample's raw and derived values without retaining duplicate series.

    Attributes:
        index: Original source sample index.
        recording_seconds: Recording-relative time under the declared time basis.
        replay_seconds: Time relative to the recording's replay origin.
        raw: Original typed source acceleration vector, without inferred semantics.
        projected: Unfiltered force values, or None when unavailable/invalid.
        smoothed: Filtered force values, or None when unavailable/invalid.
        combined_g: Norm of smoothed device axes, or None when unavailable/invalid.
        orientation_degrees: Tilt with valid source correspondence, otherwise None.
        context: Prepared category, or None when the context stage is unavailable.
        projection_availability: Whole-stage availability for projected forces.
        smoothing_availability: Whole-stage availability for filtered forces.
        orientation_availability: Whole-stage availability for tilt.
        context_availability: Whole-stage availability for context labels.
        quality: Stage/sample diagnostics explaining missing values and limitations.
    """

    index: int
    recording_seconds: float
    replay_seconds: float
    raw: Vector3
    projected: ForceSample | None
    smoothed: ForceSample | None
    combined_g: float | None
    orientation_degrees: float | None
    context: VerticalContext | None
    projection_availability: StageAvailability
    smoothing_availability: StageAvailability
    orientation_availability: StageAvailability
    context_availability: StageAvailability
    quality: AnalysisQuality


@dataclass(frozen=True, slots=True)
class RecordingAnalysis:
    """Assemble one consistent immutable snapshot from shared analysis stages.

    Constructors store references only. Explicit validate checks the assembled
    graph without changing values or copying buffers. Preparation uses the
    existing numerical functions; reconfiguration replaces only affected stages.

    Attributes:
        source: Complete original import retained without modification.
        configuration: Configuration represented by this completed snapshot.
        time: Shared source sample/time correspondence.
        forces: Projection and smoothing stages with consistent dependencies.
        orientation: Independently reusable tilt stage.
        context: Prepared labels bound to their actual force input.
        events: Explicit event-evaluation outcome, including NOT_EVALUATED.
        quality: Aggregate scientific capabilities and diagnostics.
        revision: Service revision that produced this snapshot, not a cache key.
        calibration: Shared custom reference basis/provenance; None retains source axes.
    """

    source: ImportSuccess
    configuration: AnalysisConfiguration
    time: AnalysisTime
    forces: ForceSeries
    orientation: OrientationSeries
    context: SampleContext
    events: EventAnalysis
    quality: AnalysisQuality
    revision: int
    calibration: CalibrationBasis | None = None

    def validate(self) -> None:
        """Validate availability, source identity, indices and stage dependencies.

        Returns:
            None after successful structural validation, without mutating data.

        Raises:
            TypeError: A field has an incompatible type or mutable collection.
            ValueError: Field values, payloads or source/stage relationships
                contradict the declared model. This check does not certify
                projection math, filtering, event rules or physical accuracy.
            AssertionError: If a required internal invariant does not hold.
        """
        validate_snapshot(self)

    @property
    def ride_bounds(self) -> tuple[int, int]:
        """Return inclusive effective markers, retaining source markers separately.

        Returns:
            Inclusive effective markers, retaining source markers separately.
        """
        indices = self.source.recording.indices
        return self.configuration.ride_bounds or (indices.start, indices.end)

    @property
    def replay_origin(self) -> int:
        """Return effective replay zero; time.replay_origin retains source provenance.

        Returns:
            Effective replay zero; time.replay_origin retains source provenance.
        """
        return self.ride_bounds[0]

    def sample(self, index: int) -> AnalyzedSample:
        """Read one source sample without recalculating or retaining a row cache.

        Args:
            index: Original source sample index to inspect.

        Returns:
            AnalyzedSample with raw values, inferred times, prepared stage values
            and applicable diagnostics. Missing stage/row values remain None.

        Raises:
            TypeError: Index is not an integer (booleans are not indices).
            IndexError: Index is outside the original recording.
            ValueError: A manually assembled snapshot has no time rate. Call
                validate before reading snapshots not produced by preparation.
        """
        if type(index) is not int:
            raise TypeError("Sample index must be an integer")
        if not 0 <= index < len(self.time.source_indices):
            raise IndexError("Sample index outside recording")
        rate = self.time.basis.sample_rate
        if rate is None:
            raise ValueError("Sample times require a sample rate")
        orientation = self.orientation.values
        combined = self.forces.smoothed.combined
        angle = (
            float(orientation.values[index])
            if orientation is not None and orientation.valid_rows[index]
            else None
        )
        return AnalyzedSample(
            index=index,
            recording_seconds=index / rate.value,
            replay_seconds=(index - self.replay_origin) / rate.value,
            raw=self.source.recording.motion.acceleration[index],
            projected=_force_sample(self.forces.projected.channels, index),
            smoothed=_force_sample(self.forces.smoothed.channels, index),
            combined_g=(
                float(combined.values[index])
                if combined is not None and combined.valid_rows[index]
                else None
            ),
            orientation_degrees=angle,
            context=self.context.labels[index] if self.context.labels is not None else None,
            projection_availability=self.forces.projected.availability,
            smoothing_availability=self.forces.smoothed.availability,
            orientation_availability=self.orientation.availability,
            context_availability=self.context.availability,
            quality=replace(
                self.quality,
                diagnostics=tuple(
                    item
                    for item in self.quality.diagnostics
                    if item.source_index is None or item.source_index == index
                ),
            ),
        )

    def with_configuration(
        self,
        configuration: AnalysisConfiguration,
        *,
        revision: int,
        calculation_time: datetime,
    ) -> RecordingAnalysis:
        """Reconfigure this snapshot, reusing compatible immutable stages.

        Args:
            configuration: Requested effective analysis configuration.
            revision: Request revision, strictly greater than this snapshot's.
            calculation_time: Timezone-aware UTC time for recalculated stages.

        Returns:
            New validated snapshot sharing unchanged stages and their provenance.
            The previous snapshot remains unchanged; no history is retained.

        Raises:
            TypeError: Snapshot or configuration has incompatible field types.
            ValueError: Snapshot, configuration, revision or calculation time is
                invalid. Failed requests leave this snapshot unchanged.
        """
        from ..preparation import reconfigure_recording_analysis

        return reconfigure_recording_analysis(
            self,
            configuration,
            revision=revision,
            calculation_time=calculation_time,
        )

    def with_smoothing(
        self,
        window_samples: int,
        *,
        revision: int,
        calculation_time: datetime,
    ) -> RecordingAnalysis:
        """Change smoothing while retaining source, projection, time and orientation.

        Args:
            window_samples: Requested odd centered-mean window, 1 through 51.
            revision: Request revision, strictly greater than this snapshot's.
            calculation_time: Timezone-aware UTC time for recalculated stages.

        Returns:
            New consistent snapshot. Smoothing always starts from the retained
            unfiltered projection; only consumers of changed stages are replaced.

        Raises:
            TypeError: Snapshot fields have incompatible types.
            ValueError: Snapshot, window, revision or UTC time is invalid.
        """
        parameters = dict(self.configuration.smoothing.parameters)
        if type(window_samples) is int and window_samples == parameters.get("window_samples", 11):
            configuration = self.configuration
        else:
            parameters["window_samples"] = window_samples
            configuration = replace(
                self.configuration,
                smoothing=replace(
                    self.configuration.smoothing,
                    parameters=tuple(parameters.items()),
                ),
            )
        return self.with_configuration(
            configuration,
            revision=revision,
            calculation_time=calculation_time,
        )


def _force_sample(channels: ForceChannels | None, index: int) -> ForceSample | None:
    """Read one force row; absent or invalid rows remain absent."""
    if channels is None or not all(axis.valid_rows[index] for axis in channels):
        return None
    return ForceSample(*(float(axis.values[index]) for axis in channels))
