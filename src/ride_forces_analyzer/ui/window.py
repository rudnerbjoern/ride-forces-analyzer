"""First usable raw-recording explorer; Qt Charts owns interactive chart drawing.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap

from ride_forces_analyzer import __version__
from ride_forces_analyzer.i18n import Language, tr
from .translation import bind, items, set_ui_language, system_ui_language

from pathlib import Path
from typing import TYPE_CHECKING, Literal
from importlib.util import find_spec
from time import monotonic
from math import ceil

from PySide6.QtCharts import QCategoryAxis, QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QElapsedTimer, QPointF, Qt, QThreadPool, QTimer, Signal, Slot
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
    QComboBox,
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QFileDialog,
    QHBoxLayout,
    QGraphicsSimpleTextItem,
    QGraphicsRectItem,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionSpinBox,
    QSplitter,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.config import AppSettings
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.explorer import ExplorerData, failure_text
from ride_forces_analyzer.importers import ImportFailure
from ride_forces_analyzer.playback import SamplePlayback

from ride_forces_analyzer.gps_overview import prepare_gps_overview

from .chrome import app_icon
from .about import AboutDialog
from .preferences import SettingsDialog
from .updates import UpdateController
from .gps import gps_dialog
from .loading import LoadWorker
from .theme import THEMES, apply_theme, system_theme


if TYPE_CHECKING:
    from .analysis import AnalysisController


class SmoothingSlider(QSlider):
    """Right click restores the default 11-sample window (slider position five)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.setValue(5)
            event.accept()
            return
        super().mousePressEvent(event)


class SelectionSpinBox(QSpinBox):
    """Use 1/5/10/20/50-sample steps after 0/1/2/3/5 seconds holding an arrow."""

    def __init__(self) -> None:
        super().__init__()
        self._hold_timer = QElapsedTimer()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._hold_timer.invalidate()
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        button = self.style().hitTestComplexControl(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            event.position().toPoint(),
            self,
        )
        if event.button() == Qt.MouseButton.LeftButton and button in (
            QStyle.SubControl.SC_SpinBoxUp,
            QStyle.SubControl.SC_SpinBoxDown,
        ):
            self._hold_timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._hold_timer.invalidate()
        super().mouseReleaseEvent(event)

    def stepBy(self, steps: int) -> None:
        elapsed = self._hold_timer.elapsed() if self._hold_timer.isValid() else 0
        stride = (
            50
            if elapsed >= 5000
            else 20
            if elapsed >= 3000
            else 10
            if elapsed >= 2000
            else 5
            if elapsed >= 1000
            else 1
        )
        super().stepBy(steps * stride)


