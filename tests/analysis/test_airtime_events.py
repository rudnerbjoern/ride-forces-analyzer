"""Separate event rules: source intervals, coverage, onset and immutable reuse."""

from dataclasses import replace
from datetime import timedelta
from math import nan
from unittest.mock import Mock

import numpy as np
import pytest

from ride_forces_analyzer.analysis import events as detection, recording
from ride_forces_analyzer.analysis.models import CapabilityState, SampleValues
from ride_forces_analyzer.analysis.recording import (
    AnalysisStage,
    EventEvaluationState,
    RecordingAnalysis,
    StageConfiguration,
    VerticalContext,
    source_app_configuration,
)
from ride_forces_analyzer.analysis.service import AnalysisService
from tests.analysis.test_recording_preparation import NOW, prepare_snapshot, synthetic_source


def snapshot_for(
    values: tuple[float, ...],
    rate: float = 10,
    **parameters: float,
) -> RecordingAnalysis:
    configuration = source_app_configuration()
    source = synthetic_source(
        sampleRate=rate,
        startIndex=0,
        accelerationSequence=[{"x": "0", "y": "0", "z": str(value)} for value in values],
        gravitySequence=[{"x": "0", "y": "0", "z": "1"}] * len(values),
    )
    return prepare_snapshot(
        replace(
            configuration,
            smoothing=StageConfiguration("centered-mean", "1", (("window_samples", 1),)),
            events=StageConfiguration("airtime-events", "1", tuple(parameters.items())),
        ),
        source,
    )


@pytest.mark.parametrize(
    "value,category",
    (
        (0.25, VerticalContext.FLOATER_AIRTIME),
        (-0.25, VerticalContext.FLOATER_AIRTIME),
        (-0.25001, VerticalContext.AIRTIME),
        (-0.5, VerticalContext.AIRTIME),
        (-0.50001, VerticalContext.STRONG_AIRTIME),
    ),
)
def test_event_category_bounds_and_truncated_constant_loading(
    value: float,
    category: VerticalContext,
) -> None:
    snapshot = snapshot_for((value,) * 4)
    result = snapshot.events
    assert result.status is EventEvaluationState.EVALUATED and result.events is not None
    assert len(result.events) == 1
    event = result.events[0]
    assert (event.first_sample, event.last_sample, event.minimum_sample) == (0, 3, 0)
    assert event.duration_seconds == 0.4 and event.minimum_vertical_g == value
    assert event.start_incomplete and event.end_incomplete
    assert event.category is category and event.onset_g_per_second == 0
    assert result.reason is None and result.provenance is not None
    assert result.provenance.algorithm == "airtime-events"
    assert result.quality.capabilities == (("events", CapabilityState.PROVISIONAL),)


def test_load_above_floater_bound_does_not_form_an_event() -> None:
    assert snapshot_for((0.25001,) * 4).events.events == ()


def test_minimum_duration_uses_qualifying_samples_and_complete_inclusive_bounds() -> None:
    result = snapshot_for((1, 0, 1, 0, 0, 1)).events.events
    assert result is not None and len(result) == 1
    event = result[0]
    assert (event.first_sample, event.last_sample) == (3, 4)
    assert event.duration_seconds == 0.2
    assert not event.start_incomplete and not event.end_incomplete


@pytest.mark.parametrize("rate,needed", ((25, 5), (50, 10), (59.94, 12)))
def test_minimum_duration_rounds_up_at_actual_source_rate(rate: float, needed: int) -> None:
    assert snapshot_for((1,) + (0,) * (needed - 1) + (1,), rate).events.events == ()
    result = snapshot_for((1,) + (0,) * needed + (1,), rate).events.events
    assert result is not None and len(result) == 1
    assert result[0].duration_seconds == needed / rate


def test_short_valid_interruptions_join_but_do_not_supply_minimum_airtime() -> None:
    result = snapshot_for((1, 0, 0, 1, 0, 0, 1, 1), maximum_interruption_seconds=0.1).events.events
    assert result is not None and len(result) == 1
    event = result[0]
    assert (event.first_sample, event.last_sample) == (1, 5) and event.duration_seconds == 0.5
    # The span is long enough, but one qualifying sample cannot satisfy two samples.
    assert (
        snapshot_for(
            (1, 0, 1, 1),
            maximum_interruption_seconds=0.2,
        ).events.events
        == ()
    )
    separated = snapshot_for(
        (1, 0, 0, 1, 1, 0, 0, 1),
        maximum_interruption_seconds=0.1,
    ).events.events
    assert separated is not None and [(e.first_sample, e.last_sample) for e in separated] == [
        (1, 2),
        (5, 6),
    ]


def test_pending_positive_tail_is_excluded_and_recorded_as_incomplete() -> None:
    result = snapshot_for((1, 0, 0, 1), maximum_interruption_seconds=0.1).events.events
    assert result is not None and len(result) == 1
    assert result[0].last_sample == 2 and result[0].duration_seconds == 0.2
    assert result[0].end_incomplete


