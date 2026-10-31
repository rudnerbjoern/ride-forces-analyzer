"""Two-page video-export assistant coordinating previews and background jobs.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.ui.presentation.translation import bind, items

# cspell:words pixmap Deutsch

from pathlib import Path
from dataclasses import replace
from functools import partial

from PySide6.QtCore import (
    QEvent,
    QThreadPool,
    Qt,
    Slot,
    QSize,
)
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QStackedWidget,
    QToolButton,
)

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import find_ffmpeg
from ride_forces_analyzer.rendering.progress import ExportPhase, ExportProgress
from ride_forces_analyzer.ui.exports.progress import show_export_progress
from ride_forces_analyzer.ui.presentation.taskbar import taskbar_progress
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    PROFILES,
    prepare_export,
    prepare_export_analysis,
)
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.storage.export_models import SavedPreset
from ride_forces_analyzer.storage.exports import (
    ExportStore,
    default_database_path,
)


from .workers import ExportWorker
from .form import ExportForm
from .presets import ExportPresets
from .preview_controller import PreviewController
from .preview import PreviewView, preview_pixmap


class ExportDialog(QDialog):
    """Configure, preview and export one recording through the two-page assistant.

    Attributes:
        analysis: Prepared recording-analysis snapshot used by this operation.
        form: Export-input widget and retained layout placements.
        presets: Preset persistence and batch-dialog component.
        previews: Debounced preview-worker controller.
        data: Prepared view data, retained bytes or item payload owned by this object.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        preferences: Local application preference access for this window or controller.
        current_sample: Opening graph sample, independent of the range-based preview.
        worker: Current background worker, or None when no task is active.
        step_label: Label displaying step label.
        profile_buttons: Layout-selection buttons keyed by profile.
        gallery: Container displaying the selectable layout previews.
        pages: Stacked pages for pages.
        summary: Label displaying summary.
        review_fields: Value labels keyed by export-summary field.
        review_size_estimate: Label displaying review size estimate.
        preview_caption: Label displaying preview caption.
        preview_view: Widget displaying the selected frame preview.
        background: Choice control for background.
        preview_note: Label displaying preview note.
        progress: Progress display for progress.
        status: Label displaying status.
        eta: Label displaying eta.
        back: Button for back.
        next: Button for next.
        start: Button for start.
        cancel: Button for cancel.
        controls: Controls enabled or disabled together during background processing.
    """

    def __init__(
        self,
        data: ExplorerData,
        first: int,
        last: int,
        parent: QWidget,
        *,
        current_sample: int | None = None,
        store: ExportStore | None = None,
    ) -> None:
        """Initialize export dialog and its owned state.

        Args:
            data: Input data in the representation declared by the parameter type.
            first: First included source sample index.
            last: Last included source sample index.
            parent: Qt parent that owns this object's lifetime.
            current_sample: Opening graph sample, independent of the range-based preview.
            store: Local export-definition storage.

        Returns:
            None.

        Raises:
            ValueError: Prepared recording analysis is unavailable.
        """
        super().__init__(parent)
        self._taskbar = taskbar_progress(self)
        bind(self, tr("Export assistant · {0}", data.title), "windowTitle")
        self.resize(1240, 820)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        if data.analysis is None:
            raise ValueError("Prepared recording analysis is unavailable")
        self.analysis = data.analysis
        self.data, self.first, self.last = data, first, last
        self.preferences = Preferences()
        self.form = ExportForm(data, self.preferences, self)
        self.presets = ExportPresets(
            store if store is not None else ExportStore(default_database_path()),
            self.form,
            self.analysis,
            first,
            last,
            self,
        )
        self.presets.selected.connect(self._load_preset)
        self.presets.message.connect(self._preset_message)
        self.previews = PreviewController(self)
        self.previews.ready.connect(self._preview_ready)
        self.previews.failed.connect(self._preview_failed)
        self.current_sample = (
            self.analysis.replay_origin if current_sample is None else current_sample
        )
        self.worker: ExportWorker | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        content_scroll = QScrollArea()
        content_scroll.setObjectName("exportContentScroll")
        content_scroll.setWidgetResizable(True)
        content_body = QWidget()
        layout = QVBoxLayout(content_body)
        content_scroll.setWidget(content_body)
        outer.addWidget(content_scroll, 1)
        self.step_label = bind(QLabel(), tr("1 · Set up export · {0}", data.title))
        self.step_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.step_label)
        layout.addWidget(self.presets)
        self.profile_buttons: list[QToolButton] = []
        gallery = QScrollArea()
        self.gallery = gallery
        gallery.setWidgetResizable(True)
        gallery.setFixedHeight(132)
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        for index, (_, title) in enumerate(PROFILES):
            button = QToolButton()
            bind(button, tr(title), "text")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(144, 81))
            button.setMinimumSize(158, 110)
            button.clicked.connect(partial(self._choose_profile, index))
            strip_layout.addWidget(button)
            self.profile_buttons.append(button)
        gallery.setWidget(strip)
        layout.addWidget(gallery)
        self.pages = QStackedWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        self.pages.addWidget(scroll)
        review_page = QWidget()
        review_layout = QVBoxLayout(review_page)
        self.summary = bind(QLabel(), tr("Export settings"))
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        summary_font = self.summary.font()
        summary_font.setBold(True)
        self.summary.setFont(summary_font)
        review_layout.addWidget(self.summary)
        review_form = QFormLayout()
        self._review_form = review_form
        review_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.review_fields: dict[str, QLabel] = {}
        for key, label in (
            ("layout", tr("Layout profile")),
            ("aspect", tr("Layout format")),
            ("extent", tr("Export area")),
            ("position", tr("Position")),
            ("resolution", tr("Output dimensions")),
            ("output", tr("Output")),
            ("language", tr("Overlay language")),
            ("fps", tr("Video frame rate")),
            ("range", tr("Range")),
            ("samples", tr("Samples")),
            ("smoothing", tr("Smoothing")),
            ("window", tr("Visible time window")),
        ):
            value = QLabel()
            value.setWordWrap(True)
            value.setTextFormat(Qt.TextFormat.PlainText)
            self.review_fields[key] = value
            review_form.addRow(bind(QLabel(), label), value)
        review_layout.addLayout(review_form)
        self.review_size_estimate = QLabel()
        self.review_size_estimate.setWordWrap(True)
        review_form.addRow(bind(QLabel(), tr("Estimated file size")), self.review_size_estimate)
        review_size_note = bind(
            QLabel(),
            tr(
                "Rough planning range, not a guarantee. Actual size depends on motion, detail and CPU/GPU encoding.",
            ),
        )
        review_size_note.setWordWrap(True)
        review_layout.addWidget(review_size_note)
        review_layout.addStretch()
        self.pages.addWidget(review_page)
        self.pages.setMaximumWidth(500)
        body = QHBoxLayout()
        body.addWidget(self.pages, 2)
        right = QVBoxLayout()
        self.preview_caption = QLabel()
        self.preview_caption.setWordWrap(True)
        self.preview_caption.setTextFormat(Qt.TextFormat.PlainText)
        right.addWidget(self.preview_caption)
        self.preview_view = PreviewView()
        right.addWidget(self.preview_view, 1)
        self.background = QComboBox()
        items(
            self.background,
            [
                tr("Checkerboard · alpha preview only"),
                tr("Light background · preview only"),
                tr("Dark background · preview only"),
            ],
        )
        for index, background in enumerate(PreviewBackground):
            self.background.setItemData(index, background.value)
        right.addWidget(self.background)
        self.preview_note = QLabel()
        self.preview_note.setWordWrap(True)
        self.preview_note.setTextFormat(Qt.TextFormat.PlainText)
        right.addWidget(self.preview_note)
        body.addLayout(right, 3)
        layout.addLayout(body, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        status_panel = QWidget()
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(11, 0, 11, 0)
        status_layout.addWidget(self.progress)
        self.status = bind(QLabel(), tr("Ready. Original recording remains unchanged."))
        self.eta = QLabel()
        self.eta.setWordWrap(True)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        self.eta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.eta, 1)
        status_layout.addLayout(status_row)
        outer.addWidget(status_panel)
        buttons = QHBoxLayout()
        self.back = bind(QPushButton(), tr("Back"))
        self.back.clicked.connect(self._back)
        self.back.setVisible(False)
        self.next = bind(QPushButton(), tr("Review export →"))
        self.next.setObjectName("Primary")
        self.next.clicked.connect(self._review)
        buttons.addWidget(self.back)
        buttons.addWidget(self.next)
        self.start = bind(QPushButton(), tr("Export video…"))
        self.start.setObjectName("Primary")
        self.start.clicked.connect(self._start)
        self.start.setVisible(False)
        self.cancel = bind(QPushButton(), tr("Close"))
        self.cancel.clicked.connect(self._cancel)
        buttons.addWidget(self.start)
        buttons.addWidget(self.cancel)
        buttons.setContentsMargins(11, 0, 11, 11)
        outer.addLayout(buttons)
        self.controls = (
            *self.form.controls,
            self.background,
            *self.profile_buttons,
            *self.presets.controls,
        )
        self.form.changed.connect(self._schedule_preview)
        self.background.currentIndexChanged.connect(self._schedule_preview)
        self.form.smoothing_changed.connect(self._smoothing_changed)
        self.presets.refresh()
        self._schedule_preview()

    @Slot(object)
    def _load_preset(self, preset: SavedPreset) -> None:
        try:
            self.analysis = prepare_export_analysis(
                self.analysis,
                replace(
                    preset.analysis_configuration,
                    ride_bounds=self.analysis.configuration.ride_bounds,
                    calibration=self.analysis.configuration.calibration,
                ),
            )
            self.data = self.data.with_analysis(self.analysis)
        except (TypeError, ValueError) as error:
            record_error("Export configuration", error)
            bind(self.status, tr(str(error)), "text")
            return
        self.presets.set_analysis(self.analysis)
        self.form.apply_preset(preset)
        self._schedule_preview()
        bind(self.status, tr("Loaded preset: {0}", preset.name), "text")

    @Slot(object)
    def _preset_message(self, message: str) -> None:
        bind(self.status, message, "text")

    @Slot(int)
    def _smoothing_changed(self, index: int) -> None:
        self.data = self.data.with_smoothing(index * 2 + 1)
        assert self.data.analysis is not None
        self.analysis = self.data.analysis
        self.presets.set_analysis(self.analysis)
        bind(self.form.smoothing, self.data.smoothing_text, "toolTip")
        self._schedule_preview()

    def _choose_profile(self, index: int, _checked: bool = False) -> None:
        if (
            self.form.settings().aspect
            not in registry.PLUGINS[PROFILES[index][0]].supported_aspects
        ):
            return
        self.form.layout_profile.setCurrentIndex(index)

    def _update_profile_availability(self) -> None:
        """Reflect plugin format capabilities without enabling controls during export."""
        aspect = self.form.settings().aspect
        for (key, _), button in zip(PROFILES, self.profile_buttons, strict=True):
            button.setEnabled(
                self.worker is None and aspect in registry.PLUGINS[key].supported_aspects,
            )

    def _bounds(self) -> tuple[int, int]:
        return self.form.bounds(self.analysis, (self.first, self.last))

    @Slot()
    def _schedule_preview(self) -> None:
        self._update_profile_availability()
        self.form.remember_positions()
        self._update_summary()
        first, last = self._bounds()
        self.previews.schedule(
            self.analysis,
            self.form.settings(),
            first,
            last,
            first + round(0.6 * (last - first)),
            PreviewBackground(self.background.currentData()),
            self.form.positions,
        )
        self.next.setEnabled(False)
        self.start.setEnabled(False)
        bind(self.preview_note, tr("Updating layout previews…"), "text")

    @Slot(object)
    def _preview_ready(self, result: ExportPreview) -> None:
        selected = PROFILES[self.form.layout_profile.currentIndex()][0]
        profiles = {profile.layout: profile for profile in result.profiles}
        for (key, _), button in zip(PROFILES, self.profile_buttons, strict=True):
            profile = profiles.get(key)
            button.setIcon(QIcon(preview_pixmap(profile.image)) if profile is not None else QIcon())
            button.setChecked(key == selected)
        self._update_profile_availability()
        self.preview_view.show_image(profiles[selected].image)
        self._update_preview_caption()
        bind(
            self.preview_note,
            tr(
                "Graph sample is OUTSIDE the export interval. Preview shows that exact sample with full-recording context; it is not part of this export.",
            )
            if result.outside_range
            else tr("Preview background is not exported."),
            "text",
        )
        self.next.setEnabled(self.worker is None)
        self.start.setEnabled(self.worker is None)
        self._update_summary()

    @Slot(str)
    def _preview_failed(self, message: str) -> None:
        bind(self.preview_note, tr("Preview failed: {0}", message), "text")

    def _update_summary(self) -> None:
        self._update_size_estimate()
        first, last = self._bounds()
        settings = self.form.settings()
        width, height = registry.resolve_geometry(settings).output_size
        values = {
            "layout": self.form.layout_profile.currentText(),
            "aspect": self.form.aspect.currentText(),
            "extent": self.form.extent.currentText()
            if not self.form.extent.isHidden()
            else self.form.fixed_extent.text(),
            "position": self.form.position.currentText(),
            "output": self.form.mode.currentText(),
            "language": self.form.overlay_language.currentText(),
            "resolution": f"{width}×{height}",
            "fps": self.form.fps.currentText(),
            "range": f"{self.data.replay_text(first)}–{self.data.replay_text(last)}",
            "samples": tr("{0:,}–{1:,} (inclusive)", first, last),
            "smoothing": self.data.smoothing_text,
            "window": tr("{0} s", self.form.seconds.value()),
        }
        for key, value in values.items():
            bind(self.review_fields[key], value)
        self._review_form.setRowVisible(
            self.review_fields["position"],
            not self.form.position.isHidden(),
        )

    def _update_preview_caption(self) -> None:
        result = self.previews.result
        if result is None:
            return
        self.preview_note.setVisible(self.pages.currentIndex() == 0 or result.outside_range)
        bind(
            self.preview_caption,
            tr(
                "Preview: graph sample {0:,} · Replay {1}",
                result.sample,
                self.data.replay_text(result.sample),
            ),
        )

    def _update_size_estimate(self) -> None:
        from ride_forces_analyzer.rendering.size_estimate import estimate_size_bytes

        first, last = self._bounds()
        low, high = estimate_size_bytes(
            self.form.settings(),
            last - first + 1,
            self.data.sample_rate,
        )
        bind(
            self.form.size_estimate,
            tr("{0:.0f}–{1:.0f} MiB", low / 2**20, high / 2**20),
        )
        bind(
            self.review_size_estimate,
            tr("{0:.0f}–{1:.0f} MiB", low / 2**20, high / 2**20),
        )

    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated or themed controls after a Qt change event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "controls"):
            self._update_summary()

    @Slot()
    def _review(self) -> None:
        if self.previews.result is None:
            return
        self._update_summary()
        self.pages.setCurrentIndex(1)
        bind(self.step_label, tr("2 · Review export · {0}", self.data.title), "text")
        for widget in (self.presets, self.gallery):
            widget.hide()
        self.pages.setMaximumWidth(420)
        self.preview_caption.setMinimumHeight(0)
        self._update_preview_caption()
        self.back.setVisible(True)
        self.next.setVisible(False)
        self.start.setVisible(True)

    @Slot()
    def _back(self) -> None:
        self.pages.setCurrentIndex(0)
        for widget in (self.presets, self.gallery):
            widget.show()
        self.pages.setMaximumWidth(500)
        self._update_preview_caption()
        bind(self.step_label, tr("1 · Set up export · {0}", self.data.title), "text")
        self.back.setVisible(False)
        self.next.setVisible(True)
        self.start.setVisible(False)

    @Slot()
    def _start(self) -> None:
        if (
            self.worker is not None
            or self.pages.currentIndex() != 1
            or self.previews.result is None
        ):
            return
        try:
            settings = self.form.settings()
            first, last = self._bounds()
            timeline = prepare_export(self.analysis, settings, first, last)
            encoder = find_ffmpeg(
                Path(self.form.encoder.text()) if self.form.encoder.text() else None,
            )
        except (ValueError, OSError) as error:
            record_error("Export preparation", error)
            bind(self.status, tr(str(error)), "text")
            return
        suffix = ".mov" if settings.output == VideoOutput.TRANSPARENT else ".mp4"
        source_path = self.data.source.recording.source.provenance.path
        stem = source_path.stem if source_path is not None else "ride-forces"
        name = f"{stem} - {self.form.layout_profile.currentText()}{suffix}"
        suggested = Path(self.preferences.export_directory()) / name
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save video"),
            str(suggested),
            tr("Video (*{0})", suffix),
        )
        if not filename:
            return
        worker = ExportWorker(
            timeline,
            Path(filename),
            encoder,
            render_jobs=self.preferences.render_jobs(),
            overwrite=Path(filename).exists(),
        )
        worker.signals.progress.connect(self._progress)
        worker.signals.finished.connect(self._finished)
        worker.signals.failed.connect(self._finished)
        worker.signals.saved.connect(self._export_saved)
        self.worker = worker
        self._taskbar.start()
        bind(self.eta, tr("Remaining frame time: estimating…"), "text")
        self.progress.setValue(0)
        self.progress.show()
        for control in self.controls:
            control.setEnabled(False)
        self.start.setEnabled(False)
        self.back.setEnabled(False)
        bind(self.cancel, tr("Cancel export"), "text")
        bind(self.status, tr("Exporting video…"), "text")
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _export_saved(self, path: str) -> None:
        self.preferences.remember_export(Path(path))

    @Slot(object)
    def _progress(self, update: ExportProgress) -> None:
        if self.worker is not None and not self.worker.cancelled.is_set():
            show_export_progress(update, self.progress, self.status, self.eta)
            if update.phase is not ExportPhase.PREPARING:
                self._taskbar.set_value(update.percent)

    @Slot(str)
    def _finished(self, message: str) -> None:
        self._taskbar.clear()
        bind(self.eta, "")
        self.worker = None
        for control in self.controls:
            control.setEnabled(True)
        self._update_profile_availability()
        self.form.flip_vertical.setEnabled(True)
        self.form.flip_lateral.setEnabled(False)
        self.start.setEnabled(True)
        self.back.setEnabled(True)
        bind(self.cancel, tr("Close"), "text")
        bind(self.status, message, "text")

    @Slot()
    def _cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancelled.set()
            self._taskbar.clear()
            bind(self.eta, "")
            bind(self.status, tr("Cancelling export…"), "text")
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window closure while preserving the owned worker lifecycle.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if not self.presets.close_batches():
            event.ignore()
            return
        if self.worker is not None:
            self._cancel()
            bind(self.status, tr("Cancelling export; close after completion."), "text")
            event.ignore()
        else:
            self.previews.close()
            super().closeEvent(event)

    def reject(self) -> None:
        """Close the dialog through its cancellation and worker-cleanup path.

        Returns:
            None.
        """
        if not self.presets.close_batches():
            return
        if self.worker is not None:
            self._cancel()
            return
        self.previews.close()
        super().reject()
