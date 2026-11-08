"""Route authenticated device commands through existing GUI actions and services.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, replace
from functools import partial
import json
from typing import Literal, cast, get_args
from uuid import uuid4

from pydantic import ValidationError
from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QTimer, Slot
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime import control_contract as wire
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.runtime.stream_deck import ControlServer
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.explorer.window import ExplorerWindow

_MARKERS: tuple[wire.MarkerName, ...] = ("start", "gravity", "incline", "end")
_CURVES: tuple[wire.CurveName, ...] = ("first", "second", "third", "combined", "calibrated")


@dataclass(frozen=True)
class _Pending:
    """Retain the originating connection until an existing analysis is adopted.

    Attributes:
        client: Authenticated sender awaiting its final response.
        command: Original request and its immutable target.
        window: Explorer whose analysis is being updated.
        marker: Marker being applied.
        sample: Requested source-sample position.
    """

    client: QWebSocket
    command: wire.Command
    window: ExplorerWindow
    marker: wire.MarkerName
    sample: int


class StreamDeckController(QObject):
    """Own the optional server and route control on the application's Qt thread.

    Attributes:
        application: Existing application, used for foreground/focus checks.
        preferences: Existing user-preference store.
        transport: Authenticated loopback server, stopped unless explicitly enabled.
    """

    def __init__(self, application: QApplication, preferences: Preferences) -> None:
        """Create a stopped controller without publishing an endpoint.

        Args:
            application: Application owning this controller and its GUI thread.
            preferences: Store containing the saved opt-in preference.
        """
        super().__init__(application)
        self.application = application
        self.preferences = preferences
        self.transport = ControlServer(parent=self)
        self.transport.command_received.connect(self._receive)
        self._windows: dict[ExplorerWindow, tuple[str, int]] = {}
        self._context: tuple[ExplorerWindow, int] | None = None
        self._generation = 0
        self._session = uuid4().hex
        self._sequence = 0
        self._last_state = ""
        self._previews: dict[wire.MarkerName, int] = {}
        self._errors: dict[wire.MarkerName, wire.ErrorCode] = {}
        self._apply_ids: dict[wire.MarkerName, str] = {}
        self._pending: _Pending | None = None
        self._requests: dict[QWebSocket, set[str]] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(75)
        self._timer.timeout.connect(self.publish)
        application.installEventFilter(self)
        application.focusChanged.connect(self.schedule)
        application.applicationStateChanged.connect(self.schedule)
        application.aboutToQuit.connect(self.close)

    def register(self, window: ExplorerWindow) -> None:
        """Subscribe to existing UI signals without polling or recalculating data.

        Args:
            window: Newly registered Explorer in the same application.
        """
        self._windows[window] = uuid4().hex, 0
        window.closed.connect(partial(self._closed, window))
        window.recording_changed.connect(partial(self._recording_changed, window))
        window.stream_deck_selected.connect(self.set_enabled)
        window.open_action.changed.connect(self.schedule)
        window.windowTitleChanged.connect(self.schedule)
        window.navigation.sample_changed.connect(self.schedule)
        window.navigation.play_button.clicked.connect(self.schedule)
        window.navigation.playback_speed.currentIndexChanged.connect(self.schedule)
        window.navigation.playback_timer.timeout.connect(self.schedule)
        window.plot.axis_x.rangeChanged.connect(self.schedule)
        window.inspector.selection_changed.connect(self.schedule)
        window.inspector.smoothing_slider.valueChanged.connect(self.schedule)
        for checkbox in (*window.visibility, window.reference_toggle, window.combined_toggle):
            checkbox.toggled.connect(self.schedule)
        window.library.recordings.currentItemChanged.connect(self.schedule)
        window.library.recordings.model().modelReset.connect(self.schedule)
        window.library.recordings.model().rowsInserted.connect(self.schedule)
        window.library.search.textChanged.connect(self.schedule)
        for control in (window.library.park_filter, window.library.workflow_filter):
            control.currentIndexChanged.connect(self.schedule)
            model = control.model()
            model.dataChanged.connect(self.schedule)
            model.rowsInserted.connect(self.schedule)
            model.rowsRemoved.connect(self.schedule)
            model.modelReset.connect(self.schedule)
        window.library.changed.connect(self.schedule)
        analysis = window.analysis_controller
        if analysis is not None:
            analysis.pending_changed.connect(self.schedule)
            analysis.snapshot_ready.connect(partial(self._analysis_ready, window))
            analysis.failed.connect(partial(self._analysis_failed, window))
        if self.transport.server.isListening() and window.library.park_filter.count() == 0:
            window.library.refresh()
        self.schedule()

    @Slot(bool)
    def set_enabled(self, enabled: bool) -> None:
        """Apply the already saved setting and start or stop the local server.

        Args:
            enabled: Whether Stream Deck control should be available.
        """
        if not enabled:
            self.close()
            return
        if self.transport.server.isListening():
            return
        self._session = uuid4().hex
        self._last_state = ""
        self._sequence = 0
        try:
            for registered in self._windows:
                if registered.library.park_filter.count() == 0:
                    registered.library.refresh()
            self.transport.start()
            self.publish()
        except (OSError, RuntimeError) as error:
            record_error("Stream Deck", error)
            window = self._active_window()
            if window is not None:
                window.statusBar().showMessage(tr("Could not enable Stream Deck: {0}", str(error)))

    @Slot()
    def close(self) -> None:
        """Stop discovery, connected clients and pending device feedback."""
        self._timer.stop()
        self._pending = None
        self._previews.clear()
        for window in self._windows:
            window.plot.set_marker_previews({})
        self._errors.clear()
        self._apply_ids.clear()
        try:
            self.transport.close()
        except OSError as error:
            record_error("Stream Deck shutdown", error)
        self._requests.clear()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Observe focus, modal and popup changes without consuming GUI events.

        Args:
            watched: Qt object receiving the event.
            event: Original event being observed.

        Returns:
            False, preserving normal application interaction.
        """
        if event.type() in {
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        }:
            self.schedule()
        return False

    def schedule(self, *_arguments: object) -> None:
        """Coalesce GUI-originated feedback while the integration is enabled.

        Args:
            *_arguments: Existing Qt signal arguments, which need no interpretation.
        """
        if self.transport.server.isListening() and not self._timer.isActive():
            self._timer.start()

    def _active_window(self) -> ExplorerWindow | None:
        """Resolve the active registered Explorer through any owned dialog."""
        widget = self.application.activeWindow()
        while widget is not None:
            if isinstance(widget, ExplorerWindow) and widget in self._windows:
                return widget
            widget = widget.parentWidget()
        return None

    def _target(self) -> tuple[ExplorerWindow | None, wire.Target | None]:
        """Discard stale previews when the active window or recording changes."""
        window = self._active_window()
        context = (window, self._windows[window][1]) if window is not None else None
        if context != self._context:
            pending, self._pending = self._pending, None
            if pending is not None:
                self._failure(pending.client, pending.command, "target.stale")
            self._context = context
            self._generation += 1
            self._previews.clear()
            for registered in self._windows:
                registered.plot.set_marker_previews({})
            self._errors.clear()
            self._apply_ids.clear()
        if window is None:
            return None, None
        return window, wire.Target(
            window_id=self._windows[window][0],
            recording_id=window.data.source.source_sha256 if window.data is not None else None,
            generation=self._generation,
        )

    def _global_availability(self, window: ExplorerWindow | None) -> wire.Availability:
        """Apply foreground, input, modal and import guards before dispatch."""
        reason: wire.UnavailableReason | None = None
        if window is None:
            reason = "window.active.missing"
        elif self.application.applicationState() != Qt.ApplicationState.ApplicationActive:
            reason = "application.background"
        elif (
            self.application.activeModalWidget() is not None
            or self.application.activePopupWidget() is not None
        ):
            reason = "dialog.open"
        elif isinstance(
            self.application.focusWidget(),
            (QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit),
        ):
            reason = "input.focused"
        elif not window.open_action.isEnabled():
            reason = "application.busy"
        return (
            wire.Unavailable(available=False, reason=reason)
            if reason
            else wire.Available(available=True)
        )

    @staticmethod
    def _library_items(window: ExplorerWindow) -> list[QTreeWidgetItem]:
        """Read selectable rows in the existing filtered visual ordering."""
        items: list[QTreeWidgetItem] = []
        iterator = QTreeWidgetItemIterator(window.library.recordings)
        while iterator.value():
            item = iterator.value()
            if isinstance(item.data(0, Qt.ItemDataRole.UserRole), str) and not item.isHidden():
                items.append(item)
            iterator += 1
        return items

    @staticmethod
    def _positions(window: ExplorerWindow) -> dict[wire.MarkerName, int | None]:
        """Read adopted marker values without inferring absent calibration indices."""
        data = window.data
        if data is None:
            return {name: None for name in _MARKERS}
        indices = data.source.recording.indices
        calibration = data.analysis.configuration.calibration if data.analysis is not None else None
        return {
            "start": data.ride_bounds[0],
            "end": data.ride_bounds[1],
            "gravity": calibration.gravity_index
            if calibration and calibration.gravity_index is not None
            else indices.gravity,
            "incline": calibration.incline_index
            if calibration and calibration.incline_index is not None
            else indices.incline,
        }

    @staticmethod
    def _position(window: ExplorerWindow, sample: int | None) -> wire.Position | None:
        """Use existing source-time and replay-label formatting for feedback."""
        data = window.data
        return (
            wire.Position(
                sample=sample,
                time_seconds=data.time_at(sample),
                label=data.replay_text(sample),
            )
            if data is not None and sample is not None
            else None
        )

    def _marker_availability(
        self,
        window: ExplorerWindow,
        marker: wire.MarkerName,
    ) -> dict[Literal["preview", "apply", "discard"], wire.Availability]:
        """Expose preview/apply/discard guards for the current marker context."""
        reason: wire.UnavailableReason | None = None
        if window.data is None:
            reason = "recording.missing"
        elif window.analysis_controller is None or window.data.analysis is None:
            reason = "operation.unsupported"
        elif window.analysis_controller.pending:
            reason = "application.busy"
        preview = self._previews.get(marker)
        apply_reason = reason
        if preview is None:
            apply_reason = apply_reason or "preview.missing"
        elif window.data is not None and (
            (marker == "start" and preview > window.data.ride_bounds[1])
            or (marker == "end" and preview < window.data.ride_bounds[0])
        ):
            apply_reason = apply_reason or "marker.invalid"
        return {
            "preview": wire.Unavailable(available=False, reason=reason or "marker.invalid")
            if reason or self._positions(window)[marker] is None
            else wire.Available(available=True),
            "apply": wire.Unavailable(available=False, reason=apply_reason)
            if apply_reason
            else wire.Available(available=True),
            "discard": wire.Unavailable(
                available=False,
                reason="application.busy"
                if self._pending is not None and self._pending.marker == marker
                else "preview.missing",
            )
            if preview is None or (self._pending is not None and self._pending.marker == marker)
            else wire.Available(available=True),
        }

    def snapshot(self) -> wire.StateEvent:
        """Read existing controls and prepared values for one complete wire snapshot.

        Returns:
            Actual application state; unavailable values are explicit nulls.
        """
        window, target = self._target()
        global_state = self._global_availability(window)
        controls: dict[wire.ActionName, wire.Availability] = {
            name: global_state for name in get_args(wire.ActionName)
        }
        state = wire.StateEvent(
            version=wire.PROTOCOL_VERSION,
            type="state",
            session_id=self._session,
            sequence=self._sequence,
            target=target,
            availability=global_state,
            controls=controls,
            library=None,
            playback=None,
            view=None,
            selection=None,
            curves=(),
            markers=(),
        )
        controls = state.controls
        if window is None:
            return state
        items = self._library_items(window)
        current = window.library.recordings.currentItem()
        entry = window.library.selected_entry
        filters = tuple(
            wire.LibraryFilterState(
                value=control.currentData(),
                options=tuple(
                    wire.LibraryFilterOption(
                        value=control.itemData(index),
                        label=control.itemText(index),
                    )
                    for index in range(control.count())
                ),
            )
            for control in (window.library.park_filter, window.library.workflow_filter)
        )
        library = wire.LibraryState(
            count=len(items),
            park_filter=filters[0],
            status_filter=filters[1],
            selected=wire.LibraryEntry(
                id=entry.source_sha256,
                title=entry.ride_name or entry.filename,
                index=items.index(current),
            )
            if entry is not None and current is not None and current in items
            else None,
        )
        if not items:
            controls["library.move"] = wire.Unavailable(available=False, reason="library.empty")
        if library.selected is None:
            controls["library.open.same"] = wire.Unavailable(
                available=False,
                reason="selection.missing",
            )
            controls["library.open.new"] = controls["library.open.same"]
        data = window.data
        if data is None:
            for name in controls:
                if not name.startswith("library."):
                    controls[name] = wire.Unavailable(available=False, reason="recording.missing")
            return state.model_copy(update={"library": library})
        if not window.inspector.first.isEnabled() or not window.inspector.last.isEnabled():
            controls["selection.step"] = wire.Unavailable(
                available=False,
                reason="application.busy",
            )
        for name in ("smoothing.step", "smoothing.reset"):
            if not window.inspector.smoothing_slider.isEnabled():
                controls[name] = wire.Unavailable(available=False, reason="operation.unsupported")
            elif window.analysis_controller is not None and window.analysis_controller.pending:
                controls[name] = wire.Unavailable(available=False, reason="application.busy")
        navigation = window.navigation
        playback = wire.PlaybackState(
            playing=navigation.playback is not None and navigation.playback.playing,
            speed=navigation.playback.speed if navigation.playback is not None else 1.0,
            position=self._position(window, navigation.slider.value()),
            last_sample=navigation.slider.maximum(),
        )
        view = wire.ViewState(
            start_seconds=window.plot.axis_x.min(),
            end_seconds=window.plot.axis_x.max(),
            smoothing_window=data.smoothing_window,
        )
        selection_start = self._position(window, window.inspector.first.value())
        selection_end = self._position(window, window.inspector.last.value())
        assert selection_start is not None and selection_end is not None
        selection = wire.SelectionState(start=selection_start, end=selection_end)
        checkboxes = (*window.visibility, window.combined_toggle, window.reference_toggle)
        curves = tuple(
            wire.CurveState(
                curve=name,
                label=checkbox.text(),
                active=checkbox.isChecked() and (name != "combined" or data.calibrated_enabled),
                availability=wire.Available(available=True)
                if checkbox.isEnabled() and (name != "combined" or data.calibrated_enabled)
                else wire.Unavailable(available=False, reason="operation.unsupported"),
            )
            for name, checkbox in zip(_CURVES, checkboxes, strict=True)
        )
        positions = self._positions(window)
        markers = tuple(
            wire.MarkerState(
                marker=marker,
                applied=self._position(window, positions[marker]),
                preview=self._position(window, self._previews.get(marker)),
                status="pending"
                if self._pending is not None and self._pending.marker == marker
                else "failed"
                if marker in self._errors
                else "preview"
                if marker in self._previews
                else "applied",
                request_id=self._apply_ids.get(marker),
                error=self._errors.get(marker),
                availability=self._marker_availability(window, marker),
            )
            for marker in _MARKERS
        )
        return state.model_copy(
            update={
                "library": library,
                "playback": playback,
                "view": view,
                "selection": selection,
                "curves": curves,
                "markers": markers,
            },
        )

    @Slot()
    def publish(self) -> None:
        """Publish changed snapshots only, coalescing unchanged GUI notifications."""
        if not self.transport.server.isListening():
            return
        state = self.snapshot()
        if self._context is not None:
            self._context[0].plot.set_marker_previews(
                {f"{marker}Index": sample for marker, sample in self._previews.items()},
            )
        signature = state.model_dump_json(exclude={"sequence"})
        if signature != self._last_state:
            self._last_state = signature
            self._sequence += 1
            self.transport.publish_state(
                state.model_copy(update={"sequence": self._sequence}).model_dump_json(),
            )

    @Slot(object, str)
    def _receive(self, sender: object, payload: str) -> None:
        """Validate, correlate and guard one authenticated command before execution."""
        if not isinstance(sender, QWebSocket):
            return
        try:
            command = wire.parse_command(payload)
        except ValidationError:
            code: wire.ErrorCode = "command.invalid"
            request_id: str | None = None
            target: wire.Target | None = None
            try:
                value: object = json.loads(payload)
                if isinstance(value, dict):
                    envelope = cast(dict[str, object], value)
                    if (
                        type(envelope.get("version")) is int
                        and envelope.get("version") != wire.PROTOCOL_VERSION
                    ):
                        code = "protocol.unsupported"
                    raw_id = envelope.get("id")
                    if isinstance(raw_id, str) and 0 < len(raw_id) <= 128:
                        request_id = raw_id
                    try:
                        target = wire.Target.model_validate(envelope.get("target"))
                    except ValidationError:
                        pass
            except ValueError:
                pass
            self.transport.reply(
                sender,
                wire.Failure(
                    version=wire.PROTOCOL_VERSION,
                    type="response",
                    id=request_id,
                    target=target,
                    status="error",
                    code=code,
                    reason=None,
                ).model_dump_json(),
            )
            return
        if sender not in self._requests:
            self._requests[sender] = set()
            sender.disconnected.connect(partial(self._requests.pop, sender, None))
        if command.id in self._requests[sender]:
            self._failure(sender, command, "command.invalid")
            return
        self._requests[sender].add(command.id)
        state = self.snapshot()
        if command.target != state.target:
            self._failure(sender, command, "target.stale")
            return
        availability = (
            state.availability
            if not state.availability.available
            else state.controls[command.action.name]
        )
        if isinstance(availability, wire.Unavailable):
            self._failure(sender, command, "command.unavailable", availability.reason)
            return
        window = self._active_window()
        if window is None:
            self._failure(sender, command, "target.stale")
            return
        action = command.action
        if isinstance(action, wire.LibraryFilterSet):
            filter_control = (
                window.library.park_filter
                if action.filter == "park"
                else window.library.workflow_filter
            )
            if filter_control.findData(action.value) < 0:
                self._failure(sender, command, "command.invalid")
                return
        if isinstance(action, (wire.MarkerPreview, wire.MarkerDecision)):
            marker = next(value for value in state.markers if value.marker == action.marker)
            choice: Literal["preview", "apply", "discard"] = (
                "preview"
                if isinstance(action, wire.MarkerPreview)
                else "apply"
                if action.name == "marker.apply"
                else "discard"
            )
            permitted = marker.availability[choice]
            if isinstance(permitted, wire.Unavailable):
                self._failure(sender, command, "command.unavailable", permitted.reason)
                return
        if isinstance(action, wire.CurveSet):
            curve = next(value for value in state.curves if value.curve == action.curve)
            if isinstance(curve.availability, wire.Unavailable):
                self._failure(sender, command, "command.unavailable", curve.availability.reason)
                return
        status = self._execute(window, sender, command)
        self.transport.reply(
            sender,
            wire.Result(
                version=wire.PROTOCOL_VERSION,
                type="response",
                id=command.id,
                target=command.target,
                status=status,
            ).model_dump_json(),
        )
        self.publish()

    def _execute(
        self,
        window: ExplorerWindow,
        sender: QWebSocket,
        command: wire.Command,
    ) -> Literal["ok", "pending"]:
        """Invoke existing controls; delegate marker analysis and persistence."""
        action = command.action
        navigation = window.navigation
        if isinstance(action, wire.LibraryMove):
            window.library.toggle_button.setChecked(True)
            items = self._library_items(window)
            current = window.library.recordings.currentItem()
            index = (
                items.index(current)
                if current is not None and current in items
                else (-1 if action.direction > 0 else 0)
            )
            selected = items[(index + action.direction) % len(items)]
            # Retain the existing selection presentation without its mouse-open signal.
            with QSignalBlocker(window.library):
                window.library.recordings.setCurrentItem(selected)
            window.library.recordings.scrollToItem(selected)
            window.library.notify_view_changed()
        elif isinstance(action, wire.LibraryFilterSet):
            filter_control = (
                window.library.park_filter
                if action.filter == "park"
                else window.library.workflow_filter
            )
            filter_control.setCurrentIndex(filter_control.findData(action.value))
        elif isinstance(action, wire.PositionStep):
            navigation.pause()
            navigation.step_sample(action.steps)
        elif isinstance(action, wire.SelectionStep):
            control = (
                window.inspector.first if action.boundary == "start" else window.inspector.last
            )
            control.setValue(control.value() + action.steps)
        elif isinstance(action, wire.CurveSet):
            (*window.visibility, window.combined_toggle, window.reference_toggle)[
                _CURVES.index(action.curve)
            ].setChecked(action.enabled)
        elif isinstance(action, wire.SettingStep):
            if action.name == "playback.speed.step":
                navigation.playback_speed.setCurrentIndex(
                    max(0, min(2, navigation.playback_speed.currentIndex() + action.direction)),
                )
            elif action.name == "smoothing.step":
                window.inspector.smoothing_slider.setValue(
                    window.inspector.smoothing_slider.value() + action.direction,
                )
            else:
                window.zoom_wheel(0.5, action.direction)
        elif isinstance(action, wire.MarkerPreview):
            navigation.pause()
            original = self._previews.get(action.marker, self._positions(window)[action.marker])
            assert original is not None and window.data is not None
            first, last = window.data.ride_bounds
            low = first if action.marker == "end" else 0
            high = last if action.marker == "start" else navigation.slider.maximum()
            self._previews[action.marker] = max(low, min(high, original + action.steps))
            self._errors.pop(action.marker, None)
            window.plot.reveal_sample(self._previews[action.marker])
        elif isinstance(action, wire.MarkerDecision):
            if action.name == "marker.discard":
                self._previews.pop(action.marker, None)
                self._errors.pop(action.marker, None)
                self._apply_ids.pop(action.marker, None)
            else:
                assert (
                    window.data is not None
                    and window.data.analysis is not None
                    and window.analysis_controller is not None
                )
                sample = self._previews[action.marker]
                bounds = window.data.ride_bounds
                calibration = window.data.analysis.configuration.calibration
                if action.marker == "start":
                    bounds = sample, bounds[1]
                elif action.marker == "end":
                    bounds = bounds[0], sample
                elif action.marker == "gravity":
                    calibration = replace(calibration, gravity_index=sample)
                else:
                    calibration = replace(calibration, incline_index=sample)
                self._errors.pop(action.marker, None)
                self._apply_ids[action.marker] = command.id
                self._pending = _Pending(sender, command, window, action.marker, sample)
                window.analysis_controller.request_markers(bounds, calibration)
                return "pending"
        else:
            if action.name == "library.open.same":
                entry = window.library.selected_entry
                assert entry is not None
                window.open_archived(entry.source_sha256)
            elif action.name == "library.open.new":
                window.library.new_window_action.trigger()
            elif action.name == "library.import":
                window.choose_file()
            elif action.name == "library.filter.reset":
                window.library.clear_filters.click()
            elif action.name == "playback.toggle":
                navigation.toggle_playback()
            elif action.name == "playback.speed.reset":
                navigation.playback_speed.setCurrentIndex(1)
            elif action.name == "smoothing.reset":
                window.inspector.smoothing_slider.setValue(5)
            elif action.name == "view.selection":
                window.zoom_selection()
            else:
                window.reset_view()
        return "ok"

    def _failure(
        self,
        client: QWebSocket,
        command: wire.Command,
        code: wire.ErrorCode,
        reason: wire.UnavailableReason | None = None,
    ) -> None:
        """Send a correlated error only to the originating authenticated client."""
        self.transport.reply(
            client,
            wire.Failure(
                version=wire.PROTOCOL_VERSION,
                type="response",
                id=command.id,
                target=command.target,
                status="error",
                code=code,
                reason=reason,
            ).model_dump_json(),
        )

    def _analysis_ready(self, window: ExplorerWindow, _snapshot: object) -> None:
        """Confirm an apply only after its requested marker is actually adopted."""
        self._target()
        pending = self._pending
        if pending is not None and pending.window is window:
            self._pending = None
            if self._positions(window)[pending.marker] == pending.sample:
                self._previews.pop(pending.marker, None)
                self._errors.pop(pending.marker, None)
                self.transport.reply(
                    pending.client,
                    wire.Result(
                        version=wire.PROTOCOL_VERSION,
                        type="response",
                        id=pending.command.id,
                        target=pending.command.target,
                        status="ok",
                    ).model_dump_json(),
                )
            else:
                self._errors[pending.marker] = "analysis.failed"
                self._failure(pending.client, pending.command, "analysis.failed")
        self.schedule()

    def _analysis_failed(self, window: ExplorerWindow, _message: str) -> None:
        """Retain adopted values and expose the unsuccessful preview to the device."""
        self._target()
        pending = self._pending
        if pending is not None and pending.window is window:
            self._pending = None
            self._errors[pending.marker] = "analysis.failed"
            self._failure(pending.client, pending.command, "analysis.failed")
        self.schedule()

    def _recording_changed(self, window: ExplorerWindow) -> None:
        """Invalidate device targets even when the same recording is reopened."""
        identifier, generation = self._windows[window]
        self._windows[window] = identifier, generation + 1
        self.schedule()

    def _closed(self, window: ExplorerWindow) -> None:
        """Stop routing to a closed window without selecting a fallback."""
        self._windows.pop(window, None)
        self.schedule()
