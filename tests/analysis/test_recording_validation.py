"""Structural validation preserves source identity, missingness and shared stages."""

from dataclasses import replace
import json
from typing import cast

import numpy as np
import pytest

from ride_forces_analyzer.analysis.models import (
    AnalysisChannel,
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisResult,
    CapabilityState,
    ParameterValue,
    QuantityKind,
    SampleValues,
    SourceSequence,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
)
from ride_forces_analyzer.analysis.recording import (
    AirtimeEvent,
    AnalysisQuality,
    AnalysisStage,
    AvailabilityState,
    EventEvaluationState,
    ForceChannels,
    ForceSeries,
    ProjectedForces,
    RecordingAnalysis,
    SmoothedForces,
    StageAvailability,
    StageConfiguration,
    VerticalContext,
)
from ride_forces_analyzer.domain import SampleRate, ValueOrigin
from ride_forces_analyzer.importers import ImportSuccess, Severity, import_forces_bytes
from tests.analysis.test_recording import analysis as analysis


def _linked(
    snapshot: RecordingAnalysis,
    *,
    projection: ProjectedForces | None = None,
    smoothing: SmoothedForces | None = None,
) -> RecordingAnalysis:
    """Replace test force stages while keeping their consumers bound consistently."""
    projected = snapshot.forces.projected if projection is None else projection
    smoothed = snapshot.forces.smoothed if smoothing is None else smoothing
    smoothed = replace(smoothed, projection=projected)
    return replace(
        snapshot,
        forces=ForceSeries(projected, smoothed),
        context=replace(
            snapshot.context,
            input=projected
            if snapshot.configuration.context_input is AnalysisStage.PROJECTION
            else smoothed,
        ),
        events=replace(
            snapshot.events,
            input=projected
            if snapshot.configuration.events_input is AnalysisStage.PROJECTION
            else smoothed,
        ),
    )


@pytest.fixture
def evaluated(analysis: RecordingAnalysis) -> RecordingAnalysis:
    configuration = StageConfiguration("synthetic-events", "1", (("option", 0.5),))
    provenance = analysis.context.provenance
    assert provenance is not None
    event = AirtimeEvent(0, 2, 0.04, 1.0, 1, None, VerticalContext.AIRTIME, True, False)
    return replace(
        analysis,
        configuration=replace(analysis.configuration, events=configuration),
        events=replace(
            analysis.events,
            configuration=configuration,
            status=EventEvaluationState.EVALUATED,
            events=(event,),
            reason=None,
            provenance=replace(provenance, algorithm=configuration.algorithm),
        ),
    )


def test_validation_preserves_all_references_bytes_and_provenance(
    analysis: RecordingAnalysis,
) -> None:
    source, forces, time, orientation = (
        analysis.source,
        analysis.forces,
        analysis.time,
        analysis.orientation,
    )
    original = source.recording.source.original_bytes
    provenance = forces.projected.provenance
    assert provenance is not None
    result = AnalysisResult(
        source,
        AnalysisProfile(),
        replace(provenance, algorithm="raw-snapshot"),
        (
            AnalysisChannel(
                "raw-x",
                QuantityKind.SOURCE_VALUES,
                CapabilityState.VERIFIED,
                SourceSequence.ACCELERATION,
                samples=SampleValues(np.array([0.0])),
                source_indices=(0,),
                columns=("x",),
            ),
        ),
    )
    snapshot = replace(analysis, quality=AnalysisQuality(existing_results=(result,)))
    assert snapshot.validate() is None
    assert snapshot.source is source and snapshot.time is time
    assert snapshot.forces is forces and snapshot.orientation is orientation
    assert source.recording.source.original_bytes is original
    assert snapshot.quality.existing_results[0] is result
    assert forces.projected.quality.capabilities == (("forces", CapabilityState.PROVISIONAL),)


def test_index_only_time_retains_source_axis_without_inventing_seconds(
    analysis: RecordingAnalysis,
) -> None:
    time = replace(analysis.time, basis=TimeBasis())
    snapshot = _linked(
        replace(analysis, time=time),
        projection=replace(analysis.forces.projected, time=time),
    )
    replace(snapshot, orientation=replace(snapshot.orientation, time=time)).validate()


