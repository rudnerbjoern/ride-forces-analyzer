"""Recording container contracts and explicitly pending analysis behavior."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import json

import numpy as np
import pytest

from ride_forces_analyzer.analysis.models import (
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    CapabilityState,
    EvidenceState,
    ProfileName,
    SampleValues,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisFailed,
    AnalysisInvalidated,
    AnalysisQuality,
    AnalysisStage,
    AnalysisState,
    AnalysisTime,
    AnalysisUpdated,
    AvailabilityState,
    EventAnalysis,
    EventEvaluationState,
    ForceSeries,
    OrientationSeries,
    ProjectedForces,
    RecordingAnalysis,
    RequestStatus,
    SampleContext,
    SmoothedForces,
    StageAvailability,
    StageConfiguration,
    VerticalContext,
    prepare_recording_analysis,
)
from ride_forces_analyzer.importers import ImportSuccess, Severity, import_forces_bytes

NOW = datetime(2026, 10, 20, tzinfo=UTC)
PENDING = "Recording analysis operations are intentionally NotImplementedError stubs"


@pytest.fixture
def analysis() -> RecordingAnalysis:
    source = import_forces_bytes(
        json.dumps(
            {
                "schemaVersion": "2.2.0",
                "device": "Apple Watch",
                "sampleRate": 50,
                "accelerationSequence": [{"x": "0", "y": "0", "z": "1"}] * 3,
                "startIndex": 1,
                "endIndex": 2,
            },
        ).encode(),
    )
    assert isinstance(source, ImportSuccess)
    profile = AnalysisProfile(
        name=ProfileName.RIDER_CALIBRATED,
        policy_references=("Synthetic container fixture; no source qualification",),
        assumptions=("Synthetic force channels are supplied, not calculated",),
        allow_provisional=True,
    )
    configuration = AnalysisConfiguration(
        profile=profile,
        projection=StageConfiguration("synthetic-projection", "1"),
        smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 1),)),
        orientation=StageConfiguration("source-gravity-tilt", "1"),
        context=StageConfiguration("synthetic-context", "1"),
    )
    time = AnalysisTime(
        TimeBasis(TimeBasisKind.INFERRED_UNIFORM, source.recording.motion.sample_rate),
        (0, 1, 2),
        1,
    )
    quality = AnalysisQuality(capabilities=(("forces", CapabilityState.PROVISIONAL),))
    available = StageAvailability(AvailabilityState.AVAILABLE)
    provenance = AnalysisProvenance(
        source.recording.source.provenance,
        "test",
        configuration.projection.algorithm,
        NOW,
    )
    projected = ProjectedForces(
        source,
        time,
        configuration.projection,
        available,
        (
            SampleValues(np.array([1.0, 1.0, 1.0])),
            SampleValues(np.array([0.0, 0.0, 0.0])),
            SampleValues(np.array([0.0, 0.0, 0.0])),
        ),
        UnitAssignment(UnitLabel.DIMENSIONLESS, EvidenceState.ASSUMED, profile.assumptions),
        quality,
        provenance,
    )
    smoothed = SmoothedForces(
        projected,
        configuration.smoothing,
        available,
        projected.channels,
        quality,
        replace(provenance, algorithm=configuration.smoothing.algorithm),
    )
    missing_gravity = AnalysisDiagnostic("MISSING_GRAVITY", Severity.INFO, "No source gravity")
    orientation = OrientationSeries(
        source,
        time,
        configuration.orientation,
        StageAvailability(AvailabilityState.UNAVAILABLE, missing_gravity),
        None,
        UnitAssignment(UnitLabel.DEGREES, EvidenceState.ASSUMED, profile.assumptions),
        AnalysisQuality(diagnostics=(missing_gravity,)),
        None,
    )
    context = SampleContext(
        smoothed,
        configuration.context,
        available,
        (VerticalContext.NORMAL_GS,) * 3,
        quality,
        replace(provenance, algorithm=configuration.context.algorithm),
    )
    events = EventAnalysis(
        smoothed,
        None,
        EventEvaluationState.NOT_EVALUATED,
        None,
        AnalysisDiagnostic("EVENT_RULES_UNDEFINED", Severity.INFO, "No event rule contract"),
        quality,
        None,
    )
    return RecordingAnalysis(
        source,
        configuration,
        time,
        ForceSeries(projected, smoothed),
        orientation,
        context,
        events,
        quality,
        1,
    )


def test_new_snapshot_shares_existing_stage_objects_without_copying(
    analysis: RecordingAnalysis,
) -> None:
    changed = replace(analysis, revision=2)
    assert changed is not analysis
    assert changed.source is analysis.source
    assert changed.time is analysis.time
    assert changed.forces.projected is analysis.forces.projected
    assert changed.forces.projected.channels is analysis.forces.projected.channels
    assert changed.orientation is analysis.orientation
    with pytest.raises(FrozenInstanceError):
        setattr(changed, "revision", 3)
    with pytest.raises(FrozenInstanceError):
        setattr(changed.forces.projected, "channels", None)


def test_unavailable_orientation_keeps_raw_source_and_explicit_reason(
    analysis: RecordingAnalysis,
) -> None:
    orientation = analysis.orientation
    assert orientation.availability.state is AvailabilityState.UNAVAILABLE
    assert orientation.availability.reason is not None
    assert orientation.availability.reason.code == "MISSING_GRAVITY"
    assert orientation.values is None
    assert analysis.source.recording.motion.acceleration[1].z == 1
    assert analysis.source.recording.source.original_bytes
    assert analysis.forces.projected.quality.capabilities == (
        ("forces", CapabilityState.PROVISIONAL),
    )


def test_not_evaluated_events_are_distinct_from_evaluated_empty(
    analysis: RecordingAnalysis,
) -> None:
    not_evaluated = analysis.events
    evaluated = replace(
        not_evaluated,
        status=EventEvaluationState.EVALUATED,
        events=(),
        reason=None,
        configuration=StageConfiguration("synthetic-event-rules", "1"),
    )
    assert not_evaluated.events is None and not_evaluated.reason is not None
    assert evaluated.events == () and evaluated.status is EventEvaluationState.EVALUATED


def test_request_state_distinguishes_retained_snapshot_from_requested_configuration(
    analysis: RecordingAnalysis,
) -> None:
    requested = replace(
        analysis.configuration,
        smoothing=replace(analysis.configuration.smoothing, parameters=(("window_samples", 5),)),
    )
    dirty = frozenset((AnalysisStage.SMOOTHING, AnalysisStage.CONTEXT, AnalysisStage.EVENTS))
    state = AnalysisState(
        analysis.source.source_sha256,
        analysis,
        requested,
        2,
        RequestStatus.PENDING,
        dirty,
    )
    invalidated = AnalysisInvalidated(analysis.source.source_sha256, 2, dirty)
    failure = AnalysisFailed(
        analysis.source.source_sha256,
        2,
        dirty,
        AnalysisDiagnostic("RECALCULATION_FAILED", Severity.ERROR, "Calculation failed"),
    )
    failed_state = replace(state, status=RequestStatus.FAILED, failure=failure.failure)
    assert state.snapshot is failed_state.snapshot is analysis
    assert state.snapshot is not None
    assert state.snapshot.revision == 1 and state.requested_revision == 2
    assert state.snapshot.configuration is not state.requested_configuration
    assert invalidated.dirty_stages == failure.affected_stages
    assert AnalysisStage.ORIENTATION not in dirty and AnalysisStage.PROJECTION not in dirty
    update = AnalysisUpdated(analysis.source.source_sha256, 1, frozenset(), analysis)
    assert update.snapshot is analysis and update.revision != state.requested_revision


def test_calculation_and_access_operations_remain_unimplemented(
    analysis: RecordingAnalysis,
) -> None:
    with pytest.raises(NotImplementedError, match="RecordingAnalysis.sample"):
        analysis.sample(0)
    with pytest.raises(NotImplementedError, match="RecordingAnalysis.with_configuration"):
        analysis.with_configuration(analysis.configuration, revision=2, calculation_time=NOW)
    with pytest.raises(NotImplementedError, match="RecordingAnalysis.with_smoothing"):
        analysis.with_smoothing(5, revision=2, calculation_time=NOW)
    with pytest.raises(NotImplementedError, match="prepare_recording_analysis"):
        prepare_recording_analysis(
            analysis.source,
            analysis.configuration,
            revision=1,
            calculation_time=NOW,
        )


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_pending_sample_view_preserves_source_time_and_unavailable_orientation(
    analysis: RecordingAnalysis,
) -> None:
    sample = analysis.sample(1)
    assert sample.index == 1 and sample.raw is analysis.source.recording.motion.acceleration[1]
    assert sample.recording_seconds == pytest.approx(0.02)
    assert sample.replay_seconds == 0
    assert sample.smoothed is not None and sample.smoothed.vertical == 1
    assert sample.context is VerticalContext.NORMAL_GS
    assert sample.orientation_degrees is None
    assert sample.orientation_availability == analysis.orientation.availability


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_pending_smoothing_reuses_projection_time_and_orientation(
    analysis: RecordingAnalysis,
) -> None:
    changed = analysis.with_smoothing(5, revision=2, calculation_time=NOW)
    assert changed is not analysis and changed.revision == 2
    assert changed.source is analysis.source and changed.time is analysis.time
    assert changed.forces.projected is analysis.forces.projected
    assert changed.orientation is analysis.orientation
    assert changed.forces.smoothed is not analysis.forces.smoothed
    assert changed.context.input is changed.forces.smoothed
    assert changed.events.input is changed.forces.smoothed


@pytest.mark.parametrize(
    "defect",
    ("available_without_data", "not_evaluated_with_events", "length"),
)
def test_validation_rejects_inconsistent_stage_payloads(
    analysis: RecordingAnalysis,
    defect: str,
) -> None:
    if defect == "available_without_data":
        invalid = replace(
            analysis,
            forces=replace(
                analysis.forces,
                projected=replace(analysis.forces.projected, channels=None),
            ),
        )
    elif defect == "not_evaluated_with_events":
        invalid = replace(analysis, events=replace(analysis.events, events=()))
    else:
        invalid = replace(
            analysis,
            context=replace(analysis.context, labels=(VerticalContext.NORMAL_GS,)),
        )
    with pytest.raises(ValueError):
        invalid.validate()
