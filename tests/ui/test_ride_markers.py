"""Chart marker actions persist independently and preserve original source bytes."""

from pathlib import Path
from datetime import datetime
from threading import Event
from unittest.mock import Mock

import pytest

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.analysis.service import AnalysisService
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.test_analysis import open_source
from tests.ui.helpers import wait_until


SOURCE = Path("tests/fixtures/real/VoltronNevera-6BC967BE-5333-42D1-B4B6-C8C73FC5BCEA.forces")


def trigger_marker(window: ExplorerWindow, sample: int, text: str) -> None:
    """Select a real menu action; the main test additionally owns mouse/zoom checks."""
    assert window.data is not None
    window.axis_x.setRange(
        (sample - 1) / window.data.sample_rate,
        (sample + 1) / window.data.sample_rate,
    )

    def pick() -> None:
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        next(action for action in menu.actions() if action.text() == text).trigger()
        menu.close()

    QTimer.singleShot(0, pick)
    fraction = (window.data.time_at(sample) - window.axis_x.min()) / (
        window.axis_x.max() - window.axis_x.min()
    )
    window.show_marker_menu(fraction, window.mapToGlobal(window.rect().center()))


def test_invalid_reference_keeps_snapshot_and_saved_markers_while_storage_failure_is_visible(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "0", "z": "1"}] * 7)
    open_source(window, source, monkeypatch)
    controller = window.analysis_controller
    assert controller is not None
    trigger_marker(window, 0, "Set gravity here")
    wait_until(lambda: not controller.pending)
    valid = window.data
    assert valid is not None and valid.analysis is not None
    assert dict(valid.markers)["gravityIndex"] == 0
    assert source.recording.indices.gravity is None
    assert window.preferences.recording_calibration(source.source_sha256) == CalibrationOverrides(
        gravity_index=0,
    )
    before = window.preferences.path.read_bytes()
    trigger_marker(window, 3, "Set incline here")
    wait_until(lambda: not controller.pending)
    assert window.data is valid
    assert "Analysis failed:" in window.statusBar().currentMessage()
    assert window.preferences.path.read_bytes() == before
    controller.request_smoothing(5)
    wait_until(lambda: not controller.pending)
    assert window.data is not None and window.data.smoothing_window == 5
    assert window.data.analysis is not None
    assert window.data.analysis.configuration.calibration == CalibrationOverrides(gravity_index=0)
    monkeypatch.setattr(window.preferences, "remember_recording_markers", Mock(return_value=False))
    trigger_marker(window, 5, "Set end here")
    wait_until(lambda: not controller.pending)
    assert window.data is not None and window.data.ride_bounds == (2, 5)
    assert "local saving failed" in window.statusBar().currentMessage()
    assert window.preferences.path.read_bytes() == before
    save = Mock(return_value=True)
    monkeypatch.setattr(window.preferences, "remember_recording_markers", save)
    trigger_marker(window, 5, "Set end here")
    wait_until(lambda: not controller.pending)
    assert save.call_count == 1


