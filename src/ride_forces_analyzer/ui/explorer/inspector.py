"""Inspector controls and prepared recording details, independent of the main window.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""
# cspell:words Pixmap

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.translation import (
    bind,
    button_text,
)


from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.explorer import ExplorerData


from .controls import SelectionSpinBox, SmoothingSlider


from ride_forces_analyzer.explorer import SampleRange
from .controls import create_panel


class ExplorerInspector(QScrollArea):
    """Own recording details, smoothing controls and inclusive sample selection.

    Attributes:
        smoothing_requested: Signal carrying a smoothing slider position.
        selection_changed: Signal requesting adoption of changed selection controls.
        details_hidden: Signal emitted when technical details are collapsed.
        data: Current prepared presentation snapshot, or None before loading.
        availability: Recording capability summary.
        smoothing_slider: Control selecting an odd smoothing window.
        smoothing_label: Current smoothing description.
        signs: Explanation of force-axis polarity.
        first: First included source sample control.
        last: Last included source sample control.
        selection_label: Inclusive selection description.
        extrema_context: Description of the current visible interval.
        extrema_labels: Prepared per-axis extrema descriptions.
        ride_metadata: Available ride, train, row and seat details.
        details_button: Control expanding technical details.
        details_body: Container for retained technical information.
        summary: Source and processing provenance description.
        disclaimer: Processing policy and scientific limits.
        readout: Detailed values for the current source sample.
        notes: Read-only import diagnostic display.
        original_diagnostics: Control selecting untranslated technical diagnostics.
    """

    smoothing_requested = Signal(int)
    selection_changed = Signal()
    details_hidden = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build the inspector without binding recording-specific state.

        Args:
            parent: Widget owning the inspector's lifetime.

        Returns:
            None.
        """
        super().__init__(parent)
        self.data: ExplorerData | None = None
        self.setObjectName("inspector")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_body = QWidget()
        inspector_body.setObjectName("InspectorBody")
        inspector_layout = QVBoxLayout(inspector_body)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(10)
        self.setWidget(inspector_body)

        display, display_layout = create_panel(tr("DISPLAY"))
        self.availability = bind(QLabel(), tr("No recording loaded"))
        self.availability.setObjectName("Muted")
        self.availability.setWordWrap(True)
        display_layout.addWidget(self.availability)
        display_layout.addWidget(bind(QLabel(), tr("Smoothing")))
        self.smoothing_slider = SmoothingSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setObjectName("smoothingSlider")
        self.smoothing_slider.setRange(0, 25)
        self.smoothing_slider.setValue(5)
        self.smoothing_slider.setTracking(True)
        self.smoothing_slider.setEnabled(False)
        bind(
            self.smoothing_slider,
            tr(
                "Centered mean: 1 (off) to 51 samples, odd windows. Default 11 (right click to reset); stronger smoothing can suppress force peaks. Updates while dragging.",
            ),
            "toolTip",
        )
        self.smoothing_slider.valueChanged.connect(self.smoothing_requested)
        display_layout.addWidget(self.smoothing_slider)
        self.smoothing_label = bind(QLabel(), tr("11 samples"))
        self.smoothing_label.setWordWrap(True)
        display_layout.addWidget(self.smoothing_label)
        smoothing_hint = bind(QLabel(), tr("Live preview · Right-click to reset"))
        smoothing_hint.setObjectName("Muted")
        smoothing_hint.setWordWrap(True)
        display_layout.addWidget(smoothing_hint)
        self.signs = bind(
            QLabel(),
            tr("Lateral: + right / − left\nLongitudinal: + acceleration / − braking"),
        )
        self.signs.setWordWrap(True)
        display_layout.addWidget(self.signs)
        inspector_layout.addWidget(display)

        selection, selection_layout = create_panel(tr("SELECTION"))
        fields = QGridLayout()
        self.first = SelectionSpinBox()
        self.first.setObjectName("selectionStart")
        self.last = SelectionSpinBox()
        self.last.setObjectName("selectionEnd")
        fields.addWidget(bind(QLabel(), tr("From sample")), 0, 0)
        fields.addWidget(bind(QLabel(), tr("To sample")), 0, 1)
        fields.addWidget(self.first, 1, 0)
        fields.addWidget(self.last, 1, 1)
        selection_layout.addLayout(fields)
        self.selection_label = bind(QLabel(), tr("Inclusive sample indices"))
        self.selection_label.setWordWrap(True)
        selection_layout.addWidget(self.selection_label)
        self.first.valueChanged.connect(self.selection_changed)
        self.last.valueChanged.connect(self.selection_changed)
        inspector_layout.addWidget(selection)

        extrema, extrema_layout = create_panel(tr("VISIBLE RANGE EXTREMA"))
        self.extrema_context = bind(QLabel(), tr("Select a recording to inspect minimum/maximum"))
        self.extrema_context.setWordWrap(True)
        self.extrema_context.setTextFormat(Qt.TextFormat.PlainText)
        extrema_layout.addWidget(self.extrema_context)
        self.extrema_labels = [QLabel() for _ in range(3)]
        for extrema_label in self.extrema_labels:
            extrema_label.setTextFormat(Qt.TextFormat.RichText)
            extrema_label.setWordWrap(True)
            extrema_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            extrema_layout.addWidget(extrema_label)
        inspector_layout.addWidget(extrema)

        recording, recording_layout = create_panel(tr("RECORDING"))
        self.ride_metadata = QLabel()
        self.ride_metadata.setObjectName("rideMetadata")
        self.ride_metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.ride_metadata.setWordWrap(True)
        self.ride_metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ride_metadata.hide()
        recording_layout.addWidget(self.ride_metadata)
        inspector_layout.addWidget(recording)

        details, details_layout = create_panel()
        self.details_button = button_text(QPushButton(), tr("Technical details"))
        self.details_button.setCheckable(True)
        self.details_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.details_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
        )
        details_layout.addWidget(self.details_button)
        self.details_body = QWidget()
        details_body_layout = QVBoxLayout(self.details_body)
        details_body_layout.setContentsMargins(0, 0, 0, 0)
        self.summary = bind(QLabel(), tr("Source provenance and import diagnostics appear here."))
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.disclaimer = bind(
            QLabel(),
            tr("Raw source values · Units and rider directions unverified"),
        )
        self.disclaimer.setWordWrap(True)
        self.readout = bind(QLabel(), tr("No recording loaded"))
        self.readout.setWordWrap(True)
        self.readout.setTextFormat(Qt.TextFormat.RichText)
        self.readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.notes = QPlainTextEdit()
        self.notes.setAcceptDrops(False)
        self.original_diagnostics = bind(QCheckBox(), tr("Original diagnostics (technical text)"))
        self.original_diagnostics.toggled.connect(self._refresh_diagnostics)
        self.original_diagnostics.hide()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(160)
        self.notes.hide()
        for title, detail in (
            (tr("Source"), self.summary),
            (tr("Processing"), self.disclaimer),
            (tr("Current sample"), self.readout),
        ):
            heading = bind(QLabel(), title)
            heading.setObjectName("SectionTitle")
            details_body_layout.addWidget(heading)
            details_body_layout.addWidget(detail)
        details_body_layout.addWidget(self.original_diagnostics)
        details_body_layout.addWidget(self.notes)
        details_layout.addWidget(self.details_body)
        self.details_body.hide()
        self.details_button.toggled.connect(self._toggle_details)
        inspector_layout.addWidget(details)
        inspector_layout.addStretch()

    def bind_recording(self, data: ExplorerData) -> None:
        """Adopt a recording and reset only its source-bound controls.

        Args:
            data: Prepared presentation snapshot for the newly opened source.

        Returns:
            None.
        """
        self.data = data
        self.restore_smoothing()
        self.set_selection(SampleRange(0, data.count - 1))

    def set_data(self, data: ExplorerData) -> None:
        """Refresh prepared metadata and processing descriptions, retaining selection.

        Args:
            data: Snapshot to display without recalculating its analysis.

        Returns:
            None.
        """
        self.data = data
        bind(self.ride_metadata, data.metadata_rows_text, "text")
        self.ride_metadata.setVisible(bool(data.metadata_text))
        bind(self.availability, data.availability_text, "text")
        active = self.data.calibrated_enabled
        bind(self.summary, self.data.technical_summary, "text")
        bind(
            self.disclaimer,
            tr(
                "Calibrated forces\nReference calibration\n{0}\nInferred time"
                if self.data.analysis is not None and self.data.analysis.calibration is not None
                else "Calibrated forces\nSource directions\n{0}\nInferred time",
                self.data.smoothing_text.replace(" • ", "\n"),
            )
            if active
            else tr(
                "Raw acceleration x/y/z\nUnits and rider directions unverified\nInferred time",
            ),
            "text",
        )
        self.smoothing_slider.setEnabled(active)
        bind(
            self.smoothing_label,
            self.data.smoothing_text if active else tr("Raw source values"),
            "text",
        )
        self.signs.setVisible(active)
        self._refresh_diagnostics()

    def restore_smoothing(self) -> None:
        """Restore the last accepted window without sending another request.

        Returns:
            None; leave the control unchanged before loading a recording.
        """
        if self.data is None:
            return
        self.smoothing_slider.blockSignals(True)
        self.smoothing_slider.setValue((self.data.smoothing_window - 1) // 2)
        self.smoothing_slider.blockSignals(False)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable source-selection inputs during recording operations.

        Args:
            enabled: Whether source selection may be edited.

        Returns:
            None.
        """
        self.first.setEnabled(enabled)
        self.last.setEnabled(enabled)

    def set_selection(self, selected: SampleRange) -> None:
        """Adopt a source selection without emitting intermediate changes.

        Args:
            selected: Validated inclusive bounds within the bound recording.

        Returns:
            None; leave controls unchanged when no recording is bound.
        """
        if self.data is None:
            return
        for control in (self.first, self.last):
            control.blockSignals(True)
            control.setRange(0, self.data.count - 1)
        self.first.setValue(selected.first)
        self.last.setValue(selected.last)
        for control in (self.first, self.last):
            control.blockSignals(False)

    def update_selection(self) -> SampleRange | None:
        """Format the selected interval through its existing data contract.

        Returns:
            The inclusive selection, or None before a recording is bound.

        Raises:
            ValueError: Source-sample bounds are invalid.
        """
        if self.data is None:
            return None
        # Reassigning an unchanged range stops native spin-button auto-repeat.
        if self.first.maximum() != self.last.value():
            self.first.setMaximum(self.last.value())
        if self.last.minimum() != self.first.value():
            self.last.setMinimum(self.first.value())
        selected = self.data.select(self.first.value(), self.last.value())
        bind(
            self.selection_label,
            tr(
                "{0:,} samples (inclusive)\nReplay {1}–{2} @ {3:g} Hz",
                selected.count,
                self.data.replay_text(selected.first),
                self.data.replay_text(selected.last),
                self.data.sample_rate,
            ),
            "text",
        )
        return selected

    def show_sample(self, index: int) -> None:
        """Display prepared technical values at the selected source sample.

        Args:
            index: Source-sample index to inspect.

        Returns:
            None; leave the empty inspector unchanged before loading.

        Raises:
            ValueError: The sample index lies outside the bound recording.
        """
        if self.data is not None:
            bind(self.readout, self.data.sample_text(index, rich=True), "text")

    def show_extrema(self, context: str, rows: tuple[str, ...]) -> None:
        """Display already formatted visible-range extrema.

        Args:
            context: Prepared interval and processing description.
            rows: Three prepared descriptions for the force or raw channels.

        Returns:
            None.

        Raises:
            ValueError: The number of rows differs from the three displayed channels.
        """
        bind(self.extrema_context, context, "text")
        for label, text in zip(self.extrema_labels, rows, strict=True):
            bind(label, text, "text")

    def show_notes(self, checked: bool) -> None:
        """Expand and reveal import diagnostics, or hide their technical controls.

        Args:
            checked: Whether diagnostic text should be visible.

        Returns:
            None.
        """
        if checked:
            self.details_button.setChecked(True)
        self.notes.setVisible(checked)
        self.original_diagnostics.setVisible(checked)
        if checked:
            QTimer.singleShot(0, lambda: self.ensureWidgetVisible(self.notes))

    @Slot()
    def _refresh_diagnostics(self) -> None:
        if self.data is not None:
            bind(
                self.notes,
                self.data.notes
                if self.original_diagnostics.isChecked()
                else self.data.localized_notes,
                "plainText",
            )

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_ArrowUp if checked else QStyle.StandardPixmap.SP_ArrowDown,
            ),
        )
        self.details_body.setVisible(checked)
        if not checked:
            self.details_hidden.emit()
