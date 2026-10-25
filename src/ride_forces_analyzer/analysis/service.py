"""Qt-independent synchronous analysis service with revision-guarded delivery.

Calculations and callbacks run outside the state lock, in the calling thread.
Adapters own worker scheduling and UI-thread checks; this module owns coherent
state, subscriptions and suppression of superseded results. No history is kept.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
import logging
from threading import RLock

from ride_forces_analyzer.importers import ImportSuccess, Severity
from ride_forces_analyzer.domain._validation import has_type

from .models import AnalysisDiagnostic
from .calibration import CalibrationOverrides, CalibrationReferenceError
from .recording import (
    AnalysisConfiguration,
    AnalysisFailed,
    AnalysisInvalidated,
    AnalysisNotification,
    AnalysisStage,
    AnalysisState,
    AnalysisUpdated,
    RecordingAnalysis,
    RequestStatus,
    prepare_recording_analysis,
)


#: Initial coherent state or a subsequent technical change notification.
type AnalysisDelivery = AnalysisState | AnalysisNotification
#: Callbacks run synchronously; a UI adapter must marshal and recheck deliveries.
type AnalysisSubscriber = Callable[[AnalysisDelivery], None]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnalysisSubscription:
    """Immutable registration handle; only the issuing service accepts this object.

    Attributes:
        identifier: Service-assigned registration number, never reused locally.
            Equal numbers from other services do not confer registration ownership.
    """

    identifier: int


@dataclass(slots=True)
class _Registration:
    """Serialize one callback, retaining only current queued deliveries.

    Attributes:
        handle: Handle identifying the observer registration.
        callback: Callback invoked by the operation's documented delivery path.
        stages: Stage interests or prepared stages selected for this operation.
        queue: Pending observer deliveries.
        pending_revision: Revision awaiting delivery.
        delivering: Whether observer delivery is active.
    """

    handle: AnalysisSubscription
    callback: AnalysisSubscriber
    stages: frozenset[AnalysisStage] | None
    queue: deque[AnalysisDelivery] = field(default_factory=lambda: deque[AnalysisDelivery]())
    pending_revision: int | None = None
    delivering: bool = False


class AnalysisService:
    """Manage coherent snapshots, subscriptions and monotonically increasing requests.

    Construction starts no workers. Requests calculate synchronously outside an
    internal lock. Concurrent/reentrant requests may supersede work; stale success
    and failure never replace current state. Callbacks run outside that lock and
    are serialized per registration. Callback exceptions are logged and remove
    that registration without turning successful calculations into failures.

    A later UI adapter must recheck source, revision, terminal status and active
    subscription when processing queued UI deliveries. This service has no Qt,
    database, executor or historical snapshot/configuration cache.

    Attributes:
        _lock: Lock protecting service state.
        _state: Current retained analysis state.
        _source: Retained source recording.
        _subscriptions: Registered analysis observers.
        _next_subscription: Next subscription identifier.
        _closed: Whether the service or controller has stopped accepting work.
    """

    def __init__(self, snapshot: RecordingAnalysis | None = None) -> None:
        """Own an optional validated completed snapshot without recalculating it.

        Args:
            snapshot: Immutable analysis snapshot for this operation.

        Returns:
            None.
        """
        self._lock = RLock()
        self._state = AnalysisState(None, None, None, 0, RequestStatus.IDLE)
        self._source: ImportSuccess | None = None
        if snapshot is not None:
            snapshot.validate()
            self._source = snapshot.source
            self._state = AnalysisState(
                snapshot.source.source_sha256,
                snapshot,
                snapshot.configuration,
                snapshot.revision,
                RequestStatus.READY,
            )
        self._subscriptions: dict[int, _Registration] = {}
        self._next_subscription = 0
        self._closed = False

    def get_state(self) -> AnalysisState:
        """Return the immutable current state, including retained older results.

        Returns:
            Coherent source/request identity, snapshot, pending stages or failure.
            After close, returns an empty idle state with an advanced revision.
        """
        with self._lock:
            return self._state

    def subscribe(
        self,
        subscriber: AnalysisSubscriber,
        *,
        stages: frozenset[AnalysisStage] | None = None,
    ) -> AnalysisSubscription:
        """Register and immediately deliver initial state before later notifications.

        Args:
            subscriber: Synchronous callback. Exceptions remove it and are logged.
            stages: Immutable stage interests, or None for all notifications.
                Initial state and terminal status matching observed pending work
                bypass this filter. Duplicate callbacks register independently.

        Returns:
            Service-owned handle for unsubscribe. Registration/state capture are
            coordinated; reentrant notifications wait until initial delivery ends.

        Raises:
            TypeError: Callback is not callable or interests are not typed/frozen.
            RuntimeError: Service is closed.
        """
        if not callable(subscriber):
            raise TypeError("Subscriber must be callable")
        if stages is not None and (
            not has_type(stages, frozenset)
            or any(not has_type(stage, AnalysisStage) for stage in stages)
        ):
            raise TypeError("Stage interests require a frozenset of AnalysisStage")
        with self._lock:
            self._ensure_open()
            self._next_subscription += 1
            handle = AnalysisSubscription(self._next_subscription)
            entry = _Registration(handle, subscriber, stages)
            entry.queue.append(self._state)
            self._subscriptions[handle.identifier] = entry
        self._drain(entry)
        return handle

    def unsubscribe(self, subscription: AnalysisSubscription) -> None:
        """Remove a registration and release its callback and queued references.

        Args:
            subscription: Exact handle returned by this service. Removal is
                idempotent; an already executing callback may finish.

        Raises:
            TypeError: Handle has the wrong type.
            ValueError: A matching number belongs to another handle object.

        Returns:
            None.
        """
        if not has_type(subscription, AnalysisSubscription):
            raise TypeError("Expected AnalysisSubscription")
        with self._lock:
            entry = self._subscriptions.get(subscription.identifier)
            if entry is not None:
                if entry.handle is not subscription:
                    raise ValueError("Subscription belongs to another registration")
                del self._subscriptions[subscription.identifier]
                entry.queue.clear()

    def request_analysis(
        self,
        source: ImportSuccess,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        """Prepare an imported source and publish its matching success or failure.

        Args:
            source: Complete successful import; parsing remains outside the service.
            configuration: Desired supported stage/policy configuration.
            calculation_time: Explicit aware UTC time passed to numerical APIs.

        Returns:
            Assigned revision, also if calculation failed or was superseded.
            Calculation/configuration errors become AnalysisFailed, retaining the
            previous snapshot with its original identity/configuration.

        Raises:
            TypeError: Source or configuration has the wrong top-level type.
            RuntimeError: Service is closed.
        """
        if not has_type(source, ImportSuccess) or not has_type(
            configuration,
            AnalysisConfiguration,
        ):
            raise TypeError("Analysis requests require ImportSuccess and AnalysisConfiguration")
        with self._lock:
            self._ensure_open()
            previous = self._state.snapshot
            revision = self._state.requested_revision + 1
            dirty = _dirty_stages(previous, source, configuration)
            self._source = source
            self._state = AnalysisState(
                source.source_sha256,
                previous,
                configuration,
                revision,
                RequestStatus.PENDING,
                dirty,
            )
            self._enqueue(AnalysisInvalidated(source.source_sha256, revision, dirty))
        self._flush()
        with self._lock:
            if not self._is_current(revision):
                return revision
        try:
            if previous is not None and previous.source is source:
                result = previous.with_configuration(
                    configuration,
                    revision=revision,
                    calculation_time=calculation_time,
                )
            else:
                result = prepare_recording_analysis(
                    source,
                    configuration,
                    revision=revision,
                    calculation_time=calculation_time,
                )
        except Exception as error:
            _LOG.exception("Analysis recalculation failed")
            failure = (
                error.diagnostic
                if isinstance(error, CalibrationReferenceError)
                else AnalysisDiagnostic(
                    "ANALYSIS_FAILED",
                    Severity.ERROR,
                    f"{type(error).__name__}: {error}",
                )
            )
            with self._lock:
                if self._is_current(revision):
                    self._state = replace(
                        self._state,
                        status=RequestStatus.FAILED,
                        dirty_stages=frozenset(),
                        failure=failure,
                    )
                    self._enqueue(AnalysisFailed(source.source_sha256, revision, dirty, failure))
        else:
            with self._lock:
                if self._is_current(revision):
                    self._state = AnalysisState(
                        source.source_sha256,
                        result,
                        configuration,
                        revision,
                        RequestStatus.READY,
                    )
                    self._enqueue(AnalysisUpdated(source.source_sha256, revision, dirty, result))
        self._flush()
        return revision

    def request_configuration(
        self,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        """Reconfigure the selected source, reusing compatible completed stages.

        Args:
            configuration: Desired configuration, including after a failed request.
            calculation_time: Explicit aware UTC calculation time.

        Returns:
            Assigned request revision; calculation failures are delivered as events.

        Raises:
            RuntimeError: No selected source exists or service is closed.
            TypeError: Configuration has the wrong top-level type.
        """
        with self._lock:
            self._ensure_open()
            source = self._source
            if source is None:
                raise RuntimeError("No analysis source is selected")
        return self.request_analysis(source, configuration, calculation_time=calculation_time)

    def request_smoothing(self, window_samples: int, *, calculation_time: datetime) -> int:
        """Change the requested configuration's force window, preserving other settings.

        Args:
            window_samples: Odd centered-mean window, 1 through 51. Domain window
                errors terminate the request with AnalysisFailed.
            calculation_time: Explicit aware UTC calculation time.

        Returns:
            Assigned revision, with no calculation for an unchanged effective window.

        Raises:
            TypeError: Window is not an integer, including booleans.
            RuntimeError: No source/configuration exists or service is closed.
        """
        if type(window_samples) is not int:
            raise TypeError("Smoothing window must be an integer")
        with self._lock:
            self._ensure_open()
            configuration = self._state.requested_configuration
            if configuration is None:
                raise RuntimeError("No analysis configuration is selected")
            parameters = dict(configuration.smoothing.parameters)
            if window_samples != parameters.get("window_samples", 11):
                parameters["window_samples"] = window_samples
                configuration = replace(
                    configuration,
                    smoothing=replace(
                        configuration.smoothing,
                        parameters=tuple(parameters.items()),
                    ),
                )
        return self.request_configuration(configuration, calculation_time=calculation_time)

    def close(self) -> None:
        """Stop publication and release owned source, snapshot, callbacks and queues.

        Close is idempotent. Active calculations may finish but cannot publish.
        Independent consumers keep their own snapshot references.

        Returns:
            None.
        """
        with self._lock:
            if not self._closed:
                self._closed = True
                for entry in self._subscriptions.values():
                    entry.queue.clear()
                self._subscriptions.clear()
                self._source = None
                self._state = AnalysisState(
                    None,
                    None,
                    None,
                    self._state.requested_revision + 1,
                    RequestStatus.IDLE,
                )

    def _ensure_open(self) -> None:
        """Reject new work after shutdown; caller holds the lock."""
        if self._closed:
            raise RuntimeError("Analysis service is closed")

    def _is_current(self, revision: int) -> bool:
        """Check a completion against the active request while holding the lock."""
        return not self._closed and revision == self._state.requested_revision

    def _enqueue(self, notification: AnalysisNotification) -> None:
        """Queue relevant current notifications; caller holds the state lock."""
        invalidated = isinstance(notification, AnalysisInvalidated)
        if isinstance(notification, AnalysisInvalidated):
            affected = notification.dirty_stages
        elif isinstance(notification, AnalysisUpdated):
            affected = notification.replaced_stages
        else:
            affected = notification.affected_stages
        for entry in self._subscriptions.values():
            if invalidated:
                # Superseded notifications release snapshot references immediately.
                entry.queue = deque(
                    self._state for item in entry.queue if isinstance(item, AnalysisState)
                )
            interested = (
                entry.stages is None
                or bool(entry.stages & affected)
                or (
                    entry.pending_revision is not None
                    if invalidated
                    else entry.pending_revision == notification.revision
                )
            )
            if interested:
                entry.queue.append(notification)
                if invalidated:
                    entry.pending_revision = notification.revision

    def _flush(self) -> None:
        """Dispatch outside the state lock, allowing reentrant state requests."""
        with self._lock:
            entries = tuple(self._subscriptions.values())
        for entry in entries:
            self._drain(entry)

    def _drain(self, entry: _Registration) -> None:
        """Serialize callbacks; suppress pending indications already completed."""
        with self._lock:
            if entry.delivering:
                return
            entry.delivering = True
        while True:
            with self._lock:
                if self._subscriptions.get(entry.handle.identifier) is not entry or not entry.queue:
                    entry.delivering = False
                    return
                delivery = entry.queue.popleft()
                if isinstance(delivery, AnalysisState):
                    delivery = self._state
                    entry.pending_revision = (
                        delivery.requested_revision
                        if delivery.status is RequestStatus.PENDING
                        else None
                    )
                elif (
                    isinstance(delivery, AnalysisInvalidated)
                    and self._state.status is not RequestStatus.PENDING
                ):
                    continue
                elif not isinstance(delivery, AnalysisInvalidated):
                    entry.pending_revision = None
            try:
                entry.callback(delivery)
            except Exception:
                with self._lock:
                    self._subscriptions.pop(entry.handle.identifier, None)
                    entry.queue.clear()
                    entry.delivering = False
                _LOG.exception("Analysis subscriber failed; registration removed")
                return


def _dirty_stages(
    previous: RecordingAnalysis | None,
    source: ImportSuccess,
    configuration: AnalysisConfiguration,
) -> frozenset[AnalysisStage]:
    """Determine affected dependencies without calculating or copying stage data."""
    if previous is None or previous.source is not source:
        return frozenset(AnalysisStage)
    old = previous.configuration
    dirty: set[AnalysisStage] = set()
    calibration_changed = configuration.calibration != old.calibration
    if calibration_changed:
        dirty.add(AnalysisStage.CALIBRATION)
    if (
        calibration_changed
        or configuration.profile != old.profile
        or configuration.projection != old.projection
    ):
        dirty.add(AnalysisStage.PROJECTION)
    if AnalysisStage.PROJECTION in dirty or configuration.smoothing != old.smoothing:
        dirty.add(AnalysisStage.SMOOTHING)
    if (
        configuration.profile != old.profile
        or configuration.orientation != old.orientation
        or not has_type(configuration.calibration, CalibrationOverrides)
        or configuration.calibration.gravity_index != old.calibration.gravity_index
    ):
        dirty.add(AnalysisStage.ORIENTATION)
    if (
        configuration.context != old.context
        or configuration.context_input != old.context_input
        or configuration.context_input in dirty
    ):
        dirty.add(AnalysisStage.CONTEXT)
    if (
        configuration.events != old.events
        or configuration.events_input != old.events_input
        or configuration.events_input in dirty
    ):
        dirty.add(AnalysisStage.EVENTS)
    return frozenset(dirty)
