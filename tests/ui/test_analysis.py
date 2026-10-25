"""Native Qt worker transport, UI-thread guards and snapshot presentation."""

from datetime import datetime
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.analysis.service import AnalysisService
from ride_forces_analyzer.explorer import ExplorerData, present_recording
from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.ui.explorer import loading
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


def open_source(
    window: ExplorerWindow,
    source: ImportSuccess,
    monkeypatch: pytest.MonkeyPatch,
) -> ExplorerData:
    data = present_recording(source)

    def loaded(path: Path) -> ExplorerData:
        return data

    monkeypatch.setattr(loading, "load_recording", loaded)
    window.open_path(Path("synthetic.forces"))
    wait_until(window.open_action.isEnabled)
    return data


def test_worker_keeps_ui_responsive_and_applies_snapshot_on_ui_thread(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    controller = window.analysis_controller
    old = window.data
    assert controller is not None and old is not None and old.analysis is not None
    QApplication.processEvents()
    entered, release = Event(), Event()
    method = AnalysisService.request_smoothing
    worker_threads: list[QThread] = []
    delivered_threads: list[QThread] = []

    def delivery_thread(value: object) -> None:
        delivered_threads.append(QThread.currentThread())

    controller.snapshot_ready.connect(delivery_thread)

    def blocked(self: AnalysisService, value: int, *, calculation_time: datetime) -> int:
        worker_threads.append(QThread.currentThread())
        entered.set()
        assert release.wait(5)
        return method(self, value, calculation_time=calculation_time)

    monkeypatch.setattr(AnalysisService, "request_smoothing", blocked)
    try:
        window.inspector.smoothing_slider.setValue(2)
        assert entered.wait(5)
        assert controller.pending and window.data is old
        window.navigation.position.setValue(3)
        window.inspector.first.setValue(1)
        window.inspector.last.setValue(5)
        window.plot.axis_x.setRange(old.time_at(1), old.time_at(5))
        QApplication.processEvents()
        assert window.navigation.position.value() == 3
    finally:
        release.set()
    wait_until(lambda: not controller.pending)
    data = window.data
    assert data is not None and data.analysis is not None and data.calibration_available
    assert window.plot.data is data
    assert window.inspector.data is data and window.navigation.data is data
    assert data.smoothing_window == 5
    assert data.analysis.forces.projected is old.analysis.forces.projected
    assert data.analysis.orientation is old.analysis.orientation
    assert (
        window.inspector.first.value(),
        window.inspector.last.value(),
        window.navigation.position.value(),
    ) == (1, 5, 3)
    assert (window.plot.axis_x.min(), window.plot.axis_x.max()) == (old.time_at(1), old.time_at(5))
    assert all(thread != window.thread() for thread in worker_threads)
    assert delivered_threads and all(thread == window.thread() for thread in delivered_threads)


def test_latest_ui_intent_rejects_already_queued_success(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    controller, old = window.analysis_controller, window.data
    assert controller is not None and old is not None
    QApplication.processEvents()
    observed: list[int] = []

    def applied(value: object) -> None:
        assert isinstance(value, RecordingAnalysis)
        window_samples = dict(value.configuration.smoothing.parameters)["window_samples"]
        assert type(window_samples) is int
        observed.append(window_samples)

    controller.snapshot_ready.connect(applied)
    controller.request_smoothing(5)
    assert controller.pool.waitForDone(5000)
    # The service has completed, but Qt has not applied its queued callback yet.
    assert window.data is old
    controller.request_smoothing(7)
    wait_until(lambda: not controller.pending)
    assert observed == [7]
    assert window.data is not None and window.data.calibration_available
    assert window.data.smoothing_window == 7


@pytest.mark.parametrize("rate", (25, 50))
def test_rebinding_and_close_reject_queued_old_recording_deliveries(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
    rate: int,
) -> None:
    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    controller = window.analysis_controller
    assert controller is not None
    controller.request_smoothing(5)
    assert controller.pool.waitForDone(5000)
    second = open_source(window, synthetic_source(sampleRate=rate), monkeypatch)
    QApplication.processEvents()
    assert window.data is not None and window.data.analysis is second.analysis
    controller.request_smoothing(7)
    assert controller.pool.waitForDone(5000)
    controller.close()
    QApplication.processEvents()
    assert not controller.pending
    assert window.data.analysis is second.analysis


def test_analysis_failure_keeps_previous_values_and_recovers(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    controller, old = window.analysis_controller, window.data
    assert controller is not None and old is not None
    QApplication.processEvents()
    controller.request_smoothing(2)
    wait_until(lambda: not controller.pending)
    assert window.data is old and window.inspector.smoothing_slider.value() == 5
    assert window.statusBar().currentMessage().startswith("Analysis failed:")
    controller.request_smoothing(5)
    wait_until(lambda: not controller.pending)
    assert window.data is not old
    assert window.data is not None and window.data.calibration_available
    assert window.data.smoothing_window == 5


def test_unexpected_worker_failure_clears_pending_and_preserves_view(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    controller, old = window.analysis_controller, window.data
    assert controller is not None

    def fail(self: AnalysisService, value: int, *, calculation_time: datetime) -> int:
        raise RuntimeError("Worker transport failed")

    monkeypatch.setattr(AnalysisService, "request_smoothing", fail)
    controller.request_smoothing(5)
    wait_until(lambda: not controller.pending)
    assert window.data is old
    assert "Worker transport failed" in window.statusBar().currentMessage()


@pytest.mark.parametrize("failure", (False, True))
def test_late_import_cannot_replace_reopened_window_source_or_error_status(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
    failure: bool,
) -> None:
    from PySide6.QtCore import QThreadPool

    window = explorer_window
    open_source(window, synthetic_source(), monkeypatch)
    entered, release = Event(), Event()
    late = present_recording(synthetic_source(sampleRate=50))

    def blocked(path: Path) -> ExplorerData:
        entered.set()
        assert release.wait(5)
        if failure:
            raise OSError("Old import failed")
        return late

    monkeypatch.setattr(loading, "load_recording", blocked)
    window.open_path(Path("late.forces"))
    try:
        assert entered.wait(5)
        window.close()
        window.show()
        current = open_source(window, synthetic_source(sampleRate=75), monkeypatch)
        message = window.statusBar().currentMessage()
    finally:
        release.set()
    assert QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    assert window.data is not None and window.data.analysis is current.analysis
    assert window.data.analysis is not late.analysis
    assert window.statusBar().currentMessage() == message


def test_loaded_snapshot_restores_its_smoothing_window(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = present_recording(synthetic_source()).with_smoothing(3)

    def loaded(path: Path) -> ExplorerData:
        return data

    monkeypatch.setattr(loading, "load_recording", loaded)
    explorer_window.open_path(Path("prepared.forces"))
    wait_until(explorer_window.open_action.isEnabled)
    assert explorer_window.data is not None
    assert explorer_window.data.analysis is data.analysis
    assert explorer_window.data.smoothing_window == 3
    assert explorer_window.inspector.smoothing_slider.value() == 1
    assert "3 samples" in explorer_window.inspector.smoothing_label.text()
