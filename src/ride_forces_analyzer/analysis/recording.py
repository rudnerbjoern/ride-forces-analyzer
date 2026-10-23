"""Recording-analysis containers with explicit structural snapshot validation.

Constructors store references without validation or calculation. Call
``RecordingAnalysis.validate`` before trusting a snapshot's structure. It checks
source/time correspondence, availability, payloads and stage dependencies, not
scientific correctness. Supply immutable tuples/frozen sets; inputs are never
copied or normalized. Assigning frozen fields raises ``FrozenInstanceError``.
Preparation and sample access reuse the existing source-app calculations.
Reconfiguration shares compatible stages without retaining snapshot history.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from math import isfinite

import numpy as np

from ride_forces_analyzer import __version__
from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.importers import ImportSuccess, Severity

from . import airtime
from .calibration import (
    CalibrationBasis,
    CalibrationOverrides,
    CalibrationReferences,
    REFERENCE_WINDOW_SAMPLES,
    prepare_calibration_basis,
)
from .models import (
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    EvidenceState,
    ParameterValue,
    ProfileName,
    SampleValues,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from .orientation import orientation_degrees
from .projection import project_directions
from .smoothing import centered_mean, combined_force


class AnalysisStage(StrEnum):
    """Stable identifiers for independently reusable or invalidated analysis stages."""

    TIME = "time"
    CALIBRATION = "calibration"
    PROJECTION = "projection"
    SMOOTHING = "smoothing"
    ORIENTATION = "orientation"
    CONTEXT = "context"
    EVENTS = "events"


class AvailabilityState(StrEnum):
    """Payload presence, independent of scientific quality and pending requests.

    AVAILABLE requires a payload; UNAVAILABLE requires a reason and no payload.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EventEvaluationState(StrEnum):
    """Distinguish completed event evaluation from evaluation that did not occur.

    EVALUATED permits an empty event tuple. NOT_EVALUATED requires a reason
    and an absent event collection, not an empty one.
    """

    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class RequestStatus(StrEnum):
    """Request lifecycle: no request, pending work, published result or failure.

    This status describes the service request, not the retained snapshot's age
    or scientific capabilities. A failed request can retain an older snapshot.
    """

    IDLE = "idle"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class VerticalContext(StrEnum):
    """Language-independent identifiers for provisional per-sample context labels.

    UNAVAILABLE denotes a missing/invalid sample in an otherwise prepared
    context series. It does not establish a whole stage's availability.
    """

    HEAVY_GS = "heavy_gs"
    NORMAL_GS = "normal_gs"
    LIGHT_GS = "light_gs"
    FLOATER_AIRTIME = "floater_airtime"
    AIRTIME = "airtime"
    STRONG_AIRTIME = "strong_airtime"
    EJECTOR_AIRTIME = "ejector_airtime"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class StageConfiguration:
    """Identify a stage algorithm and its effective scalar parameters.

    Attributes:
        algorithm: Stable algorithm identifier, without presentation settings.
        version: Version of that algorithm's calculation contract.
        parameters: Immutable name/value pairs, such as window_samples for
            smoothing. Snapshot validation checks scalar types and unique names;
            algorithm-specific parameter admission remains a calculation concern.
    """

    algorithm: str
    version: str
    parameters: tuple[tuple[str, ParameterValue], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisConfiguration:
    """Collect scientific policy, stage configurations and declared dependencies.

    Attributes:
        profile: Existing analysis policy, evidence and provisional permissions.
        projection: Source-axis projection configuration.
        smoothing: Force filter configuration, independent of orientation.
        orientation: Source-gravity tilt configuration.
        context: Sample-label and stabilization configuration.
        events: Event-rule configuration, or None when no rules are configured.
        context_input: Force stage consumed by context; projection or smoothing.
        events_input: Force stage consumed by event detection when configured.
        ride_bounds: Optional inclusive user start/end markers; original source
            markers and full-history numerical stages remain unchanged.
        calibration: Typed custom Gravity/Incline references; default retains
            the exact original source directions and projection policy.
    """

    profile: AnalysisProfile
    projection: StageConfiguration
    smoothing: StageConfiguration
    orientation: StageConfiguration
    context: StageConfiguration
    events: StageConfiguration | None = None
    context_input: AnalysisStage = AnalysisStage.SMOOTHING
    events_input: AnalysisStage = AnalysisStage.SMOOTHING
    ride_bounds: tuple[int, int] | None = None
    calibration: CalibrationOverrides = CalibrationOverrides()


@dataclass(frozen=True, slots=True)
class AnalysisTime:
    """Retain the existing time contract and explicit force-sample correspondence.

    Attributes:
        basis: Effective sample rate and measured/inferred time evidence.
        source_indices: Original source index corresponding to each force row.
        replay_origin: Source sample defining replay time zero, not a UTC epoch.
    """

    basis: TimeBasis
    source_indices: tuple[int, ...]
    replay_origin: int


@dataclass(frozen=True, slots=True)
class StageAvailability:
    """Describe whole-stage payload availability without claiming physical accuracy.

    Attributes:
        state: Whether calculated data is present.
        reason: Stable diagnostic explaining UNAVAILABLE; None for AVAILABLE.
    """

    state: AvailabilityState
    reason: AnalysisDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class AnalysisQuality:
    """Aggregate existing scientific capability and diagnostic contracts.

    Attributes:
        capabilities: Identifier/capability pairs retaining provisional or invalid
            status independently of payload availability.
        diagnostics: Ordered diagnostics, including gaps and coverage limitations.
        existing_results: Compatible existing analysis results retained by reference,
            without reinterpreting their units, frames or evidence.
    """

    capabilities: tuple[tuple[str, CapabilityState], ...] = ()
    diagnostics: tuple[AnalysisDiagnostic, ...] = ()
    existing_results: tuple[AnalysisResult, ...] = ()


#: Immutable sample buffers in vertical, lateral, longitudinal order.
type ForceChannels = tuple[SampleValues, SampleValues, SampleValues]


@dataclass(frozen=True, slots=True)
class ProjectedForces:
    """Unfiltered source-direction forces shared by subsequent processing stages.

    Attributes:
        source: Complete lossless import, including original bytes and identity.
        time: Source-index/time correspondence for the channel rows.
        configuration: Projection algorithm and effective parameters.
        availability: Whole-stage presence or reason for missing prerequisites.
        channels: Vertical/lateral/longitudinal buffers, or None when unavailable.
        unit: Existing explicit unit assignment and evidence.
        quality: Capabilities, diagnostics and scientific limitations.
        provenance: Original calculation identity/time, or None if not calculated.
        calibration: Shared effective reference basis, or None for source axes.
    """

    source: ImportSuccess
    time: AnalysisTime
    configuration: StageConfiguration
    availability: StageAvailability
    channels: ForceChannels | None  # Vertical, lateral, longitudinal, in this order.
    unit: UnitAssignment
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None
    calibration: CalibrationBasis | None = None


@dataclass(frozen=True, slots=True)
class SmoothedForces:
    """Filtered forces retaining their original, unfiltered projection dependency.

    Attributes:
        projection: Shared input projection; never a previously smoothed stage.
        configuration: Filter algorithm and effective window/parameters.
        availability: Whole-stage presence or exclusion reason.
        channels: Filtered buffers in projection order/units, or None if unavailable.
        quality: Filter-specific capability and validity information.
        provenance: This filter calculation's provenance, or None if not calculated.
        combined: Norm of smoothed device axes, or None when smoothing is unavailable.
    """

    projection: ProjectedForces
    configuration: StageConfiguration
    availability: StageAvailability
    channels: ForceChannels | None
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None
    combined: SampleValues | None


@dataclass(frozen=True, slots=True)
class ForceSeries:
    """Pair projected and smoothed stages without copying their numerical buffers.

    Attributes:
        projected: Unfiltered force stage, reusable across smoothing changes.
        smoothed: Filtered stage whose projection must reference projected.
    """

    projected: ProjectedForces
    smoothed: SmoothedForces


@dataclass(frozen=True, slots=True)
class OrientationSeries:
    """Source-gravity tilt, independent of force projection, smoothing and context.

    Attributes:
        source: Recording supplying gravity and original calibration evidence.
        time: Explicit correspondence for orientation rows, without invented data.
        configuration: Tilt algorithm/parameters, not yaw or track heading.
        availability: Whole-stage presence or reason prerequisites are absent.
        values: Immutable tilt samples with validity, or None when unavailable.
        unit: Degree unit assignment and evidence.
        quality: Missing/zero-gravity diagnostics and scientific limitations.
        provenance: Original tilt calculation provenance, or None if not calculated.
        gravity_index: Custom Gravity reference used for tilt; None uses the
            original source vertical, independently of custom Incline choices.
    """

    source: ImportSuccess
    time: AnalysisTime
    configuration: StageConfiguration
    availability: StageAvailability
    values: SampleValues | None
    unit: UnitAssignment
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None
    gravity_index: int | None = None


#: The explicitly selected numerical force stage used by context or events.
type ForceInput = ProjectedForces | SmoothedForces


@dataclass(frozen=True, slots=True)
class SampleContext:
    """Prepared presentation categories on the selected force stage's sample axis.

    Attributes:
        input: Actual projection or smoothing dependency.
        configuration: Label algorithm, provisional thresholds and stabilization.
        availability: Whole-stage presence or exclusion reason.
        labels: One category per force row, or None when the stage is unavailable.
        quality: Label coverage and interpretation limitations.
        provenance: Label preparation provenance, or None if not calculated.
    """

    input: ForceInput
    configuration: StageConfiguration
    availability: StageAvailability
    labels: tuple[VerticalContext, ...] | None
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None


@dataclass(frozen=True, slots=True)
class AirtimeEvent:
    """Describe a provisional domain event under separately defined detection rules.

    The separate airtime-events version-1 contract defines detection and inclusive
    boundaries. Display-label confirmation does not establish event duration.

    Attributes:
        first_sample: Event start in original source indices.
        last_sample: Event end in source indices; inclusion follows the event rules.
        duration_seconds: Duration under the declared rules and time basis.
        minimum_vertical_g: Minimum vertical loading ratio within valid event data.
        minimum_sample: Source index of the reported minimum.
        onset_g_per_second: Declared load-change indicator, or None if unavailable;
            not a qualified biomechanical jerk measurement.
        category: Provisional event category established by the event rules.
        start_incomplete: Whether the event's beginning could not be fully observed.
        end_incomplete: Whether the event's ending could not be fully observed.
    """

    first_sample: int
    last_sample: int
    duration_seconds: float
    minimum_vertical_g: float
    minimum_sample: int
    onset_g_per_second: float | None
    category: VerticalContext
    start_incomplete: bool
    end_incomplete: bool


@dataclass(frozen=True, slots=True)
class EventAnalysis:
    """Wrap domain-event evaluation separately from presentation context labels.

    Attributes:
        input: Force stage actually selected for event detection.
        configuration: Versioned event rules, or None when not configured.
        status: Whether event evaluation completed or did not occur.
        events: Tuple, possibly empty, when EVALUATED; None when NOT_EVALUATED.
        reason: Required diagnostic for NOT_EVALUATED; None for completed evaluation.
        quality: Coverage/gap limitations; empty events do not qualify missing data.
        provenance: Evaluation provenance, or None when evaluation did not occur.
    """

    input: ForceInput
    configuration: StageConfiguration | None
    status: EventEvaluationState
    events: tuple[AirtimeEvent, ...] | None
    reason: AnalysisDiagnostic | None
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None


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
        """
        for value, kind in (
            (self.source, ImportSuccess),
            (self.configuration, AnalysisConfiguration),
            (self.time, AnalysisTime),
            (self.forces, ForceSeries),
            (self.orientation, OrientationSeries),
            (self.context, SampleContext),
            (self.events, EventAnalysis),
        ):
            _typed(value, kind)
        _typed(self.forces.projected, ProjectedForces)
        _typed(self.forces.smoothed, SmoothedForces)
        _require(type(self.revision) is int and self.revision >= 0, "Invalid snapshot revision")
        _configuration(self.configuration)
        _time(self.time, self.source)
        _require(
            self.ride_bounds[1] < len(self.time.source_indices),
            "Ride markers outside recording",
        )
        _quality(self.quality, self.source)
        count = len(self.time.source_indices)
        _calibration(self.calibration, self.configuration.calibration, self.source)
        projected, smoothed = self.forces.projected, self.forces.smoothed
        orientation, context, events = self.orientation, self.context, self.events
        _require(
            projected.calibration is self.calibration,
            "Projection must reference the snapshot calibration",
        )
        _require(
            (orientation.gravity_index is None or type(orientation.gravity_index) is int)
            and orientation.gravity_index == self.configuration.calibration.gravity_index,
            "Orientation Gravity reference differs from configuration",
        )
        for source, time in (
            (projected.source, projected.time),
            (orientation.source, orientation.time),
        ):
            _source(source, self.source)
            _typed(time, AnalysisTime)
            _require(time == self.time, "Stage time differs from snapshot time")
        _require(smoothed.projection is projected, "Smoothing must reference the shared projection")
        for actual, configuration in (
            (projected.configuration, self.configuration.projection),
            (smoothed.configuration, self.configuration.smoothing),
            (orientation.configuration, self.configuration.orientation),
            (context.configuration, self.configuration.context),
        ):
            _typed(actual, StageConfiguration)
            _require(
                actual == configuration,
                "Stage configuration differs from snapshot",
            )
        projection_available = _stage(
            projected.availability,
            projected.channels,
            projected.quality,
            projected.provenance,
            projected.configuration,
            self.source,
        )
        _typed(projected.unit, UnitAssignment)
        if projection_available:
            _require(
                projected.unit.label is UnitLabel.DIMENSIONLESS,
                "Force unit must be dimensionless",
            )
            _channels(projected.channels, count)
        smoothing_available = _stage(
            smoothed.availability,
            smoothed.channels,
            smoothed.quality,
            smoothed.provenance,
            smoothed.configuration,
            self.source,
        )
        if smoothing_available:
            _require(projection_available, "Smoothing requires an available projection")
            _channels(smoothed.channels, count)
            _samples(smoothed.combined, count)
            assert smoothed.combined is not None
            _require(
                all(
                    value >= 0
                    for value, valid in zip(
                        smoothed.combined.values,
                        smoothed.combined.valid_rows,
                        strict=True,
                    )
                    if valid
                ),
                "Combined force magnitude must be nonnegative",
            )
        else:
            _require(smoothed.combined is None, "Unavailable smoothing has no Combined values")
        orientation_available = _stage(
            orientation.availability,
            orientation.values,
            orientation.quality,
            orientation.provenance,
            orientation.configuration,
            self.source,
        )
        _typed(orientation.unit, UnitAssignment)
        if orientation_available:
            _require(
                orientation.unit.label is UnitLabel.DEGREES,
                "Orientation unit must be degrees",
            )
            _samples(orientation.values, count)
            gravity = self.source.recording.motion.gravity
            _require(gravity is not None, "Orientation requires source gravity")
            _require(
                self.source.recording.vectors.vertical_direction is not None,
                "Orientation requires a vertical direction",
            )
            assert gravity is not None and orientation.values is not None
            for index, vector in enumerate(gravity):
                _require(
                    (vector.x, vector.y, vector.z) != (0.0, 0.0, 0.0)
                    or not orientation.values.valid_rows[index],
                    "Zero gravity cannot produce a valid orientation sample",
                )
        for actual_input, selected in (
            (context.input, self.configuration.context_input),
            (events.input, self.configuration.events_input),
        ):
            expected = projected if selected is AnalysisStage.PROJECTION else smoothed
            _require(
                actual_input is expected,
                "Stage must reference its configured shared force input",
            )
        context_available = _stage(
            context.availability,
            context.labels,
            context.quality,
            context.provenance,
            context.configuration,
            self.source,
        )
        if context_available:
            _require(
                context.input.availability.state is AvailabilityState.AVAILABLE,
                "Context requires available input",
            )
            labels = context.labels
            _typed(labels, tuple)
            assert labels is not None
            _require(len(labels) == count, "Context labels do not match the source axis")
            for index, label in enumerate(labels):
                _typed(label, VerticalContext)
                channels = context.input.channels
                assert channels is not None
                _require(
                    channels[0].valid_rows[index] or label is VerticalContext.UNAVAILABLE,
                    "Missing vertical samples cannot have an available context",
                )
        _events(events, self.configuration.events, self.source, count)

    @property
    def ride_bounds(self) -> tuple[int, int]:
        """Return inclusive effective markers, retaining source markers separately."""
        indices = self.source.recording.indices
        return self.configuration.ride_bounds or (indices.start, indices.end)

    @property
    def replay_origin(self) -> int:
        """Return effective replay zero; time.replay_origin retains source provenance."""
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
        self.validate()
        _require(
            type(revision) is int and revision > self.revision,
            "Reconfiguration revision must increase",
        )
        return _prepare_analysis(
            self.source,
            configuration,
            revision=revision,
            calculation_time=calculation_time,
            previous=self,
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


@dataclass(frozen=True, slots=True)
class AnalysisState:
    """Describe subscription initial state independently of snapshot configuration.

    Attributes:
        source_sha256: Current complete-source identity, or None without a source.
        snapshot: Last completed snapshot, possibly older than the current request,
            or None when no completed result exists.
        requested_configuration: Current requested configuration, or None if idle.
        requested_revision: Revision used to reject stale queued deliveries.
        status: Current request lifecycle status.
        dirty_stages: Stages awaiting recalculation for the requested configuration.
        failure: Current request's failure diagnostic, or None without a failure.
    """

    source_sha256: str | None
    snapshot: RecordingAnalysis | None
    requested_configuration: AnalysisConfiguration | None
    requested_revision: int
    status: RequestStatus
    dirty_stages: frozenset[AnalysisStage] = frozenset()
    failure: AnalysisDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class AnalysisUpdated:
    """Publication payload for a completed consistent snapshot, not an emitter.

    Attributes:
        source_sha256: Full source hash associated with the published result.
        revision: Completed request revision, rechecked at UI delivery time.
        replaced_stages: Stages replaced relative to the preceding snapshot.
        snapshot: New immutable result; subscribers may share its references.
    """

    source_sha256: str
    revision: int
    replaced_stages: frozenset[AnalysisStage]
    snapshot: RecordingAnalysis


@dataclass(frozen=True, slots=True)
class AnalysisInvalidated:
    """Optional pending-work payload, leaving the completed snapshot unchanged.

    Attributes:
        source_sha256: Source identity for the pending request.
        revision: Requested revision, rechecked before updating pending UI state.
        dirty_stages: Invalidated stages, including their affected dependents.
    """

    source_sha256: str
    revision: int
    dirty_stages: frozenset[AnalysisStage]


@dataclass(frozen=True, slots=True)
class AnalysisFailed:
    """Failure payload terminating a matching request without publishing partial data.

    Attributes:
        source_sha256: Source identity of the failed request.
        revision: Failed revision; stale failures must not clear newer pending work.
        affected_stages: Stages affected by the failed recalculation.
        failure: Structured diagnostic; the older snapshot retains its configuration.
    """

    source_sha256: str
    revision: int
    affected_stages: frozenset[AnalysisStage]
    failure: AnalysisDiagnostic


#: Technical service payloads, separate from AirtimeEvent domain data.
type AnalysisNotification = AnalysisUpdated | AnalysisInvalidated | AnalysisFailed


def source_app_configuration() -> AnalysisConfiguration:
    """Return the existing owner-adopted source-app policy and default window.

    Returns:
        Versioned source-direction projection, centered mean (11 samples),
        independent gravity tilt and current provisional context rules.
        This opt-in policy does not qualify universal physical rider loading.
    """
    return AnalysisConfiguration(
        AnalysisProfile(
            ProfileName.RIDER_CALIBRATED,
            policy_references=("ADR-0006: source-app projection and centered mean",),
            assumptions=("Source acceleration interpreted as g under the owner-adopted policy",),
            allow_provisional=True,
        ),
        StageConfiguration("source-direction-unit-projection", "1"),
        StageConfiguration("centered-mean", "1", (("window_samples", 11),)),
        StageConfiguration("source-gravity-tilt", "1"),
        StageConfiguration("vertical-context", "1"),
    )


def prepare_recording_analysis(
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
) -> RecordingAnalysis:
    """Prepare a validated immutable snapshot using the existing source-app policy.

    Args:
        source: Successful lossless import retaining original bytes and metadata.
        configuration: Effective stage configurations and scientific policy.
        revision: Service request revision assigned to the planned result.
        calculation_time: Caller-supplied timezone-aware UTC calculation time.

    Returns:
        RecordingAnalysis retaining the complete source, inferred time axis,
        independent orientation, projected/smoothed forces and prepared context.
        Missing prerequisites retain raw values and explicit exclusion reasons.
        Configured airtime-events version 1 evaluates separate domain episodes.
        Disabled/unavailable event stages retain NOT_EVALUATED with a reason.

    Raises:
        TypeError: Source/configuration has an incompatible type.
        ValueError: Configuration, revision or UTC calculation time is invalid.
            Only version 1 of the documented algorithms/default context rules
            is supported. Numerical force range failures exclude affected stages.
    """
    return _prepare_analysis(
        source,
        configuration,
        revision=revision,
        calculation_time=calculation_time,
    )


def _prepare_analysis(
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
    previous: RecordingAnalysis | None = None,
) -> RecordingAnalysis:
    """Prepare changed stages; retain compatible dependencies, never old snapshots."""
    _typed(source, ImportSuccess)
    _typed(configuration, AnalysisConfiguration)
    _require(type(revision) is int and revision >= 0, "Invalid snapshot revision")
    _configuration(configuration)
    if configuration.ride_bounds is not None:
        _require(
            configuration.ride_bounds[1] < len(source.recording.motion.acceleration),
            "Ride markers outside recording",
        )
    window = _preparation_window(configuration)
    if configuration.events is not None:
        from .events import event_rules

        event_rules(configuration.events)
    provenance = AnalysisProvenance(
        source.recording.source.provenance,
        f"{__version__}; numpy={np.__version__}",
        "recording-analysis",
        calculation_time,
    )
    motion, vectors = source.recording.motion, source.recording.vectors
    time = (
        previous.time
        if previous is not None
        else AnalysisTime(
            TimeBasis(TimeBasisKind.INFERRED_UNIFORM, motion.sample_rate),
            tuple(range(len(motion.acceleration))),
            source.recording.indices.start,
        )
    )
    raw_mode = configuration.profile.name is ProfileName.RAW_DEVICE_ONLY
    evidence = configuration.profile.policy_references + configuration.profile.assumptions
    vertical, lateral, longitudinal = (
        vectors.vertical_direction,
        vectors.lateral_direction,
        vectors.longitudinal_direction,
    )
    same_policy = previous is not None and configuration.profile == previous.configuration.profile
    same_calibration = (
        previous is not None and configuration.calibration == previous.configuration.calibration
    )
    calibration = (
        previous.calibration
        if previous is not None and same_calibration
        else prepare_calibration_basis(
            source,
            configuration.calibration,
            calculation_time=calculation_time,
        )
    )
    if calibration is not None:
        vertical, lateral, longitudinal = calibration.directions
    if (
        previous is not None
        and same_policy
        and same_calibration
        and configuration.projection == previous.configuration.projection
    ):
        projected = previous.forces.projected
    else:
        raw = None
        projection_availability = StageAvailability(AvailabilityState.AVAILABLE)
        if raw_mode:
            projection_availability = _unavailable(
                "RAW_PROFILE",
                "Raw profile excludes derived forces",
            )
        elif vertical is None or lateral is None or longitudinal is None:
            projection_availability = _unavailable(
                "PROJECTION_UNAVAILABLE",
                "Source directions are incomplete",
            )
        else:
            try:
                raw = project_directions(motion.acceleration, (vertical, lateral, longitudinal))
            except ValueError as error:
                projection_availability = _unavailable("PROJECTION_UNAVAILABLE", str(error))
        projected = ProjectedForces(
            source,
            time,
            configuration.projection,
            projection_availability,
            _force_channels(raw) if raw is not None else None,
            UnitAssignment(UnitLabel.DIMENSIONLESS, EvidenceState.ASSUMED, evidence)
            if not raw_mode
            else UnitAssignment(),
            _prepared_quality("projection", projection_availability),
            replace(provenance, algorithm=configuration.projection.algorithm)
            if raw is not None
            else None,
            calibration,
        )
    if (
        previous is not None
        and projected is previous.forces.projected
        and configuration.smoothing == previous.configuration.smoothing
    ):
        smoothed = previous.forces.smoothed
    else:
        filtered = None
        combined_values = None
        smoothing_availability = StageAvailability(AvailabilityState.AVAILABLE)
        channels = projected.channels
        if channels is None:
            smoothing_availability = _unavailable(
                "SMOOTHING_UNAVAILABLE",
                "Projection is unavailable",
            )
        else:
            try:
                filtered = tuple(
                    centered_mean(tuple(float(value) for value in axis.values), window)
                    for axis in channels
                )
            except ValueError as error:
                filtered = None
                smoothing_availability = _unavailable("SMOOTHING_UNAVAILABLE", str(error))
        if filtered is not None:
            try:
                combined_values = combined_force(motion.acceleration, window)
            except ValueError:
                combined_values = (None,) * len(motion.acceleration)
        combined_diagnostics = tuple(
            AnalysisDiagnostic(
                "COMBINED_SAMPLE_UNAVAILABLE",
                Severity.WARNING,
                "Device-axis smoothing or magnitude exceeds finite display range",
                "combined",
                index,
            )
            for index, value in enumerate(combined_values or ())
            if value is None
        )
        smoothing_quality = _prepared_quality("smoothing", smoothing_availability)
        smoothed = SmoothedForces(
            projected,
            configuration.smoothing,
            smoothing_availability,
            _force_channels(filtered) if filtered is not None else None,
            replace(
                smoothing_quality,
                diagnostics=smoothing_quality.diagnostics + combined_diagnostics,
            ),
            replace(provenance, algorithm=configuration.smoothing.algorithm)
            if filtered is not None
            else None,
            SampleValues(
                np.array([np.nan if value is None else value for value in combined_values]),
                valid_rows=tuple(value is not None for value in combined_values),
            )
            if combined_values is not None
            else None,
        )
    if (
        previous is not None
        and same_policy
        and configuration.orientation == previous.configuration.orientation
        and configuration.calibration.gravity_index
        == previous.configuration.calibration.gravity_index
    ):
        orientation = previous.orientation
    else:
        orientation_availability = StageAvailability(AvailabilityState.AVAILABLE)
        orientation_values = None
        orientation_diagnostics: tuple[AnalysisDiagnostic, ...] = ()
        if (
            raw_mode
            or motion.gravity is None
            or vertical is None
            or (vertical.x, vertical.y, vertical.z) == (0.0, 0.0, 0.0)
        ):
            orientation_availability = _unavailable(
                "ORIENTATION_UNAVAILABLE",
                "Orientation requires gravity, a vertical direction and an opt-in profile",
            )
        else:
            angles = orientation_degrees(
                source.recording,
                vertical_direction=(
                    vertical
                    if configuration.calibration.gravity_index is not None
                    else vectors.vertical_direction
                ),
            )
            orientation_values = SampleValues(
                np.array([np.nan if value is None else value for value in angles]),
                valid_rows=tuple(value is not None for value in angles),
            )
            orientation_diagnostics = tuple(
                AnalysisDiagnostic(
                    "ORIENTATION_SAMPLE_UNAVAILABLE",
                    Severity.WARNING,
                    "Zero gravity has no orientation",
                    "orientation",
                    index,
                )
                for index, value in enumerate(angles)
                if value is None
            )
        orientation_quality = _prepared_quality("orientation", orientation_availability)
        orientation = OrientationSeries(
            source,
            time,
            configuration.orientation,
            orientation_availability,
            orientation_values,
            UnitAssignment(UnitLabel.DEGREES, EvidenceState.ASSUMED, evidence)
            if not raw_mode
            else UnitAssignment(),
            replace(
                orientation_quality,
                diagnostics=orientation_quality.diagnostics + orientation_diagnostics,
            ),
            replace(provenance, algorithm=configuration.orientation.algorithm)
            if orientation_values is not None
            else None,
            configuration.calibration.gravity_index,
        )
    context_input = (
        projected if configuration.context_input is AnalysisStage.PROJECTION else smoothed
    )
    if (
        previous is not None
        and context_input is previous.context.input
        and configuration.context == previous.configuration.context
    ):
        context = previous.context
    else:
        context_availability = StageAvailability(AvailabilityState.AVAILABLE)
        labels = None
        channels = context_input.channels
        if channels is None:
            context_availability = _unavailable(
                "CONTEXT_UNAVAILABLE",
                "Selected force input is unavailable",
            )
        else:
            values = tuple(float(value) for value in channels[0].values)
            labels = tuple(
                VerticalContext(label.lower().replace(" ", "_"))
                for label in airtime.AirtimeContext.prepare(values, motion.sample_rate.value).labels
            )
        context = SampleContext(
            context_input,
            configuration.context,
            context_availability,
            labels,
            _prepared_quality("context", context_availability),
            replace(provenance, algorithm=configuration.context.algorithm)
            if labels is not None
            else None,
        )
    events_input = projected if configuration.events_input is AnalysisStage.PROJECTION else smoothed
    if (
        previous is not None
        and events_input is previous.events.input
        and configuration.events == previous.configuration.events
    ):
        events = previous.events
    else:
        from .events import evaluate_events

        events = evaluate_events(
            events_input,
            configuration.events,
            motion.sample_rate.value,
            provenance,
        )
    qualities = (
        projected.quality,
        smoothed.quality,
        orientation.quality,
        context.quality,
        events.quality,
    )
    result = RecordingAnalysis(
        source,
        configuration,
        time,
        previous.forces
        if previous is not None
        and projected is previous.forces.projected
        and smoothed is previous.forces.smoothed
        else ForceSeries(projected, smoothed),
        orientation,
        context,
        events,
        AnalysisQuality(
            capabilities=(
                (("calibration", calibration.references.capability),)
                if calibration is not None
                else ()
            )
            + tuple(item for quality in qualities for item in quality.capabilities),
            diagnostics=tuple(item for quality in qualities for item in quality.diagnostics),
        ),
        revision,
        calibration,
    )
    result.validate()
    return result


def _preparation_window(configuration: AnalysisConfiguration) -> int:
    """Admit supported algorithms/parameters and return the centered-mean window."""
    for stage, algorithm in (
        (configuration.projection, "source-direction-unit-projection"),
        (configuration.smoothing, "centered-mean"),
        (configuration.orientation, "source-gravity-tilt"),
        (configuration.context, "vertical-context"),
    ):
        _require(
            stage.algorithm == algorithm and stage.version == "1",
            "Unsupported stage algorithm/version",
        )
    _require(
        not configuration.projection.parameters and not configuration.orientation.parameters,
        "Projection/orientation parameters are unsupported",
    )
    smoothing = dict(configuration.smoothing.parameters)
    _require(smoothing.keys() <= {"window_samples"}, "Unsupported smoothing parameters")
    window = smoothing.get("window_samples", 11)
    _require(
        type(window) is int and 1 <= window <= 51 and window % 2 == 1,
        "Smoothing window must be an odd integer from 1 through 51",
    )
    defaults = {
        "floater_bound_g": airtime.FLOATER_BOUND_G,
        "strong_bound_g": airtime.STRONG_BOUND_G,
        "onset_window_seconds": airtime.ONSET_WINDOW_SECONDS,
        "ejector_onset_g_per_second": airtime.EJECTOR_ONSET_G_PER_SECOND,
        "onset_memory_seconds": airtime.ONSET_MEMORY_SECONDS,
        "context_confirm_seconds": airtime.CONTEXT_CONFIRM_SECONDS,
        "floater_exit_bound_g": airtime.FLOATER_EXIT_BOUND_G,
        "strong_exit_bound_g": airtime.STRONG_EXIT_BOUND_G,
    }
    for key, value in configuration.context.parameters:
        _require(
            key in defaults and type(value) in (int, float) and value == defaults[key],
            "Unsupported context parameters; version 1 uses the existing default rules",
        )
    profile = configuration.profile
    _require(
        profile.name in (ProfileName.RAW_DEVICE_ONLY, ProfileName.RIDER_CALIBRATED),
        "Unsupported recording analysis profile",
    )
    if profile.name is ProfileName.RIDER_CALIBRATED:
        _require(profile.allow_provisional, "Source-app analysis requires provisional permission")
    assert isinstance(window, int)
    return window


def _unavailable(code: str, message: str) -> StageAvailability:
    """Retain an explicit whole-stage exclusion without manufacturing payloads."""
    return StageAvailability(
        AvailabilityState.UNAVAILABLE,
        AnalysisDiagnostic(code, Severity.WARNING, message),
    )


def _prepared_quality(identifier: str, availability: StageAvailability) -> AnalysisQuality:
    """Keep source-app derivations provisional, independently of payload presence."""
    return AnalysisQuality(
        capabilities=(
            (
                identifier,
                CapabilityState.PROVISIONAL
                if availability.state is AvailabilityState.AVAILABLE
                else CapabilityState.UNAVAILABLE,
            ),
        ),
        diagnostics=(availability.reason,) if availability.reason is not None else (),
    )


def _force_channels(values: tuple[tuple[float, ...], ...]) -> ForceChannels:
    """Own immutable scalar buffers without changing existing float64 results."""
    return (
        SampleValues(np.array(values[0])),
        SampleValues(np.array(values[1])),
        SampleValues(np.array(values[2])),
    )


def _force_sample(channels: ForceChannels | None, index: int) -> ForceSample | None:
    """Read one force row; absent or invalid rows remain absent."""
    if channels is None or not all(axis.valid_rows[index] for axis in channels):
        return None
    return ForceSample(*(float(axis.values[index]) for axis in channels))


def _require(condition: bool, message: str) -> None:
    """Raise ValueError when a structural or semantic model constraint is false."""
    if not condition:
        raise ValueError(message)


def _typed(value: object, kind: type) -> None:
    """Reject incompatible runtime types without coercion or collection copying."""
    if not has_type(value, kind):
        raise TypeError(f"Expected {kind.__name__}")


def _text(value: str) -> None:
    """Require a nonempty textual identifier, preserving the supplied spelling."""
    _typed(value, str)
    _require(bool(value.strip()), "Identifier must contain text")


def _configuration(configuration: AnalysisConfiguration) -> None:
    """Validate reusable configuration metadata without admitting algorithm math."""
    _typed(configuration.calibration, CalibrationOverrides)
    if configuration.ride_bounds is not None:
        bounds = configuration.ride_bounds
        _typed(bounds, tuple)
        _require(
            len(bounds) == 2
            and all(type(value) is int for value in bounds)
            and 0 <= bounds[0] <= bounds[1],
            "Ride markers require ordered nonnegative integer indices",
        )
    _typed(configuration.profile, AnalysisProfile)
    for selector in (configuration.context_input, configuration.events_input):
        _typed(selector, AnalysisStage)
        _require(
            selector in (AnalysisStage.PROJECTION, AnalysisStage.SMOOTHING),
            "Context/events require a force input stage",
        )
    stages: tuple[StageConfiguration, ...] = (
        configuration.projection,
        configuration.smoothing,
        configuration.orientation,
        configuration.context,
    )
    if configuration.events is not None:
        stages += (configuration.events,)
    for stage in stages:
        _typed(stage, StageConfiguration)
        _text(stage.algorithm)
        _text(stage.version)
        _typed(stage.parameters, tuple)
        keys: set[str] = set()
        for item in stage.parameters:
            _typed(item, tuple)
            _require(len(item) == 2, "Parameters require name/value pairs")
            key, value = item
            _text(key)
            _require(key not in keys, "Parameter names must be unique")
            keys.add(key)
            _require(
                type(value) in (type(None), bool, str, int, float),
                "Parameter values must be immutable scalars",
            )
            if isinstance(value, float):
                _require(isfinite(value), "Parameter values must be finite")


def _calibration(
    basis: CalibrationBasis | None,
    overrides: CalibrationOverrides,
    source: ImportSuccess,
) -> None:
    """Check reference identity/support and graph ownership without recalculation."""
    if not overrides.active:
        _require(basis is None, "Inactive overrides require original source axes")
        return
    _typed(basis, CalibrationBasis)
    assert basis is not None
    references = basis.references
    _typed(references, CalibrationReferences)
    _require(references.overrides == overrides, "Calibration references differ from configuration")
    _provenance(
        references.provenance,
        StageConfiguration("user-reference-calibration", references.algorithm_version),
        source,
    )
    _require(
        references.window_samples == REFERENCE_WINDOW_SAMPLES
        and references.algorithm_version == "1"
        and references.capability is CapabilityState.PROVISIONAL,
        "Unsupported calibration reference contract",
    )
    count = len(source.recording.motion.acceleration)
    radius = REFERENCE_WINDOW_SAMPLES // 2
    for index, support in (
        (overrides.gravity_index, references.gravity_interval),
        (overrides.incline_index, references.incline_interval),
    ):
        if index is None:
            _require(support is None, "Retained source axis has no reference interval")
        else:
            _require(index < count, "Calibration index outside recording")
            _require(
                support == (max(0, index - radius), min(count - 1, index + radius)),
                "Calibration reference support differs from its original index",
            )
    for vector in (
        *basis.directions,
        references.vertical_reference,
        references.longitudinal_reference,
        references.polarity_reference,
    ):
        _typed(vector, Vector3)


def _time(time: AnalysisTime, source: ImportSuccess) -> None:
    """Check the full force axis against original acceleration indices and rate."""
    _typed(time.basis, TimeBasis)
    _typed(time.source_indices, tuple)
    for index in time.source_indices:
        _require(type(index) is int, "Source indices must be integers, not booleans")
    count = len(source.recording.motion.acceleration)
    _require(
        time.source_indices == tuple(range(count)),
        "Force axis must retain the complete original sample order",
    )
    _require(type(time.replay_origin) is int, "Replay origin must be an integer")
    _require(
        time.replay_origin == source.recording.indices.start,
        "Replay origin differs from source start marker",
    )
    if time.basis.sample_rate is None:
        _require(
            time.basis.kind is TimeBasisKind.SAMPLE_INDEX,
            "Timed axes require an explicit source sample rate",
        )
    else:
        _require(
            time.basis.sample_rate == source.recording.motion.sample_rate,
            "Time rate/value provenance differs from source",
        )


def _source(source: ImportSuccess, expected: ImportSuccess) -> None:
    """Compare content identity independently of a recording's filesystem path."""
    _typed(source, ImportSuccess)
    _require(
        (source.source_sha256, source.byte_count) == (expected.source_sha256, expected.byte_count),
        "Stage belongs to another source",
    )


def _quality(quality: AnalysisQuality, source: ImportSuccess) -> None:
    """Preserve typed scientific capabilities, diagnostics and source-bound results."""
    _typed(quality, AnalysisQuality)
    _typed(quality.capabilities, tuple)
    identifiers: set[str] = set()
    for item in quality.capabilities:
        _typed(item, tuple)
        _require(len(item) == 2, "Capabilities require identifier/state pairs")
        identifier, state = item
        _text(identifier)
        _typed(state, CapabilityState)
        _require(identifier not in identifiers, "Capability identifiers must be unique")
        identifiers.add(identifier)
    _typed(quality.diagnostics, tuple)
    for diagnostic in quality.diagnostics:
        _typed(diagnostic, AnalysisDiagnostic)
    _typed(quality.existing_results, tuple)
    for result in quality.existing_results:
        _typed(result, AnalysisResult)
        _source(result.source, source)


def _provenance(
    provenance: AnalysisProvenance | None,
    configuration: StageConfiguration,
    source: ImportSuccess,
) -> None:
    """Require calculation provenance to match the source and declared algorithm."""
    _typed(provenance, AnalysisProvenance)
    assert provenance is not None
    _require(
        (provenance.source.sha256, provenance.source.byte_count)
        == (source.source_sha256, source.byte_count),
        "Calculation provenance belongs to another source",
    )
    _require(
        provenance.algorithm == configuration.algorithm,
        "Calculation algorithm differs from stage configuration",
    )


def _stage(
    availability: StageAvailability,
    payload: object,
    quality: AnalysisQuality,
    provenance: AnalysisProvenance | None,
    configuration: StageConfiguration,
    source: ImportSuccess,
) -> bool:
    """Validate stage state/payload/provenance and return whether data is available."""
    _typed(availability, StageAvailability)
    _typed(availability.state, AvailabilityState)
    if availability.reason is not None:
        _typed(availability.reason, AnalysisDiagnostic)
    available = availability.state is AvailabilityState.AVAILABLE
    _require(
        available == (availability.reason is None),
        "Availability and exclusion reason disagree",
    )
    _require(available == (payload is not None), "Availability and payload disagree")
    _quality(quality, source)
    if available:
        _provenance(provenance, configuration, source)
    else:
        _require(provenance is None, "Unavailable stages have no calculation provenance")
    return available


def _samples(samples: SampleValues | None, count: int) -> None:
    """Require an existing immutable scalar buffer matching the source row count."""
    _typed(samples, SampleValues)
    assert samples is not None
    _require(samples.shape == (count,), "Sample buffer shape differs from the scalar source axis")


def _channels(channels: ForceChannels | None, count: int) -> None:
    """Require exactly three immutable scalar channels in the declared axis order."""
    _typed(channels, tuple)
    assert channels is not None
    _require(len(channels) == 3, "Forces require vertical, lateral and longitudinal channels")
    for samples in channels:
        _samples(samples, count)


def _events(
    events: EventAnalysis,
    configuration: StageConfiguration | None,
    source: ImportSuccess,
    count: int,
) -> None:
    """Validate event result representation, not event detection or duration rules."""
    _typed(events.status, EventEvaluationState)
    _require(events.configuration == configuration, "Event configuration differs from snapshot")
    _quality(events.quality, source)
    if events.status is EventEvaluationState.NOT_EVALUATED:
        _typed(events.reason, AnalysisDiagnostic)
        _require(
            events.events is None and events.provenance is None,
            "Unevaluated events cannot carry results or calculation provenance",
        )
        return
    _typed(configuration, StageConfiguration)
    assert configuration is not None
    _require(events.reason is None, "Evaluated events cannot have an exclusion reason")
    _require(
        events.input.availability.state is AvailabilityState.AVAILABLE,
        "Event evaluation requires available input",
    )
    _typed(events.events, tuple)
    assert events.events is not None
    _provenance(events.provenance, configuration, source)
    for event in events.events:
        _typed(event, AirtimeEvent)
        indices = (event.first_sample, event.minimum_sample, event.last_sample)
        for index in indices:
            _require(type(index) is int, "Event indices must be integers")
        _require(
            0 <= event.first_sample <= event.minimum_sample <= event.last_sample < count,
            "Event indices are outside their source interval",
        )
        channels = events.input.channels
        assert channels is not None
        _require(
            channels[0].valid_rows[event.minimum_sample],
            "Event minimum refers to a missing vertical sample",
        )
        for number in (event.duration_seconds, event.minimum_vertical_g):
            _require(
                type(number) in (int, float) and isfinite(number),
                "Event values must be finite numbers",
            )
        _require(event.duration_seconds >= 0, "Event duration must not be negative")
        if event.onset_g_per_second is not None:
            _require(
                type(event.onset_g_per_second) in (int, float)
                and isfinite(event.onset_g_per_second),
                "Event onset must be finite",
            )
        _typed(event.category, VerticalContext)
        _require(
            event.category
            in (
                VerticalContext.FLOATER_AIRTIME,
                VerticalContext.AIRTIME,
                VerticalContext.STRONG_AIRTIME,
                VerticalContext.EJECTOR_AIRTIME,
            ),
            "Airtime events require an airtime category",
        )
        _require(
            type(event.start_incomplete) is bool and type(event.end_incomplete) is bool,
            "Event completeness requires booleans",
        )
