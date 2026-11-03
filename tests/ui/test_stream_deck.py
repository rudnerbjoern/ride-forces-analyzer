"""Native application routing, opt-in lifecycle and existing analysis adoption."""

# cspell:words qapp

from datetime import datetime
import json
import subprocess
import sys
from threading import Event

import pytest
from PySide6.QtCore import QEvent, QThreadPool, Qt, QUrl
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from PySide6.QtWebSockets import QWebSocket

from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.analysis.service import AnalysisService
from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.runtime import control_contract as wire
from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.runtime.instance import OpenRequest
from ride_forces_analyzer.storage.library import LibraryStore
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.application import RecordingApplication
from ride_forces_analyzer.ui.dialogs.settings import SettingsDialog
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow
from tests.analysis.test_recording_preparation import synthetic_source
from tests.ui.helpers import wait_until


class Device:
    def __init__(self, application: RecordingApplication) -> None:
        self.application = application
        self.socket = QWebSocket()
        self.messages: list[wire.ServerMessage] = []
        self.ready = False
        self.counter = 0
        self.socket.textMessageReceived.connect(self.received)
        endpoint = json.loads(application.stream_deck.transport.endpoint_path.read_text())
        self.socket.open(QUrl(f"ws://127.0.0.1:{endpoint['port']}"))
        wait_until(self.socket.isValid)
        self.socket.sendTextMessage(json.dumps({"version": 1, "token": endpoint["token"]}))
        wait_until(lambda: self.ready and bool(self.messages))

    def received(self, payload: str) -> None:
        if json.loads(payload).get("transport") == "ready":
            self.ready = True
        else:
            self.messages.append(wire.parse_server_message(payload))

    def request(
        self,
        action: wire.Action,
        *,
        target: wire.Target | None = None,
    ) -> wire.Result | wire.Failure:
        self.counter += 1
        context = target or self.application.stream_deck.snapshot().target
        assert context is not None
        command = wire.Command(
            version=wire.PROTOCOL_VERSION,
            type="command",
            id=str(self.counter),
            target=context,
            action=action,
        )
        self.socket.sendTextMessage(command.model_dump_json())
        wait_until(
            lambda: any(
                isinstance(value, (wire.Result, wire.Failure)) and value.id == command.id
                for value in self.messages
            ),
        )
        return next(
            value
            for value in self.messages
            if isinstance(value, (wire.Result, wire.Failure)) and value.id == command.id
        )

    def final(self, request_id: str) -> wire.Result | wire.Failure:
        wait_until(
            lambda: any(
                isinstance(value, (wire.Result, wire.Failure))
                and value.id == request_id
                and value.status != "pending"
                for value in self.messages
            ),
        )
        return next(
            value
            for value in self.messages
            if isinstance(value, (wire.Result, wire.Failure))
            and value.id == request_id
            and value.status != "pending"
        )


def activate(application: RecordingApplication, window: ExplorerWindow) -> None:
    window.show()
    window.raise_()
    window.activateWindow()
    window.plot.chart_view.setFocus()
    wait_until(
        lambda: (
            application.activeWindow() is window
            and application.stream_deck.snapshot().availability.available
        ),
    )


