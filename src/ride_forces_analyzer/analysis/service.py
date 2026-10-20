"""Qt-independent analysis-service API; every operation is intentionally a stub.

No subscribers, workers or snapshots are managed yet. The methods document the
planned contracts and always raise NotImplementedError without performing work.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ride_forces_analyzer.importers import ImportSuccess

from .recording import (
    AnalysisConfiguration,
    AnalysisNotification,
    AnalysisStage,
    AnalysisState,
)


#: Initial coherent state or a subsequent technical change notification.
type AnalysisDelivery = AnalysisState | AnalysisNotification
#: Callback transported to the UI thread by an adapter, never by this service.
type AnalysisSubscriber = Callable[[AnalysisDelivery], None]


@dataclass(frozen=True, slots=True)
class AnalysisSubscription:
    """Opaque handle identifying one subscriber registration with a service.

    Attributes:
        identifier: Service-assigned registration identity. Consumers retain the
            returned handle for removal rather than constructing their own.
            A handle belongs to the service that issued it.
    """

    identifier: int


class AnalysisService:
    """Reserve snapshot management, partial recalculation and subscriptions.

    Creating this placeholder starts no work and registers no callbacks. All
    explicit methods raise NotImplementedError, including state queries. The
    intended service owns request revisions and stage dependencies; consumers
    receive immutable payloads and never mutate completed snapshots.

    Future UI adapters must marshal deliveries to their UI thread and recheck
    source, revision and subscription validity when processing queued messages.
    Numerical calculation, thread scheduling and callback dispatch remain
    unimplemented; no Qt, database or general event-bus dependency is introduced.
    """

    def get_state(self) -> AnalysisState:
        """Reserve reading the current coherent snapshot and request status.

        Returns:
            Planned: AnalysisState, including an older completed snapshot and
            the current requested configuration/status when applicable.
            Currently no state is returned.

        Raises:
            NotImplementedError: Always; service state management is absent.
        """
        raise NotImplementedError("AnalysisService.get_state is not implemented")

    def subscribe(
        self,
        subscriber: AnalysisSubscriber,
        *,
        stages: frozenset[AnalysisStage] | None = None,
    ) -> AnalysisSubscription:
        """Reserve registration with immediate initial state and later notifications.

        Args:
            subscriber: Callback receiving a coherent AnalysisState first, then
                applicable AnalysisNotification payloads in delivery order.
            stages: Stage interests, or None for all stages. The initial state
                is always delivered. A matching pending indication must receive
                its terminal update/failure, even with no replaced stage data.

        Returns:
            Planned: Service-owned handle for unsubscribe. Initial-state capture
            and registration must be coordinated so no intervening update is
            lost. Currently no registration, callback or handle is produced.

        Raises:
            NotImplementedError: Always; registration and dispatch are absent.
        """
        raise NotImplementedError("AnalysisService.subscribe is not implemented")

    def unsubscribe(self, subscription: AnalysisSubscription) -> None:
        """Reserve removal of a registration and release of its callback references.

        Args:
            subscription: Handle issued by this service's subscribe method.

        Returns:
            Planned: None after removal. Queued UI deliveries for the removed
            subscription must be rejected by the adapter. Currently never returns.

        Raises:
            NotImplementedError: Always; no registration is removed.
        """
        raise NotImplementedError("AnalysisService.unsubscribe is not implemented")

    def request_analysis(
        self,
        source: ImportSuccess,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        """Reserve analysis of an imported source under an explicit configuration.

        Args:
            source: Complete successful import; this method does not parse files.
            configuration: Requested stage algorithms, parameters and policy.
            calculation_time: Caller-supplied timezone-aware UTC calculation time.

        Returns:
            Planned: Service-assigned monotonically increasing request revision.
            Completion is delivered as AnalysisUpdated or AnalysisFailed, with
            stale completions suppressed. Currently no request is started.

        Raises:
            NotImplementedError: Always; analysis orchestration is absent.
        """
        raise NotImplementedError("AnalysisService.request_analysis is not implemented")

    def request_configuration(
        self,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        """Reserve reconfiguration of the active source with compatible stage reuse.

        Args:
            configuration: Desired configuration for the currently managed source.
            calculation_time: Caller-supplied timezone-aware UTC calculation time.

        Returns:
            Planned: Service-assigned request revision. Only affected stages are
            recalculated, and the last completed snapshot remains readable.
            Currently no request is started.

        Raises:
            NotImplementedError: Always, including when no source is active;
                configuration validation and recalculation are absent.
        """
        raise NotImplementedError("AnalysisService.request_configuration is not implemented")

    def request_smoothing(self, window_samples: int, *, calculation_time: datetime) -> int:
        """Reserve a force-smoothing update for the active source.

        Args:
            window_samples: Requested odd centered-mean window, 1 through 51.
            calculation_time: Caller-supplied timezone-aware UTC calculation time.

        Returns:
            Planned: Service-assigned revision for smoothing and dependent stages;
            source, time, projection and orientation are reused. Currently no
            request is started or revision returned.

        Raises:
            NotImplementedError: Always; no window validation or work is performed.
        """
        raise NotImplementedError("AnalysisService.request_smoothing is not implemented")

    def close(self) -> None:
        """Reserve service shutdown and release of owned registrations/results.

        Returns:
            Planned: None after pending work can no longer publish through this
            service and owned references are released. Independent consumers,
            such as running exports, retain their bound snapshots.
            Currently never returns.

        Raises:
            NotImplementedError: Always; shutdown and cleanup are absent.
        """
        raise NotImplementedError("AnalysisService.close is not implemented")