@pytest.mark.parametrize(
    "indices,origin,basis,message",
    [
        ((0, 1), 1, None, "complete original"),
        ((0, 2, 1), 1, None, "complete original"),
        ((0, 1, 1), 1, None, "complete original"),
        ((0, 1, 3), 1, None, "complete original"),
        ((False, 1, 2), 1, None, "integers"),
        ((0, 1, 2), True, None, "integer"),
        ((0, 1, 2), 0, None, "source start marker"),
        ((0, 1, 2), 1, TimeBasis(TimeBasisKind.SOURCE_UNVERIFIED), "explicit source sample rate"),
        (
            (0, 1, 2),
            1,
            TimeBasis(TimeBasisKind.INFERRED_UNIFORM, SampleRate(25, ValueOrigin.SOURCE)),
            "rate/value provenance",
        ),
        (
            (0, 1, 2),
            1,
            TimeBasis(TimeBasisKind.INFERRED_UNIFORM, SampleRate()),
            "rate/value provenance",
        ),
    ],
)
def test_invalid_time_mapping_is_rejected(
    analysis: RecordingAnalysis,
    indices: tuple[int, ...],
    origin: int,
    basis: TimeBasis | None,
    message: str,
) -> None:
    time = replace(
        analysis.time,
        source_indices=indices,
        replay_origin=origin,
        basis=analysis.time.basis if basis is None else basis,
    )
    with pytest.raises(ValueError, match=message):
        replace(analysis, time=time).validate()


@pytest.mark.parametrize("revision", (-1, True, 1.0))
def test_invalid_snapshot_revision_is_rejected(analysis: RecordingAnalysis, revision: int) -> None:
    with pytest.raises(ValueError, match="revision"):
        replace(analysis, revision=revision).validate()


