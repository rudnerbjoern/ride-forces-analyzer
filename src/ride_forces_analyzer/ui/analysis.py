"""Qt worker and UI-thread delivery adapter for the pure analysis service.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

from ride_forces_analyzer.analysis.recording import (
    AnalysisConfiguration,
    AnalysisFailed,
    AnalysisInvalidated,
    AnalysisState,
    RecordingAnalysis,
    RequestStatus,
)
from ride_forces_analyzer.analysis.service import (
    AnalysisDelivery,
    AnalysisService,
    AnalysisSubscription,
)
from datetime import UTC, datetime


@dataclass(slots=True)
class _Binding:
    """Identity and UI-intent generation for one imported recording."""

    service: AnalysisService
    generation: int = 0
    running_generation: int = 0
    subscription: AnalysisSubscription | None = None
    active: bool = True


@dataclass(frozen=True, slots=True)
class _Delivery:
    binding: _Binding
    generation: int
    value: AnalysisDelivery


class _SmoothingWorker(QRunnable):
    def __init__(
        self,
        binding: _Binding,
        generation: int,
        window: int,
        report: Callable[[object], None],
        configuration: AnalysisConfiguration | None = None,
    ) -> None:
        super().__init__()
        self.binding, self.generation, self.window = binding, generation, window
        self.report = report
        self.configuration = configuration

    @Slot()
    def run(self) -> None:
        binding = self.binding
        if not binding.active or binding.generation != self.generation:
            return
        binding.running_generation = self.generation
        try:
            if self.configuration is None:
                binding.service.request_smoothing(self.window, calculation_time=datetime.now(UTC))
            else:
                binding.service.request_configuration(
                    self.configuration,
                    calculation_time=datetime.now(UTC),
                )
        except Exception as error:
            if binding.active:
                self.report(_WorkerFailure(binding, self.generation, str(error)))


@dataclass(frozen=True, slots=True)
class _WorkerFailure:
    binding: _Binding
    generation: int
    message: str


class AnalysisController(QObject):
    """Own the active service and marshal guarded notifications to the UI thread.

    A single worker queue preserves UI intent order; obsolete queued requests are
    skipped. A generation also rejects already queued deliveries when a newer UI
    request has not reached the service yet. Service revisions/status and binding
    identity are checked again in the queued UI slot before any consumer signal.
    """

    snapshot_ready = Signal(object)
    failed = Signal(str)
    pending_changed = Signal(bool)
    _received = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._binding: _Binding | None = None
        self._closed = False
        self._pending = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._received.connect(self._apply, Qt.ConnectionType.QueuedConnection)

    @property
    def pending(self) -> bool:
        return self._pending

    def bind_snapshot(self, snapshot: RecordingAnalysis | None) -> None:
        """Activate a worker-prepared import, also after an explicit close/reopen."""
        self._closed = False
        self._release()
        if snapshot is None:
            return
        binding = _Binding(AnalysisService(snapshot))
        self._binding = binding
        binding.subscription = binding.service.subscribe(
            lambda value: self._received.emit(
                _Delivery(binding, binding.running_generation, value),
            ),
        )

    def request_smoothing(self, window: int) -> None:
        """Schedule the latest UI intent while retaining the last complete view."""
        binding = self._binding
        if self._closed or binding is None:
            return
        binding.generation += 1
        self._set_pending(True)
        self.pool.start(_SmoothingWorker(binding, binding.generation, window, self._received.emit))

    def request_ride_bounds(self, bounds: tuple[int, int] | None) -> None:
        """Change markers through the same revision-guarded worker queue."""
        binding = self._binding
        if self._closed or binding is None:
            return
        configuration = binding.service.get_state().requested_configuration
        if configuration is None:
            return
        binding.generation += 1
        self._set_pending(True)
        self.pool.start(
            _SmoothingWorker(
                binding,
                binding.generation,
                0,
                self._received.emit,
                replace(configuration, ride_bounds=bounds),
            ),
        )

    @Slot(object)
    def _apply(self, payload: object) -> None:
        if not isinstance(payload, (_Delivery, _WorkerFailure)):
            return
        binding = payload.binding
        if (
            self._closed
            or binding is not self._binding
            or not binding.active
            or binding.subscription is None
            or payload.generation != binding.generation
        ):
            return
        if isinstance(payload, _WorkerFailure):
            self._set_pending(False)
            self.failed.emit(payload.message)
            return
        value = payload.value
        state = binding.service.get_state()
        source = value.source_sha256
        revision = value.requested_revision if isinstance(value, AnalysisState) else value.revision
        if source != state.source_sha256 or revision != state.requested_revision:
            return
        if isinstance(value, AnalysisInvalidated):
            if state.status is RequestStatus.PENDING:
                self._set_pending(True)
            return
        if isinstance(value, AnalysisFailed):
            if state.status is RequestStatus.FAILED:
                self._set_pending(False)
                self.failed.emit(value.failure.message)
            return
        snapshot = value.snapshot
        if (
            state.status is not RequestStatus.READY
            or snapshot is None
            or snapshot is not state.snapshot
        ):
            return
        self._set_pending(False)
        self.snapshot_ready.emit(snapshot)

    def _set_pending(self, pending: bool) -> None:
        self._pending = pending
        self.pending_changed.emit(pending)

    def _release(self) -> None:
        binding, self._binding = self._binding, None
        if binding is not None:
            binding.active = False
            if binding.subscription is not None:
                binding.service.unsubscribe(binding.subscription)
                binding.subscription = None
            binding.service.close()
        self.pool.clear()
        self._set_pending(False)

    def close(self) -> None:
        """Reject pending UI deliveries and release service/registration ownership."""
        self._closed = True
        self._release()
