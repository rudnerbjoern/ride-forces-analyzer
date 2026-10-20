"""Analysis-service API stubs and explicitly pending subscriber contracts."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from ride_forces_analyzer.analysis.models import AnalysisProfile
from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisStage,
    AnalysisState,
    RequestStatus,
    StageConfiguration,
)
from ride_forces_analyzer.analysis.service import (
    AnalysisDelivery,
    AnalysisService,
    AnalysisSubscription,
)
from ride_forces_analyzer.importers import ImportSuccess, import_forces_bytes

NOW = datetime(2026, 10, 20, tzinfo=UTC)
PENDING = "Analysis service operations are intentionally NotImplementedError stubs"


@pytest.fixture
def configuration() -> AnalysisConfiguration:
    return AnalysisConfiguration(
        AnalysisProfile(),
        StageConfiguration("source-projection", "1"),
        StageConfiguration("centered-mean", "1", (("window_samples", 11),)),
        StageConfiguration("source-gravity-tilt", "1"),
        StageConfiguration("vertical-context", "1"),
    )


def test_subscription_handle_is_immutable() -> None:
    handle = AnalysisSubscription(1)
    with pytest.raises(FrozenInstanceError):
        setattr(handle, "identifier", 2)


def test_subscriber_methods_are_explicit_stubs_without_deliveries() -> None:
    service = AnalysisService()
    deliveries: list[AnalysisDelivery] = []
    with pytest.raises(NotImplementedError, match="AnalysisService.get_state"):
        service.get_state()
    with pytest.raises(NotImplementedError, match="AnalysisService.subscribe"):
        service.subscribe(deliveries.append, stages=frozenset((AnalysisStage.CONTEXT,)))
    assert deliveries == []
    with pytest.raises(NotImplementedError, match="AnalysisService.unsubscribe"):
        service.unsubscribe(AnalysisSubscription(1))
    with pytest.raises(NotImplementedError, match="AnalysisService.close"):
        service.close()


def test_analysis_requests_are_explicit_stubs(configuration: AnalysisConfiguration) -> None:
    source = import_forces_bytes(
        b'{"schemaVersion":"2.2.0","device":"Apple Watch",'
        b'"accelerationSequence":[{"x":"0","y":"0","z":"1"}]}',
    )
    assert isinstance(source, ImportSuccess)
    service = AnalysisService()
    with pytest.raises(NotImplementedError, match="AnalysisService.request_analysis"):
        service.request_analysis(source, configuration, calculation_time=NOW)
    with pytest.raises(NotImplementedError, match="AnalysisService.request_configuration"):
        service.request_configuration(configuration, calculation_time=NOW)
    with pytest.raises(NotImplementedError, match="AnalysisService.request_smoothing"):
        service.request_smoothing(5, calculation_time=NOW)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_pending_idle_state_is_explicit_before_first_import() -> None:
    state = AnalysisService().get_state()
    assert state.status is RequestStatus.IDLE
    assert state.source_sha256 is None and state.snapshot is None
    assert state.requested_configuration is None
    assert state.dirty_stages == frozenset() and state.failure is None


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_pending_subscription_supplies_initial_state_without_waiting_for_changes() -> None:
    service = AnalysisService()
    deliveries: list[AnalysisDelivery] = []
    subscription = service.subscribe(
        deliveries.append,
        stages=frozenset((AnalysisStage.CONTEXT,)),
    )
    assert len(deliveries) == 1
    initial = deliveries[0]
    assert isinstance(initial, AnalysisState)
    assert initial == service.get_state()
    assert initial.status is RequestStatus.IDLE
    service.unsubscribe(subscription)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=PENDING)
def test_pending_duplicate_callback_registrations_have_separate_handles() -> None:
    service = AnalysisService()
    deliveries: list[AnalysisDelivery] = []
    first = service.subscribe(deliveries.append)
    second = service.subscribe(deliveries.append)
    assert first != second
    assert len(deliveries) == 2
    service.unsubscribe(first)
    service.unsubscribe(second)
