"""Recording-analysis containers with explicit structural snapshot validation.

Constructors store references without validation or calculation. Call
``RecordingAnalysis.validate`` before trusting a snapshot's structure. It checks
source/time correspondence, availability, payloads and stage dependencies, not
scientific correctness. Supply immutable tuples/frozen sets; inputs are never
copied or normalized. Assigning frozen fields raises ``FrozenInstanceError``.
Preparation, sample access and recalculation still raise ``NotImplementedError``.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.importers import ImportSuccess

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


class AnalysisStage(StrEnum):
    """Stable identifiers for independently reusable or invalidated analysis stages."""

    TIME = "time"
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
    """

    profile: AnalysisProfile
    projection: StageConfiguration
    smoothing: StageConfiguration
    orientation: StageConfiguration
    context: StageConfiguration
    events: StageConfiguration | None = None
    context_input: AnalysisStage = AnalysisStage.SMOOTHING
    events_input: AnalysisStage = AnalysisStage.SMOOTHING


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
    """

    source: ImportSuccess
    time: AnalysisTime
    configuration: StageConfiguration
    availability: StageAvailability
    channels: ForceChannels | None  # Vertical, lateral, longitudinal, in this order.
    unit: UnitAssignment
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None


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
    """

    projection: ProjectedForces
    configuration: StageConfiguration
    availability: StageAvailability
    channels: ForceChannels | None
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None


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
        source: Recording supplying gravity and stored vertical direction.
        time: Explicit correspondence for orientation rows, without invented data.
        configuration: Tilt algorithm/parameters, not yaw or track heading.
        availability: Whole-stage presence or reason prerequisites are absent.
        values: Immutable tilt samples with validity, or None when unavailable.
        unit: Degree unit assignment and evidence.
        quality: Missing/zero-gravity diagnostics and scientific limitations.
        provenance: Original tilt calculation provenance, or None if not calculated.
    """

    source: ImportSuccess
    time: AnalysisTime
    configuration: StageConfiguration
    availability: StageAvailability
    values: SampleValues | None
    unit: UnitAssignment
    quality: AnalysisQuality
    provenance: AnalysisProvenance | None


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

    This container defines no thresholds, minimum duration or boundary policy.
    Display-label confirmation times do not establish domain-event duration.

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
    graph without changing values or copying buffers. Numerical processing and
    sample access remain unimplemented.

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
        _quality(self.quality, self.source)
        count = len(self.time.source_indices)
        projected, smoothed = self.forces.projected, self.forces.smoothed
        orientation, context, events = self.orientation, self.context, self.events
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

    def sample(self, index: int) -> AnalyzedSample:
        """Reserve access to one source sample with explicit missing derived values.

        Args:
            index: Original source sample index to inspect.

        Returns:
            Planned: AnalyzedSample with source values, time, forces, orientation,
            context and quality. Currently no sample is returned.

        Raises:
            NotImplementedError: Always, including for invalid indices; sample
                access and index validation are not implemented.
        """
        raise NotImplementedError("RecordingAnalysis.sample is not implemented")

    def with_configuration(
        self,
        configuration: AnalysisConfiguration,
        *,
        revision: int,
        calculation_time: datetime,
    ) -> RecordingAnalysis:
        """Reserve reconfiguration with reuse of compatible retained upstream stages.

        Args:
            configuration: Requested effective analysis configuration.
            revision: New service request revision, distinct from this snapshot's.
            calculation_time: Caller-supplied timezone-aware UTC calculation time.

        Returns:
            Planned: Consistent RecordingAnalysis sharing unchanged stage objects.
            Currently no result is calculated or returned.

        Raises:
            NotImplementedError: Always; no dependency comparison, parameter
                validation or recalculation is implemented.
        """
        raise NotImplementedError("RecordingAnalysis.with_configuration is not implemented")

    def with_smoothing(
        self,
        window_samples: int,
        *,
        revision: int,
        calculation_time: datetime,
    ) -> RecordingAnalysis:
        """Reserve a smoothing change that retains projection, time and orientation.

        Args:
            window_samples: Requested filter window in source samples; the
                intended centered-mean contract accepts odd integers from 1 to 51.
            revision: New service request revision for the changed configuration.
            calculation_time: Caller-supplied timezone-aware UTC calculation time.

        Returns:
            Planned: RecordingAnalysis with replaced smoothing/dependent stages
            and shared upstream objects. Currently no result is returned.

        Raises:
            NotImplementedError: Always; filtering and window validation are not
                implemented, including for invalid window values.
        """
        raise NotImplementedError("RecordingAnalysis.with_smoothing is not implemented")


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


def prepare_recording_analysis(
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
    *,
    revision: int,
    calculation_time: datetime,
) -> RecordingAnalysis:
    """Reserve initial snapshot preparation independently of presentation and storage.

    Args:
        source: Successful lossless import retaining original bytes and metadata.
        configuration: Effective stage configurations and scientific policy.
        revision: Service request revision assigned to the planned result.
        calculation_time: Caller-supplied timezone-aware UTC calculation time.

    Returns:
        Planned: Consistent RecordingAnalysis with prepared or explicitly
        unavailable stages. Currently no analysis is calculated or returned.

    Raises:
        NotImplementedError: Always; initial preparation is not implemented.
    """
    raise NotImplementedError("prepare_recording_analysis is not implemented")


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