@pytest.mark.parametrize(
    "configuration,error,message",
    [
        (StageConfiguration(" ", "1"), ValueError, "Identifier"),
        (StageConfiguration("test", ""), ValueError, "Identifier"),
        (StageConfiguration("test", "1", (("", 1),)), ValueError, "Identifier"),
        (StageConfiguration("test", "1", (("a", 1), ("a", 2))), ValueError, "unique"),
        (StageConfiguration("test", "1", (("a", float("nan")),)), ValueError, "finite"),
        (StageConfiguration("test", "1", (("a", float("inf")),)), ValueError, "finite"),
        (
            StageConfiguration("test", "1", (("a", cast(ParameterValue, [])),)),
            ValueError,
            "immutable scalars",
        ),
        (
            StageConfiguration(
                "test",
                "1",
                cast(tuple[tuple[str, ParameterValue], ...], (("a",),)),
            ),
            ValueError,
            "pairs",
        ),
        (
            StageConfiguration("test", "1", cast(tuple[tuple[str, ParameterValue], ...], [])),
            TypeError,
            "tuple",
        ),
    ],
)
def test_invalid_stage_metadata_is_rejected(
    analysis: RecordingAnalysis,
    configuration: StageConfiguration,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        replace(
            analysis,
            configuration=replace(analysis.configuration, smoothing=configuration),
        ).validate()


def test_scalar_parameters_and_projection_input_are_supported(analysis: RecordingAnalysis) -> None:
    parameters = (
        ("text", "value"),
        ("enabled", True),
        ("number", 3),
        ("optional", None),
        ("ratio", 0.5),
    )
    configuration = replace(
        analysis.configuration,
        projection=replace(analysis.configuration.projection, parameters=parameters),
        context_input=AnalysisStage.PROJECTION,
        events_input=AnalysisStage.PROJECTION,
    )
    _linked(
        replace(analysis, configuration=configuration),
        projection=replace(analysis.forces.projected, configuration=configuration.projection),
    ).validate()


@pytest.mark.parametrize(
    "selector",
    (AnalysisStage.TIME, AnalysisStage.ORIENTATION, AnalysisStage.CONTEXT),
)
def test_non_force_input_selector_is_rejected(
    analysis: RecordingAnalysis,
    selector: AnalysisStage,
) -> None:
    with pytest.raises(ValueError, match="force input stage"):
        replace(
            analysis,
            configuration=replace(analysis.configuration, context_input=selector),
        ).validate()


def test_source_and_calculation_identity_must_match(analysis: RecordingAnalysis) -> None:
    other = import_forces_bytes(analysis.source.recording.source.original_bytes + b" ")
    assert isinstance(other, ImportSuccess)
    with pytest.raises(ValueError, match="another source"):
        _linked(analysis, projection=replace(analysis.forces.projected, source=other)).validate()
    provenance = analysis.forces.projected.provenance
    assert provenance is not None
    for changed, message in (
        (replace(provenance, source=other.recording.source.provenance), "another source"),
        (replace(provenance, algorithm="other-algorithm"), "algorithm differs"),
    ):
        with pytest.raises(ValueError, match=message):
            _linked(
                analysis,
                projection=replace(analysis.forces.projected, provenance=changed),
            ).validate()


def test_stage_time_configuration_and_shared_dependencies_must_match(
    analysis: RecordingAnalysis,
) -> None:
    wrong_time = replace(analysis.time, replay_origin=0)
    with pytest.raises(ValueError, match="Stage time"):
        _linked(analysis, projection=replace(analysis.forces.projected, time=wrong_time)).validate()
    with pytest.raises(ValueError, match="shared projection"):
        replace(
            analysis,
            forces=replace(
                analysis.forces,
                smoothed=replace(
                    analysis.forces.smoothed,
                    projection=replace(analysis.forces.projected),
                ),
            ),
        ).validate()
    with pytest.raises(ValueError, match="Stage configuration"):
        replace(
            analysis,
            configuration=replace(analysis.configuration, context=StageConfiguration("other", "1")),
        ).validate()
    with pytest.raises(ValueError, match="configured shared force input"):
        replace(
            analysis,
            context=replace(analysis.context, input=analysis.forces.projected),
        ).validate()


@pytest.mark.parametrize(
    "defect",
    (
        "available_reason",
        "unavailable_reason",
        "unavailable_payload",
        "unavailable_provenance",
        "no_provenance",
        "bad_state",
    ),
)
def test_availability_payload_and_reason_are_consistent(
    analysis: RecordingAnalysis,
    defect: str,
) -> None:
    reason = AnalysisDiagnostic("UNAVAILABLE_INPUT", Severity.INFO, "Unavailable input")
    stage = analysis.forces.smoothed
    error: type[Exception] = ValueError
    if defect == "available_reason":
        stage = replace(stage, availability=StageAvailability(AvailabilityState.AVAILABLE, reason))
    elif defect == "unavailable_reason":
        stage = replace(stage, availability=StageAvailability(AvailabilityState.UNAVAILABLE))
    elif defect == "unavailable_payload":
        stage = replace(
            stage,
            availability=StageAvailability(AvailabilityState.UNAVAILABLE, reason),
        )
    elif defect == "unavailable_provenance":
        stage = replace(
            stage,
            availability=StageAvailability(AvailabilityState.UNAVAILABLE, reason),
            channels=None,
        )
    elif defect == "no_provenance":
        stage = replace(stage, provenance=None)
        error = TypeError
    else:
        stage = replace(stage, availability=StageAvailability(cast(AvailabilityState, "available")))
        error = TypeError
    with pytest.raises(error):
        _linked(analysis, smoothing=stage).validate()


@pytest.mark.parametrize("values", [None, (1.0, 2.0), (-1.0, 0.0, 1.0)])
def test_combined_requires_nonnegative_scalar_samples_matching_the_source(
    analysis: RecordingAnalysis,
    values: tuple[float, ...] | None,
) -> None:
    combined = SampleValues(np.array(values)) if values is not None else None
    snapshot = _linked(analysis, smoothing=replace(analysis.forces.smoothed, combined=combined))
    with pytest.raises(TypeError if values is None else ValueError):
        snapshot.validate()


def test_raw_fallback_and_unavailable_dependencies(analysis: RecordingAnalysis) -> None:
    reason = AnalysisDiagnostic("UNAVAILABLE_INPUT", Severity.INFO, "Missing calibration")
    unavailable = StageAvailability(AvailabilityState.UNAVAILABLE, reason)
    projection = replace(
        analysis.forces.projected,
        availability=unavailable,
        channels=None,
        provenance=None,
    )
    smoothing = replace(
        analysis.forces.smoothed,
        availability=unavailable,
        channels=None,
        combined=None,
        provenance=None,
    )
    raw = _linked(analysis, projection=projection, smoothing=smoothing)
    with pytest.raises(ValueError, match="Context requires available"):
        raw.validate()
    raw = replace(
        raw,
        context=replace(raw.context, availability=unavailable, labels=None, provenance=None),
    )
    raw.validate()
    assert raw.source is analysis.source
    assert raw.context.labels is None and raw.events.events is None
    with pytest.raises(ValueError, match="Smoothing requires"):
        _linked(analysis, projection=projection).validate()


@pytest.mark.parametrize("shape", ((2,), (3, 1)))
def test_sample_buffers_require_one_scalar_per_source_sample(
    analysis: RecordingAnalysis,
    shape: tuple[int, ...],
) -> None:
    channels = (SampleValues(np.ones(shape)),) * 3
    with pytest.raises(ValueError, match="buffer shape"):
        _linked(analysis, smoothing=replace(analysis.forces.smoothed, channels=channels)).validate()


def test_three_channels_and_dimensionless_unit_are_required(analysis: RecordingAnalysis) -> None:
    channels = analysis.forces.projected.channels
    assert channels is not None
    with pytest.raises(ValueError, match="three|vertical, lateral"):
        _linked(
            analysis,
            projection=replace(
                analysis.forces.projected,
                channels=cast(ForceChannels, channels[:2]),
            ),
        ).validate()
    with pytest.raises(ValueError, match="dimensionless"):
        _linked(
            analysis,
            projection=replace(analysis.forces.projected, unit=UnitAssignment()),
        ).validate()


def test_missing_force_rows_cannot_have_normal_context(analysis: RecordingAnalysis) -> None:
    channels = (SampleValues(np.array([1.0, np.nan, 1.0]), valid_rows=[True, False, True]),) * 3
    snapshot = _linked(analysis, smoothing=replace(analysis.forces.smoothed, channels=channels))
    with pytest.raises(ValueError, match="Missing vertical"):
        snapshot.validate()
    replace(
        snapshot,
        context=replace(
            snapshot.context,
            labels=(
                VerticalContext.NORMAL_GS,
                VerticalContext.UNAVAILABLE,
                VerticalContext.NORMAL_GS,
            ),
        ),
    ).validate()


def test_quality_retains_invalid_capability_without_promoting_it(
    analysis: RecordingAnalysis,
) -> None:
    quality = AnalysisQuality(capabilities=(("example", CapabilityState.INVALID),))
    replace(analysis, quality=quality).validate()
    assert quality.capabilities[0][1] is CapabilityState.INVALID
    with pytest.raises(ValueError, match="unique"):
        replace(
            analysis,
            quality=replace(quality, capabilities=quality.capabilities * 2),
        ).validate()
    with pytest.raises(ValueError, match="pairs"):
        replace(
            analysis,
            quality=replace(
                quality,
                capabilities=cast(tuple[tuple[str, CapabilityState], ...], (("broken",),)),
            ),
        ).validate()


def test_evaluated_events_accept_empty_results_and_optional_onset(
    evaluated: RecordingAnalysis,
) -> None:
    evaluated.validate()
    events = evaluated.events.events
    assert events is not None
    replace(evaluated, events=replace(evaluated.events, events=())).validate()
    replace(
        evaluated,
        events=replace(evaluated.events, events=(replace(events[0], onset_g_per_second=-3.0),)),
    ).validate()


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("first_sample", -1, "source interval"),
        ("last_sample", 3, "source interval"),
        ("minimum_sample", 4, "source interval"),
        ("first_sample", True, "integers"),
        ("duration_seconds", -1.0, "negative"),
        ("duration_seconds", float("nan"), "finite"),
        ("minimum_vertical_g", float("inf"), "finite"),
        ("onset_g_per_second", float("nan"), "finite"),
        ("category", VerticalContext.NORMAL_GS, "airtime category"),
        ("start_incomplete", 1, "booleans"),
    ],
)
def test_event_fields_are_structurally_validated(
    evaluated: RecordingAnalysis,
    field: str,
    value: object,
    message: str,
) -> None:
    events = evaluated.events.events
    assert events is not None
    event = replace(events[0], **{field: value})
    with pytest.raises(ValueError, match=message):
        replace(evaluated, events=replace(evaluated.events, events=(event,))).validate()


