"""Partial recalculation shares stages without retaining prior snapshots."""

# cspell:words getrefcount

from dataclasses import replace
from datetime import timedelta
from sys import getrefcount
from unittest.mock import Mock

import numpy as np
import pytest

from ride_forces_analyzer.analysis import airtime, preparation
from ride_forces_analyzer.analysis.models import AnalysisProfile
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisStage,
    EventEvaluationState,
    StageConfiguration,
)
from tests.analysis.test_recording_preparation import (
    NOW,
    prepare_snapshot,
    synthetic_source,
    configuration as configuration,
)

LATER = NOW + timedelta(seconds=1)


def _spies(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock, Mock]:
    calls: list[Mock] = []
    for name in ("project_directions", "centered_mean", "orientation_degrees"):
        spy = Mock(wraps=getattr(preparation, name))
        monkeypatch.setattr(preparation, name, spy)
        calls.append(spy)
    context = Mock(wraps=airtime.AirtimeContext.prepare)
    monkeypatch.setattr(airtime.AirtimeContext, "prepare", context)
    return calls[0], calls[1], calls[2], context


def test_smoothing_reuses_upstream_stages_and_matches_fresh_preparation(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    original_sample = original.sample(2)
    calls = _spies(monkeypatch)
    changed = original.with_smoothing(5, revision=4, calculation_time=LATER)
    assert tuple(call.call_count for call in calls) == (0, 3, 0, 1)
    assert changed is not original and changed.revision == 4
    assert changed.source is original.source and changed.time is original.time
    assert changed.forces.projected is original.forces.projected
    assert changed.forces.projected.channels is original.forces.projected.channels
    assert changed.orientation is original.orientation
    assert changed.orientation.values is original.orientation.values
    assert changed.forces.smoothed is not original.forces.smoothed
    assert changed.context.input is changed.forces.smoothed
    assert changed.events.input is changed.forces.smoothed
    assert original.sample(2) == original_sample and original.revision == 3
    for stage in (changed.forces.projected, changed.orientation):
        assert stage.provenance is not None and stage.provenance.calculation_time == NOW
    for stage in (changed.forces.smoothed, changed.context):
        assert stage.provenance is not None and stage.provenance.calculation_time == LATER
    fresh = prepare_snapshot(changed.configuration, original.source)
    assert changed.forces.smoothed.channels == fresh.forces.smoothed.channels
    assert changed.context.labels == fresh.context.labels
    changed.validate()


def test_chained_smoothing_always_uses_original_projection(
    configuration: AnalysisConfiguration,
) -> None:
    original = prepare_snapshot(configuration)
    first = original.with_smoothing(5, revision=4, calculation_time=LATER)
    second = first.with_smoothing(1, revision=5, calculation_time=LATER)
    assert second.forces.projected is original.forces.projected
    assert second.forces.smoothed.channels == original.forces.projected.channels
    assert original.forces.smoothed.channels != second.forces.smoothed.channels
    # Returning to an earlier window computes it again, without a history cache.
    restored = second.with_configuration(configuration, revision=6, calculation_time=LATER)
    assert restored.forces.smoothed is not original.forces.smoothed
    assert restored.forces.smoothed.channels == original.forces.smoothed.channels


def test_same_configuration_shares_every_stage_without_work(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    calls = _spies(monkeypatch)
    updated = original.with_configuration(
        replace(configuration),
        revision=4,
        calculation_time=LATER,
    )
    assert all(call.call_count == 0 for call in calls)
    assert updated is not original and updated.revision == 4
    assert updated.time is original.time and updated.forces is original.forces
    assert updated.orientation is original.orientation
    assert updated.context is original.context and updated.events is original.events
    same_window = original.with_smoothing(11, revision=4, calculation_time=LATER)
    assert same_window.forces is original.forces
    assert all(call.call_count == 0 for call in calls)


def test_context_only_change_keeps_force_orientation_and_event_stages(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    calls = _spies(monkeypatch)
    configured = replace(
        configuration,
        context=replace(
            configuration.context,
            parameters=(("floater_bound_g", airtime.FLOATER_BOUND_G),),
        ),
    )
    changed = original.with_configuration(configured, revision=4, calculation_time=LATER)
    assert tuple(call.call_count for call in calls) == (0, 0, 0, 1)
    assert changed.forces is original.forces and changed.orientation is original.orientation
    assert changed.context is not original.context and changed.events is original.events
    assert changed.context.labels == original.context.labels
    assert changed.context.provenance is not None
    assert changed.context.provenance.calculation_time == LATER


def test_event_rules_change_keeps_numerical_stages(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    calls = _spies(monkeypatch)
    changed = original.with_configuration(
        replace(configuration, events=StageConfiguration("airtime-events", "1")),
        revision=4,
        calculation_time=LATER,
    )
    assert all(call.call_count == 0 for call in calls)
    assert changed.forces is original.forces and changed.orientation is original.orientation
    assert changed.context is original.context
    assert changed.events is not original.events
    assert changed.events.input is changed.forces.smoothed
    assert changed.events.status is EventEvaluationState.EVALUATED


@pytest.mark.parametrize("selector", ("context_input", "events_input"))
def test_force_input_switch_replaces_only_its_consumer(
    configuration: AnalysisConfiguration,
    selector: str,
) -> None:
    original = prepare_snapshot(configuration)
    changed = original.with_configuration(
        replace(configuration, **{selector: AnalysisStage.PROJECTION}),
        revision=4,
        calculation_time=LATER,
    )
    assert changed.forces is original.forces and changed.orientation is original.orientation
    assert (changed.context is original.context) == (selector != "context_input")
    assert (changed.events is original.events) == (selector != "events_input")
    consumer = changed.context if selector == "context_input" else changed.events
    assert consumer.input is changed.forces.projected


def test_smoothing_keeps_consumers_of_unfiltered_projection(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(
        replace(
            configuration,
            context_input=AnalysisStage.PROJECTION,
            events_input=AnalysisStage.PROJECTION,
        ),
    )
    calls = _spies(monkeypatch)
    changed = original.with_smoothing(5, revision=4, calculation_time=LATER)
    assert tuple(call.call_count for call in calls) == (0, 3, 0, 0)
    assert changed.context is original.context and changed.events is original.events


def test_profile_change_rebuilds_policy_dependent_stages(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    calls = _spies(monkeypatch)
    profile = replace(configuration.profile, assumptions=("Changed interpretation assumptions",))
    changed = original.with_configuration(
        replace(configuration, profile=profile),
        revision=4,
        calculation_time=LATER,
    )
    assert tuple(call.call_count for call in calls) == (1, 3, 1, 1)
    assert changed.source is original.source and changed.time is original.time
    assert changed.forces.projected is not original.forces.projected
    assert changed.orientation is not original.orientation
    assert changed.forces.projected.channels == original.forces.projected.channels
    assert changed.orientation.values == original.orientation.values
    assert profile.assumptions[0] in changed.forces.projected.unit.evidence


def test_raw_switch_and_unavailable_stages_remain_consistent(
    configuration: AnalysisConfiguration,
) -> None:
    original = prepare_snapshot(configuration)
    raw = original.with_configuration(
        replace(configuration, profile=AnalysisProfile()),
        revision=4,
        calculation_time=LATER,
    )
    assert raw.sample(0).smoothed is None and raw.sample(0).orientation_degrees is None
    changed = raw.with_smoothing(5, revision=5, calculation_time=LATER)
    assert changed.forces.projected is raw.forces.projected
    assert changed.orientation is raw.orientation
    assert changed.forces.smoothed is not raw.forces.smoothed
    assert changed.sample(0).raw is original.sample(0).raw
    restored = changed.with_configuration(configuration, revision=6, calculation_time=LATER)
    assert restored.forces.projected.channels == original.forces.projected.channels
    assert restored.context.labels == original.context.labels


def test_missing_orientation_is_reused_without_blocking_smoothing(
    configuration: AnalysisConfiguration,
) -> None:
    original = prepare_snapshot(configuration, synthetic_source(gravitySequence=None))
    changed = original.with_smoothing(5, revision=4, calculation_time=LATER)
    assert changed.orientation is original.orientation
    assert changed.sample(0).smoothed is not None
    assert changed.sample(0).orientation_degrees is None


@pytest.mark.parametrize("revision", (0, 3, True))
def test_stale_revisions_are_rejected(configuration: AnalysisConfiguration, revision: int) -> None:
    original = prepare_snapshot(configuration)
    with pytest.raises(ValueError, match="revision must increase"):
        original.with_smoothing(5, revision=revision, calculation_time=LATER)


@pytest.mark.parametrize("window", (0, 2, 53, True, 11.0))
def test_invalid_smoothing_requests_do_not_reuse_matching_numeric_values(
    configuration: AnalysisConfiguration,
    window: int,
) -> None:
    original = prepare_snapshot(configuration)
    with pytest.raises(ValueError, match="odd integer"):
        original.with_smoothing(window, revision=4, calculation_time=LATER)


def test_partial_range_failure_and_recovery_keep_upstream_stages(
    configuration: AnalysisConfiguration,
) -> None:
    source = synthetic_source(
        accelerationSequence=[{"x": "1.7e308", "y": "1.7e308", "z": "1.7e308"}] * 7,
    )
    original = prepare_snapshot(
        replace(
            configuration,
            smoothing=replace(configuration.smoothing, parameters=(("window_samples", 1),)),
        ),
        source,
    )
    with np.errstate(over="ignore", invalid="ignore"):
        excluded = original.with_smoothing(11, revision=4, calculation_time=LATER)
    assert excluded.forces.projected is original.forces.projected
    assert excluded.orientation is original.orientation
    assert excluded.sample(0).smoothed is None and excluded.sample(0).context is None
    assert original.sample(0).smoothed is not None
    assert original.sample(0).combined_g is None
    assert any(
        item.code == "COMBINED_SAMPLE_UNAVAILABLE"
        for item in original.sample(0).quality.diagnostics
    )
    restored = excluded.with_smoothing(1, revision=5, calculation_time=LATER)
    assert restored.forces.projected is original.forces.projected
    assert restored.forces.smoothed.channels == original.forces.smoothed.channels
    assert restored.context.labels == original.context.labels


def test_failed_reconfiguration_does_not_modify_previous_snapshot(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = prepare_snapshot(configuration)
    before = original.sample(2)
    calls = _spies(monkeypatch)
    for invalid in (
        replace(
            configuration,
            smoothing=replace(configuration.smoothing, parameters=(("window_samples", 2),)),
        ),
        replace(configuration, context=StageConfiguration("unknown", "1")),
    ):
        with pytest.raises(ValueError):
            original.with_configuration(invalid, revision=4, calculation_time=LATER)
    with pytest.raises(ValueError, match="UTC"):
        original.with_configuration(
            configuration,
            revision=4,
            calculation_time=LATER.replace(tzinfo=None),
        )
    assert all(call.call_count == 0 for call in calls)
    assert original.sample(2) == before and original.revision == 3


def test_recalculation_does_not_retain_snapshot_history_or_change_export_snapshot(
    configuration: AnalysisConfiguration,
) -> None:
    export_snapshot = prepare_snapshot(configuration)
    exported_sample = export_snapshot.sample(2)
    retained_references = getrefcount(export_snapshot)
    current = export_snapshot.with_smoothing(5, revision=4, calculation_time=LATER)
    assert getrefcount(export_snapshot) == retained_references
    for revision in range(5, 25):
        previous_references = getrefcount(current)
        updated = current.with_smoothing(
            1 if revision % 2 else 5,
            revision=revision,
            calculation_time=LATER,
        )
        # A new result must not acquire a reference to the previous snapshot.
        assert getrefcount(current) == previous_references
        current = updated
        del updated
    assert getrefcount(export_snapshot) == retained_references
    assert export_snapshot.sample(2) == exported_sample
    assert current.source is export_snapshot.source
    assert current.forces.projected is export_snapshot.forces.projected