def test_ejector_requires_strong_loading_and_recent_contiguous_decline() -> None:
    result = snapshot_for((1, 1, 1, -0.8, -0.9, -0.9, 1)).events.events
    assert result is not None and len(result) == 1
    event = result[0]
    assert event.category is VerticalContext.EJECTOR_AIRTIME
    assert event.minimum_sample == 4 and event.minimum_vertical_g == -0.9
    assert event.onset_g_per_second == pytest.approx(-9.5)
    # A gradual descent reaches strong loading after onset memory has expired.
    gradual = snapshot_for(
        (0, 0, -0.1, -0.2, -0.3, -0.4, -0.6, -0.7, 1),
    ).events.events
    assert gradual is not None and gradual[0].category is VerticalContext.STRONG_AIRTIME
    # Strong loading at the recording boundary has no observed rapid onset.
    initial = snapshot_for((-0.8, -0.8), minimum_duration_seconds=0.2).events.events
    assert initial is not None and initial[0].onset_g_per_second is None
    assert initial[0].category is VerticalContext.STRONG_AIRTIME


def test_onset_memory_expiry_and_positive_recovery_clear_ejector_qualification() -> None:
    expired = snapshot_for(
        (1, 1, 0, 0, 0, 0, 0, -0.55, -0.55, 1),
        onset_memory_seconds=0.1,
    ).events.events
    assert expired is not None and expired[0].category is VerticalContext.STRONG_AIRTIME
    recovered = snapshot_for(
        (1, 1, -0.1, -0.1, 0.3, -0.55, -0.55, 1),
        maximum_interruption_seconds=0.1,
        onset_window_seconds=0.1,
        ejector_onset_g_per_second=-10,
    ).events.events
    assert recovered is not None and recovered[0].category is VerticalContext.STRONG_AIRTIME
    retained = snapshot_for(
        (1, 1, -0.1, -0.1, 0.2, -0.55, -0.55, 1),
        onset_window_seconds=0.1,
        ejector_onset_g_per_second=-10,
    ).events.events
    assert retained is not None and retained[0].category is VerticalContext.EJECTOR_AIRTIME


def test_gaps_always_split_and_reset_onset_and_mark_incomplete_coverage() -> None:
    snapshot = snapshot_for((1, 0, 0, 0, -0.8, -0.8, 1), maximum_interruption_seconds=1)
    source = snapshot.forces.smoothed
    channels = source.channels
    assert channels is not None and snapshot.events.provenance is not None
    vertical = SampleValues(
        np.array([1, 0, 0, nan, -0.8, -0.8, 1]),
        valid_rows=(True, True, True, False, True, True, True),
    )
    source = replace(source, channels=(vertical, *channels[1:]))
    result = detection.evaluate_events(
        source,
        snapshot.configuration.events,
        10,
        snapshot.events.provenance,
    )
    assert result.events is not None and len(result.events) == 2
    first, second = result.events
    assert (first.first_sample, first.last_sample) == (1, 2)
    assert first.end_incomplete and not first.start_incomplete
    assert second.first_sample == 4 and second.start_incomplete and second.end_incomplete
    assert second.category is VerticalContext.STRONG_AIRTIME
    assert second.onset_g_per_second is None
    assert result.quality.diagnostics[-1].code == "EVENT_INPUT_GAPS"


def test_disabled_unavailable_empty_and_all_missing_results_remain_distinct() -> None:
    snapshot = snapshot_for((1, 1, 1))
    assert snapshot.events.status is EventEvaluationState.EVALUATED and snapshot.events.events == ()
    provenance = snapshot.events.provenance
    assert provenance is not None
    for source, configuration in (
        (snapshot.forces.smoothed, None),
        (replace(snapshot.forces.smoothed, channels=None), snapshot.configuration.events),
    ):
        result = detection.evaluate_events(source, configuration, 10, provenance)
        assert result.status is EventEvaluationState.NOT_EVALUATED
        assert result.reason is not None and result.events is None and result.provenance is None
    channels = snapshot.forces.smoothed.channels
    assert channels is not None
    missing = SampleValues(np.array([nan] * 3), valid_rows=(False,) * 3)
    result = detection.evaluate_events(
        replace(snapshot.forces.smoothed, channels=(missing, *channels[1:])),
        snapshot.configuration.events,
        10,
        provenance,
    )
    assert result.status is EventEvaluationState.NOT_EVALUATED


@pytest.mark.parametrize(
    "parameter,value",
    (
        ("unknown", 1),
        ("minimum_duration_seconds", 0),
        ("maximum_interruption_seconds", -1),
        ("floater_bound_g", -0.1),
        ("strong_bound_g", 0),
        ("onset_window_seconds", 0),
        ("ejector_onset_g_per_second", 0),
        ("onset_memory_seconds", -1),
        ("minimum_duration_seconds", True),
        ("minimum_duration_seconds", "0.2"),
        ("minimum_duration_seconds", float("inf")),
    ),
)
def test_unsupported_event_parameters_fail_explicitly(parameter: str, value: object) -> None:
    from typing import cast
    from ride_forces_analyzer.analysis.models import ParameterValue

    with pytest.raises(ValueError):
        detection.event_rules(
            StageConfiguration("airtime-events", "1", ((parameter, cast(ParameterValue, value)),)),
        )