def exercise(application: RecordingApplication) -> None:
    application.settings = AppSettings(language=Language.ENGLISH)
    application.start(OpenRequest(new_window=True))
    window = application.windows[0]
    controller = application.stream_deck
    preferences = window.preferences
    assert not preferences.stream_deck_enabled()
    assert not controller.transport.server.isListening()
    assert not controller.transport.endpoint_path.exists()
    window.show_settings()
    dialog = window.findChild(SettingsDialog)
    assert dialog is not None and not dialog.stream_deck.isChecked()
    dialog.stream_deck.setChecked(True)
    dialog.reject()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not preferences.stream_deck_enabled()
    assert not controller.transport.server.isListening()
    window.show_settings()
    dialog = window.findChild(SettingsDialog)
    assert dialog is not None
    dialog.stream_deck.setChecked(True)
    dialog.save()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    activate(application, window)
    assert Preferences(preferences.path).stream_deck_enabled()
    assert controller.transport.endpoint_path.exists()
    device = Device(application)
    other_device = Device(application)
    source = synthetic_source(
        name="First ride",
        location="Park A",
        startIndex=20,
        endIndex=180,
        gravityIndex=0,
        inclineIndex=100,
        accelerationSequence=[{"x": 0, "y": 0, "z": 1}] * 70 + [{"x": 0, "y": 1, "z": 1}] * 131,
        gravitySequence=[{"x": 0, "y": 0, "z": 1}] * 201,
    )
    second_source = synthetic_source(name="Second ride", location="Park B")
    store = LibraryStore()
    store.archive(source, "first.forces", (20, 180), CalibrationOverrides())
    store.archive(second_source, "second.forces", (2, 6), CalibrationOverrides())
    window.library.refresh()
    window.open_archived(source.source_sha256)
    wait_until(lambda: window.data is not None and window.open_action.isEnabled())
    activate(application, window)
    assert window.data is not None
    original = window.data
    assert len(application.windows) == 1
    assert controller.snapshot().library is not None

    # Selection edits reuse the GUI range, clamp both boundaries and leave markers/analysis alone.
    selection_markers = controller.snapshot().markers
    selection_bounds = store.source(source.source_sha256).bounds
    selected_analysis = window.data.analysis
    window.inspector.first.setValue(40)
    window.inspector.last.setValue(100)
    wait_until(lambda: controller.snapshot().selection is not None)
    response = device.request(wire.SelectionStep(name="selection.step", boundary="start", steps=10))
    assert response.status == "ok" and window.inspector.first.value() == 50
    assert window.inspector.last.value() == 100
    device.request(wire.SelectionStep(name="selection.step", boundary="end", steps=-1))
    assert window.inspector.last.value() == 99
    selection = controller.snapshot().selection
    assert selection is not None and selection.start.sample == 50 and selection.end.sample == 99
    assert window.data.analysis is selected_analysis
    assert controller.snapshot().markers == selection_markers
    assert store.source(source.source_sha256).bounds == selection_bounds
    window.inspector.first.setValue(99)
    device.request(wire.SelectionStep(name="selection.step", boundary="start", steps=10))
    assert window.inspector.first.value() == 99
    device.request(wire.SelectionStep(name="selection.step", boundary="end", steps=-10))
    assert window.inspector.last.value() == 99
    window.inspector.first.setValue(0)
    device.request(wire.SelectionStep(name="selection.step", boundary="start", steps=-10))
    assert window.inspector.first.value() == 0
    window.inspector.last.setValue(window.data.count - 1)
    device.request(wire.SelectionStep(name="selection.step", boundary="end", steps=10))
    assert window.inspector.last.value() == window.data.count - 1
    device.request(wire.SimpleAction(name="view.selection"))
    assert window.plot.axis_x.min() == pytest.approx(window.data.time_at(0))
    assert window.plot.axis_x.max() == pytest.approx(window.data.time_at(window.data.count - 1))
    # GUI-originated changes reach both peers through the same state events.
    checkpoint = len(device.messages)
    window.inspector.first.setValue(20)
    window.inspector.last.setValue(180)
    wait_until(
        lambda: any(
            isinstance(value, wire.StateEvent)
            and value.selection is not None
            and value.selection.start.sample == 20
            and value.selection.end.sample == 180
            for value in device.messages[checkpoint:]
        ),
    )

    # Reuse actual controls; GUI changes also reach the connected devices.
    response = device.request(wire.CurveSet(name="curve.set", curve="first", enabled=False))
    assert response.status == "ok" and not window.visibility[0].isChecked()
    checkpoint = len(device.messages)
    window.visibility[0].setChecked(True)
    wait_until(
        lambda: any(
            isinstance(value, wire.StateEvent)
            and value.sequence > 1
            and value.curves
            and value.curves[0].active
            for value in device.messages[checkpoint:]
        ),
    )
    assert window.data.analysis is original.analysis
    assert (
        device.request(wire.CurveSet(name="curve.set", curve="calibrated", enabled=False)).status
        == "ok"
    )
    blocked = device.request(wire.CurveSet(name="curve.set", curve="combined", enabled=True))
    assert isinstance(blocked, wire.Failure) and blocked.reason == "unsupported"
    device.request(wire.CurveSet(name="curve.set", curve="calibrated", enabled=True))
    device.request(wire.CurveSet(name="curve.set", curve="combined", enabled=True))
    assert window.combined_toggle.isChecked()
    device.request(wire.SimpleAction(name="playback.toggle"))
    assert window.navigation.playback is not None and window.navigation.playback.playing
    device.request(wire.SettingStep(name="playback.speed.step", direction=1))
    assert window.navigation.playback.speed == 2
    assert window.navigation.playback.playing
    device.request(wire.SimpleAction(name="playback.speed.reset"))
    assert window.navigation.playback.speed == 1
    device.request(wire.PositionStep(name="position.step", steps=-10))
    assert not window.navigation.playback.playing
    device.request(wire.SettingStep(name="smoothing.step", direction=1))
    wait_until(lambda: window.data is not None and window.data.smoothing_window == 13)
    device.request(wire.SimpleAction(name="smoothing.reset"))
    wait_until(lambda: window.data is not None and window.data.smoothing_window == 11)
    # Repeated outward turns remain at the existing slider limits, without new analysis.
    smoothing = window.inspector.smoothing_slider
    boundaries: tuple[tuple[int, wire.Direction], ...] = (
        (smoothing.minimum(), -1),
        (smoothing.maximum(), 1),
    )
    for boundary, direction in boundaries:
        smoothing.setValue(boundary)
        expected_window = boundary * 2 + 1
        wait_until(
            lambda: window.data is not None and window.data.smoothing_window == expected_window,
        )
        wait_until(lambda: controller.snapshot().controls["smoothing.step"].available)
        assert window.data is not None
        adopted = window.data.analysis
        for _ in range(2):
            result = device.request(wire.SettingStep(name="smoothing.step", direction=direction))
            assert result.status == "ok"
            assert smoothing.value() == boundary
            assert window.data.smoothing_window == expected_window
            assert window.data.analysis is adopted
    device.request(wire.SimpleAction(name="smoothing.reset"))
    wait_until(lambda: window.data is not None and window.data.smoothing_window == 11)
    before = window.plot.axis_x.max() - window.plot.axis_x.min()
    device.request(wire.SettingStep(name="view.zoom", direction=1))
    assert window.plot.axis_x.max() - window.plot.axis_x.min() < before
    device.request(wire.SimpleAction(name="view.selection"))
    device.request(wire.SimpleAction(name="view.reset"))
    assert window.plot.axis_x.min() == window.data.default_time_range[0]

    # Every response is private to its originating authenticated connection.
    assert not any(
        isinstance(value, (wire.Result, wire.Failure)) for value in other_device.messages
    )
    target = controller.snapshot().target
    assert target is not None
    incompatible = wire.Command(
        version=wire.PROTOCOL_VERSION,
        type="command",
        id="future",
        target=target,
        action=wire.SimpleAction(name="view.reset"),
    ).model_dump()
    incompatible["version"] = 99
    device.socket.sendTextMessage(json.dumps(incompatible))
    future_error = device.final("future")
    assert isinstance(future_error, wire.Failure) and future_error.code == "unsupported_protocol"
    duplicate = wire.Command(
        version=wire.PROTOCOL_VERSION,
        type="command",
        id=str(device.counter),
        target=target,
        action=wire.SimpleAction(name="playback.toggle"),
    )
    device.socket.sendTextMessage(duplicate.model_dump_json())

    def duplicate_rejected() -> bool:
        return any(isinstance(v, wire.Failure) and v.id == duplicate.id for v in device.messages)

    wait_until(duplicate_rejected)
    duplicate_error = next(
        v for v in device.messages if isinstance(v, wire.Failure) and v.id == duplicate.id
    )
    assert duplicate_error.code == "invalid_command"
    assert not window.navigation.playback.playing
    window.navigation.position.setFocus()
    wait_until(lambda: isinstance(controller.snapshot().availability, wire.Unavailable))
    blocked = device.request(wire.PositionStep(name="position.step", steps=1))
    assert isinstance(blocked, wire.Failure) and blocked.reason == "input_focus"
    activate(application, window)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            application,
            "applicationState",
            lambda: Qt.ApplicationState.ApplicationInactive,
        )
        blocked = device.request(wire.SimpleAction(name="playback.toggle"))
        assert isinstance(blocked, wire.Failure) and blocked.reason == "background"
    modal = QDialog(window)
    modal.setWindowModality(Qt.WindowModality.WindowModal)
    modal.show()
    wait_until(lambda: application.activeModalWidget() is modal)
    blocked = device.request(wire.SimpleAction(name="playback.toggle"))
    assert isinstance(blocked, wire.Failure) and blocked.reason == "dialog_open"
    modal.close()
    activate(application, window)

    # Previews never persist; only the existing adopted analysis saves markers.
    analysis = window.analysis_controller
    assert analysis is not None
    saved = store.markers(source)
    for name in ("gravity", "incline"):
        device.request(wire.MarkerPreview(name="marker.preview", marker=name, steps=1))
        device.request(wire.MarkerDecision(name="marker.discard", marker=name))
    device.request(wire.MarkerPreview(name="marker.preview", marker="start", steps=1))
    device.request(wire.MarkerPreview(name="marker.preview", marker="end", steps=-1))
    assert window.data.ride_bounds == (20, 180)
    assert store.markers(source) == saved
    entered, release = Event(), Event()
    original_configuration = AnalysisService.request_configuration

    def delayed(
        self: AnalysisService,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        entered.set()
        assert release.wait(10)
        return original_configuration(self, configuration, calculation_time=calculation_time)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(AnalysisService, "request_configuration", delayed)
        try:
            response = device.request(wire.MarkerDecision(name="marker.apply", marker="start"))
            assert isinstance(response, wire.Result) and response.status == "pending"
            wait_until(entered.is_set)
            assert store.markers(source) == saved
            blocked = device.request(wire.MarkerDecision(name="marker.apply", marker="end"))
            assert isinstance(blocked, wire.Failure) and blocked.reason == "busy"
        finally:
            release.set()
        assert device.final(response.id).status == "ok"
    assert window.data.ride_bounds == (21, 180)
    stored = store.markers(source)
    assert stored is not None and stored[0] == (21, 180)
    calibration_cases: tuple[tuple[wire.MarkerName, int], ...] = (("gravity", 1), ("incline", 101))
    for name, expected in calibration_cases:
        device.request(wire.MarkerPreview(name="marker.preview", marker=name, steps=1))
        response = device.request(wire.MarkerDecision(name="marker.apply", marker=name))
        assert isinstance(response, wire.Result) and response.status == "pending"
        assert device.final(response.id).status == "ok"
        adopted = next(value for value in controller.snapshot().markers if value.marker == name)
        assert adopted.applied is not None and adopted.applied.sample == expected
    stored = store.markers(source)
    assert stored is not None and stored[0] == (21, 180)
    assert stored[1].gravity_index == 1 and stored[1].incline_index == 101
    assert (
        next(value for value in controller.snapshot().markers if value.marker == "end").preview
        is not None
    )

    def failed(
        self: AnalysisService,
        configuration: AnalysisConfiguration,
        *,
        calculation_time: datetime,
    ) -> int:
        raise ValueError("Controlled analysis failure")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(AnalysisService, "request_configuration", failed)
        response = device.request(wire.MarkerDecision(name="marker.apply", marker="end"))
        assert isinstance(response, wire.Result) and response.status == "pending"
        assert device.final(response.id).status == "error"
    marker = next(value for value in controller.snapshot().markers if value.marker == "end")
    assert marker.status == "failed" and marker.applied is not None and marker.applied.sample == 180
    stored = store.markers(source)
    assert stored is not None and stored[0] == (21, 180)
    device.request(wire.MarkerDecision(name="marker.discard", marker="end"))
    assert (
        next(value for value in controller.snapshot().markers if value.marker == "end").preview
        is None
    )

    # Visible Library order, filtering, cyclic movement and current-window opening.
    selection = controller.snapshot().library
    assert selection is not None and selection.count == 2 and selection.selected is not None
    initial = selection.selected.id
    loaded = window.data
    device.request(wire.LibraryMove(name="library.move", direction=1))
    assert window.data is loaded and window.open_action.isEnabled()
    selection = controller.snapshot().library
    assert (
        selection is not None
        and selection.selected is not None
        and selection.selected.id != initial
    )
    device.request(wire.LibraryMove(name="library.move", direction=1))
    assert window.data is loaded and window.open_action.isEnabled()
    selection = controller.snapshot().library
    assert (
        selection is not None
        and selection.selected is not None
        and selection.selected.id == initial
    )
    device.request(wire.LibraryMove(name="library.move", direction=-1))
    assert window.data is loaded and window.open_action.isEnabled()
    selection = controller.snapshot().library
    assert selection is not None and selection.selected is not None
    selected = selection.selected.id
    device.request(wire.SimpleAction(name="library.open"))
    wait_until(
        lambda: (
            window.data is not None
            and window.data.source.source_sha256 == selected
            and window.open_action.isEnabled()
        ),
    )
    assert len(application.windows) == 1
    window.library.search.setText("First ride")
    selection = controller.snapshot().library
    assert selection is not None and selection.count == 1
    loaded = window.data
    device.request(wire.LibraryMove(name="library.move", direction=1))
    device.request(wire.LibraryMove(name="library.move", direction=-1))
    selection = controller.snapshot().library
    assert selection is not None and selection.selected is not None
    assert selection.selected.id == source.source_sha256 and selection.selected.index == 0
    assert window.data is loaded and len(application.windows) == 1
    window.library.search.setText("no matching recording")
    blocked = device.request(wire.LibraryMove(name="library.move", direction=1))
    assert isinstance(blocked, wire.Failure) and blocked.reason == "empty_library"
    window.library.search.clear()
    with pytest.MonkeyPatch.context() as patch:
        imports: list[bool] = []
        patch.setattr(window, "choose_file", lambda: imports.append(True))
        device.request(wire.SimpleAction(name="library.import"))
        assert imports == [True]

    # Active Explorer changes invalidate old targets/previews without a fallback.
    activate(application, window)
    old_target = controller.snapshot().target
    assert old_target is not None
    other = application.create_window()
    activate(application, other)
    state = controller.snapshot()
    assert state.target is not None and state.target.window_id != old_target.window_id
    blocked = device.request(wire.SimpleAction(name="library.import"), target=old_target)
    assert isinstance(blocked, wire.Failure) and blocked.code == "stale_target"
    other.close()
    activate(application, window)
    outside = QWidget()
    outside.show()
    outside.activateWindow()
    wait_until(lambda: application.activeWindow() is outside)
    assert controller.snapshot().target is None
    assert controller.snapshot().availability == wire.Unavailable(
        available=False,
        reason="no_active_window",
    )
    outside.close()
    activate(application, window)

    # Save off disconnects every client and removes discovery; Save on survives exit.
    window.show_settings()
    dialog = window.findChild(SettingsDialog)
    assert dialog is not None and dialog.stream_deck.isChecked()
    dialog.stream_deck.setChecked(False)
    dialog.save()
    wait_until(lambda: not device.socket.isValid() and not other_device.socket.isValid())
    assert not controller.transport.endpoint_path.exists()
    assert not controller.transport.server.isListening()
    assert not Preferences(preferences.path).stream_deck_enabled()
    preferences.remember_stream_deck_enabled(True)
    window.close()
    QThreadPool.globalInstance().waitForDone()
    controller.close()
    QApplication.processEvents()
    print("Stream Deck native actions: passed", flush=True)


def startup(application: RecordingApplication) -> None:
    application.settings = AppSettings(language=Language.ENGLISH)
    assert Preferences().stream_deck_enabled()
    application.start(OpenRequest(new_window=True))
    assert application.stream_deck.transport.server.isListening()
    assert application.stream_deck.transport.endpoint_path.exists()
    for window in application.windows[:]:
        window.close()
    application.stream_deck.close()
    assert not application.stream_deck.transport.endpoint_path.exists()
    print("Stream Deck saved startup: passed", flush=True)


def test_application_actions_and_saved_startup_share_native_sessions() -> None:
    for phase in ("exercise", "startup"):
        result = subprocess.run(
            [sys.executable, "-m", "tests.ui.test_stream_deck", phase],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=100,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "passed" in result.stdout, result.stdout + result.stderr


if __name__ == "__main__":
    app = RecordingApplication([])
    try:
        exercise(app) if sys.argv[1] == "exercise" else startup(app)
    finally:
        app.stream_deck.close()
        for remaining in app.windows[:]:
            remaining.close()
        QThreadPool.globalInstance().waitForDone()
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
