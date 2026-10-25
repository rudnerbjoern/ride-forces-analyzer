"""Qt worker and UI-thread delivery adapter for the pure analysis service.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from collections.abc import Callable
from ride_forces_analyzer.runtime.error_reporting import record_error

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
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.i18n import diagnostic_message
from datetime import UTC, datetime


@dataclass(slots=True)
class _Binding:
    """Identity and UI-intent generation for one imported recording.

    Attributes:
        service: Analysis service bound to the current recording.
        markers: Last persisted ride bounds and calibration references.
        generation: Request generation used to reject late worker deliveries.
        running_generation: Generation identifying the active background computation.
        subscription: Handle identifying the active analysis subscription.
        active: Whether this recording binding accepts results.
        save_markers: Whether changed analysis markers should be persisted.
    """

    service: AnalysisService
    markers: tuple[tuple[int, int] | None, CalibrationOverrides]
    generation: int = 0
    running_generation: int = 0
    subscription: AnalysisSubscription | None = None
    active: bool = True
    save_markers: bool = False


@dataclass(frozen=True, slots=True)
class _Delivery:
    """Delivery contract and owned data.

    Attributes:
        binding: Binding identifying the active recording and analysis service.
        generation: Request generation used to reject late worker deliveries.
        value: Candidate value to validate, format or store.
    """

    binding: _Binding
    generation: int
    value: AnalysisDelivery


class _SmoothingWorker(QRunnable):
    """Smoothing worker contract and owned data.

    Attributes:
        binding: Binding identifying the active recording and analysis service.
        generation: Request generation used to reject late worker deliveries.
        window: Odd number of samples in the centered smoothing window.
        report: Path for the local JSON verification report.
        configuration: Requested immutable analysis or export configuration.
    """

    def __init__(
        self,
        binding: _Binding,
        generation: int,
        window: int,
        report: Callable[[object], None],
        configuration: AnalysisConfiguration | None = None,
    ) -> None:
        """Initialize smoothing worker and its owned state.

        Args:
            binding: Binding identifying the active recording and analysis service.
            generation: Request generation used to reject late worker deliveries.
            window: Odd number of source samples in the smoothing window.
            report: Path for the local JSON verification report.
            configuration: Requested immutable analysis or export configuration.

        Returns:
            None.
        """
        super().__init__()
        self.binding, self.generation, self.window = binding, generation, window
        self.report = report
        self.configuration = configuration

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
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
            record_error("Analysis worker", error)
            if binding.active:
                self.report(_WorkerFailure(binding, self.generation, str(error)))


@dataclass(frozen=True, slots=True)
class _WorkerFailure:
    """Worker failure contract and owned data.

    Attributes:
        binding: Binding identifying the active recording and analysis service.
        generation: Request generation used to reject late worker deliveries.
        message: Text or diagnostic message to present or validate.
    """

    binding: _Binding
    generation: int
    message: str


class AnalysisController(QObject):
    """Own the active service and marshal guarded notifications to the UI thread.

    A single worker queue preserves UI intent order; obsolete queued requests are
    skipped. A generation also rejects already queued deliveries when a newer UI
    request has not reached the service yet. Service revisions/status and binding
    identity are checked again in the queued UI slot before any consumer signal.

    Attributes:
        snapshot_ready: Qt signal for snapshot ready notifications.
        failed: Qt signal for failed notifications.
        markers_saved: Qt signal for markers saved notifications.
        pending_changed: Qt signal for pending changed notifications.
        _received: Qt signal for received notifications.
        _binding: Current recording and analysis-service binding.
        _closed: Whether the service or controller has stopped accepting work.
        _pending: Pending analysis deliveries.
        preferences: Local application preference access for this window or controller.
        pool: Thread pool used for background analysis.
    """

    snapshot_ready = Signal(object)
    failed = Signal(str)
    markers_saved = Signal(bool)
    pending_changed = Signal(bool)
    _received = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        preferences: Preferences | None = None,
    ) -> None:
        """Initialize analysis controller and its owned state.

        Args:
            parent: Qt parent that owns this object's lifetime.
            preferences: Local application preference access.

        Returns:
            None.
        """
        super().__init__(parent)
        self._binding: _Binding | None = None
        self._closed = False
        self._pending = False
        self.preferences = preferences if preferences is not None else Preferences()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._received.connect(self._apply, Qt.ConnectionType.QueuedConnection)

    @property
    def pending(self) -> bool:
        """Return whether analysis work is pending.

        Returns:
            Whether analysis work is pending.
        """
        return self._pending

    def bind_snapshot(self, snapshot: RecordingAnalysis | None) -> None:
        """Activate a worker-prepared import, also after an explicit close/reopen.

        Args:
            snapshot: Immutable analysis snapshot for this operation.

        Returns:
            None.
        """
        self._closed = False
        self._release()
        if snapshot is None:
            return
        binding = _Binding(
            AnalysisService(snapshot),
            (snapshot.configuration.ride_bounds, snapshot.configuration.calibration),
        )
        self._binding = binding
        binding.subscription = binding.service.subscribe(
            lambda value: self._received.emit(
                _Delivery(binding, binding.running_generation, value),
            ),
        )

    def request_smoothing(self, window: int) -> None:
        """Schedule the latest UI intent while retaining the last complete view.

        Args:
            window: Odd number of source samples in the smoothing window.

        Returns:
            None.
        """
        binding = self._binding
        if self._closed or binding is None:
            return
        state = binding.service.get_state()
        configuration = None
        if state.status is RequestStatus.FAILED and state.snapshot is not None:
            configuration = state.snapshot.configuration
            parameters = dict(configuration.smoothing.parameters)
            parameters["window_samples"] = window
            configuration = replace(
                configuration,
                smoothing=replace(configuration.smoothing, parameters=tuple(parameters.items())),
            )
        binding.generation += 1
        self._set_pending(True)
        self.pool.start(
            _SmoothingWorker(
                binding,
                binding.generation,
                window,
                self._received.emit,
                configuration,
            ),
        )

    def request_markers(
        self,
        bounds: tuple[int, int] | None,
        calibration: CalibrationOverrides,
    ) -> None:
        """Change all four choices through the same revision-guarded worker queue.

        Args:
            bounds: Selected inclusive source-sample bounds.
            calibration: Selected calibration basis and reference evidence.

        Returns:
            None.
        """
        binding = self._binding
        if self._closed or binding is None:
            return
        snapshot = binding.service.get_state().snapshot
        if snapshot is None:
            return
        binding.save_markers = True
        binding.generation += 1
        self._set_pending(True)
        self.pool.start(
            _SmoothingWorker(
                binding,
                binding.generation,
                0,
                self._received.emit,
                replace(snapshot.configuration, ride_bounds=bounds, calibration=calibration),
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
            binding.save_markers = False
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
                binding.save_markers = False
                self._set_pending(False)
                self.failed.emit(diagnostic_message(value.failure.code, value.failure.message))
            return
        snapshot = value.snapshot
        if (
            state.status is not RequestStatus.READY
            or snapshot is None
            or snapshot is not state.snapshot
        ):
            return
        markers = snapshot.configuration.ride_bounds, snapshot.configuration.calibration
        if binding.save_markers or markers != binding.markers:
            saved = self.preferences.remember_recording_markers(snapshot.source, *markers)
            binding.markers = markers
            binding.save_markers = False
            self.markers_saved.emit(saved)
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
        """Reject pending UI deliveries and release service/registration ownership.

        Returns:
            None.
        """
        self._closed = True
        self._release()