@pytest.mark.parametrize("algorithm,version", (("unknown", "1"), ("airtime-events", "2")))
def test_unsupported_rules_terminate_service_request_and_keep_snapshot(
    algorithm: str,
    version: str,
) -> None:
    original = snapshot_for((1, 0, 0, 1))
    service = AnalysisService(original)
    service.request_configuration(
        replace(original.configuration, events=StageConfiguration(algorithm, version)),
        calculation_time=NOW,
    )
    state = service.get_state()
    assert state.snapshot is original and state.failure is not None
    assert state.failure.code == "ANALYSIS_FAILED"


def test_rules_and_context_changes_respect_independent_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = snapshot_for((1, 1, -0.8, -0.8, 1))
    detector = Mock(wraps=detection.evaluate_events)
    monkeypatch.setattr(detection, "evaluate_events", detector)
    monkeypatch.setattr(
        recording,
        "project_directions",
        Mock(side_effect=AssertionError("Projection")),
    )
    context_only = snapshot.with_configuration(
        replace(snapshot.configuration, context_input=AnalysisStage.PROJECTION),
        revision=4,
        calculation_time=NOW + timedelta(seconds=1),
    )
    assert context_only.events is snapshot.events and not detector.called
    rules_only = snapshot.with_configuration(
        replace(
            snapshot.configuration,
            events=StageConfiguration(
                "airtime-events",
                "1",
                (("minimum_duration_seconds", 0.5),),
            ),
        ),
        revision=4,
        calculation_time=NOW + timedelta(seconds=1),
    )
    assert detector.call_count == 1 and rules_only.events.events == ()
    assert rules_only.forces is snapshot.forces and rules_only.context is snapshot.context
    assert snapshot.events.events and snapshot.events.provenance is not None
    assert snapshot.events.provenance.calculation_time == NOW
    projected = snapshot.with_configuration(
        replace(snapshot.configuration, events_input=AnalysisStage.PROJECTION),
        revision=4,
        calculation_time=NOW,
    )
    smoothed = projected.with_smoothing(3, revision=5, calculation_time=NOW)
    assert smoothed.events is projected.events
    assert (
        snapshot.with_smoothing(3, revision=4, calculation_time=NOW).events is not snapshot.events
    )


@pytest.mark.parametrize("rate", (0.0, -1.0, float("nan"), float("inf"), True))
def test_invalid_source_rates_cannot_create_events(rate: float) -> None:
    snapshot = snapshot_for((1, 0, 0, 1))
    assert snapshot.events.provenance is not None
    with pytest.raises(ValueError, match="sample rate"):
        detection.evaluate_events(
            snapshot.forces.smoothed,
            snapshot.configuration.events,
            rate,
            snapshot.events.provenance,
        )


def test_timing_overflow_and_duplicate_parameters_are_rejected() -> None:
    snapshot = snapshot_for((1, 0, 0, 1))
    assert snapshot.events.provenance is not None
    with pytest.raises(ValueError, match="timing products"):
        detection.evaluate_events(
            snapshot.forces.smoothed,
            StageConfiguration("airtime-events", "1", (("minimum_duration_seconds", 1e308),)),
            10,
            snapshot.events.provenance,
        )
    with pytest.raises(ValueError, match="timing products"):
        detection.evaluate_events(
            snapshot.forces.smoothed,
            snapshot.configuration.events,
            5e-324,
            snapshot.events.provenance,
        )
    with pytest.raises(ValueError, match="parameters"):
        detection.event_rules(
            StageConfiguration(
                "airtime-events",
                "1",
                (("minimum_duration_seconds", 0.2), ("minimum_duration_seconds", 0.3)),
            ),
        )


def test_invalid_onset_is_missing_and_cannot_establish_ejector() -> None:
    snapshot = snapshot_for((1, 0, 0, 1))
    channels = snapshot.forces.smoothed.channels
    assert channels is not None and snapshot.events.provenance is not None
    extreme = SampleValues(np.array([1e308, 1e308, -1e308, -1e308]))
    result = detection.evaluate_events(
        replace(snapshot.forces.smoothed, channels=(extreme, *channels[1:])),
        snapshot.configuration.events,
        10,
        snapshot.events.provenance,
    )
    assert result.events is not None and len(result.events) == 1
    assert result.events[0].category is VerticalContext.STRONG_AIRTIME
    assert result.events[0].onset_g_per_second is None
    assert result.quality.diagnostics[0].code == "EVENT_ONSET_UNAVAILABLE"
