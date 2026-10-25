"""Immutable analysis stages, availability, quality and domain events.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from enum import StrEnum

from ride_forces_analyzer.importers import ImportSuccess

from ..calibration import (
    CalibrationBasis,
)
from ..models import (
    AnalysisDiagnostic,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    SampleValues,
    TimeBasis,
    UnitAssignment,
)

from .configuration import (
    StageConfiguration,
)


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
