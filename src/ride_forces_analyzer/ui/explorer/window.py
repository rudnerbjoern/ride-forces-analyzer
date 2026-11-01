"""Recording explorer window with chart, playback and dialog coordination.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap

from ride_forces_analyzer import __version__
from ride_forces_analyzer.ui.presentation.error_report import ErrorReportButton
from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, Language, tr
from ride_forces_analyzer.ui.presentation.translation import (
    bind,
    button_text,
    set_ui_language,
    system_ui_language,
)

from pathlib import Path
from dataclasses import replace
from typing import TYPE_CHECKING
from ride_forces_analyzer.exports.formats import DataExportFormat
from importlib.util import find_spec

from PySide6.QtCore import QPoint, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QResizeEvent,
    QShowEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGridLayout,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.runtime.config import AppSettings
from ride_forces_analyzer.storage.preferences import Appearance, Preferences
from ride_forces_analyzer.explorer import ExplorerData, failure_text
from ride_forces_analyzer.importers import ImportFailure

from ride_forces_analyzer.gps.overview import prepare_gps_overview

from ride_forces_analyzer.ui.presentation.chrome import app_icon
from ride_forces_analyzer.ui.presentation.taskbar import taskbar_progress
from ride_forces_analyzer.ui.dialogs.about import AboutDialog
from ride_forces_analyzer.ui.presentation.icons import (
    data_export_icon,
    gps_overview_icon,
    reset_view_icon,
    select_visible_icon,
    settings_icon,
    video_export_icon,
    zoom_selection_icon,
)
from ride_forces_analyzer.ui.dialogs.settings import APPEARANCE_CHOICES, SettingsDialog
from ride_forces_analyzer.ui.presentation.updates import UpdateController
from ride_forces_analyzer.ui.dialogs.gps import gps_dialog
from ride_forces_analyzer.ui.explorer.loading import LoadWorker
from ride_forces_analyzer.ui.presentation.theme import THEMES, apply_theme, system_theme


if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
    from ride_forces_analyzer.ui.explorer.analysis import AnalysisController


from .controls import create_panel
from .inspector import ExplorerInspector
from .library import LibraryPanel
from .navigation import ExplorerNavigation
from ride_forces_analyzer.ui.exports.data_controller import DataExportController
from .chart import ExplorerChart
from functools import partial


class ExplorerWindow(QMainWindow):
    """Coordinate recording loading, analysis delivery and explorer UI components.

    Attributes:
        new_window_requested: Qt signal for new window requested notifications.
        closed: Qt signal for closed notifications.
        _application_title: Configured application title used in window captions.
        preferences: Local application preference access for this window or controller.
        _marker_save_failed: Whether the latest marker-persistence attempt failed.
        updates: Update-check service used by this window.
        ui_language: Selected interface language.
        appearance_preference: Stored light, dark or system appearance choice.
        theme: Application appearance palette.
        data: Prepared view data, retained bytes or item payload owned by this object.
        analysis_controller: Controller coordinating background analysis and view updates.
        _accept_results: Whether the window still accepts asynchronous results.
        _load_generation: Generation identifying the current recording-open request.
        _worker: Current recording-import worker.
        open_action: Action opening a recording in this window.
        new_window_action: Action opening a separate explorer window.
        gps_button: Button for gps button.
        export_button: Button for export button.
        data_export_button: Button for data export button.
        csv_action: Action opening CSV export.
        json_action: Action opening source-shaped JSON export.
        analyzer_json_action: Action opening analyzer JSON export.
        export_window: Open video-export assistant, when present.
        batch_window: Open batch-export dialog, when present.
        batches_button: Button for batches button.
        notes_button: Button for notes button.
        inspector_button: Button for inspector button.
        library: Collapsible Library component and its toolbar toggle.
        settings_action: Action opening application settings.
        about_action: Action opening application information.
        gps_window: Open GPS-context dialog, when present.
        _wide_layout: Whether the workspace currently uses the wide arrangement.
        heading: Label displaying heading.
        header_summary: Label displaying header summary.
        workspace: Container for the chart and recording controls.
        plot_panel: Container for the force chart.
        plot_scroll: Scrollable container for plot scroll.
        chart_tools: Controls for chart navigation and playback.
        plot: Component owning curves, axes, viewport and chart graphics.
        reference_toggle: Checkbox controlling reference toggle.
        reset_button: Button for reset button.
        zoom_button: Button for zoom button.
        visible_button: Button for visible button.
        visibility: Channel-visibility controls.
        inspector: Component owning recording details and selection controls.
        navigation: Component owning sample controls, readouts and playback transport.
        data_exports: Controller owning destination prompts and sample-export dialogs.
        progress: Progress display for progress.
        taskbar_progress: Native export-progress presentation for this window.
    """

    new_window_requested = Signal(object)
    closed = Signal()

    def __init__(self, settings: AppSettings, *, restore_last_file: bool = True) -> None:
        """Initialize explorer window and its owned state.

        Args:
            settings: Validated settings controlling this operation.
            restore_last_file: Whether startup may reopen the last recording.

        Returns:
            None.
        """
        super().__init__()
        self.taskbar_progress = taskbar_progress(self)
        self.setAcceptDrops(True)
        self._application_title = settings.window_title
        self.preferences = Preferences()
        self._marker_save_failed = False
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
        self.appearance_preference: Appearance = appearance
        self.theme = THEMES[
            system_theme(application)
            if appearance is Appearance.SYSTEM and isinstance(application, QApplication)
            else Appearance.DARK
            if appearance is Appearance.SYSTEM
            else appearance
        ]
        bind(self, settings.window_title, "windowTitle")
        self.setWindowIcon(app_icon())
        self.resize(settings.window_width, settings.window_height)
        self.data: ExplorerData | None = None
        self.analysis_controller: AnalysisController | None = None
        if find_spec("numpy") is not None:
            from ride_forces_analyzer.ui.explorer.analysis import AnalysisController

            self.analysis_controller = AnalysisController(self, preferences=self.preferences)
            self.analysis_controller.snapshot_ready.connect(self._analysis_updated)
            self.analysis_controller.failed.connect(self._analysis_failed)
            self.analysis_controller.markers_saved.connect(self._markers_saved)
            self.analysis_controller.pending_changed.connect(self._analysis_pending)
        self._accept_results = True
        self._load_generation = 0
        self._worker: LoadWorker | None = None
        self._create_toolbar()
        self._wide_layout: bool | None = None
        body, layout = self._create_workspace()
        self.inspector = ExplorerInspector(self)
        self.workspace.addWidget(self.inspector)
        self.inspector.smoothing_requested.connect(self.set_smoothing)
        self.inspector.selection_changed.connect(self.update_selection)
        self.inspector.details_hidden.connect(lambda: self.notes_button.setChecked(False))
        self.inspector_button.toggled.connect(self._toggle_inspector)
        self.data_exports = DataExportController(self.preferences, self)
        self.data_exports.starting.connect(self.navigation.pause)
        self.data_exports.saved.connect(self._data_saved)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.setCentralWidget(body)
        version_label = QLabel(f"v{__version__}")
        version_label.setObjectName("applicationVersion")
        self.statusBar().addPermanentWidget(ErrorReportButton(self.statusBar()))
        self.statusBar().addPermanentWidget(version_label)
        bind(self.statusBar(), tr("Ready — open a recording"), "message")
        self._set_controls(False)
        self.plot.axis_x.setRange(0, 1)
        self.plot.axis_y.setRange(-1, 1)
        self._style_chart()
        self._adapt_layout()
        if isinstance(application, QApplication):
            application.styleHints().colorSchemeChanged.connect(self._system_appearance_changed)
        QTimer.singleShot(0, lambda: self.updates.check(manual=False))
        if restore_last_file:
            QTimer.singleShot(0, self._restore_last_file)
        for key, step in (("Left", -1), ("Right", 1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda step=step: self.navigation.step_sample(step))

    def _create_toolbar(self) -> None:
        """Create recording actions, export menus and auxiliary-dialog controls."""
        self.open_action = bind(QAction(self), tr("&Open recording…"))
        bind(self.open_action, tr("Open recording…"), "toolTip")
        self.open_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
        )
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)
        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, self.theme)
        toolbar = bind(QToolBar(self), tr("Recording"), "windowTitle")
        toolbar.setMovable(False)
        self.library = LibraryPanel(self)
        self.library.open_requested.connect(self._open_archived)
        toolbar.addWidget(self.library.toggle_button)
        toolbar.addAction(self.open_action)
        open_widget = toolbar.widgetForAction(self.open_action)
        open_widget.setObjectName("Primary")
        self.new_window_action = bind(QAction(self), tr("Open in new window…"))
        self.new_window_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.new_window_action.triggered.connect(lambda: self.choose_file(new_window=True))
        self.addAction(self.new_window_action)
        if isinstance(open_widget, QToolButton):
            button_text(open_widget, tr("Open recording…"), caption=tr("&Open recording…"))
            open_widget.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            open_menu = QMenu(open_widget)
            open_menu.addAction(self.new_window_action)
            open_widget.setMenu(open_menu)
            open_widget.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.gps_button = button_text(QPushButton(), tr("GPS overview"))
        self.gps_button.setIcon(gps_overview_icon())
        self.gps_button.setEnabled(False)
        self.gps_button.clicked.connect(self.show_gps)
        toolbar.addWidget(self.gps_button)
        self.export_button = button_text(QPushButton(), tr("Export video…"))
        self.export_button.setIcon(video_export_icon())
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.show_export)
        toolbar.addWidget(self.export_button)
        self.data_export_button = button_text(QPushButton(), tr("Data export"))
        self.data_export_button.setIcon(data_export_icon())
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
        self.batch_window: QDialog | None = None
        self.batches_button = button_text(QPushButton(), tr("Batches…"))
        self.batches_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        self.batches_button.clicked.connect(self.show_batches)
        toolbar.addWidget(self.batches_button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.notes_button = button_text(QPushButton(), tr("Import notes"))
        self.notes_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        )
        self.notes_button.setCheckable(True)
        self.notes_button.toggled.connect(self._show_notes)
        notes_action = toolbar.addWidget(self.notes_button)
        self.inspector_button = button_text(QPushButton(), tr("Inspector"))
        self.inspector_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView),
        )
        self.inspector_button.setCheckable(True)
        toolbar.insertWidget(notes_action, self.inspector_button)
        self.addToolBar(toolbar)
        self.settings_action = bind(QAction(self), tr("Settings…"))
        self.settings_action.setIcon(settings_icon())
        self.settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(self.settings_action)
        self.about_action = bind(QAction(self), tr("About…"))
        self.about_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
        )
        self.about_action.triggered.connect(self.show_about)
        toolbar.addAction(self.about_action)
        for action in (self.settings_action, self.about_action):
            action_button = toolbar.widgetForAction(action)
            if isinstance(action_button, QToolButton):
                button_text(
                    action_button,
                    tr("Settings…") if action is self.settings_action else tr("About…"),
                )
        self.gps_window: QDialog | None = None

    def _create_workspace(self) -> tuple[QWidget, QVBoxLayout]:
        """Create the header, splitter, chart panel and sample navigation."""
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
        self.heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        # A positive minimum overrides QLabel's unshrinkable text-width hint.
        self.heading.setMinimumWidth(1)
        header = QHBoxLayout()
        header.addWidget(self.heading, 0, Qt.AlignmentFlag.AlignBottom)
        self.header_summary = bind(
            QLabel(),
            tr(
                "Choose Open recording or press {0}",
                self.open_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText),
            ),
        )
        self.header_summary.setObjectName("Muted")
        self.header_summary.setTextFormat(Qt.TextFormat.PlainText)
        for label in (self.heading, self.header_summary):
            label.ensurePolished()
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        descent = max(
            self.heading.fontMetrics().descent(),
            self.header_summary.fontMetrics().descent(),
        )
        for label in (self.heading, self.header_summary):
            label.setContentsMargins(0, 0, 0, descent - label.fontMetrics().descent())
        header.addWidget(self.header_summary, 0, Qt.AlignmentFlag.AlignBottom)
        header.addStretch()
        layout.addLayout(header)
        self.workspace = QSplitter(Qt.Orientation.Horizontal)
        self.workspace.setChildrenCollapsible(False)
        self.workspace.setHandleWidth(10)
        self.library.addWidget(self.workspace)
        self.library.setStretchFactor(1, 1)
        self.library.setSizes([260, 1000])
        layout.addWidget(self.library, 1)
        self.plot_panel, plot_layout = create_panel()
        self.plot_scroll = QScrollArea()
        self.plot_scroll.setObjectName("plotScroll")
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plot_scroll.setWidget(self.plot_panel)
        self.workspace.addWidget(self.plot_scroll)
        self._create_plot(plot_layout)
        self.navigation: ExplorerNavigation = ExplorerNavigation(self.plot, self)
        self.navigation.sample_changed.connect(self._refresh_sample)
        plot_layout.addWidget(self.navigation)
        return body, layout

    def _create_plot(self, plot_layout: QVBoxLayout) -> None:
        """Compose the chart component, visibility switches and view controls."""
        self.chart_tools = QGridLayout()
        self.chart_tools.setColumnStretch(5, 1)
        self.reference_toggle = bind(QCheckBox(), tr("Calibrated forces"))
        self.reference_toggle.setEnabled(False)
        self.reference_toggle.toggled.connect(self.set_reference_view)
        self.chart_tools.addWidget(self.reference_toggle, 0, 0)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        self.chart_tools.addWidget(divider, 0, 1)
        self.reset_button = QPushButton()
        bind(self.reset_button, tr("Reset view"), "toolTip")
        bind(self.reset_button, tr("Reset view"), "accessibleName")
        self.reset_button.setIcon(reset_view_icon())
        self.reset_button.clicked.connect(self.reset_view)
        self.zoom_button = QPushButton()
        bind(self.zoom_button, tr("Zoom to selection"), "toolTip")
        bind(self.zoom_button, tr("Zoom to selection"), "accessibleName")
        self.zoom_button.setIcon(zoom_selection_icon())
        self.zoom_button.clicked.connect(self.zoom_selection)
        self.visible_button = QPushButton()
        bind(self.visible_button, tr("Select visible range"), "toolTip")
        bind(self.visible_button, tr("Select visible range"), "accessibleName")
        self.visible_button.setIcon(select_visible_icon())
        self.visible_button.clicked.connect(self.select_visible)
        for column, button in enumerate(
            (self.reset_button, self.zoom_button, self.visible_button),
            start=6,
        ):
            self.chart_tools.addWidget(button, 0, column)
        plot_layout.addLayout(self.chart_tools)
        self.plot = ExplorerChart(self.theme, self)
        self.plot.chart_view.sample_requested.connect(self.select_chart_sample)
        self.plot.chart_view.marker_menu_requested.connect(self.show_marker_menu)
        self.plot.range_changed.connect(self._refresh_extrema)
        plot_layout.addWidget(self.plot.chart_view, 1)
        self.visibility: list[QCheckBox] = []
        for index, name in enumerate(("x", "y", "z")):
            toggle = bind(QCheckBox(), tr("Show {0}", name))
            toggle.setObjectName("forceVisibility")
            toggle.setChecked(True)
            toggle.toggled.connect(partial(self.plot.set_channel_visible, index))
            self.visibility.append(toggle)
            self.chart_tools.addWidget(toggle, 0, index + 2)
        plot_layout.addWidget(self.plot.airtime_legend)

    @Slot(int)
    def set_ui_language(self, index: int) -> None:
        """Apply the selected interface language while preserving recording state.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        application = QApplication.instance()
        if not isinstance(application, QApplication) or not 0 <= index < len(LANGUAGE_CHOICES):
            return
        self.ui_language = LANGUAGE_CHOICES[index]
        set_ui_language(application, self.ui_language)
        self.preferences.remember_language(self.ui_language)
        for window in application.topLevelWidgets():
            if isinstance(window, ExplorerWindow):
                window.ui_language = self.ui_language
                window._refresh_language()

    def _refresh_language(self) -> None:
        self.library.refresh_labels()
        if self.data is not None:
            self._draw_channels()
            self._refresh_sample(self.navigation.slider.value())
            self.update_selection()
            self.plot.redraw_value_labels()
            self.plot.redraw_source_markers()

    @Slot(int)
    def set_appearance(self, index: int) -> None:
        """Apply the selected workspace appearance preference.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        self._preview_appearance(index)
        self.preferences.remember_appearance(self.appearance_preference)

    @Slot(int)
    def _preview_appearance(self, index: int) -> None:
        self.appearance_preference = (
            APPEARANCE_CHOICES[index] if 0 <= index < len(APPEARANCE_CHOICES) else Appearance.DARK
        )
        self.apply_appearance()

    def _system_appearance_changed(self, scheme: Qt.ColorScheme) -> None:
        if self.appearance_preference is Appearance.SYSTEM:
            self.apply_appearance()

    def apply_appearance(self) -> None:
        """Apply the selected appearance to all recording windows without saving it.

        Returns:
            None.
        """
        application = QApplication.instance()
        if isinstance(application, QApplication):
            self.theme = THEMES[
                system_theme(application)
                if self.appearance_preference is Appearance.SYSTEM
                else self.appearance_preference
            ]
            apply_theme(application, self.theme)
            for window in application.topLevelWidgets():
                if isinstance(window, ExplorerWindow):
                    window.theme = self.theme
                    window.appearance_preference = self.appearance_preference
                    window.library.refresh_labels()
                    window._style_chart()
                    window._draw_channels()
        else:
            self._style_chart()
            self._draw_channels()

    def _style_chart(self) -> None:
        self.plot.set_theme(self.theme)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update view geometry after a Qt resize event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
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
        self.inspector.show_notes(checked)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window closure while preserving the owned worker lifecycle.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        self.navigation.pause()
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
        self.data_exports.close()
        self.updates.stopped = True
        self._accept_results = False
        self._load_generation += 1
        self._worker = None
        if self.analysis_controller is not None:
            self.analysis_controller.close()
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()

    def _set_controls(self, enabled: bool) -> None:
        self.navigation.set_enabled(enabled)
        self.inspector.set_enabled(enabled)
        for control in (
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
        self.data_export_button.setEnabled(
            enabled and self.data is not None and self.data.analysis is not None,
        )

        self.csv_action.setEnabled(self.data_export_button.isEnabled())
        self.json_action.setEnabled(self.data_export_button.isEnabled())
        self.analyzer_json_action.setEnabled(self.data_export_button.isEnabled())

    @Slot()
    def show_csv_export(self) -> None:
        """Open the CSV export flow for the current recording selection.

        Returns:
            None.
        """
        self._show_data_export(DataExportFormat.CSV)

    @Slot()
    def show_json_export(self) -> None:
        """Open the app-shaped JSON export flow for the current selection.

        Returns:
            None.
        """
        self._show_data_export(DataExportFormat.JSON)

    @Slot()
    def show_analyzer_json_export(self) -> None:
        """Open the Analyzer JSON export flow for the current selection.

        Returns:
            None.
        """
        self._show_data_export(DataExportFormat.ANALYZER_JSON)

    def _show_data_export(self, format: DataExportFormat) -> None:
        if self.data is not None and self.data.analysis is not None:
            self.data_exports.start(
                self.data.analysis,
                self.inspector.first.value(),
                self.inspector.last.value(),
                format,
            )

    @Slot(object, str)
    def _data_saved(self, format: DataExportFormat, path: str) -> None:
        self.library.refresh()
        bind(
            self.statusBar(),
            tr("CSV saved to {0}", path)
            if format is DataExportFormat.CSV
            else tr("JSON saved to {0}", path),
            "message",
        )

    @Slot()
    def show_export(self) -> None:
        """Open the video export assistant bound to the current analysis snapshot.

        Returns:
            None.
        """
        if self.data is None or not self.data.calibration_available:
            return
        self.navigation.pause()
        if self.export_window is not None and self.export_window.isVisible():
            self.export_window.raise_()
            self.export_window.activateWindow()
            return
        if self.export_window is not None:
            self.export_window.deleteLater()
        from ride_forces_analyzer.ui.exports.video import ExportDialog

        self.export_window = ExportDialog(
            self.data,
            self.inspector.first.value(),
            self.inspector.last.value(),
            self,
            current_sample=self.navigation.slider.value(),
        )
        self.export_window.finished.connect(self.library.refresh)
        self.export_window.show()

    @Slot()
    def show_batches(self) -> None:
        """Open the saved batch editor.

        Returns:
            None.
        """
        from ride_forces_analyzer.ui.exports.batches import BatchDialog
        from ride_forces_analyzer.storage.exports import ExportStore, default_database_path

        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.raise_()
            return
        self.batch_window = BatchDialog(ExportStore(default_database_path()), self)
        self.batch_window.show()

    @Slot()
    def show_settings(self) -> None:
        """Open application and export preferences.

        Returns:
            None.
        """
        previous_appearance = APPEARANCE_CHOICES.index(self.appearance_preference)
        dialog = SettingsDialog(
            self.preferences,
            self,
            language=self.ui_language,
            updates=self.updates,
        )
        dialog.language_selected.connect(self.set_ui_language)
        dialog.appearance_previewed.connect(self._preview_appearance)
        dialog.rejected.connect(lambda: self._preview_appearance(previous_appearance))
        dialog.appearance_selected.connect(self.set_appearance)
        dialog.open()

    @Slot()
    def show_about(self) -> None:
        """Open application information and local diagnostics.

        Returns:
            None.
        """
        dialog = self.findChild(AboutDialog, "aboutDialog")
        if dialog is None:
            dialog = AboutDialog(self)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    @Slot()
    def choose_file(self, *, new_window: bool = False) -> None:
        """Ask for a local recording path and schedule its import.

        Args:
            new_window: Whether to open a separate recording window.

        Returns:
            None.
        """
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open Ride Forces recording"),
            self.preferences.recording_directory(),
            tr("Ride Forces (*.forces *.zforces);;All files (*)"),
        )
        if filename:
            if new_window:
                self.new_window_requested.emit(Path(filename))
            else:
                self.open_path(Path(filename))

    @property
    def recording_path(self) -> Path | None:
        """Return the pending or loaded source path for external-open deduplication.

        Returns:
            The pending or loaded source path for external-open deduplication.
        """
        if self._worker is not None:
            return self._worker.path.resolve() if self._worker.path is not None else None
        if self.data is not None:
            path = self.data.source.recording.source.provenance.path
            return path.resolve() if path is not None else None
        return None

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

    def _dropped_recording(self, event: QDropEvent) -> Path | None:
        """Accept one local recording while the existing importer is idle."""
        mime = event.mimeData()
        if self._worker is not None:
            return None
        urls = mime.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if path.suffix.lower() not in {".forces", ".zforces"} or not path.is_file():
            return None
        return path

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept supported local recording-file drag payloads.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if self._dropped_recording(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Open a supported recording from a local-file drop.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        path = self._dropped_recording(event)
        if path is None:
            event.ignore()
            return
        self.open_path(path)
        event.acceptProposedAction()

    def open_path(self, path: Path) -> None:
        """Schedule read-only import of a recording while retaining the previous view.

        Args:
            path: Filesystem path read or written by this operation.

        Returns:
            None.
        """
        if self._worker is not None:
            return
        self.navigation.pause()
        self._load_generation += 1
        worker = LoadWorker(path, self._load_generation)
        worker.signals.completed.connect(self._load_completed)
        worker.signals.failed.connect(self._load_failed)
        self._worker = worker
        self.open_action.setEnabled(False)
        self.library.recordings.setEnabled(False)
        self.library.editor.setEnabled(False)
        self.library.edit_button.setEnabled(False)
        self.progress.show()
        bind(self.statusBar(), tr("Opening {0}…", path.name), "message")
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _open_archived(self, source_sha256: str) -> None:
        """Open the selected archived source through the existing load lifecycle."""
        if self._worker is not None:
            return
        self.navigation.pause()
        self._load_generation += 1
        worker = LoadWorker(None, self._load_generation, source_sha256=source_sha256)
        worker.signals.completed.connect(self._load_completed)
        worker.signals.failed.connect(self._load_failed)
        self._worker = worker
        self.open_action.setEnabled(False)
        self.library.recordings.setEnabled(False)
        self.library.editor.setEnabled(False)
        self.library.edit_button.setEnabled(False)
        self.progress.show()
        entry = self.library.selected_entry
        bind(
            self.statusBar(),
            tr("Opening {0}…", entry.filename if entry else tr("Recording")),
            "message",
        )
        QThreadPool.globalInstance().start(worker)

    def showEvent(self, event: QShowEvent) -> None:
        """Apply the view's startup geometry and appearance when it becomes visible.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
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
        self._marker_save_failed = False
        self.navigation.pause()
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
        self.library.show_recording(outcome)
        self.navigation.bind_recording(outcome)
        self.inspector.bind_recording(outcome)
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
        park = outcome.source.effective_metadata.location
        bind(self.heading, f"{outcome.title} · {park}" if park else outcome.title, "text")
        bind(self.header_summary, outcome.overview_text, "text")
        self._draw_channels()
        button_text(
            self.notes_button,
            tr(
                "Import notes ({0})",
                len(outcome.source.diagnostics) + bool(outcome.calibration_error),
            ),
        )
        self._set_controls(True)
        self.update_selection()
        self.plot.reset_axes()
        self.navigation.slider.setValue(outcome.ride_bounds[0])
        self.show_sample(self.navigation.slider.value())
        self._finish_loading()
        bind(self.statusBar(), "", "toolTip")
        bind(
            self.statusBar(),
            tr("Loaded — calibration unavailable; see Import notes")
            if outcome.calibration_error
            else tr("Loaded — drag to zoom, navigate samples or select an interval"),
            "message",
        )

    @Slot(float, QPoint)
    def show_marker_menu(self, fraction: float, position: QPoint) -> None:
        """Offer marker actions for the selected chart position.

        Args:
            fraction: Normalized time coordinate within the plotted interval.
            position: Pointer position in widget coordinates.

        Returns:
            None.
        """
        if (
            self.data is None
            or self.data.analysis is None
            or self.analysis_controller is None
            or self.analysis_controller.pending
            or not self.open_action.isEnabled()
        ):
            return
        self.navigation.pause()
        source = self.data.source
        low, high = self.plot.axis_x.min(), self.plot.axis_x.max()
        sample = self.data.sample_at_time(low + fraction * (high - low))
        first, last = self.data.ride_bounds
        indices = self.data.source.recording.indices
        original = indices.start, indices.end
        from ride_forces_analyzer.analysis.calibration import CalibrationOverrides

        calibration = self.data.analysis.configuration.calibration
        menu = QMenu(self)

        def add(
            text: str,
            bounds: tuple[int, int],
            reference: "CalibrationOverrides",
            enabled: bool = True,
        ) -> None:
            action = bind(QAction(menu), tr(text))
            action.setEnabled(enabled)

            def apply() -> None:
                if self.data is not None and self.data.source is source:
                    self._change_ride_markers(None if bounds == original else bounds, reference)

            action.triggered.connect(apply)
            menu.addAction(action)

        add("Set start here", (sample, last), calibration, sample <= last)
        add("Set end here", (first, sample), calibration, sample >= first)
        add("Set gravity here", (first, last), replace(calibration, gravity_index=sample))
        add("Set incline here", (first, last), replace(calibration, incline_index=sample))
        menu.addSeparator()
        add("Reset start to original", (indices.start, last), calibration, indices.start <= last)
        add("Reset end to original", (first, indices.end), calibration, first <= indices.end)
        add("Reset gravity to original", (first, last), replace(calibration, gravity_index=None))
        add("Reset incline to original", (first, last), replace(calibration, incline_index=None))
        menu.addSeparator()
        add("Reset all ride markers", original, CalibrationOverrides())
        menu.exec(position)
        menu.deleteLater()

    def _change_ride_markers(
        self,
        bounds: tuple[int, int] | None,
        calibration: "CalibrationOverrides",
    ) -> None:
        if self.data is None or self.analysis_controller is None:
            return
        self.analysis_controller.request_markers(bounds, calibration)

    @Slot(bool)
    def _markers_saved(self, saved: bool) -> None:
        self._marker_save_failed = not saved

    @Slot()
    def show_gps(self) -> None:
        """Open the current recording's independent GPS overview.

        Returns:
            None.
        """
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
        self.inspector.set_data(self.data)
        self.navigation.set_data(self.data, self.theme)
        self.plot.set_data(self.data)
        for i, name in enumerate(self.data.channel_names):
            bind(self.visibility[i], name.partition(" (")[0], "text")
            bind(self.visibility[i], name, "toolTip")
            color = (self.theme.forces if self.data.calibrated_enabled else self.theme.raw)[i]
            self.visibility[i].setStyleSheet(f"QCheckBox {{ color: {color}; }}")

    @Slot(int)
    def set_smoothing(self, position: int) -> None:
        """Request the selected smoothing window through the analysis controller.

        Args:
            position: Source-sample position.

        Returns:
            None.
        """
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
        markers_changed = self.data.analysis is not None and (
            outcome.configuration.ride_bounds != self.data.analysis.configuration.ride_bounds
        )
        self.data = self.data.with_analysis(outcome)
        self._refresh_analysis_view()
        if markers_changed:
            self.navigation.pause()
            self.plot.axis_x.setRange(*self.data.default_time_range)
            self.plot.redraw_time_labels()
            self.update_selection()
        if self._marker_save_failed:
            bind(
                self.statusBar(),
                tr("Ride markers applied for this session; local saving failed."),
                "message",
            )
            return
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
            self.plot.axis_y,
            tr("G-force (g)")
            if self.data.calibrated_enabled
            else tr("Source value (unit unknown)"),
            "titleText",
        )
        self._draw_channels()
        self.plot.axis_y.setRange(*self.data.value_range)
        self.plot.redraw_value_labels()
        self.plot.redraw_source_markers()
        self.navigation.redraw_cursor()
        self._refresh_sample(self.navigation.slider.value())
        self._refresh_extrema()

    @Slot(bool)
    def _analysis_pending(self, pending: bool) -> None:
        if pending:
            bind(self.statusBar(), tr("Updating analysis…"), "message")

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        if self.data is None:
            return
        self.inspector.restore_smoothing()
        bind(self.statusBar(), tr("Analysis failed: {0}", message), "message")

    @Slot(bool)
    def set_reference_view(self, enabled: bool) -> None:
        """Switch between available raw and calibrated presentation.

        Args:
            enabled: Whether the requested presentation or stored preference is enabled.

        Returns:
            None.
        """
        if self.data is None:
            return
        self.data = self.data.with_calibration(enabled)
        self._draw_channels()
        bind(
            self.plot.axis_y,
            tr("G-force (g)")
            if self.data.calibrated_enabled
            else tr("Source value (unit unknown)"),
            "titleText",
        )
        self.plot.axis_y.setRange(*self.data.value_range)
        self.plot.redraw_value_labels()
        self.plot.redraw_source_markers()
        self.navigation.redraw_cursor()
        self._refresh_sample(self.navigation.slider.value())
        self._refresh_extrema()

    def _finish_loading(self) -> None:
        self._worker = None
        self.open_action.setEnabled(True)
        self.library.recordings.setEnabled(True)
        self.library.editor.setEnabled(True)
        self.library.edit_button.setEnabled(True)
        self.progress.hide()

    @Slot(str)
    def _failed(self, message: str) -> None:
        if self._worker is not None and self._worker.source_sha256 is not None:
            self.library.show_error(message)
        self._finish_loading()
        bind(self.statusBar(), "", "toolTip")
        bind(self.statusBar(), message, "message")
        bind(self.statusBar(), message, "toolTip")

    def _refresh_sample(self, index: int) -> None:
        self.inspector.show_sample(index)

    @Slot(int)
    def show_sample(self, index: int) -> None:
        """Display the selected source sample without recalculating analysis.

        Args:
            index: Source or collection index selected for this operation.

        Returns:
            None.
        """
        self.navigation.show_sample(index)

    @Slot(float)
    def select_chart_sample(self, fraction: float) -> None:
        """Select the source sample corresponding to a chart interaction.

        Args:
            fraction: Normalized time coordinate within the plotted interval.

        Returns:
            None.
        """
        if self.data is not None:
            low, high = self.plot.axis_x.min(), self.plot.axis_x.max()
            self.navigation.position.setValue(
                self.data.sample_at_time(low + fraction * (high - low)),
            )

    @Slot(float, float)
    def zoom_wheel(self, fraction: float, steps: float) -> None:
        """Apply the chart's wheel-zoom request around its anchor.

        Args:
            fraction: Normalized time coordinate within the plotted interval.
            steps: Number of increments to apply.

        Returns:
            None.
        """
        self.plot.zoom_wheel(fraction, steps)

    @Slot()
    def update_selection(self) -> None:
        """Refresh the inclusive export selection and its displayed bounds.

        Returns:
            None.
        """
        selected = self.inspector.update_selection()
        if selected is not None:
            self.plot.set_selection(selected)
            self._refresh_extrema()

    @Slot()
    def _refresh_extrema(self) -> None:
        if self.data is None:
            return
        visible = self.data.select_visible(self.plot.axis_x.min(), self.plot.axis_x.max())
        context, rows = self.data.extrema_text(visible.first, visible.last, rich=True)
        self.inspector.show_extrema(context, rows)

    @Slot()
    def zoom_selection(self) -> None:
        """Fit the chart viewport to the current inclusive selection.

        Returns:
            None.
        """
        if self.data is not None:
            selected = self.data.select(self.inspector.first.value(), self.inspector.last.value())
            self.plot.axis_x.setRange(
                self.data.time_at(selected.first),
                self.data.time_at(selected.last)
                if selected.last > selected.first
                else self.data.time_at(selected.first) + 1 / self.data.sample_rate,
            )

    @Slot()
    def select_visible(self) -> None:
        """Select the source samples intersecting a visible time interval.

        Returns:
            None.
        """
        if self.data is None:
            return
        selected = self.data.select_visible(self.plot.axis_x.min(), self.plot.axis_x.max())
        self.inspector.set_selection(selected)
        self.update_selection()

    @Slot()
    def reset_view(self) -> None:
        """Restore the recording's effective default chart interval.

        Returns:
            None.
        """
        self.plot.reset_view()
