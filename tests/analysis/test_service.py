"""Service lifecycle, coherent initial delivery and revision/error contracts."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from sys import getrefcount
from threading import Event
from typing import cast
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.analysis import service as service_module
from ride_forces_analyzer.analysis.models import AnalysisProfile
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisFailed,
    AnalysisInvalidated,
    AnalysisStage,
    AnalysisState,
    AnalysisUpdated,
    RecordingAnalysis,
    RequestStatus,
    StageConfiguration,
)
from ride_forces_analyzer.analysis.preparation import (
    source_app_configuration,
    prepare_recording_analysis,
)
from ride_forces_analyzer.analysis.service import (
    AnalysisDelivery,
    AnalysisService,
    AnalysisSubscriber,
    AnalysisSubscription,
)
from ride_forces_analyzer.importers import ImportSuccess
from tests.analysis.test_recording_preparation import (
    NOW,
    synthetic_source,
    configuration as configuration,
)

# cspell:words getrefcount caplog


def test_idle_state_and_immediate_initial_delivery() -> None:
    service = AnalysisService()
    state = service.get_state()
    assert state == AnalysisState(None, None, None, 0, RequestStatus.IDLE)
    values: list[AnalysisDelivery] = []
    handle = service.subscribe(values.append, stages=frozenset())
    assert values == [state]
    with pytest.raises(FrozenInstanceError):
        setattr(handle, "identifier", 2)


def test_prepared_import_can_seed_service_without_repeating_calculations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = synthetic_source()
    snapshot = prepare_recording_analysis(
        source,
        source_app_configuration(),
        revision=1,
        calculation_time=NOW,
    )
    prepare = Mock(side_effect=AssertionError("Prepared imports must not be recalculated"))
    monkeypatch.setattr(service_module, "prepare_recording_analysis", prepare)
    service = AnalysisService(snapshot)
    values: list[AnalysisDelivery] = []
    service.subscribe(values.append)
    state = service.get_state()
    assert values == [state] and state.snapshot is snapshot
    assert state.status is RequestStatus.READY and state.requested_revision == 1
    service.request_smoothing(5, calculation_time=NOW)
    updated = service.get_state().snapshot
    assert updated is not None and updated.forces.projected is snapshot.forces.projected
    assert prepare.call_count == 0


def test_success_pending_and_initial_snapshot(configuration: AnalysisConfiguration) -> None:
    service = AnalysisService()
    values: list[AnalysisDelivery] = []
    service.subscribe(values.append)
    source = synthetic_source()
    revision = service.request_analysis(source, configuration, calculation_time=NOW)
    assert revision == 1
    initial, pending, updated = values
    assert isinstance(initial, AnalysisState)
    assert isinstance(pending, AnalysisInvalidated)
    assert pending.revision == revision and pending.dirty_stages == frozenset(AnalysisStage)
    assert isinstance(updated, AnalysisUpdated)
    assert updated.snapshot.source is source
    assert updated.replaced_stages == pending.dirty_stages
    state = service.get_state()
    assert state.status is RequestStatus.READY and state.snapshot is updated.snapshot
    assert not state.dirty_stages and state.failure is None
    assert state.requested_configuration is configuration
    later: list[AnalysisDelivery] = []
    service.subscribe(later.append)
    assert later == [state]
    assert service.request_smoothing(11, calculation_time=NOW) == 2
    assert service.get_state().snapshot is not updated.snapshot
    current = service.get_state().snapshot
    assert current is not None
    assert current.forces is updated.snapshot.forces


def test_failure_retains_previous_configuration_and_can_recover(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    old = service.get_state().snapshot
    values: list[AnalysisDelivery] = []
    service.subscribe(values.append)
    revision = service.request_smoothing(2, calculation_time=NOW)
    failure = values[-1]
    assert isinstance(failure, AnalysisFailed) and failure.revision == revision
    state = service.get_state()
    assert state.status is RequestStatus.FAILED and state.snapshot is old
    assert old is not None and state.requested_configuration != old.configuration
    assert state.failure is failure.failure and not state.dirty_stages
    assert failure.affected_stages == frozenset(
        (AnalysisStage.SMOOTHING, AnalysisStage.CONTEXT, AnalysisStage.EVENTS),
    )
    late: list[AnalysisDelivery] = []
    service.subscribe(late.append)
    assert late == [state]
    service.request_smoothing(5, calculation_time=NOW)
    assert service.get_state().status is RequestStatus.READY
    assert service.get_state().failure is None


def test_failed_first_request_and_failed_source_switch(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    first = synthetic_source()
    service.request_analysis(first, configuration, calculation_time=NOW.replace(tzinfo=None))
    assert service.get_state().status is RequestStatus.FAILED
    assert service.get_state().snapshot is None
    service.request_configuration(configuration, calculation_time=NOW)
    old = service.get_state().snapshot
    second = synthetic_source(sampleRate=50)
    invalid = replace(configuration, projection=StageConfiguration("unknown", "1"))
    service.request_analysis(second, invalid, calculation_time=NOW)
    state = service.get_state()
    assert state.source_sha256 == second.source_sha256
    assert state.snapshot is old and old is not None and old.source is first
    service.request_configuration(configuration, calculation_time=NOW)
    current = service.get_state().snapshot
    assert current is not None and current.source is second


def test_unavailable_stages_are_successful_raw_capable_results(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    service.request_analysis(
        synthetic_source(gravitySequence=None, lateralDirectionVector=None),
        configuration,
        calculation_time=NOW,
    )
    state = service.get_state()
    assert state.status is RequestStatus.READY and state.snapshot is not None
    assert state.snapshot.sample(0).smoothed is None
    assert state.snapshot.sample(0).raw is state.snapshot.source.recording.motion.acceleration[0]


def test_stage_filters_and_partial_recalculation(configuration: AnalysisConfiguration) -> None:
    service = AnalysisService()
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    old = service.get_state().snapshot
    force_values: list[AnalysisDelivery] = []
    orientation_values: list[AnalysisDelivery] = []
    service.subscribe(force_values.append, stages=frozenset((AnalysisStage.SMOOTHING,)))
    service.subscribe(orientation_values.append, stages=frozenset((AnalysisStage.ORIENTATION,)))
    service.request_smoothing(5, calculation_time=NOW)
    assert len(force_values) == 3 and len(orientation_values) == 1
    updated = force_values[-1]
    assert isinstance(updated, AnalysisUpdated) and old is not None
    assert updated.snapshot.forces.projected is old.forces.projected
    assert updated.snapshot.orientation is old.orientation
    service.request_configuration(
        replace(updated.snapshot.configuration, context_input=AnalysisStage.PROJECTION),
        calculation_time=NOW,
    )
    assert len(force_values) == 3 and len(orientation_values) == 1


@pytest.mark.parametrize(
    "change",
    ("context", "events", "orientation", "projection", "profile", "selectors"),
)
def test_dirty_stage_dependencies(configuration: AnalysisConfiguration, change: str) -> None:
    service = AnalysisService()
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    if change in ("context", "events", "orientation", "projection"):
        changed = replace(configuration, **{change: StageConfiguration("unknown", "1")})
        expected = {
            "context": {AnalysisStage.CONTEXT},
            "events": {AnalysisStage.EVENTS},
            "orientation": {AnalysisStage.ORIENTATION},
            "projection": {
                AnalysisStage.PROJECTION,
                AnalysisStage.SMOOTHING,
                AnalysisStage.CONTEXT,
                AnalysisStage.EVENTS,
            },
        }[change]
    elif change == "profile":
        changed = replace(configuration, profile=AnalysisProfile())
        expected = set(AnalysisStage) - {AnalysisStage.TIME, AnalysisStage.CALIBRATION}
    else:
        changed = replace(
            configuration,
            context_input=AnalysisStage.PROJECTION,
            events_input=AnalysisStage.PROJECTION,
        )
        expected = {AnalysisStage.CONTEXT, AnalysisStage.EVENTS}
    values: list[AnalysisDelivery] = []
    service.subscribe(values.append)
    service.request_configuration(changed, calculation_time=NOW)
    pending = values[1]
    assert isinstance(pending, AnalysisInvalidated)
    assert pending.dirty_stages == frozenset(expected)


def test_duplicate_handles_owner_validation_and_unsubscribe(
    configuration: AnalysisConfiguration,
) -> None:
    service, other = AnalysisService(), AnalysisService()
    values: list[AnalysisDelivery] = []
    first = service.subscribe(values.append)
    second = service.subscribe(values.append)
    foreign = other.subscribe(values.append)
    assert first != second
    with pytest.raises(ValueError, match="another registration"):
        service.unsubscribe(foreign)
    with pytest.raises(TypeError):
        service.unsubscribe(cast(AnalysisSubscription, None))
    service.unsubscribe(first)
    service.unsubscribe(first)
    count = len(values)
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    assert len(values) == count + 2
    service.unsubscribe(second)
    count = len(values)
    service.request_smoothing(5, calculation_time=NOW)
    assert len(values) == count


def test_initial_delivery_precedes_reentrant_notifications(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    values: list[AnalysisDelivery] = []

    def subscriber(value: AnalysisDelivery) -> None:
        values.append(value)
        if isinstance(value, AnalysisState):
            service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)

    service.subscribe(subscriber)
    assert isinstance(values[0], AnalysisState)
    assert isinstance(values[-1], AnalysisUpdated)
    assert all(not isinstance(value, AnalysisState) for value in values[1:])


@pytest.mark.parametrize("finish", ("success", "failure", "close"))
def test_superseded_completion_and_pending_initial_delivery(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
    finish: str,
) -> None:
    service = AnalysisService()
    source = synthetic_source()
    entered, release = Event(), Event()
    prepare = service_module.prepare_recording_analysis

    def blocked(
        source_arg: ImportSuccess,
        config: AnalysisConfiguration,
        *,
        revision: int,
        calculation_time: datetime,
    ) -> RecordingAnalysis:
        if source_arg is source:
            entered.set()
            assert release.wait(5)
            if finish == "failure":
                raise RuntimeError("Superseded failure")
        return prepare(source_arg, config, revision=revision, calculation_time=calculation_time)

    monkeypatch.setattr(service_module, "prepare_recording_analysis", blocked)
    values: list[AnalysisDelivery] = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.request_analysis, source, configuration, calculation_time=NOW)
        try:
            assert entered.wait(5)
            service.subscribe(values.append, stages=frozenset())
            initial = values[0]
            assert isinstance(initial, AnalysisState) and initial.status is RequestStatus.PENDING
            if finish == "close":
                service.close()
            else:
                service.request_analysis(
                    synthetic_source(sampleRate=50),
                    configuration,
                    calculation_time=NOW,
                )
        finally:
            release.set()
        assert future.result(timeout=5) == 1
    state = service.get_state()
    if finish == "close":
        assert state.status is RequestStatus.IDLE and state.snapshot is None
    else:
        assert state.status is RequestStatus.READY and state.requested_revision == 2
        assert isinstance(values[-1], AnalysisUpdated) and values[-1].revision == 2
        assert not any(
            isinstance(value, (AnalysisUpdated, AnalysisFailed)) and value.revision == 1
            for value in values
        )


def test_pending_initial_state_receives_matching_terminal_despite_filter(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    late: list[AnalysisDelivery] = []

    def subscriber(value: AnalysisDelivery) -> None:
        if isinstance(value, AnalysisInvalidated):
            service.subscribe(late.append, stages=frozenset())

    service.subscribe(subscriber)
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    assert isinstance(late[0], AnalysisState) and late[0].status is RequestStatus.PENDING
    assert isinstance(late[-1], AnalysisUpdated)


def test_reentrant_request_supersedes_old_work_and_releases_old_queues(
    configuration: AnalysisConfiguration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AnalysisService()
    first_values: list[AnalysisDelivery] = []
    second_values: list[AnalysisDelivery] = []
    prepare = Mock(wraps=service_module.prepare_recording_analysis)
    monkeypatch.setattr(service_module, "prepare_recording_analysis", prepare)

    def first(value: AnalysisDelivery) -> None:
        first_values.append(value)
        if isinstance(value, AnalysisInvalidated) and value.revision == 1:
            service.request_analysis(
                synthetic_source(sampleRate=50),
                configuration,
                calculation_time=NOW,
            )

    service.subscribe(first)
    service.subscribe(second_values.append)
    revision = service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    assert revision == 1 and prepare.call_count == 1
    assert service.get_state().requested_revision == 2
    assert not any(
        isinstance(value, AnalysisInvalidated) and value.revision == 1 for value in second_values
    )
    assert isinstance(first_values[-1], AnalysisUpdated) and first_values[-1].revision == 2


def test_callback_failure_is_isolated_and_registration_released(
    configuration: AnalysisConfiguration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AnalysisService()
    count = 0

    def broken(value: AnalysisDelivery) -> None:
        nonlocal count
        count += 1
        if isinstance(value, AnalysisInvalidated):
            raise RuntimeError("Subscriber failed")

    service.subscribe(broken)
    values: list[AnalysisDelivery] = []
    service.subscribe(values.append)
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    service.request_smoothing(5, calculation_time=NOW)
    assert count == 2 and "registration removed" in caplog.text
    assert service.get_state().status is RequestStatus.READY
    assert isinstance(values[-1], AnalysisUpdated)


def test_filtered_pending_subscriber_gets_latest_terminal_after_queued_result_is_superseded(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    entered, release = Event(), Event()
    values: list[AnalysisDelivery] = []

    def subscriber(value: AnalysisDelivery) -> None:
        values.append(value)
        if isinstance(value, AnalysisInvalidated) and value.revision == 1:
            entered.set()
            assert release.wait(5)

    service.subscribe(subscriber, stages=frozenset((AnalysisStage.SMOOTHING,)))
    source = synthetic_source()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.request_analysis, source, configuration, calculation_time=NOW)
        try:
            assert entered.wait(5)
            service.request_analysis(source, configuration, calculation_time=NOW)
            # No stages change in revision 3. It must still terminate the
            # subscriber's observed pending state after revision 2 is discarded.
            service.request_configuration(configuration, calculation_time=NOW)
        finally:
            release.set()
        future.result(timeout=5)
    assert isinstance(values[-1], AnalysisUpdated) and values[-1].revision == 3
    assert service.get_state().requested_revision == 3


def test_close_releases_service_ownership_and_preserves_export_snapshot(
    configuration: AnalysisConfiguration,
) -> None:
    service = AnalysisService()
    values: list[AnalysisDelivery] = []
    handle = service.subscribe(values.append)
    service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)
    export = service.get_state().snapshot
    assert export is not None
    values.clear()
    before = getrefcount(export)
    service.close()
    assert getrefcount(export) < before
    closed = service.get_state()
    service.close()
    assert service.get_state() is closed
    assert closed.snapshot is None and closed.source_sha256 is None
    assert export.sample(0).smoothed is not None
    service.unsubscribe(handle)
    with pytest.raises(RuntimeError, match="closed"):
        service.subscribe(values.append)
    with pytest.raises(RuntimeError, match="closed"):
        service.request_analysis(synthetic_source(), configuration, calculation_time=NOW)


@pytest.mark.parametrize("operation", ("configuration", "smoothing"))
def test_missing_source_is_caller_error(
    configuration: AnalysisConfiguration,
    operation: str,
) -> None:
    service = AnalysisService()
    with pytest.raises(RuntimeError, match="selected"):
        if operation == "configuration":
            service.request_configuration(configuration, calculation_time=NOW)
        else:
            service.request_smoothing(5, calculation_time=NOW)


def test_invalid_api_types_do_not_start_requests(configuration: AnalysisConfiguration) -> None:
    service = AnalysisService()
    with pytest.raises(TypeError):
        service.subscribe(cast(AnalysisSubscriber, None))
    with pytest.raises(TypeError):
        service.subscribe(
            lambda value: None,
            stages=cast(frozenset[AnalysisStage], {AnalysisStage.TIME}),
        )
    with pytest.raises(TypeError):
        service.subscribe(
            lambda value: None,
            stages=cast(frozenset[AnalysisStage], frozenset(("time",))),
        )
    with pytest.raises(TypeError):
        service.request_analysis(cast(ImportSuccess, None), configuration, calculation_time=NOW)
    with pytest.raises(TypeError):
        service.request_analysis(
            synthetic_source(),
            cast(AnalysisConfiguration, None),
            calculation_time=NOW,
        )
    with pytest.raises(TypeError):
        service.request_smoothing(True, calculation_time=NOW)
    assert service.get_state().requested_revision == 0
