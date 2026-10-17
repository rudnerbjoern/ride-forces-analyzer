"""First usable raw-recording explorer; Qt Charts owns interactive chart drawing."""

from pathlib import Path

from PySide6.QtCharts import QCategoryAxis, QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QPointF, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QKeySequence,
    QMouseEvent,
    QResizeEvent,
    QShowEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QFileDialog,
    QHBoxLayout,
    QGraphicsSimpleTextItem,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.explorer import ExplorerData, failure_text
from ride_forces_analyzer.importers import ImportFailure

from ride_forces_analyzer.gps_overview import prepare_gps_overview

from .chrome import app_icon, style_native_caption
from .gps import gps_dialog
from .loading import LoadWorker
from .theme import STYLESHEET


class SmoothingSlider(QSlider):
    """Right click restores the default 11-sample window (slider position five)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.setValue(5)
            event.accept()
            return
        super().mousePressEvent(event)


class TimeChartView(QChartView):
    zoom_requested = Signal(float, float)

    def wheelEvent(self, event: QWheelEvent) -> None:
        chart = self.chart()
        point = chart.mapFromScene(self.mapToScene(event.position().toPoint()))
        plot = chart.plotArea()
        delta = event.angleDelta().y()
        if plot.contains(point) and plot.width() > 0 and delta:
            fraction = (point.x() - plot.left()) / plot.width()
            self.zoom_requested.emit(fraction, delta / 120)
            event.accept()
        else:
            event.ignore()


class ExplorerWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self._application_title = settings.window_title
        self.setWindowTitle(settings.window_title)
        self.setWindowIcon(app_icon())
        self.resize(settings.window_width, settings.window_height)
        self.data: ExplorerData | None = None
        self._worker: LoadWorker | None = None
        self.open_action = QAction("Open recording…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)
        self.setStyleSheet(STYLESHEET)
        toolbar = QToolBar("Recording", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        open_widget = toolbar.widgetForAction(self.open_action)
        open_widget.setObjectName("Primary")
        self.gps_button = QPushButton("GPS overview")
        self.gps_button.setEnabled(False)
        self.gps_button.clicked.connect(self.show_gps)
        toolbar.addWidget(self.gps_button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.notes_button = QPushButton("Import notes")
        self.notes_button.setCheckable(True)
        self.notes_button.toggled.connect(self._show_notes)
        toolbar.addWidget(self.notes_button)
        self.inspector_button = QPushButton("Inspector")
        self.inspector_button.setCheckable(True)
        toolbar.addWidget(self.inspector_button)
        self.addToolBar(toolbar)
        self.gps_window: QDialog | None = None
        self._wide_layout: bool | None = None
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        self.heading = QLabel("Open a .forces recording to explore your ride")
        self.heading.setObjectName("recordingHeading")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        self.heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.heading)
        self.header_summary = QLabel("Choose Open recording or press Ctrl+O")
        self.header_summary.setObjectName("Muted")
        self.header_summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.header_summary)
        self.workspace = QSplitter(Qt.Orientation.Horizontal)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setHandleWidth(10)
        layout.addWidget(self.workspace, 1)
        self.plot_panel, plot_layout = self._panel()
        self.plot_scroll = QScrollArea()
        self.plot_scroll.setObjectName("plotScroll")
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plot_scroll.setWidget(self.plot_panel)
        self.workspace.addWidget(self.plot_scroll)
        self.chart_tools = QGridLayout()
        self.reference_toggle = QCheckBox("Calibrated forces")
        self.reference_toggle.setEnabled(False)
        self.reference_toggle.toggled.connect(self.set_reference_view)
        self.reset_button = QPushButton("Reset view")
        self.reset_button.clicked.connect(self.reset_view)
        self.zoom_button = QPushButton("Zoom to selection")
        self.zoom_button.clicked.connect(self.zoom_selection)
        self.visible_button = QPushButton("Select visible range")
        self.visible_button.clicked.connect(self.select_visible)
        plot_layout.addLayout(self.chart_tools)
        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setBackgroundBrush(QColor("#182330"))
        self.chart.setBackgroundRoundness(0)
        self.chart.legend().hide()
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        self.chart_view = TimeChartView(self.chart)
        self.chart_view.zoom_requested.connect(self.zoom_wheel)
        self.chart_view.setObjectName("recordingChart")
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setRubberBand(QChartView.RubberBand.HorizontalRubberBand)
        self.chart_view.setMinimumSize(0, 240)
        plot_layout.addWidget(self.chart_view, 1)
        self.axis_x = QValueAxis()
        self.axis_x.setTitleText("Elapsed time (s)")
        self.axis_x.setLabelFormat("%.3f")
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Source value (unit unknown)")
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series: list[QLineSeries] = []
        axes = QHBoxLayout()
        self.visibility: list[QCheckBox] = []
        for name, color in (("x", "#2563eb"), ("y", "#ea580c"), ("z", "#059669")):
            line = QLineSeries()
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5))
            self.chart.addSeries(line)
            line.attachAxis(self.axis_x)
            line.attachAxis(self.axis_y)
            self.series.append(line)
            toggle = QCheckBox(f"Show {name}")
            toggle.setChecked(True)
            toggle.toggled.connect(line.setVisible)
            self.visibility.append(toggle)
            axes.addWidget(toggle)
        axes.addStretch()
        plot_layout.insertLayout(1, axes)
        self.source_marker_lines: dict[str, QLineSeries] = {}
        self.source_marker_labels: dict[str, QGraphicsSimpleTextItem] = {}
        for name, color in (
            ("startIndex", "#bb9aff"),
            ("endIndex", "#ff8ca8"),
            ("gravityIndex", "#50c4d4"),
            ("inclineIndex", "#ffd07b"),
        ):
            line = QLineSeries()
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.DashDotLine))
            self.chart.addSeries(line)
            line.attachAxis(self.axis_x)
            line.attachAxis(self.axis_y)
            for marker in self.chart.legend().markers(line):
                marker.setVisible(False)
            label = QGraphicsSimpleTextItem(self.chart)
            label.setBrush(QColor(color))
            label.hide()
            self.source_marker_lines[name] = line
            self.source_marker_labels[name] = label
        self.chart.plotAreaChanged.connect(self._redraw_source_markers)
        self.sample_cursor = QLineSeries()
        self.sample_cursor.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
        self.chart.addSeries(self.sample_cursor)
        self.sample_cursor.attachAxis(self.axis_x)
        self.sample_cursor.attachAxis(self.axis_y)
        for marker in self.chart.legend().markers(self.sample_cursor):
            marker.setVisible(False)
        self.axis_y.rangeChanged.connect(self._redraw_cursor)

        navigation_panel, navigation_layout = self._panel()
        navigation_layout.setContentsMargins(8, 6, 8, 6)
        navigation_layout.setSpacing(4)
        plot_layout.addWidget(navigation_panel)
        navigation = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("sampleSlider")
        self.position = QSpinBox()
        self.position.setObjectName("samplePosition")
        navigation.addWidget(QLabel("Sample"))
        navigation.addWidget(self.slider, 1)
        navigation.addWidget(self.position)
        self.slider.valueChanged.connect(self.position.setValue)
        self.position.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.show_sample)
        navigation_layout.addLayout(navigation)
        self.time_readout = QLabel("Replay —   |   Recording —")
        self.time_readout.setObjectName("Muted")
        self.time_readout.setWordWrap(True)
        navigation_layout.addWidget(self.time_readout)
        cards = QHBoxLayout()
        self.value_names: list[QLabel] = []
        self.value_labels: list[QLabel] = []
        self.value_hints: list[QLabel] = []
        for name in ("Vertical", "Lateral", "Longitudinal"):
            card, card_layout = self._panel()
            card.setObjectName("ValueCard")
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(1)
            caption, value, hint = QLabel(name), QLabel("—"), QLabel("No recording")
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

        self.inspector = QScrollArea()
        self.inspector.setObjectName("inspector")
        self.inspector.setWidgetResizable(True)
        self.inspector.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_body = QWidget()
        inspector_body.setObjectName("InspectorBody")
        inspector_layout = QVBoxLayout(inspector_body)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(10)
        self.inspector.setWidget(inspector_body)
        self.workspace.addWidget(self.inspector)
        self.inspector_button.toggled.connect(self._toggle_inspector)

        display, display_layout = self._panel("DISPLAY")
        self.availability = QLabel("No recording loaded")
        self.availability.setObjectName("Muted")
        self.availability.setWordWrap(True)
        display_layout.addWidget(self.availability)
        display_layout.addWidget(QLabel("Smoothing"))
        self.smoothing_slider = SmoothingSlider(Qt.Orientation.Horizontal)
        self.smoothing_slider.setObjectName("smoothingSlider")
        self.smoothing_slider.setRange(0, 25)
        self.smoothing_slider.setValue(5)
        self.smoothing_slider.setTracking(True)
        self.smoothing_slider.setEnabled(False)
        self.smoothing_slider.setToolTip(
            "Centered mean: 1 (off) to 51 samples, odd windows. "
            "Default 11 (right click to reset); stronger smoothing can suppress force peaks. Updates while dragging.",
        )
        self.smoothing_slider.valueChanged.connect(self.set_smoothing)
        display_layout.addWidget(self.smoothing_slider)
        self.smoothing_label = QLabel("11 samples")
        self.smoothing_label.setWordWrap(True)
        display_layout.addWidget(self.smoothing_label)
        smoothing_hint = QLabel("Live preview · Right-click to reset")
        smoothing_hint.setObjectName("Muted")
        smoothing_hint.setWordWrap(True)
        display_layout.addWidget(smoothing_hint)
        self.signs = QLabel("Lateral: + right / − left\nLongitudinal: + acceleration / − braking")
        self.signs.setWordWrap(True)
        display_layout.addWidget(self.signs)
        inspector_layout.addWidget(display)

        selection, selection_layout = self._panel("SELECTION")
        fields = QGridLayout()
        self.first = QSpinBox()
        self.first.setObjectName("selectionStart")
        self.last = QSpinBox()
        self.last.setObjectName("selectionEnd")
        fields.addWidget(QLabel("From sample"), 0, 0)
        fields.addWidget(QLabel("To sample"), 0, 1)
        fields.addWidget(self.first, 1, 0)
        fields.addWidget(self.last, 1, 1)
        selection_layout.addLayout(fields)
        self.selection_label = QLabel("Inclusive sample indices")
        self.selection_label.setWordWrap(True)
        selection_layout.addWidget(self.selection_label)
        self.first.valueChanged.connect(self.update_selection)
        self.last.valueChanged.connect(self.update_selection)
        inspector_layout.addWidget(selection)

        extrema, extrema_layout = self._panel("SELECTION EXTREMA")
        self.extrema_context = QLabel("Select a recording to inspect minimum/maximum")
        self.extrema_context.setWordWrap(True)
        self.extrema_context.setTextFormat(Qt.TextFormat.PlainText)
        extrema_layout.addWidget(self.extrema_context)
        self.extrema_labels = [QLabel() for _ in range(3)]
        for extrema_label in self.extrema_labels:
            extrema_label.setTextFormat(Qt.TextFormat.PlainText)
            extrema_label.setWordWrap(True)
            extrema_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            extrema_layout.addWidget(extrema_label)
        inspector_layout.addWidget(extrema)

        recording, recording_layout = self._panel("RECORDING")
        self.ride_metadata = QLabel()
        self.ride_metadata.setObjectName("rideMetadata")
        self.ride_metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.ride_metadata.setWordWrap(True)
        self.ride_metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ride_metadata.hide()
        recording_layout.addWidget(self.ride_metadata)
        inspector_layout.addWidget(recording)

        details, details_layout = self._panel()
        self.details_button = QPushButton("Technical details")
        self.details_button.setCheckable(True)
        details_layout.addWidget(self.details_button)
        self.details_body = QWidget()
        details_body_layout = QVBoxLayout(self.details_body)
        details_body_layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel("Source provenance and import diagnostics appear here.")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.disclaimer = QLabel("Raw source values · Units and rider directions unverified")
        self.disclaimer.setWordWrap(True)
        self.readout = QLabel("No recording loaded")
        self.readout.setWordWrap(True)
        self.readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(160)
        self.notes.hide()
        for detail in (self.summary, self.disclaimer, self.readout, self.notes):
            details_body_layout.addWidget(detail)
        details_layout.addWidget(self.details_body)
        self.details_body.hide()
        self.details_button.toggled.connect(self._toggle_details)
        inspector_layout.addWidget(details)
        inspector_layout.addStretch()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.setCentralWidget(body)
        self.statusBar().showMessage("Ready — open a recording")
        self._set_controls(False)
        self.axis_x.setRange(0, 1)
        self.axis_y.setRange(-1, 1)
        self._style_axes()
        self._adapt_layout()

    @staticmethod
    def _panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        if title:
            label = QLabel(title)
            label.setObjectName("SectionTitle")
            layout.addWidget(label)
        return panel, layout

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "workspace"):
            self._adapt_layout()

    def _adapt_layout(self) -> None:
        wide = self.width() >= 1080
        if self._wide_layout == wide:
            return
        self._wide_layout = wide
        self.workspace.setOrientation(
            Qt.Orientation.Horizontal if wide else Qt.Orientation.Vertical,
        )
        self.inspector.setMaximumWidth(360 if wide else 16777215)
        for index, control in enumerate(
            (self.reference_toggle, self.reset_button, self.zoom_button, self.visible_button),
        ):
            self.chart_tools.removeWidget(control)
            self.chart_tools.addWidget(
                control,
                0,
                index,
            )
        self.inspector_button.setChecked(wide)
        self._toggle_inspector(wide)
        self.workspace.setSizes([max(300, self.width() - 360), 330] if wide else [300, 160])

    @Slot(bool)
    def _toggle_inspector(self, checked: bool) -> None:
        self.inspector.setVisible(checked)
        self.plot_scroll.setVisible(self._wide_layout is not False or not checked)

    @Slot(bool)
    def _show_notes(self, checked: bool) -> None:
        if checked:
            self.inspector_button.setChecked(True)
            self.details_button.setChecked(True)
        self.notes.setVisible(checked)
        if checked:
            QTimer.singleShot(0, lambda: self.inspector.ensureWidgetVisible(self.notes))

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_body.setVisible(checked)
        if not checked:
            self.notes_button.setChecked(False)

    def _style_axes(self) -> None:
        for axis in (self.axis_x, self.axis_y):
            axis.setLabelsBrush(QColor("#b7c9df"))
            axis.setTitleBrush(QColor("#b7c9df"))
            axis.setGridLinePen(QPen(QColor("#314153"), 1))
            axis.setLinePen(QPen(QColor("#536981"), 1))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.gps_window is not None:
            self.gps_window.close()
        super().closeEvent(event)

    def _set_controls(self, enabled: bool) -> None:
        for control in (
            self.slider,
            self.position,
            self.first,
            self.last,
            self.zoom_button,
            self.visible_button,
            self.reset_button,
            self.notes_button,
            *self.visibility,
        ):
            control.setEnabled(enabled)

    @Slot()
    def choose_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Ride Forces recording",
            "",
            "Ride Forces (*.forces);;All files (*)",
        )
        if filename:
            self.open_path(Path(filename))

    def open_path(self, path: Path) -> None:
        if self._worker is not None:
            return
        worker = LoadWorker(path)
        worker.signals.completed.connect(self._loaded)
        worker.signals.failed.connect(self._failed)
        self._worker = worker
        self.open_action.setEnabled(False)
        self.progress.show()
        self.statusBar().showMessage(f"Opening {path.name}…")
        QThreadPool.globalInstance().start(worker)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        style_native_caption(int(self.winId()))

    @Slot(object)
    def _loaded(self, outcome: object) -> None:
        if isinstance(outcome, ImportFailure):
            self._failed(failure_text(outcome))
            return
        if not isinstance(outcome, ExplorerData):
            self._failed("Unable to display recording.")
            return
        outcome = outcome.with_reference(outcome.reference is not None)
        if self.gps_window is not None:
            self.gps_window.close()
            self.gps_window.deleteLater()
            self.gps_window = None
        self.gps_button.setEnabled(prepare_gps_overview(outcome.source.recording) is not None)
        self.data = outcome
        self.smoothing_slider.blockSignals(True)
        self.smoothing_slider.setValue(5)
        self.smoothing_slider.blockSignals(False)
        self.reference_toggle.blockSignals(True)
        self.reference_toggle.setEnabled(outcome.reference is not None)
        self.reference_toggle.setToolTip(
            f"App reference available for {outcome.title}"
            if outcome.reference is not None
            else outcome.reference_error or "Calibration unavailable for this recording",
        )
        self.reference_toggle.setChecked(outcome.reference_enabled)
        self.reference_toggle.blockSignals(False)
        self.setWindowTitle(f"{outcome.title} · {self._application_title}")
        self.heading.setText(outcome.title)
        self.ride_metadata.setText(outcome.metadata_rows_text)
        self.ride_metadata.setVisible(bool(outcome.metadata_text))
        self.summary.setText(outcome.summary)
        self.header_summary.setText(outcome.overview_text)
        self.availability.setText(outcome.availability_text)
        self._draw_channels()
        self.notes.setPlainText(outcome.notes)
        self.notes_button.setText(
            f"Import notes ({len(outcome.source.diagnostics) + bool(outcome.reference_error)})",
        )
        for control in (self.slider, self.position, self.first, self.last):
            control.blockSignals(True)
            control.setRange(0, outcome.count - 1)
        self.slider.setValue(0)
        self.position.setValue(0)
        self.first.setValue(0)
        self.last.setValue(outcome.count - 1)
        for control in (self.slider, self.position, self.first, self.last):
            control.blockSignals(False)
        self._set_controls(True)
        self.update_selection()
        self.sample_cursor.clear()
        for line in self.source_marker_lines.values():
            line.clear()
        self.chart.createDefaultAxes()
        # Keep explicit axis labels and references after the chart has all data.
        current_x = self.chart.axes(Qt.Orientation.Horizontal)[0]
        current_y = self.chart.axes(Qt.Orientation.Vertical)[0]
        assert isinstance(current_x, QValueAxis) and isinstance(current_y, QValueAxis)
        self.chart.removeAxis(current_x)
        self.axis_x = QCategoryAxis()
        self.axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        for chart_series in self.chart.series():
            chart_series.attachAxis(self.axis_x)
        current_x.deleteLater()
        self.chart.removeAxis(current_y)
        self.axis_y = QCategoryAxis()
        self.axis_y.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        for chart_series in self.chart.series():
            chart_series.attachAxis(self.axis_y)
        current_y.deleteLater()
        self._style_axes()
        self.axis_x.setTitleText(outcome.replay_time_label)
        self.axis_x.rangeChanged.connect(self._redraw_time_labels)
        self.axis_x.rangeChanged.connect(self._bound_time_view)
        self.axis_x.rangeChanged.connect(self._redraw_source_markers)
        self.axis_x.setRange(*outcome.default_time_range)
        self.axis_y.setTitleText(
            "G-force (g)" if outcome.reference_enabled else "Source value (unit unknown)",
        )
        self.axis_y.rangeChanged.connect(self._fix_value_view)
        self.axis_y.setRange(*outcome.value_range)
        self.axis_y.rangeChanged.connect(self._redraw_cursor)
        self.axis_y.rangeChanged.connect(self._redraw_value_labels)
        self._redraw_value_labels()
        self._redraw_time_labels()
        self._redraw_source_markers()
        self.slider.setValue(outcome.source.recording.indices.start)
        self.show_sample(self.slider.value())
        self._finish_loading()
        self.statusBar().setToolTip("")
        self.statusBar().showMessage(
            (
                "Loaded — calibration unavailable; see Import notes"
                if outcome.reference_error
                else "Loaded — drag to zoom, navigate samples or select an interval"
            ),
        )

    @Slot()
    def show_gps(self) -> None:
        if self.data is None:
            return
        overview = prepare_gps_overview(self.data.source.recording)
        if overview is None:
            return
        if self.gps_window is None:
            self.gps_window = gps_dialog(overview, self.data.title, self)
        self.gps_window.show()
        self.gps_window.raise_()

    def _draw_channels(self) -> None:
        if self.data is None:
            return
        active = self.data.reference_enabled
        self.disclaimer.setText(
            f"Calibrated forces • Source directions • {self.data.smoothing_text} • Inferred time"
            if active
            else "Raw acceleration x/y/z • Units and rider directions unverified • Inferred time",
        )
        self.smoothing_slider.setEnabled(active)
        self.smoothing_label.setText(self.data.smoothing_text if active else "Raw source values")
        colors = ("#009cff", "#22c55e", "#ff374b") if active else ("#2563eb", "#ea580c", "#059669")
        for i, (line, values, name, color) in enumerate(
            zip(
                self.series,
                self.data.plotted_channels,
                self.data.channel_names,
                colors,
                strict=True,
            ),
        ):
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5))
            line.replace(
                [QPointF(self.data.time_at(index), value) for index, value in enumerate(values)],
            )
            self.visibility[i].setText(name.partition(" (")[0])
            self.visibility[i].setToolTip(name)
            self.visibility[i].setStyleSheet(f"QCheckBox {{ color: {color}; }}")
            self.value_labels[i].setStyleSheet(f"color: {color};")
        self.chart.setTitle("")
        self.signs.setVisible(active)

    @Slot(int)
    def set_smoothing(self, position: int) -> None:
        if self.data is None or not self.data.reference_enabled:
            return
        self.data = self.data.with_smoothing(position * 2 + 1)
        self._draw_channels()
        self.axis_y.setRange(*self.data.value_range)
        self._redraw_value_labels()
        self._redraw_source_markers()
        self._redraw_cursor()
        self._refresh_sample(self.slider.value())
        self._refresh_extrema()

    @Slot(bool)
    def set_reference_view(self, enabled: bool) -> None:
        if self.data is None:
            return
        self.data = self.data.with_reference(enabled)
        self._draw_channels()
        self.axis_y.setTitleText(
            "G-force (g)" if self.data.reference_enabled else "Source value (unit unknown)",
        )
        self.axis_y.setRange(*self.data.value_range)
        self._redraw_value_labels()
        self._redraw_source_markers()
        self._redraw_cursor()
        self._refresh_sample(self.slider.value())
        self._refresh_extrema()

    def _finish_loading(self) -> None:
        self._worker = None
        self.open_action.setEnabled(True)
        self.progress.hide()

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._finish_loading()
        self.statusBar().setToolTip("")
        self.statusBar().showMessage(message)
        self.statusBar().setToolTip(message)

    def _refresh_sample(self, index: int) -> None:
        if self.data is None:
            return
        self.readout.setText(self.data.sample_text(index))
        self.time_readout.setText(self.data.sample_clock_text(index))
        for caption, value, hint, display in zip(
            self.value_names,
            self.value_labels,
            self.value_hints,
            self.data.sample_cards(index),
            strict=True,
        ):
            name, number, meaning = display
            caption.setText(name)
            value.setText(number)
            hint.setText(meaning)
            value.setToolTip(meaning)

    @Slot(int)
    def show_sample(self, index: int) -> None:
        if self.data is None:
            return
        self._refresh_sample(index)
        self._redraw_cursor()
        low, high = self.axis_x.min(), self.axis_x.max()
        time = self.data.time_at(index)
        if time < low or time > high:
            width = high - low
            first = max(0.0, min(time - width / 2, self.data.duration - width))
            self.axis_x.setRange(first, first + width)

    @Slot(float, float)
    def zoom_wheel(self, fraction: float, steps: float) -> None:
        if self.data is None or self.data.duration <= 0:
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        anchor = low + fraction * (high - low)
        scale = 1.25 ** -max(-20.0, min(20.0, steps))
        width = min(self.data.duration, max(1 / self.data.sample_rate, (high - low) * scale))
        first = max(0.0, min(anchor - fraction * width, self.data.duration - width))
        self.axis_x.setRange(first, first + width)

    @Slot()
    def _fix_value_view(self) -> None:
        if self.data is not None:
            low, high = self.data.value_range
            if self.axis_y.min() != low or self.axis_y.max() != high:
                self.axis_y.setRange(low, high)

    @Slot()
    def _bound_time_view(self) -> None:
        """Keep every chart interaction within the available sample timeline."""
        if self.data is None or self.data.duration <= 0:
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        if 0 <= low < high <= self.data.duration:
            return
        width = min(high - low, self.data.duration)
        first = max(0.0, min(low, self.data.duration - width))
        last = min(self.data.duration, first + width)
        if low != first or high != last:
            self.axis_x.setRange(first, last)

    @Slot()
    def _redraw_value_labels(self) -> None:
        if self.data is None or not isinstance(self.axis_y, QCategoryAxis):
            return
        low, high = self.data.value_range
        self.axis_y.blockSignals(True)
        for label in self.axis_y.categoriesLabels():
            self.axis_y.remove(label)
        self.axis_y.setStartValue(low - max(1, abs(low)) * 1e-6)
        for value in self.data.value_ticks:
            label = f"{value:.3g}" + (" g" if self.data.reference_enabled else "")
            self.axis_y.append(label, value)
        self.axis_y.setRange(low, high)
        self.axis_y.blockSignals(False)

    @Slot()
    def _redraw_time_labels(self) -> None:
        if self.data is None or not isinstance(self.axis_x, QCategoryAxis):
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        self.axis_x.blockSignals(True)
        for label in self.axis_x.categoriesLabels():
            self.axis_x.remove(label)
        self.axis_x.setStartValue(low - 1 / self.data.sample_rate)
        indices = sorted(
            {
                min(
                    self.data.count - 1,
                    max(0, round((low + (high - low) * step / 5) * self.data.sample_rate)),
                )
                for step in range(6)
            },
        )
        for index in indices:
            time = self.data.time_at(index)
            if low <= time <= high:
                self.axis_x.append(self.data.replay_text(index), time)
        self.axis_x.setRange(low, high)
        self.axis_x.blockSignals(False)

    @Slot()
    def _redraw_source_markers(self) -> None:
        if self.data is None:
            return
        for line in self.source_marker_lines.values():
            line.clear()
        for label in self.source_marker_labels.values():
            label.hide()
        plot = self.chart.plotArea()
        for row, (name, index) in enumerate(self.data.markers):
            time = self.data.time_at(index)
            line = self.source_marker_lines[name]
            line.replace(
                [QPointF(time, self.data.value_range[0]), QPointF(time, self.data.value_range[1])],
            )
            label = self.source_marker_labels[name]
            label.setText(f"{name} · {self.data.replay_text(index)}")
            label.setToolTip(f"Source {name}: sample {index}; recording {time:.3f} s")
            if self.axis_x.min() <= time <= self.axis_x.max() and plot.width() > 0:
                x = self.chart.mapToPosition(QPointF(time, self.axis_y.max()), line).x()
                x = max(plot.left(), min(x + 3, plot.right() - label.boundingRect().width()))
                label.setPos(x, plot.top() + row * (label.boundingRect().height() + 2))
                label.show()

    @Slot()
    def _redraw_cursor(self) -> None:
        if self.data is not None:
            time = self.data.time_at(self.slider.value())
            self.sample_cursor.replace(
                [QPointF(time, self.axis_y.min()), QPointF(time, self.axis_y.max())],
            )

    @Slot()
    def update_selection(self) -> None:
        if self.data is None:
            return
        self.first.setMaximum(self.last.value())
        self.last.setMinimum(self.first.value())
        selected = self.data.select(self.first.value(), self.last.value())
        self.selection_label.setText(
            f"{selected.count:,} samples (inclusive)\n"
            f"Replay {self.data.replay_text(selected.first)}–{self.data.replay_text(selected.last)}"
            f" @ {self.data.sample_rate:g} Hz",
        )
        self._refresh_extrema()

    def _refresh_extrema(self) -> None:
        if self.data is None:
            return
        context, rows = self.data.extrema_text(self.first.value(), self.last.value())
        self.extrema_context.setText(context)
        for label, text in zip(self.extrema_labels, rows, strict=True):
            label.setText(text)

    @Slot()
    def zoom_selection(self) -> None:
        if self.data is not None:
            selected = self.data.select(self.first.value(), self.last.value())
            self.axis_x.setRange(
                self.data.time_at(selected.first),
                self.data.time_at(selected.last)
                if selected.last > selected.first
                else self.data.time_at(selected.first) + 1 / self.data.sample_rate,
            )

    @Slot()
    def select_visible(self) -> None:
        if self.data is None:
            return
        selected = self.data.select_visible(self.axis_x.min(), self.axis_x.max())
        for control in (self.first, self.last):
            control.blockSignals(True)
            control.setRange(0, self.data.count - 1)
        self.first.setValue(selected.first)
        self.last.setValue(selected.last)
        for control in (self.first, self.last):
            control.blockSignals(False)
        self.update_selection()

    @Slot()
    def reset_view(self) -> None:
        self.chart.zoomReset()
        if self.data is not None:
            self.axis_x.setRange(*self.data.default_time_range)
            self.axis_y.setRange(*self.data.value_range)