def test_event_states_require_matching_rules_input_and_reason(evaluated: RecordingAnalysis) -> None:
    with pytest.raises(ValueError, match="configuration differs"):
        replace(evaluated, configuration=replace(evaluated.configuration, events=None)).validate()
    reason = AnalysisDiagnostic("EXCLUDED", Severity.INFO, "No usable input")
    with pytest.raises(ValueError, match="exclusion reason"):
        replace(evaluated, events=replace(evaluated.events, reason=reason)).validate()
    unavailable = StageAvailability(AvailabilityState.UNAVAILABLE, reason)
    snapshot = _linked(
        evaluated,
        smoothing=replace(
            evaluated.forces.smoothed,
            availability=unavailable,
            channels=None,
            combined=None,
            provenance=None,
        ),
    )
    snapshot = replace(
        snapshot,
        context=replace(snapshot.context, availability=unavailable, labels=None, provenance=None),
    )
    with pytest.raises(ValueError, match="Event evaluation requires available"):
        snapshot.validate()


def test_event_minimum_cannot_reference_a_missing_sample(evaluated: RecordingAnalysis) -> None:
    channels = (SampleValues(np.array([1.0, np.nan, 1.0]), valid_rows=[True, False, True]),) * 3
    snapshot = _linked(evaluated, smoothing=replace(evaluated.forces.smoothed, channels=channels))
    snapshot = replace(
        snapshot,
        context=replace(
            snapshot.context,
            labels=(
                VerticalContext.NORMAL_GS,
                VerticalContext.UNAVAILABLE,
                VerticalContext.NORMAL_GS,
            ),
        ),
    )
    with pytest.raises(ValueError, match="minimum refers to a missing"):
        snapshot.validate()