def test_marker_autosave_follows_latest_ui_intent_and_rejects_closed_binding(
    explorer_window: ExplorerWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = explorer_window
    source = synthetic_source(accelerationSequence=[{"x": "0", "y": "1", "z": "1"}] * 7)
    open_source(window, source, monkeypatch)
    controller = window.analysis_controller
    assert controller is not None
    controller.request_markers((1, 5), CalibrationOverrides(gravity_index=0))
    assert controller.pool.waitForDone(5000)
    controller.request_smoothing(5)
    wait_until(lambda: not controller.pending)
    choice = CalibrationOverrides(gravity_index=0)
    assert window.preferences.recording_bounds(source.source_sha256) == (1, 5)
    assert window.preferences.recording_calibration(source.source_sha256) == choice
    entered, release = Event(), Event()
    method = AnalysisService.request_configuration

    def blocked(
        self: AnalysisService,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        entered.set()
        assert release.wait(5)
        return method(self, configuration, calculation_time=calculation_time)

    monkeypatch.setattr(AnalysisService, "request_configuration", blocked)
    controller.request_markers((0, 6), CalibrationOverrides(gravity_index=3))
    try:
        assert entered.wait(5)
        window.close()
        window.show()
        open_source(window, synthetic_source(sampleRate=50), monkeypatch)
    finally:
        release.set()
    assert controller.pool.waitForDone(5000)
    QApplication.processEvents()
    assert window.preferences.recording_bounds(source.source_sha256) == (1, 5)
    assert window.preferences.recording_calibration(source.source_sha256) == choice


def test_chart_context_markers_save_reopen_and_reset_independently(
    explorer_window: ExplorerWindow,
) -> None:
    window = explorer_window
    original_bytes = SOURCE.read_bytes()
    window.open_path(SOURCE)
    wait_until(lambda: window.data is not None)
    data = window.data
    assert data is not None and data.analysis is not None
    original = data.ride_bounds
    indices = data.source.recording.indices
    assert indices.gravity is not None and indices.incline is not None
    gravity, incline = indices.gravity + 1, indices.incline + 1

    def choose(sample: int, text: str | None, *, enabled: bool = True) -> None:
        window.axis_x.setRange((sample - 100) / data.sample_rate, (sample + 100) / data.sample_rate)
        view = window.chart_view
        point = view.mapFromScene(window.chart.mapToScene(window.chart.plotArea().center()))
        viewport = window.axis_x.min(), window.axis_x.max()
        selected = window.slider.value()

        def pick() -> None:
            menu = QApplication.activePopupWidget()
            assert isinstance(menu, QMenu)
            actions = menu.actions()
            assert [a.text() for a in actions if not a.isSeparator()] == [
                "Set start here",
                "Set end here",
                "Set gravity here",
                "Set incline here",
                "Reset start to original",
                "Reset end to original",
                "Reset gravity to original",
                "Reset incline to original",
                "Reset all ride markers",
            ]
            assert actions[4].isSeparator() and actions[9].isSeparator()
            if text is not None:
                action = next(a for a in actions if a.text() == text)
                assert action.isEnabled() is enabled
                if enabled:
                    action.trigger()
            menu.close()

        QTimer.singleShot(0, pick)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.RightButton, pos=point)
        if text is None or not enabled:
            assert (window.axis_x.min(), window.axis_x.max()) == viewport
            assert window.slider.value() == selected

    def expect(bounds: tuple[int, int]) -> None:
        wait_until(lambda: window.data is not None and window.data.ride_bounds == bounds)

    choose(1700, None)
    choose(1700, "Set start here")
    expect((1700, original[1]))
    choose(9000, "Set end here")
    expect((1700, 9000))
    assert window.preferences.recording_bounds(data.source.source_sha256) == (1700, 9000)
    assert window.data is not None and window.data.replay_text(1700) == "00:00.00"
    choose(1000, "Set end here", enabled=False)
    expect((1700, 9000))
    previous = window.data.analysis
    assert previous is not None
    choose(gravity, "Set gravity here")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.gravity_index == gravity
        ),
    )
    assert window.data is not None and window.data.analysis is not None
    assert window.data.analysis.orientation is not previous.orientation
    orientation = window.data.analysis.orientation
    choose(incline, "Set incline here")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.incline_index == incline
        ),
    )
    assert window.data is not None and window.data.analysis is not None
    assert window.data.analysis.orientation is orientation
    assert dict(window.data.markers)["gravityIndex"] == gravity
    assert dict(window.data.markers)["inclineIndex"] == incline
    saved_calibration = window.preferences.recording_calibration(data.source.source_sha256)
    assert saved_calibration == window.data.analysis.configuration.calibration
    window.open_path(SOURCE)
    wait_until(lambda: window.data is not None and window.data.source is not data.source)
    expect((1700, 9000))
    assert window.slider.value() == 1700
    assert window.data is not None and window.data.analysis is not None
    assert window.data.analysis.configuration.calibration == saved_calibration
    choose(5000, "Reset start to original")
    expect((original[0], 9000))
    choose(5000, "Reset gravity to original")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.gravity_index is None
        ),
    )
    assert window.data is not None
    assert dict(window.data.markers)["gravityIndex"] == indices.gravity
    assert dict(window.data.markers)["inclineIndex"] == incline
    choose(gravity, "Set gravity here")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.gravity_index == gravity
        ),
    )
    choose(5000, "Reset incline to original")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.incline_index is None
        ),
    )
    assert window.data is not None
    assert dict(window.data.markers)["inclineIndex"] == indices.incline
    assert dict(window.data.markers)["gravityIndex"] == gravity
    choose(5000, "Reset gravity to original")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.calibration is None
        ),
    )
    assert window.preferences.recording_calibration(data.source.source_sha256) is None
    assert window.preferences.recording_bounds(data.source.source_sha256) == (original[0], 9000)
    choose(5000, "Reset end to original")
    expect(original)
    assert window.preferences.recording_bounds(data.source.source_sha256) is None
    choose(1800, "Set start here")
    expect((1800, original[1]))
    choose(9100, "Set end here")
    expect((1800, 9100))
    choose(gravity, "Set gravity here")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.calibration is not None
        ),
    )
    choose(incline, "Set incline here")
    wait_until(
        lambda: (
            window.data is not None
            and window.data.analysis is not None
            and window.data.analysis.configuration.calibration.incline_index == incline
        ),
    )
    choose(5000, "Reset all ride markers")
    expect(original)
    assert window.preferences.recording_bounds(data.source.source_sha256) is None
    assert window.preferences.recording_calibration(data.source.source_sha256) is None
    assert window.data is not None and window.data.analysis is not None
    assert window.data.analysis.calibration is None
    assert window.data.source.recording.indices == indices
    assert SOURCE.read_bytes() == original_bytes
