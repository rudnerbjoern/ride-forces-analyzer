"""Sample navigation, prepared force readouts and UI transport for the playback clock.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""
# cspell:words Pixmap

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.translation import (
    bind,
    items,
)

from time import monotonic

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStyle,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.playback import SamplePlayback


from .chart import ExplorerChart


from .controls import create_panel
from ride_forces_analyzer.ui.presentation.theme import Theme


class ExplorerNavigation(QFrame):
    """Own playback controls and use the existing source-sample playback clock.

    Attributes:
        sample_changed: Signal carrying the integer source sample being displayed.
        data: Prepared recording presentation, or None before loading.
        theme: Palette for force cards and context hints.
        plot: Chart receiving cursor positions and viewport following.
        playback: Existing monotonic source-sample clock, or None before loading.
        playback_timer: Precise Qt timer transporting clock positions to the UI.
        slider: Source-sample navigation slider.
        position: Integer source-sample input.
        play_button: Play/pause control.
        playback_speed: Choice of supported replay speeds.
        time_readout: Prepared replay and recording time description.
        value_names: Names of the three displayed force channels.
        value_labels: Prepared force or raw-value readouts.
        value_hints: Direction and provisional context descriptions.
        _playback_position: Last displayed fractional source-sample coordinate.
        _updating_playback: Guard against seeking recursively during a timer tick.
        _playback_button_playing: Play state currently represented by the button.
    """

    sample_changed = Signal(int)

    def __init__(self, plot: ExplorerChart, parent: QWidget) -> None:
        """Create navigation controls and a stopped timer for one explorer.

        Args:
            plot: Chart whose cursor and viewport follow source navigation.
            parent: Widget owning navigation and its timer.

        Returns:
            None.
        """
        super().__init__(parent)
        self.plot = plot
        self.data: ExplorerData | None = None
        self.theme = plot.theme
        self.playback: SamplePlayback | None = None
        self._playback_position = 0.0
        self._updating_playback = False
        self._playback_button_playing: bool | None = None
        self.playback_timer = QTimer(self)
        self.playback_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.playback_timer.setInterval(16)
        self.playback_timer.timeout.connect(self._playback_tick)
        self.setObjectName("Panel")
        navigation_layout = QVBoxLayout(self)
        navigation_layout.setContentsMargins(8, 6, 8, 6)
        navigation_layout.setSpacing(4)
        navigation = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("sampleSlider")
        self.position = QSpinBox()
        self.position.setObjectName("samplePosition")
        navigation.addWidget(bind(QLabel(), tr("Sample")))
        navigation.addWidget(self.slider, 1)
        self.play_button = QPushButton()
        self.play_button.setObjectName("playPauseButton")
        self.play_button.clicked.connect(self.toggle_playback)
        navigation.addWidget(self.play_button)
        self.playback_speed = QComboBox()
        self.playback_speed.setObjectName("playbackSpeed")
        items(self.playback_speed, [tr("{0:g}×", speed) for speed in (0.5, 1.0, 2.0)])
        self.playback_speed.setCurrentIndex(1)
        bind(self.playback_speed, tr("Playback speed"), "toolTip")
        bind(self.playback_speed, tr("Playback speed"), "accessibleName")
        self.playback_speed.currentIndexChanged.connect(self.set_playback_speed)
        navigation.addWidget(self.playback_speed)
        navigation.addWidget(self.position)
        self.slider.valueChanged.connect(self.position.setValue)
        self.position.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.show_sample)
        self._sync_playback_button()
        self.play_button.setFixedWidth(self.play_button.sizeHint().width())
        playback_controls = (self.play_button, self.playback_speed, self.position)
        control_height = max(control.sizeHint().height() for control in playback_controls)
        for control in playback_controls:
            control.setFixedHeight(control_height)
        navigation_layout.addLayout(navigation)
        self.time_readout = bind(QLabel(), tr("Replay —   |   Recording —"))
        self.time_readout.setObjectName("Muted")
        self.time_readout.setWordWrap(True)
        navigation_layout.addWidget(self.time_readout)
        cards = QHBoxLayout()
        self.value_names: list[QLabel] = []
        self.value_labels: list[QLabel] = []
        self.value_hints: list[QLabel] = []
        for name in (tr("Vertical"), tr("Lateral"), tr("Longitudinal")):
            card, card_layout = create_panel()
            card.setObjectName("ValueCard")
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(1)
            caption, value, hint = (
                bind(QLabel(), name),
                bind(QLabel(), "—"),
                bind(QLabel(), tr("No recording")),
            )
            caption.setObjectName("Muted")
            value.setObjectName("CurrentValue")
            hint.setObjectName("Muted")
            hint.setWordWrap(True)
            card_header = QHBoxLayout()
            hint.setWordWrap(False)
            hint.setAlignment(Qt.AlignmentFlag.AlignRight)
            for card_label in (caption, value, hint):
                card_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            card_header.addWidget(caption, 1)
            card_header.addWidget(hint, 1)
            card_layout.addLayout(card_header)
            card_layout.addWidget(value)
            self.value_names.append(caption)
            self.value_labels.append(value)
            self.value_hints.append(hint)
            cards.addWidget(card, 1)
        navigation_layout.addLayout(cards)

    def bind_recording(self, data: ExplorerData) -> None:
        """Reset navigation to a newly opened source using its existing time base.

        Args:
            data: Prepared presentation snapshot for the new source.

        Returns:
            None.
        """
        self.data = data
        self.playback = SamplePlayback(data.count, data.sample_rate, clock=monotonic)
        self.playback_speed.blockSignals(True)
        self.playback_speed.setCurrentIndex(1)
        self.playback_speed.blockSignals(False)
        for control in (self.slider, self.position):
            control.blockSignals(True)
            control.setRange(0, data.count - 1)
            control.setValue(0)
        for control in (self.slider, self.position):
            control.blockSignals(False)

    def set_data(self, data: ExplorerData, theme: Theme) -> None:
        """Refresh prepared readouts without resetting the active playback clock.

        Args:
            data: Latest prepared snapshot for the current source.
            theme: Palette for force values and context hints.

        Returns:
            None.
        """
        self.data, self.theme = data, theme
        colors = theme.forces if data.calibrated_enabled else theme.raw
        for label, color in zip(self.value_labels, colors, strict=True):
            label.setStyleSheet(f"color: {color};")
        self.refresh_sample(self.slider.value())

    def set_enabled(self, enabled: bool) -> None:
        """Enable navigation for a loaded source and stop empty-source playback.

        Args:
            enabled: Whether source navigation is currently available.

        Returns:
            None.
        """
        for control in (self.slider, self.position, self.play_button, self.playback_speed):
            control.setEnabled(enabled)
        self.play_button.setEnabled(enabled and self.data is not None and self.data.count > 1)

    def refresh_sample(self, index: int) -> None:
        """Display existing values for one source sample without moving the clock.

        Args:
            index: Source-sample index to display.

        Returns:
            None; leave the empty readouts unchanged before loading.

        Raises:
            ValueError: The source-sample index is outside the recording.
        """
        if self.data is None:
            return
        bind(self.time_readout, self.data.sample_clock_text(index), "text")
        for caption, value, hint, display in zip(
            self.value_names,
            self.value_labels,
            self.value_hints,
            self.data.sample_cards(index),
            strict=True,
        ):
            name, number, meaning = display
            bind(caption, name, "text")
            bind(value, number, "text")
            bind(hint, meaning, "text")
            bind(value, meaning, "toolTip")
        context = self.data.vertical_context_label(index)
        color = (
            self.theme.vertical_context_colors.get(context, self.theme.muted)
            if context
            else self.theme.muted
        )
        self.value_hints[0].setStyleSheet(f"color: {color};")
        bind(self.value_hints[0], self.value_hints[0].text(), "toolTip")

    @Slot(int)
    def step_sample(self, step: int) -> None:
        """Step the source position when playback and focused inputs permit it.

        Args:
            step: Signed number of source samples to move.

        Returns:
            None.
        """
        if (
            self.data is None
            or not self.slider.isEnabled()
            or (self.playback is not None and self.playback.playing)
            or isinstance(
                QApplication.focusWidget(),
                (QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QTextEdit),
            )
        ):
            return
        self.slider.setValue(self.slider.value() + step)

    @Slot(int)
    def show_sample(self, index: int) -> None:
        """Display the selected source sample without recalculating analysis.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        if self.data is None:
            return
        if self.playback is not None and not self._updating_playback:
            self.playback.seek(index)
            self._playback_position = float(index)
            self._sync_playback_button()
        self.refresh_sample(index)
        self.sample_changed.emit(index)
        if self._updating_playback:
            return
        self.redraw_cursor()
        low, high = self.plot.axis_x.min(), self.plot.axis_x.max()
        time = self.data.time_at(index)
        if time < low or time > high:
            width = high - low
            first = max(0.0, min(time - width / 2, self.data.duration - width))
            self.plot.axis_x.setRange(first, first + width)

    @Slot()
    def toggle_playback(self) -> None:
        """Start or pause playback of the current recording.

        Returns:
            None.
        """
        if self.playback is None:
            return
        if self.playback.playing:
            self.pause()
        else:
            self.slider.setValue(self.playback.play(self.slider.value()))
            self._playback_position = float(self.slider.value())
            self._sync_playback_button()

    @Slot(int)
    def set_playback_speed(self, index: int) -> None:
        """Apply the selected replay speed to the monotonic playback clock.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        if self.playback is not None and 0 <= index < 3:
            self._playback_tick()
            self.playback.set_speed((0.5, 1.0, 2.0)[index])
            self._sync_playback_button()

    @Slot()
    def _playback_tick(self) -> None:
        if self.playback is not None:
            position = self.playback.current_position()
            index = int(position)
            if self.data is not None and position != self._playback_position:
                low, high = self.plot.axis_x.min(), self.plot.axis_x.max()
                previous = self._playback_position / self.data.sample_rate
                time = position / self.data.sample_rate
                if low <= previous <= high and time >= previous:
                    width = high - low
                    first = min(
                        max(low, time - width / 2),
                        low + time - previous,
                        max(0.0, self.data.duration - width),
                    )
                    if first > low:
                        self.plot.axis_x.setRange(first, first + width)
                elif time < low or time > high:
                    width = high - low
                    first = max(0.0, min(time - width / 2, self.data.duration - width))
                    self.plot.axis_x.setRange(first, first + width)
            self._playback_position = position
            self._updating_playback = True
            try:
                self.slider.setValue(index)
            finally:
                self._updating_playback = False
            self.redraw_cursor()
            self._sync_playback_button()

    def pause(self) -> None:
        """Pause the existing clock and keep its source cursor synchronized.

        Returns:
            None.
        """
        if self.playback is not None:
            self.slider.setValue(self.playback.pause())
            self._playback_position = float(self.slider.value())
            self.redraw_cursor()
        self._sync_playback_button()

    def _sync_playback_button(self) -> None:
        playing = self.playback is not None and self.playback.playing
        if playing == self._playback_button_playing:
            return
        self._playback_button_playing = playing
        bind(self.play_button, tr("Pause") if playing else tr("Play"), "accessibleName")
        bind(
            self.play_button,
            tr("Pause playback") if playing else tr("Play recording"),
            "toolTip",
        )
        self.play_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPause
                if playing
                else QStyle.StandardPixmap.SP_MediaPlay,
            ),
        )
        if playing and not self.playback_timer.isActive():
            self.playback_timer.start()
        elif not playing:
            self.playback_timer.stop()

    @Slot()
    def redraw_cursor(self) -> None:
        """Publish the current integer or fractional position to the chart.

        Returns:
            None.
        """
        if self.data is not None:
            position = (
                self._playback_position
                if self.playback is not None and self.playback.playing
                else self.slider.value()
            )
            self.plot.set_cursor(position)