@pytest.mark.parametrize("valid_gravity", (True, False))
def test_available_orientation_requires_gravity_and_explicit_vertical_direction(
    analysis: RecordingAnalysis,
    valid_gravity: bool,
) -> None:
    provenance = analysis.context.provenance
    assert provenance is not None
    orientation = replace(
        analysis.orientation,
        values=SampleValues(np.zeros(3)),
        availability=StageAvailability(AvailabilityState.AVAILABLE),
        provenance=replace(provenance, algorithm=analysis.configuration.orientation.algorithm),
    )
    with pytest.raises(ValueError, match="source gravity"):
        replace(analysis, orientation=orientation).validate()
    payload: dict[str, object] = json.loads(analysis.source.recording.source.original_bytes)
    payload["gravitySequence"] = [{"x": "0", "y": "0", "z": "1" if valid_gravity else "0"}] * 3
    if not valid_gravity:
        orientation = replace(
            orientation,
            values=SampleValues(np.full(3, np.nan), valid_rows=[False] * 3),
        )
    source = import_forces_bytes(json.dumps(payload).encode())
    assert isinstance(source, ImportSuccess)
    for include_direction in (False, True):
        if include_direction:
            payload["verticalDirectionVector"] = {"x": "0", "y": "0", "z": "1"}
            source = import_forces_bytes(json.dumps(payload).encode())
            assert isinstance(source, ImportSuccess)
        projected = analysis.forces.projected
        assert projected.provenance is not None and analysis.forces.smoothed.provenance is not None
        snapshot = _linked(
            replace(analysis, source=source),
            projection=replace(
                projected,
                source=source,
                provenance=replace(projected.provenance, source=source.recording.source.provenance),
            ),
            smoothing=replace(
                analysis.forces.smoothed,
                provenance=replace(
                    analysis.forces.smoothed.provenance,
                    source=source.recording.source.provenance,
                ),
            ),
        )
        assert orientation.provenance is not None and snapshot.context.provenance is not None
        snapshot = replace(
            snapshot,
            orientation=replace(
                orientation,
                source=source,
                provenance=replace(
                    orientation.provenance,
                    source=source.recording.source.provenance,
                ),
            ),
            context=replace(
                snapshot.context,
                provenance=replace(
                    snapshot.context.provenance,
                    source=source.recording.source.provenance,
                ),
            ),
        )
        if include_direction:
            snapshot.validate()
            if not valid_gravity:
                with pytest.raises(ValueError, match="Zero gravity"):
                    replace(
                        snapshot,
                        orientation=replace(snapshot.orientation, values=SampleValues(np.zeros(3))),
                    ).validate()
            with pytest.raises(ValueError, match="degrees"):
                replace(
                    snapshot,
                    orientation=replace(snapshot.orientation, unit=UnitAssignment()),
                ).validate()
        else:
            with pytest.raises(ValueError, match="vertical direction"):
                snapshot.validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", None),
        ("configuration", None),
        ("time", None),
        ("forces", None),
        ("context", None),
        ("quality", None),
    ],
)
def test_wrong_top_level_types_are_rejected(
    analysis: RecordingAnalysis,
    field: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match="Expected"):
        replace(analysis, **{field: value}).validate()


def test_mutable_channel_and_label_collections_are_rejected(analysis: RecordingAnalysis) -> None:
    channels = analysis.forces.projected.channels
    assert channels is not None
    with pytest.raises(TypeError, match="tuple"):
        _linked(
            analysis,
            projection=replace(
                analysis.forces.projected,
                channels=cast(ForceChannels, list(channels)),
            ),
        ).validate()
    with pytest.raises(TypeError, match="tuple"):
        replace(
            analysis,
            context=replace(
                analysis.context,
                labels=cast(tuple[VerticalContext, ...], [VerticalContext.NORMAL_GS] * 3),
            ),
        ).validate()
