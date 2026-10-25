"""Recording-analysis containers with explicit structural snapshot validation.

Constructors store references without validation or calculation. Call
``RecordingAnalysis.validate`` before trusting a snapshot's structure. It checks
source/time correspondence, availability, payloads and stage dependencies, not
scientific correctness. Supply immutable tuples/frozen sets; inputs are never
copied or normalized. Assigning frozen fields raises ``FrozenInstanceError``.
Sample access reads prepared buffers. Reconfiguration delegates to
analysis.preparation, sharing compatible stages without retaining snapshot history.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from math import isfinite

from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess

from ._validation import require as _require, require_type as _typed
from .calibration import (
    CalibrationBasis,
    CalibrationOverrides,
    CalibrationReferences,
    REFERENCE_WINDOW_SAMPLES,
)
from .models import (
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    ParameterValue,
    SampleValues,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from .projection import source_directions


class AnalysisStage(StrEnum):
    """Stable identifiers for independently reusable or invalidated analysis stages.

    Attributes:
        TIME: Named value for time (`time`).
        CALIBRATION: Named value for calibration (`calibration`).
        PROJECTION: Named value for projection (`projection`).
        SMOOTHING: Named value for smoothing (`smoothing`).
        ORIENTATION: Named value for orientation (`orientation`).
        CONTEXT: Named value for context (`context`).
        EVENTS: Named value for events (`events`).
    """

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

    Attributes:
        AVAILABLE: Named value for available (`available`).
        UNAVAILABLE: Named value for unavailable (`unavailable`).
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EventEvaluationState(StrEnum):
    """Distinguish completed event evaluation from evaluation that did not occur.

    EVALUATED permits an empty event tuple. NOT_EVALUATED requires a reason
    and an absent event collection, not an empty one.

    Attributes:
        EVALUATED: Named value for evaluated (`evaluated`).
        NOT_EVALUATED: Named value for not evaluated (`not_evaluated`).
    """

    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class RequestStatus(StrEnum):
    """Request lifecycle: no request, pending work, published result or failure.

    This status describes the service request, not the retained snapshot's age
    or scientific capabilities. A failed request can retain an older snapshot.

    Attributes:
        IDLE: Named value for idle (`idle`).
        PENDING: Named value for pending (`pending`).
        READY: Named value for ready (`ready`).
        FAILED: Named value for failed (`failed`).
    """

    IDLE = "idle"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class VerticalContext(StrEnum):
    """Language-independent identifiers for provisional per-sample context labels.

    UNAVAILABLE denotes a missing/invalid sample in an otherwise prepared
    context series. It does not establish a whole stage's availability.

    Attributes:
        HEAVY_GS: Named value for heavy gs (`heavy_gs`).
        NORMAL_GS: Named value for normal gs (`normal_gs`).
        LIGHT_GS: Named value for light gs (`light_gs`).
        FLOATER_AIRTIME: Named value for floater airtime (`floater_airtime`).
        AIRTIME: Named value for airtime (`airtime`).
        STRONG_AIRTIME: Named value for strong airtime (`strong_airtime`).
        EJECTOR_AIRTIME: Named value for ejector airtime (`ejector_airtime`).
        UNAVAILABLE: Named value for unavailable (`unavailable`).
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
            AssertionError: If a required internal invariant does not hold.
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
        validate_configuration(self.configuration)
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
                source_directions(self.source.recording)[0] is not None,
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
        from .preparation import reconfigure_recording_analysis

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


def _force_sample(channels: ForceChannels | None, index: int) -> ForceSample | None:
    """Read one force row; absent or invalid rows remain absent."""
    if channels is None or not all(axis.valid_rows[index] for axis in channels):
        return None
    return ForceSample(*(float(axis.values[index]) for axis in channels))


def _text(value: str) -> None:
    """Require a nonempty textual identifier, preserving the supplied spelling."""
    _typed(value, str)
    _require(bool(value.strip()), "Identifier must contain text")


def validate_configuration(configuration: AnalysisConfiguration) -> None:
    """Validate configuration metadata independently of algorithm admission.

    Args:
        configuration: Configuration whose types and immutable metadata are checked.

    Returns:
        None without changing the supplied configuration.

    Raises:
        TypeError: A field has an incompatible type or mutable collection.
        ValueError: Markers, stage selectors or identifiers are invalid.
    """
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