class TimeChartView(QChartView):
    zoom_requested = Signal(float, float)
    sample_requested = Signal(float)

    def __init__(self, chart: QChart) -> None:
        super().__init__(chart)
        self._press_position: QPointF | None = None
        self._dragged = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._press_position = (
            event.position() if event.button() == Qt.MouseButton.LeftButton else None
        )
        self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_position is not None:
            self._dragged |= (
                event.position() - self._press_position
            ).manhattanLength() >= QApplication.startDragDistance()
            if not self._dragged:
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        clicked = (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_position is not None
            and not self._dragged
            and (event.position() - self._press_position).manhattanLength()
            < QApplication.startDragDistance()
        )
        self._press_position = None
        chart = self.chart()
        point = chart.mapFromScene(self.mapToScene(event.position().toPoint()))
        plot = chart.plotArea()
        super().mouseReleaseEvent(event)
        if clicked and plot.contains(point) and plot.width() > 0:
            self.sample_requested.emit((point.x() - plot.left()) / plot.width())

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
        self.preferences = Preferences()
        self.updates = UpdateController(self, self.preferences)
        language = (
            settings.language
            if "language" in settings.model_fields_set
            else self.preferences.language(system_ui_language())
        )
        self.ui_language: Language = language
        application = QApplication.instance()
        if isinstance(application, QApplication):
            set_ui_language(application, language)
        appearance = self.preferences.appearance()
        self.appearance_preference: Literal["dark", "light", "system"] = appearance
        self.theme = THEMES[
            system_theme(application)
            if appearance == "system" and isinstance(application, QApplication)
            else "light"
            if appearance == "light"
            else "dark"
        ]
        bind(self, settings.window_title, "windowTitle")
        self.setWindowIcon(app_icon())
        self.resize(settings.window_width, settings.window_height)
        self.data: ExplorerData | None = None
        self.playback: SamplePlayback | None = None
        self._playback_position = 0.0
        self._updating_playback = False
        self._playback_button_playing: bool | None = None
        self.playback_timer = QTimer(self)
        self.playback_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.playback_timer.setInterval(16)
        self.playback_timer.timeout.connect(self._playback_tick)
        self.analysis_controller: AnalysisController | None = None
        if find_spec("numpy") is not None:
            from .analysis import AnalysisController

            self.analysis_controller = AnalysisController(self)
            self.analysis_controller.snapshot_ready.connect(self._analysis_updated)
            self.analysis_controller.failed.connect(self._analysis_failed)
            self.analysis_controller.pending_changed.connect(self._analysis_pending)
        self._accept_results = True
        self._load_generation = 0
        self._worker: LoadWorker | None = None
        self.open_action = bind(QAction(self), tr("Open recording…"))
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)
        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, self.theme)
        toolbar = bind(QToolBar(self), tr("Recording"), "windowTitle")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        open_widget = toolbar.widgetForAction(self.open_action)
        open_widget.setObjectName("Primary")
        self.gps_button = bind(QPushButton(), tr("GPS overview"))
        self.gps_button.setEnabled(False)
        self.gps_button.clicked.connect(self.show_gps)
        toolbar.addWidget(self.gps_button)
        self.export_button = bind(QPushButton(), tr("Export 4K…"))
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.show_export)
        toolbar.addWidget(self.export_button)
        self.data_export_button = bind(QPushButton(), tr("Data export"))
        self.data_export_button.setEnabled(False)
        data_menu = QMenu(self.data_export_button)
        self.csv_action = bind(QAction(self), tr("Export CSV…"))
        self.csv_action.triggered.connect(self.show_csv_export)
        data_menu.addAction(self.csv_action)
        self.json_action = bind(QAction(self), tr("Export JSON…"))
        self.json_action.triggered.connect(self.show_json_export)
        data_menu.addAction(self.json_action)
        self.analyzer_json_action = bind(QAction(self), tr("Export Analyzer JSON…"))
        self.analyzer_json_action.triggered.connect(self.show_analyzer_json_export)
        data_menu.addAction(self.analyzer_json_action)
        self.data_export_button.setMenu(data_menu)
        toolbar.addWidget(self.data_export_button)
        self.export_window: QDialog | None = None
        self.data_export_window: QDialog | None = None
        self.batch_window: QDialog | None = None
        self.batches_button = bind(QPushButton(), tr("Batches…"))
        self.batches_button.clicked.connect(self.show_batches)
        toolbar.addWidget(self.batches_button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.notes_button = bind(QPushButton(), tr("Import notes"))
        self.notes_button.setCheckable(True)
        self.notes_button.toggled.connect(self._show_notes)
        notes_action = toolbar.addWidget(self.notes_button)
        self.inspector_button = bind(QPushButton(), tr("Inspector"))
        self.inspector_button.setCheckable(True)
        toolbar.insertWidget(notes_action, self.inspector_button)
        self.addToolBar(toolbar)
        self.settings_action = bind(QAction(self), tr("Settings…"))
        self.settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(self.settings_action)
        self.about_action = bind(QAction(self), tr("About…"))
        self.about_action.triggered.connect(self.show_about)
        toolbar.addAction(self.about_action)
        self.gps_window: QDialog | None = None
        self._wide_layout: bool | None = None
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        self.heading = bind(
            QLabel(),
            tr("Open a .forces or .zforces recording to explore your ride"),
        )
        self.heading.setObjectName("recordingHeading")
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        self.heading.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.heading)
        self.header_summary = bind(
            QLabel(),
            tr(
                "Choose Open recording or press {0}",
                self.open_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText),
            ),
        )
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
        self.reference_toggle = bind(QCheckBox(), tr("Calibrated forces"))
        self.reference_toggle.setEnabled(False)
        self.reference_toggle.toggled.connect(self.set_reference_view)
        self.reset_button = bind(QPushButton(), tr("Reset view"))
        self.reset_button.clicked.connect(self.reset_view)
        self.zoom_button = bind(QPushButton(), tr("Zoom to selection"))
        self.zoom_button.clicked.connect(self.zoom_selection)
        self.visible_button = bind(QPushButton(), tr("Select visible range"))
        self.visible_button.clicked.connect(self.select_visible)
        plot_layout.addLayout(self.chart_tools)
        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setBackgroundBrush(QColor("#182330"))
        self.chart.setBackgroundRoundness(0)
        self.chart.legend().hide()
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        chart_margins = self.chart.margins()
        chart_margins.setBottom(0)
        self.chart.setMargins(chart_margins)
        self.chart_view = TimeChartView(self.chart)
        self.chart_view.zoom_requested.connect(self.zoom_wheel)
        self.chart_view.sample_requested.connect(self.select_chart_sample)
        self.chart_view.setObjectName("recordingChart")
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setRubberBand(QChartView.RubberBand.HorizontalRubberBand)
        self.chart_view.setMinimumSize(0, 240)
        # Let the plot shrink instead of reusing its previous viewport height.
        self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        plot_layout.addWidget(self.chart_view, 1)
        self.selection_band = QGraphicsRectItem(self.chart)
        self.selection_band.setPen(QPen(Qt.PenStyle.NoPen))
        self.selection_band.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.selection_band.setZValue(1)
        self.selection_band.hide()
        self.chart.plotAreaChanged.connect(self._redraw_selection)
        self.axis_x = QValueAxis()
        bind(self.axis_x, tr("Elapsed time (s)"), "titleText")
        self.axis_x.setLabelFormat("%.3f")
        self.axis_y = QValueAxis()
        bind(self.axis_y, tr("Source value (unit unknown)"), "titleText")
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series: list[QLineSeries] = []
        self.vertical_context_bars: list[QGraphicsRectItem] = []
        self.vertical_context_ranges: tuple[tuple[str, int, int], ...] = ()
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
            toggle = bind(QCheckBox(), tr("Show {0}", name))
            toggle.setChecked(True)
            toggle.toggled.connect(line.setVisible)
            self.visibility.append(toggle)
            axes.addWidget(toggle)
        axes.addStretch()
        plot_layout.insertLayout(1, axes)
        self.visibility[0].toggled.connect(self._set_vertical_context_visible)
        self.airtime_legend = QLabel()
        self.airtime_legend.setWordWrap(True)
        self.airtime_legend.hide()
        plot_layout.addWidget(self.airtime_legend)
        self.chart.plotAreaChanged.connect(self._redraw_vertical_context)
        self.axis_x.rangeChanged.connect(self._redraw_vertical_context)
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
            card, card_layout = self._panel()
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

        display, display_layout = self._panel(tr("DISPLAY"))
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
        self.smoothing_slider.valueChanged.connect(self.set_smoothing)
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

        selection, selection_layout = self._panel(tr("SELECTION"))
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
        self.first.valueChanged.connect(self.update_selection)
        self.last.valueChanged.connect(self.update_selection)
        inspector_layout.addWidget(selection)

        extrema, extrema_layout = self._panel(tr("VISIBLE RANGE EXTREMA"))
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

        recording, recording_layout = self._panel(tr("RECORDING"))
        self.ride_metadata = QLabel()
        self.ride_metadata.setObjectName("rideMetadata")
        self.ride_metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.ride_metadata.setWordWrap(True)
        self.ride_metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ride_metadata.hide()
        recording_layout.addWidget(self.ride_metadata)
        inspector_layout.addWidget(recording)

        details, details_layout = self._panel()
        self.details_button = bind(QPushButton(), tr("Technical details"))
        self.details_button.setCheckable(True)
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
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.setCentralWidget(body)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("applicationVersion")
        self.statusBar().addPermanentWidget(version_label)
        bind(self.statusBar(), tr("Ready — open a recording"), "message")
        self._set_controls(False)
        self.axis_x.setRange(0, 1)
        self.axis_y.setRange(-1, 1)
        self._style_axes()
        self._style_chart()
        self._adapt_layout()
        if isinstance(application, QApplication):
            application.styleHints().colorSchemeChanged.connect(self._system_appearance_changed)
        QTimer.singleShot(0, lambda: self.updates.check(manual=False))
        QTimer.singleShot(0, self._restore_last_file)

    @Slot(int)
    def set_ui_language(self, index: int) -> None:
        application = QApplication.instance()
        if not isinstance(application, QApplication):
            return
        self.ui_language = "de" if index == 1 else "en"
        set_ui_language(application, self.ui_language)
        self.preferences.remember_language("de" if index == 1 else "en")
        if self.data is not None:
            self._refresh_diagnostics()
            bind(self.ride_metadata, self.data.metadata_rows_text)
            self._draw_channels()
            self._refresh_sample(self.slider.value())
            self.update_selection()
            self._redraw_value_labels()
            self._redraw_source_markers()

    @Slot(int)
    def set_appearance(self, index: int) -> None:
        self.appearance_preference = "system" if index == 2 else "light" if index == 1 else "dark"
        self.preferences.remember_appearance(self.appearance_preference)
        self._apply_appearance()

    def _system_appearance_changed(self, scheme: Qt.ColorScheme) -> None:
        if self.appearance_preference == "system":
            self._apply_appearance()

    def _apply_appearance(self) -> None:
        application = QApplication.instance()
        if isinstance(application, QApplication):
            self.theme = THEMES[
                system_theme(application)
                if self.appearance_preference == "system"
                else self.appearance_preference
            ]
            apply_theme(application, self.theme)
        self._style_chart()
        self._draw_channels()

    def _style_chart(self) -> None:
        self.chart.setBackgroundBrush(QColor(self.theme.panel))
        self.chart_view.setBackgroundBrush(QColor(self.theme.panel))
        self._style_axes()
        self._redraw_selection()
        for (name, line), color in zip(
            self.source_marker_lines.items(),
            self.theme.markers,
            strict=True,
        ):
            line.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.DashDotLine))
            self.source_marker_labels[name].setBrush(QColor(color))

    @staticmethod
    def _panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        if title:
            label = bind(QLabel(), title)
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
        self.original_diagnostics.setVisible(checked)
        if checked:
            QTimer.singleShot(0, lambda: self.inspector.ensureWidgetVisible(self.notes))

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_body.setVisible(checked)
        if not checked:
            self.notes_button.setChecked(False)

    def _style_axes(self) -> None:
        for axis in (self.axis_x, self.axis_y):
            axis.setLabelsBrush(QColor(self.theme.muted))
            axis.setTitleBrush(QColor(self.theme.muted))
            axis.setGridLinePen(QPen(QColor(self.theme.grid), 1))
            axis.setLinePen(QPen(QColor(self.theme.border), 1))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._pause_playback()
        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.close()
            if self.batch_window.isVisible():
                event.ignore()
                return
        if self.export_window is not None and self.export_window.isVisible():
            self.export_window.close()
            if self.export_window.isVisible():
                event.ignore()
                return
        if self.gps_window is not None:
            self.gps_window.close()
        if self.data_export_window is not None:
            self.data_export_window.close()
        self.updates.stopped = True
        self._accept_results = False
        self._load_generation += 1
        self._worker = None
        if self.analysis_controller is not None:
            self.analysis_controller.close()
        super().closeEvent(event)

    def _set_controls(self, enabled: bool) -> None:
        for control in (
            self.slider,
            self.position,
            self.play_button,
            self.playback_speed,
            self.first,
            self.last,
            self.zoom_button,
            self.visible_button,
            self.reset_button,
            self.notes_button,
            *self.visibility,
        ):
            control.setEnabled(enabled)
        self.export_button.setEnabled(
            enabled and self.data is not None and self.data.calibration_available,
        )
        self.play_button.setEnabled(enabled and self.data is not None and self.data.count > 1)
        self.data_export_button.setEnabled(
            enabled and self.data is not None and self.data.analysis is not None,
        )

        self.csv_action.setEnabled(self.data_export_button.isEnabled())
        self.json_action.setEnabled(self.data_export_button.isEnabled())
        self.analyzer_json_action.setEnabled(self.data_export_button.isEnabled())

    @Slot()
    def show_csv_export(self) -> None:
        self._show_data_export("csv")

    @Slot()
    def show_json_export(self) -> None:
        self._show_data_export("json")

    @Slot()
    def show_analyzer_json_export(self) -> None:
        self._show_data_export("analyzer_json")

    def _show_data_export(self, format: Literal["csv", "json", "analyzer_json"]) -> None:
        if self.data is None or self.data.analysis is None:
            return
        if self.data_export_window is not None and self.data_export_window.isVisible():
            self.data_export_window.raise_()
            return
        self._pause_playback()
        analysis = self.data.analysis
        first, last = self.first.value(), self.last.value()
        source_path = analysis.source.recording.source.provenance.path
        suffix = ".csv" if format == "csv" else ".json"
        stem = source_path.stem if source_path else "recording"
        name = f"{stem}{'.analyzer' if format == 'analyzer_json' else ''}{suffix}"
        directory = self.preferences.export_directory()
        suggested = (
            Path(directory) / name
            if directory
            else source_path.with_name(name)
            if source_path
            else Path(name)
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Analyzer JSON")
            if format == "analyzer_json"
            else tr("Export JSON")
            if format == "json"
            else tr("Export CSV"),
            str(suggested),
            tr("CSV files (*.csv)") if format == "csv" else tr("JSON files (*.json)"),
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != suffix:
            path = path.with_name(path.name + suffix)
        overwrite = path.exists()
        if (
            overwrite
            and QMessageBox.question(
                self,
                tr("Replace existing file?"),
                tr("The file already exists:\n{0}\n\nDo you want to replace it?", str(path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.data_export_window is not None:
            self.data_export_window.deleteLater()
        from .data_export import DataExportDialog

        dialog = DataExportDialog(
            analysis,
            path,
            first,
            last,
            self.preferences,
            self,
            format,
            overwrite,
        )
        dialog.saved.connect(self._csv_saved if format == "csv" else self._json_saved)
        self.data_export_window = dialog
        dialog.show()

    @Slot(str)
    def _json_saved(self, path: str) -> None:
        bind(self.statusBar(), tr("JSON saved to {0}", path), "message")

    @Slot(str)
    def _csv_saved(self, path: str) -> None:
        bind(self.statusBar(), tr("CSV saved to {0}", path), "message")

    @Slot()
    def show_export(self) -> None:
        if self.data is None or not self.data.calibration_available:
            return
        self._pause_playback()
        if self.export_window is not None and self.export_window.isVisible():
            self.export_window.raise_()
            self.export_window.activateWindow()
            return
        if self.export_window is not None:
            self.export_window.deleteLater()
        from .export import ExportDialog

        self.export_window = ExportDialog(
            self.data,
            self.first.value(),
            self.last.value(),
            self,
            current_sample=self.slider.value(),
        )
        self.export_window.show()

    @Slot()
    def show_batches(self) -> None:
        from .batches import BatchDialog
        from ride_forces_analyzer.storage.exports import ExportStore, default_database_path

        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.raise_()
            return
        self.batch_window = BatchDialog(ExportStore(default_database_path()), self)
        self.batch_window.show()

    @Slot()
    def show_settings(self) -> None:
        dialog = SettingsDialog(self.preferences, self, language=self.ui_language)
        dialog.language_selected.connect(self.set_ui_language)
        dialog.appearance_selected.connect(self.set_appearance)
        dialog.open()

    @Slot()
    def show_about(self) -> None:
        dialog = self.findChild(AboutDialog, "aboutDialog")
        if dialog is None:
            dialog = AboutDialog(self, self.updates)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @Slot()
    def choose_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Ride Forces recording"),
            self.preferences.recording_directory(),
            tr("Ride Forces (*.forces *.zforces);;All files (*)"),
        )
        if filename:
            self.open_path(Path(filename))

    @Slot()
    def _restore_last_file(self) -> None:
        if (
            not self._accept_results
            or self._load_generation
            or not self.preferences.restore_last_file()
        ):
            return
        path = self.preferences.last_recording()
        if path is not None:
            self.open_path(path)

    def open_path(self, path: Path) -> None:
        if self._worker is not None:
            return
        self._pause_playback()
        self._load_generation += 1
        worker = LoadWorker(path, self._load_generation)
        worker.signals.completed.connect(self._load_completed)
        worker.signals.failed.connect(self._load_failed)
        self._worker = worker
        self.open_action.setEnabled(False)
        self.progress.show()
        bind(self.statusBar(), tr("Opening {0}…", path.name), "message")
        QThreadPool.globalInstance().start(worker)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._accept_results:
            self._accept_results = True
            if self.analysis_controller is not None:
                self.analysis_controller.bind_snapshot(
                    self.data.analysis if self.data is not None else None,
                )

    @Slot(int, object)
    def _load_completed(self, generation: int, outcome: object) -> None:
        if self._accept_results and generation == self._load_generation:
            self._loaded(outcome)

    @Slot(int, str)
    def _load_failed(self, generation: int, message: str) -> None:
        if self._accept_results and generation == self._load_generation:
            self._failed(message)

    @Slot(object)
    def _loaded(self, outcome: object) -> None:
        if isinstance(outcome, ImportFailure):
            self._failed(failure_text(outcome))
            return
        if not isinstance(outcome, ExplorerData):
            self._failed(tr("Unable to display recording."))
            return
        outcome = outcome.with_calibration(outcome.calibration_available)
        self._pause_playback()
        if self.analysis_controller is not None:
            self.analysis_controller.bind_snapshot(outcome.analysis)
        path = outcome.source.recording.source.provenance.path
        if path is not None:
            self.preferences.remember_recording(path)
        if self.gps_window is not None:
            self.gps_window.close()
            self.gps_window.deleteLater()
            self.gps_window = None
        self.gps_button.setEnabled(prepare_gps_overview(outcome.source.recording) is not None)
        self.data = outcome
        self.playback = SamplePlayback(outcome.count, outcome.sample_rate, clock=monotonic)
        self.playback_speed.blockSignals(True)
        self.playback_speed.setCurrentIndex(1)
        self.playback_speed.blockSignals(False)
        self.smoothing_slider.blockSignals(True)
        self.smoothing_slider.setValue((outcome.smoothing_window - 1) // 2)
        self.smoothing_slider.blockSignals(False)
        self.reference_toggle.blockSignals(True)
        self.reference_toggle.setEnabled(outcome.calibration_available)
        bind(
            self.reference_toggle,
            tr("App reference available for {0}", outcome.title)
            if outcome.calibration_available
            else tr(outcome.calibration_error)
            if outcome.calibration_error
            else tr("Calibration unavailable for this recording"),
            "toolTip",
        )
        self.reference_toggle.setChecked(outcome.calibrated_enabled)
        self.reference_toggle.blockSignals(False)
        bind(self, f"{outcome.title} · {self._application_title}", "windowTitle")
        bind(self.heading, outcome.title, "text")
        bind(self.ride_metadata, outcome.metadata_rows_text, "text")
        self.ride_metadata.setVisible(bool(outcome.metadata_text))
        bind(self.summary, outcome.technical_summary, "text")
        bind(self.header_summary, outcome.overview_text, "text")
        bind(self.availability, outcome.availability_text, "text")
        self._draw_channels()
        self._refresh_diagnostics()
        bind(
            self.notes_button,
            tr(
                "Import notes ({0})",
                len(outcome.source.diagnostics) + bool(outcome.calibration_error),
            ),
            "text",
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
        bind(self.axis_x, outcome.replay_time_label, "titleText")
        self.axis_x.rangeChanged.connect(self._redraw_time_labels)
        self.axis_x.rangeChanged.connect(self._redraw_selection)
        self.axis_x.rangeChanged.connect(self._refresh_extrema)
        self.axis_x.rangeChanged.connect(self._bound_time_view)
        self.axis_x.rangeChanged.connect(self._redraw_source_markers)
        self.axis_x.rangeChanged.connect(self._redraw_vertical_context)
        self.axis_x.setRange(*outcome.default_time_range)
        bind(
            self.axis_y,
            tr("G-force (g)") if outcome.calibrated_enabled else tr("Source value (unit unknown)"),
            "titleText",
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
        bind(self.statusBar(), "", "toolTip")
        bind(
            self.statusBar(),
            tr("Loaded — calibration unavailable; see Import notes")
            if outcome.calibration_error
            else tr("Loaded — drag to zoom, navigate samples or select an interval"),
            "message",
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
        active = self.data.calibrated_enabled
        bind(self.summary, self.data.technical_summary, "text")
        bind(
            self.disclaimer,
            tr(
                "Calibrated forces\nSource directions\n{0}\nInferred time",
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
        colors = self.theme.forces if active else self.theme.raw
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
            bind(self.visibility[i], name.partition(" (")[0], "text")
            bind(self.visibility[i], name, "toolTip")
            self.visibility[i].setStyleSheet(f"QCheckBox {{ color: {color}; }}")
            self.value_labels[i].setStyleSheet(f"color: {color};")
        self.chart.setTitle("")
        self.signs.setVisible(active)
        self._draw_vertical_context()

    def _draw_vertical_context(self) -> None:
        for bar in self.vertical_context_bars:
            self.chart.scene().removeItem(bar)
        self.vertical_context_bars.clear()
        self.vertical_context_ranges = ()
        self.airtime_legend.hide()
        if self.data is None or not self.data.calibrated_enabled:
            return
        colors = self.theme.vertical_context_colors
        self.vertical_context_ranges = self.data.vertical_context_segments
        for label, _, _ in self.vertical_context_ranges:
            bar = QGraphicsRectItem(self.chart)
            bar.setPen(QPen(Qt.PenStyle.NoPen))
            bar.setBrush(QColor(colors.get(label, self.theme.muted)))
            bar.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            bar.setZValue(10)
            self.vertical_context_bars.append(bar)
        self.airtime_legend.setText(
            " &nbsp; ".join(
                f'<span style="color:{color}">● {tr(label)}</span>'
                for label, color in colors.items()
            ),
        )
        bind(
            self.airtime_legend,
            tr("Airtime context uses provisional thresholds."),
            "toolTip",
        )
        self._set_vertical_context_visible(self.visibility[0].isChecked())

    @Slot(bool)
    def _set_vertical_context_visible(self, visible: bool) -> None:
        self.airtime_legend.setVisible(visible and bool(self.vertical_context_bars))
        self._redraw_vertical_context()

    def _redraw_vertical_context(self) -> None:
        if self.data is None:
            return
        plot = self.chart.plotArea()
        low, high = self.axis_x.min(), self.axis_x.max()
        enabled = self.data.calibrated_enabled and self.visibility[0].isChecked()
        for bar, (_, first, last) in zip(
            self.vertical_context_bars,
            self.vertical_context_ranges,
            strict=True,
        ):
            start = max(low, self.data.time_at(first))
            end = min(high, self.data.time_at(last))
            visible = enabled and high > low and end > start and plot.height() > 10
            bar.setVisible(visible)
            if visible:
                left = plot.left() + (start - low) / (high - low) * plot.width()
                right = plot.left() + (end - low) / (high - low) * plot.width()
                bar.setRect(left, plot.bottom() - 10, right - left, 10)

    @Slot(int)
    def set_smoothing(self, position: int) -> None:
        if self.data is None or not self.data.calibrated_enabled:
            return
        if self.analysis_controller is not None and self.data.analysis is not None:
            self.analysis_controller.request_smoothing(position * 2 + 1)
            return
        self.data = self.data.with_smoothing(position * 2 + 1)
        self._refresh_analysis_view()

    @Slot(object)
    def _analysis_updated(self, outcome: object) -> None:
        if self.data is None or self.data.analysis is outcome:
            return
        from ride_forces_analyzer.analysis.recording import RecordingAnalysis

        if not isinstance(outcome, RecordingAnalysis):
            return
        self.data = self.data.with_analysis(outcome)
        self._refresh_analysis_view()
        bind(
            self.statusBar(),
            tr("Loaded — drag to zoom, navigate samples or select an interval"),
            "message",
        )

    def _refresh_analysis_view(self) -> None:
        if self.data is None:
            return
        self.reference_toggle.blockSignals(True)
        self.reference_toggle.setEnabled(self.data.calibration_available)
        self.reference_toggle.setChecked(self.data.calibrated_enabled)
        self.reference_toggle.blockSignals(False)
        bind(
            self.axis_y,
            tr("G-force (g)")
            if self.data.calibrated_enabled
            else tr("Source value (unit unknown)"),
            "titleText",
        )
        self._refresh_diagnostics()
        self._draw_channels()
        self.axis_y.setRange(*self.data.value_range)
        self._redraw_value_labels()
        self._redraw_source_markers()
        self._redraw_cursor()
        self._refresh_sample(self.slider.value())
        self._refresh_extrema()

    @Slot(bool)
    def _analysis_pending(self, pending: bool) -> None:
        if pending:
            bind(self.statusBar(), tr("Updating analysis…"), "message")

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        if self.data is None:
            return
        self.smoothing_slider.blockSignals(True)
        self.smoothing_slider.setValue(
            (self.data.smoothing_window - 1) // 2,
        )
        self.smoothing_slider.blockSignals(False)
        bind(self.statusBar(), tr("Analysis failed: {0}", message), "message")

    @Slot(bool)
    def set_reference_view(self, enabled: bool) -> None:
        if self.data is None:
            return
        self.data = self.data.with_calibration(enabled)
        self._draw_channels()
        bind(
            self.axis_y,
            tr("G-force (g)")
            if self.data.calibrated_enabled
            else tr("Source value (unit unknown)"),
            "titleText",
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
        bind(self.statusBar(), "", "toolTip")
        bind(self.statusBar(), message, "message")
        bind(self.statusBar(), message, "toolTip")

    def _refresh_sample(self, index: int) -> None:
        if self.data is None:
            return
        bind(self.readout, self.data.sample_text(index, rich=True), "text")
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

    @Slot(int)
    def show_sample(self, index: int) -> None:
        if self.data is None:
            return
        if self.playback is not None and not self._updating_playback:
            self.playback.seek(index)
            self._playback_position = float(index)
            self._sync_playback_button()
        self._refresh_sample(index)
        if self._updating_playback:
            return
        self._redraw_cursor()
        low, high = self.axis_x.min(), self.axis_x.max()
        time = self.data.time_at(index)
        if time < low or time > high:
            width = high - low
            first = max(0.0, min(time - width / 2, self.data.duration - width))
            self.axis_x.setRange(first, first + width)

    @Slot()
    def toggle_playback(self) -> None:
        if self.playback is None:
            return
        if self.playback.playing:
            self._pause_playback()
        else:
            self.slider.setValue(self.playback.play(self.slider.value()))
            self._playback_position = float(self.slider.value())
            self._sync_playback_button()

    @Slot(int)
    def set_playback_speed(self, index: int) -> None:
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
                low, high = self.axis_x.min(), self.axis_x.max()
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
                        self.axis_x.setRange(first, first + width)
                elif time < low or time > high:
                    width = high - low
                    first = max(0.0, min(time - width / 2, self.data.duration - width))
                    self.axis_x.setRange(first, first + width)
            self._playback_position = position
            self._updating_playback = True
            try:
                self.slider.setValue(index)
            finally:
                self._updating_playback = False
            self._redraw_cursor()
            self._sync_playback_button()

    def _pause_playback(self) -> None:
        if self.playback is not None:
            self.slider.setValue(self.playback.pause())
            self._playback_position = float(self.slider.value())
            self._redraw_cursor()
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

    @Slot(float)
    def select_chart_sample(self, fraction: float) -> None:
        if self.data is not None:
            low, high = self.axis_x.min(), self.axis_x.max()
            self.position.setValue(self.data.sample_at_time(low + fraction * (high - low)))

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
            label = str(tr("{0:.3g}", value)) + (" g" if self.data.calibrated_enabled else "")
            self.axis_y.append(label, value)
        self.axis_y.setRange(low, high)
        self.axis_y.blockSignals(False)

    @Slot()
    def _redraw_time_labels(self) -> None:
        if self.data is None or not isinstance(self.axis_x, QCategoryAxis):
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        stride = max(1, round(round((high - low) * self.data.sample_rate / 5, 9)))
        anchor = self.data.source.recording.indices.start or 0
        first_tick = ceil((max(0.0, low * self.data.sample_rate) - anchor - 1e-9) / stride)
        first = anchor + first_tick * stride
        indices = range(
            first,
            min(self.data.count, int(high * self.data.sample_rate + 1e-9) + 1),
            stride,
        )
        labels = [self.data.replay_text(index) for index in indices]
        if self.axis_x.categoriesLabels() == labels:
            return
        self.axis_x.blockSignals(True)
        for label in self.axis_x.categoriesLabels():
            self.axis_x.remove(label)
        self.axis_x.setStartValue(low - 1 / self.data.sample_rate)
        for index in indices:
            time = self.data.time_at(index)
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
            marker_names = {
                "startIndex": "Start marker",
                "endIndex": "End marker",
                "gravityIndex": "Gravity marker",
                "inclineIndex": "Incline marker",
            }
            display_name = tr(marker_names[name]) if self.ui_language == "de" else name
            bind(label, f"{display_name} · {self.data.replay_text(index)}", "text")
            bind(
                label,
                tr("Source {0}: sample {1}; recording {2:.3f} s", name, index, time),
                "toolTip",
            )
            if self.axis_x.min() <= time <= self.axis_x.max() and plot.width() > 0:
                x = self.chart.mapToPosition(QPointF(time, self.axis_y.max()), line).x()
                x = max(plot.left(), min(x + 3, plot.right() - label.boundingRect().width()))
                label.setPos(x, plot.top() + row * (label.boundingRect().height() + 2))
                label.show()

    @Slot()
    def _redraw_cursor(self) -> None:
        if self.data is not None:
            position = (
                self._playback_position
                if self.playback is not None and self.playback.playing
                else self.slider.value()
            )
            time = position / self.data.sample_rate
            self.sample_cursor.replace(
                [QPointF(time, self.axis_y.min()), QPointF(time, self.axis_y.max())],
            )

    @Slot()
    def _redraw_selection(self) -> None:
        if self.data is None or self.last.value() >= self.data.count:
            self.selection_band.hide()
            return
        plot = self.chart.plotArea()
        low, high = self.axis_x.min(), self.axis_x.max()
        first = max(low, self.data.time_at(self.first.value()))
        last = min(high, self.data.time_at(self.last.value()))
        visible = high > low and last >= first and plot.width() > 0 and plot.height() > 0
        self.selection_band.setVisible(visible)
        if visible:
            left = plot.left() + (first - low) / (high - low) * plot.width()
            right = plot.left() + (last - low) / (high - low) * plot.width()
            if right - left < 2:
                left = max(plot.left(), min(left - 1, plot.right() - 2))
                right = min(plot.right(), left + 2)
            color = self.chart_view.palette().highlight().color()
            color.setAlpha(32)
            self.selection_band.setBrush(color)
            self.selection_band.setRect(left, plot.top(), right - left, plot.height())

    @Slot()
    def update_selection(self) -> None:
        if self.data is None:
            return
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
        self._redraw_selection()
        self._refresh_extrema()

    @Slot()
    def _refresh_extrema(self) -> None:
        if self.data is None:
            return
        visible = self.data.select_visible(self.axis_x.min(), self.axis_x.max())
        context, rows = self.data.extrema_text(visible.first, visible.last, rich=True)
        bind(self.extrema_context, context, "text")
        for label, text in zip(self.extrema_labels, rows, strict=True):
            bind(label, text, "text")

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
