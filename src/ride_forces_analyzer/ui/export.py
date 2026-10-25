"""Export dialog and Qt worker transport; rendering/encoding stay in their subsystem.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, LANGUAGES, get_language, tr
from ride_forces_analyzer.error_reporting import record_error
from .translation import bind, items

# cspell:words pixmap Deutsch

from pathlib import Path
from typing import cast
from dataclasses import replace
from functools import partial
from threading import Event

from PySide6.QtCore import (
    QEvent,
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal,
    Slot,
    QSize,
    QTimer,
    QSignalBlocker,
)
from PySide6.QtGui import QCloseEvent, QImage, QPixmap, QResizeEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QSizePolicy,
    QInputDialog,
    QDoubleSpinBox,
)
from PIL import Image

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import ExportCancelled, export_video, find_ffmpeg
from ride_forces_analyzer.rendering.progress import ExportProgress
from .export_progress import show_export_progress
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    VideoAspect,
    EXPORT_FRAME_RATES,
    FrameRate,
    ExportLayout,
    ExportSettings,
    ExportTimeline,
    PROFILES,
    prepare_export,
    prepare_export_analysis,
)
from ride_forces_analyzer.rendering.preview import ExportPreview, PreviewBackground, build_previews
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.batches import make_job
from ride_forces_analyzer.storage.export_models import SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import (
    ExportStore,
    ExportStoreError,
    default_database_path,
)


class PreviewSignals(QObject):
    """Deliver preview completion and failure notifications to the owning dialog.

    Attributes:
        ready: Qt signal for ready notifications.
        failed: Qt signal for failed notifications.
    """

    ready = Signal(int, object)
    failed = Signal(int, str)


class PreviewWorker(QRunnable):
    """Build layout previews in the thread pool from one captured analysis snapshot.

    Attributes:
        revision: Monotonically increasing identity used to reject superseded work.
        analysis: Prepared recording-analysis snapshot used by this operation.
        settings: Validated settings controlling this operation.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        sample: Source sample index to inspect or present.
        background: Preview background, excluded from exported overlays.
        previous_positions: Previously selected positions keyed by layout.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        revision: int,
        analysis: RecordingAnalysis,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: PreviewBackground,
        previous_positions: dict[ExportLayout, LayoutPosition],
    ) -> None:
        """Initialize preview worker and its owned state.

        Args:
            revision: Monotonically increasing identity used to reject superseded work.
            analysis: Prepared recording-analysis snapshot used by this operation.
            settings: Validated settings controlling this operation.
            first: First included source sample index.
            last: Last included source sample index.
            sample: Source sample index to inspect or present.
            background: Preview background, excluded from exported overlays.
            previous_positions: Previously selected positions keyed by layout.

        Returns:
            None.
        """
        super().__init__()
        self.revision, self.analysis, self.settings = revision, analysis, settings
        self.first, self.last, self.sample, self.background = first, last, sample, background
        self.previous_positions = previous_positions.copy()
        self.signals = PreviewSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            result = build_previews(
                self.analysis,
                self.settings,
                self.first,
                self.last,
                self.sample,
                self.background,
                self.previous_positions,
            )
        except Exception as error:
            record_error("Export preview", error)
            self.signals.failed.emit(self.revision, str(error))
        else:
            self.signals.ready.emit(self.revision, result)


def _pixmap(image: Image.Image) -> QPixmap:
    raw = image.tobytes()
    return QPixmap.fromImage(
        QImage(raw, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy(),
    )


class PreviewView(QLabel):
    """Display an aspect-preserving preview image inside the available dialog space.

    Attributes:
        source: Retained input identity or image; its original representation remains
            owned.
    """

    def __init__(self) -> None:
        """Initialize preview view and its owned state.

        Returns:
            None.
        """
        super().__init__(tr("Preparing preview…"))
        self.source = QPixmap()
        self.setMinimumSize(440, 248)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_image(self, image: Image.Image) -> None:
        """Display a prepared preview image without changing its source pixels.

        Args:
            image: Raster image to inspect or draw into.

        Returns:
            None.
        """
        self.source = _pixmap(image)
        self._fit()

    def _fit(self) -> None:
        if not self.source.isNull():
            self.setPixmap(
                self.source.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Update view geometry after a Qt resize event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self._fit()


class ExportSignals(QObject):
    """Deliver video-export progress, completion and failure notifications.

    Attributes:
        saved: Qt signal for saved notifications.
        progress: Qt signal for progress notifications.
        finished: Qt signal for finished notifications.
        failed: Qt signal for failed notifications.
    """

    saved = Signal(str)
    progress = Signal(object)
    finished = Signal(str)
    failed = Signal(str)


class ExportWorker(QRunnable):
    """Run the bound video export and transport its result through Qt signals.

    Attributes:
        timeline: Bound video timeline containing the source interval and export settings.
        destination: Requested output path; replacement follows the explicit overwrite
            policy.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
        render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
            availability.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.
        cancelled: Event used to request cancellation without publishing partial output.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        timeline: ExportTimeline,
        destination: Path,
        ffmpeg: Path,
        *,
        render_jobs: int = 1,
        overwrite: bool = False,
    ) -> None:
        """Initialize export worker and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.
            destination: Requested output path; replacement follows the explicit overwrite
                policy.
            ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
            render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
                availability.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.

        Returns:
            None.
        """
        super().__init__()
        self.timeline = timeline
        self.destination = destination
        self.ffmpeg = ffmpeg
        self.render_jobs = render_jobs
        self.overwrite = overwrite
        self.cancelled = Event()
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            path = export_video(
                self.timeline,
                self.destination,
                ffmpeg=self.ffmpeg,
                cancelled=self.cancelled,
                progress=self.signals.progress.emit,
                render_jobs=self.render_jobs,
                overwrite=self.overwrite,
            )
        except ExportCancelled:
            self.signals.finished.emit(tr("Export cancelled. No incomplete output was kept."))
        except Exception as error:
            record_error("Video export", error)
            self.signals.failed.emit(tr("Export failed: {0}", error))
        else:
            self.signals.saved.emit(str(path))
            self.signals.finished.emit(tr("Saved {0}", path))


class ExportDialog(QDialog):
    """Configure, preview and export one recording through the two-page assistant.

    Attributes:
        analysis: Prepared recording-analysis snapshot used by this operation.
        data: Prepared view data, retained bytes or item payload owned by this object.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        preferences: Local application preference access for this window or controller.
        store: Local export-definition repository used by this view or service.
        saved: Saved export presets available in this dialog.
        batch_window: Open batch-export dialog, when present.
        current_sample: Exact source sample selected for the preview.
        worker: Current background worker, or None when no task is active.
        preview_worker: Background worker preparing the preview images.
        preview_result: Most recent accepted preview result.
        preview_revision: Revision used to reject stale preview results.
        preview_positions: Selected placement keyed by layout profile.
        closing: Whether shutdown has started and late results must be ignored.
        step_label: Label displaying step label.
        presets_widget: Container widget for presets widget.
        preset_selector: Choice control for preset selector.
        load_preset: Button for load preset.
        save_preset: Button for save preset.
        update_preset: Button for update preset.
        queue: Button for queue.
        manage_batches: Button for manage batches.
        profile_buttons: Layout-selection buttons keyed by profile.
        gallery: Container displaying the selectable layout previews.
        pages: Stacked pages for pages.
        layout_profile: Choice control for layout profile.
        position: Choice control for position.
        aspect: Choice control for aspect.
        overlay_language: Choice control for overlay language.
        mode: Choice control for mode.
        fps: Choice control for fps.
        interval: Choice control for interval.
        seconds: Numeric control for seconds.
        smoothing: Choice control for smoothing.
        flip_vertical: Checkbox controlling flip vertical.
        flip_lateral: Checkbox controlling flip lateral.
        gpu: Checkbox controlling gpu.
        size_estimate: Label displaying size estimate.
        size_note: Label displaying size note.
        encoder: Text input for encoder.
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
        preview_timer: Timer scheduling preview timer.
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
            current_sample: Exact source sample selected for the preview.
            store: Local export-definition storage.

        Returns:
            None.

        Raises:
            ValueError: Prepared recording analysis is unavailable.
        """
        super().__init__(parent)
        bind(self, tr("Export assistant · {0}", data.title), "windowTitle")
        self.resize(1240, 820)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        if data.analysis is None:
            raise ValueError("Prepared recording analysis is unavailable")
        self.analysis = data.analysis
        self.data, self.first, self.last = data, first, last
        self.preferences = Preferences()
        self.store = store if store is not None else ExportStore(default_database_path())
        self.saved: tuple[SavedPreset, ...] = ()
        self.batch_window: QDialog | None = None
        self.current_sample = (
            self.analysis.replay_origin if current_sample is None else current_sample
        )
        self.worker: ExportWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self.preview_result: ExportPreview | None = None
        self.preview_revision = 0
        self.preview_positions: dict[ExportLayout, LayoutPosition] = {}
        self.closing = False
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
        self.presets_widget = QWidget()
        presets_layout = QVBoxLayout(self.presets_widget)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_row = QHBoxLayout()
        presets_row.setContentsMargins(0, 0, 0, 0)
        presets_row.addWidget(bind(QLabel(), tr("Saved preset")))
        self.preset_selector = QComboBox()
        presets_row.addWidget(self.preset_selector, 1)
        self.load_preset = bind(QPushButton(), tr("Load"))
        self.load_preset.clicked.connect(self._load_preset)
        self.save_preset = bind(QPushButton(), tr("Save as…"))
        self.save_preset.clicked.connect(self._save_preset)
        self.update_preset = bind(QPushButton(), tr("Update selected"))
        self.update_preset.clicked.connect(self._update_preset)
        self.queue = bind(QPushButton(), tr("Add this export to batch…"))
        self.queue.clicked.connect(self._queue)
        self.manage_batches = bind(QPushButton(), tr("Saved batches…"))
        self.manage_batches.clicked.connect(self._manage_batches)
        presets_row.addWidget(self.load_preset)
        presets_layout.addLayout(presets_row)
        preset_actions = QHBoxLayout()
        for preset_button in (
            self.save_preset,
            self.update_preset,
            self.queue,
            self.manage_batches,
        ):
            preset_actions.addWidget(preset_button)
        presets_layout.addLayout(preset_actions)
        layout.addWidget(self.presets_widget)
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
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        section_font = self.font()
        section_font.setBold(True)

        def section(title: str) -> None:
            label = bind(QLabel(), title)
            label.setFont(section_font)
            form.addRow(label)

        section(tr("Export settings"))
        self.layout_profile = QComboBox()
        items(self.layout_profile, [tr(title) for _, title in PROFILES])
        self.layout_profile.currentIndexChanged.connect(self._layout_changed)
        layout_row = QHBoxLayout()
        layout_row.addWidget(self.layout_profile, 1)
        layout_row.addWidget(bind(QLabel(), tr("Position")))
        self.position = QComboBox()
        self.position.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        layout_row.addWidget(self.position)
        form.addRow(bind(QLabel(), tr("Layout profile")), layout_row)
        self.aspect = QComboBox()
        items(self.aspect, [tr("Landscape · 16:9"), tr("Portrait · 9:16")])
        form.addRow(bind(QLabel(), tr("Video format")), self.aspect)
        self.aspect.currentIndexChanged.connect(self._refresh_positions)
        self._refresh_positions()
        self.overlay_language = QComboBox()
        items(self.overlay_language, [definition.name for definition in LANGUAGES.values()])
        self.overlay_language.setCurrentIndex(LANGUAGE_CHOICES.index(get_language()))
        form.addRow(bind(QLabel(), tr("Overlay language")), self.overlay_language)
        self.mode = QComboBox()
        items(
            self.mode,
            [tr("Transparent overlay · ProRes 4444 MOV"), tr("Opaque video · H.264 MP4")],
        )
        form.addRow(bind(QLabel(), tr("Output")), self.mode)
        self.fps = QComboBox()
        items(self.fps, [ExportSettings(fps=rate).fps_label for rate in EXPORT_FRAME_RATES])
        for index, rate in enumerate(EXPORT_FRAME_RATES):
            self.fps.setItemData(index, rate)
        self.fps.setCurrentText(ExportSettings(fps=self.preferences.export_fps()).fps_label)
        form.addRow(bind(QLabel(), tr("Video frame rate")), self.fps)
        self.interval = QComboBox()
        items(
            self.interval,
            [tr("Start/end markers (default)"), tr("Current selection"), tr("Entire recording")],
        )
        form.addRow(bind(QLabel(), tr("Range")), self.interval)
        section(tr("Force display"))
        self.seconds = QDoubleSpinBox()
        self.seconds.setDecimals(3)
        self.seconds.setRange(1, 60)
        self.seconds.setValue(12)
        bind(self.seconds, " s", "suffix")
        form.addRow(bind(QLabel(), tr("Visible time window")), self.seconds)
        self.smoothing = QComboBox()
        items(self.smoothing, [tr("{0} samples", count) for count in range(1, 52, 2)])
        self.smoothing.setCurrentIndex(
            data.smoothing_window // 2,
        )
        form.addRow(bind(QLabel(), tr("Smoothing")), self.smoothing)
        self.flip_vertical = bind(
            QCheckBox(),
            tr("Positive values downward"),
        )
        bind(self.flip_vertical, tr("Positive values below zero, as in the reference"), "toolTip")
        self.flip_vertical.setChecked(True)
        form.addRow(bind(QLabel(), tr("Vertical")), self.flip_vertical)
        self.flip_lateral = bind(QCheckBox(), tr("+ Right / − Left"))
        self.flip_lateral.setChecked(False)
        self.flip_lateral.setEnabled(False)
        form.addRow(bind(QLabel(), tr("Lateral")), self.flip_lateral)
        section(tr("Encoding"))
        self.gpu = bind(QCheckBox(), tr("Use NVIDIA GPU"))
        bind(self.gpu, tr("Use NVIDIA GPU when supported; CPU fallback otherwise"), "toolTip")
        self.gpu.setChecked(True)
        form.addRow(bind(QLabel(), tr("Acceleration")), self.gpu)
        self.size_estimate = QLabel()
        self.size_estimate.setWordWrap(True)
        self.size_note = bind(
            QLabel(),
            tr(
                "Rough planning range, not a guarantee. Actual size depends on motion, detail and CPU/GPU encoding.",
            ),
        )
        self.size_note.setWordWrap(True)
        self.encoder = QLineEdit()
        try:
            bind(self.encoder, str(find_ffmpeg()), "text")
        except ValueError:
            self.encoder.setPlaceholderText(tr("Choose installed FFmpeg executable"))
        browse = bind(QPushButton(), tr("Browse…"))
        browse.clicked.connect(self._browse)
        encoder_row = QHBoxLayout()
        encoder_row.addWidget(self.encoder)
        encoder_row.addWidget(browse)
        form.addRow("FFmpeg", encoder_row)
        form.addRow(bind(QLabel(), tr("Estimated file size")), self.size_estimate)
        form.addRow(self.size_note)
        settings_layout.addLayout(form)
        settings_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings_page)
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
        review_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.review_fields: dict[str, QLabel] = {}
        for key, label in (
            ("layout", tr("Layout profile")),
            ("output", tr("Output")),
            ("resolution", tr("Resolution")),
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
        bind(self.smoothing, data.smoothing_text, "toolTip")
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
            self.overlay_language,
            self.aspect,
            self.layout_profile,
            self.position,
            self.mode,
            self.fps,
            self.interval,
            self.seconds,
            self.flip_vertical,
            self.flip_lateral,
            self.encoder,
            self.gpu,
            browse,
            self.background,
            *self.profile_buttons,
            self.smoothing,
            self.preset_selector,
            self.load_preset,
            self.save_preset,
            self.update_preset,
            self.queue,
            self.manage_batches,
        )
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self._request_preview)
        for combo in (
            self.overlay_language,
            self.layout_profile,
            self.aspect,
            self.position,
            self.mode,
            self.fps,
            self.interval,
            self.background,
        ):
            combo.currentIndexChanged.connect(self._schedule_preview)
        self.seconds.valueChanged.connect(self._schedule_preview)
        self.flip_vertical.toggled.connect(self._schedule_preview)
        self.flip_lateral.toggled.connect(self._schedule_preview)
        self.smoothing.currentIndexChanged.connect(self._smoothing_changed)
        self._refresh_presets()
        self._schedule_preview()

    def _refresh_presets(self, select: str | None = None) -> None:
        try:
            self.saved = self.store.presets()
            self.preset_selector.clear()
            items(self.preset_selector, [tr("Choose a saved preset…")])
            items(self.preset_selector, [preset.name for preset in self.saved])
            if select is not None:
                self.preset_selector.setCurrentText(select)
        except ExportStoreError as error:
            record_error("Export configuration", error)
            bind(self.status, tr(str(error)), "text")

    def _preset(self, name: str) -> SavedPreset:
        mode = ("markers", "selection", "entire")[self.interval.currentIndex()]
        return make_preset(
            name,
            self._settings(),
            self.smoothing.currentIndex() * 2 + 1,
            "selection" if mode == "selection" else "entire" if mode == "entire" else "markers",
            self.analysis.configuration,
        )

    @Slot()
    def _save_preset(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("Save export preset"), tr("Preset name"))
        if not accepted:
            return
        try:
            preset = self._preset(name)
            self.store.save_preset(preset)
            self._refresh_presets(preset.name)
            bind(self.status, tr("Saved preset: {0}", preset.name), "text")
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _update_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            bind(self.status, tr("Choose a saved preset to update"), "text")
            return
        try:
            preset = self._preset(self.saved[index].name)
            self.store.save_preset(preset, overwrite=True)
            self._refresh_presets(preset.name)
            bind(
                self.status,
                tr("Preset updated. Existing saved batch snapshots are unchanged."),
                "text",
            )
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _load_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            bind(self.status, tr("Choose a saved preset first"), "text")
            return
        preset = self.saved[index]
        settings = preset.settings
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
        self.overlay_language.setCurrentIndex(LANGUAGE_CHOICES.index(settings.language))
        self.aspect.setCurrentIndex(0 if settings.aspect is VideoAspect.LANDSCAPE else 1)
        self.layout_profile.setCurrentIndex(
            next(i for i, (key, _) in enumerate(PROFILES) if key == settings.layout),
        )
        plugin = registry.PLUGINS[settings.layout]
        positions = (
            plugin.landscape if settings.aspect is VideoAspect.LANDSCAPE else plugin.portrait
        )
        self.position.setCurrentIndex(
            self.position.findData((settings.position or positions.default).value),
        )
        self.mode.setCurrentIndex(0 if settings.output == VideoOutput.TRANSPARENT else 1)
        if self.fps.findText(settings.fps_label) < 0:
            self.fps.addItem(settings.fps_label, settings.fps)
        self.fps.setCurrentText(settings.fps_label)
        self.seconds.setValue(settings.window_seconds)
        self.smoothing.setCurrentIndex(preset.smoothing_window // 2)
        self.flip_vertical.setChecked(settings.invert_vertical)
        self.flip_lateral.setChecked(False)
        self.gpu.setChecked(settings.prefer_gpu)
        self.interval.setCurrentIndex(("markers", "selection", "entire").index(preset.range_mode))
        self._schedule_preview()
        bind(self.status, tr("Loaded preset: {0}", preset.name), "text")

    @Slot(int)
    def _smoothing_changed(self, index: int) -> None:
        self.data = self.data.with_smoothing(index * 2 + 1)
        assert self.data.analysis is not None
        self.analysis = self.data.analysis
        bind(self.smoothing, self.data.smoothing_text, "toolTip")
        self._schedule_preview()

    @Slot()
    def _queue(self) -> None:
        try:
            names = tuple(batch.name for batch in self.store.batches())
            name, accepted = QInputDialog.getItem(
                self,
                tr("Add to saved batch"),
                tr("Choose an existing batch or enter a new name"),
                names,
                0,
                True,
            )
            if not accepted:
                return
            preset_name = (
                self.preset_selector.currentText()
                if self.preset_selector.currentIndex() > 0
                else self.layout_profile.currentText()
            )
            first, last = self._bounds()
            job = make_job(self.analysis, self._preset(preset_name), first=first, last=last)
            if name.strip() not in names:
                name = self.store.create_batch(name).name
            self.store.append_jobs(name, (job,))
            bind(
                self.status,
                tr("Saved this recording/preset in batch: {0}. No video was rendered.", name),
                "text",
            )
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _manage_batches(self) -> None:
        from .batches import BatchDialog

        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.raise_()
            return
        self.batch_window = BatchDialog(self.store, self)
        self.batch_window.show()

    def _close_batches(self) -> bool:
        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.close()
            return not self.batch_window.isVisible()
        return True

    def _choose_profile(self, index: int, _checked: bool = False) -> None:
        self.layout_profile.setCurrentIndex(index)

    def _settings(self) -> ExportSettings:
        return ExportSettings(
            language=LANGUAGE_CHOICES[self.overlay_language.currentIndex()],
            aspect=VideoAspect.LANDSCAPE
            if self.aspect.currentIndex() == 0
            else VideoAspect.PORTRAIT,
            fps=cast(FrameRate, self.fps.currentData()),
            window_seconds=float(self.seconds.value()),
            output=VideoOutput.TRANSPARENT if self.mode.currentIndex() == 0 else VideoOutput.OPAQUE,
            invert_vertical=self.flip_vertical.isChecked(),
            invert_lateral=self.flip_lateral.isChecked(),
            prefer_gpu=self.gpu.isChecked(),
            layout=PROFILES[self.layout_profile.currentIndex()][0],
            position=LayoutPosition(self.position.currentData()),
        )

    def _bounds(self) -> tuple[int, int]:
        return (self.analysis.ride_bounds, (self.first, self.last), (0, self.data.count - 1))[
            self.interval.currentIndex()
        ]

    @Slot()
    def _schedule_preview(self) -> None:
        settings = self._settings()
        for key, plugin in registry.PLUGINS.items():
            positions = (
                plugin.landscape if settings.aspect is VideoAspect.LANDSCAPE else plugin.portrait
            )
            self.preview_positions[key] = positions.select(
                settings.position,
                self.preview_positions.get(key),
            )
        self._update_size_estimate()
        self.preview_revision += 1
        self.preview_result = None
        self.next.setEnabled(False)
        self.start.setEnabled(False)
        bind(self.preview_note, tr("Updating all five previews…"), "text")
        self.preview_timer.start()

    @Slot()
    def _request_preview(self) -> None:
        if self.closing or self.preview_worker is not None or self.preview_result is not None:
            return
        self.preview_timer.stop()
        first, last = self._bounds()
        worker = PreviewWorker(
            self.preview_revision,
            self.analysis,
            self._settings(),
            first,
            last,
            self.current_sample,
            PreviewBackground(self.background.currentData()),
            self.preview_positions,
        )
        worker.signals.ready.connect(self._preview_ready)
        worker.signals.failed.connect(self._preview_failed)
        self.preview_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(int, object)
    def _preview_ready(self, revision: int, result: object) -> None:
        self.preview_worker = None
        if self.closing:
            return
        if revision != self.preview_revision:
            self._request_preview()
            return
        if not isinstance(result, ExportPreview):
            return
        self.preview_result = result
        selected = self.layout_profile.currentIndex()
        for index, profile in enumerate(result.profiles):
            self.profile_buttons[index].setIcon(QIcon(_pixmap(profile.image)))
            self.profile_buttons[index].setChecked(index == selected)
        self.preview_view.show_image(result.profiles[selected].image)
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

    @Slot(int, str)
    def _preview_failed(self, revision: int, message: str) -> None:
        self.preview_worker = None
        if self.closing:
            return
        if revision != self.preview_revision:
            self._request_preview()
            return
        bind(self.preview_note, tr("Preview failed: {0}", message), "text")

    def _update_summary(self) -> None:
        self._update_size_estimate()
        first, last = self._bounds()
        width, height = self._settings().dimensions
        values = {
            "layout": self.layout_profile.currentText(),
            "output": self.mode.currentText(),
            "resolution": f"{width}×{height}",
            "fps": self.fps.currentText(),
            "range": f"{self.data.replay_text(first)}–{self.data.replay_text(last)}",
            "samples": tr("{0:,}–{1:,} (inclusive)", first, last),
            "smoothing": self.data.smoothing_text,
            "window": tr("{0} s", self.seconds.value()),
        }
        for key, value in values.items():
            bind(self.review_fields[key], value)

    def _update_preview_caption(self) -> None:
        result = self.preview_result
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
        low, high = estimate_size_bytes(self._settings(), last - first + 1, self.data.sample_rate)
        bind(
            self.size_estimate,
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
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "preview_timer"):
            self._update_summary()

    @Slot()
    def _review(self) -> None:
        if self.preview_result is None:
            return
        self._update_summary()
        self.pages.setCurrentIndex(1)
        bind(self.step_label, tr("2 · Review export · {0}", self.data.title), "text")
        for widget in (self.presets_widget, self.gallery):
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
        for widget in (self.presets_widget, self.gallery):
            widget.show()
        self.pages.setMaximumWidth(500)
        self._update_preview_caption()
        bind(self.step_label, tr("1 · Set up export · {0}", self.data.title), "text")
        self.back.setVisible(False)
        self.next.setVisible(True)
        self.start.setVisible(False)

    @Slot(int)
    def _layout_changed(self, index: int) -> None:
        self._refresh_positions()
        if PROFILES[index][0] == ExportLayout.HUD:
            self.seconds.setValue(30.0)
        self.flip_vertical.setChecked(True)
        self.flip_lateral.setChecked(False)
        self.flip_vertical.setEnabled(True)
        self.flip_lateral.setEnabled(False)

    @Slot()
    def _refresh_positions(self) -> None:
        previous = self.position.currentData()
        plugin = registry.PLUGINS[PROFILES[self.layout_profile.currentIndex()][0]]
        positions = plugin.landscape if self.aspect.currentIndex() == 0 else plugin.portrait
        labels = {
            LayoutPosition.FULL_SCREEN: tr("Full screen"),
            LayoutPosition.TOP: tr("Top"),
            LayoutPosition.BOTTOM: tr("Bottom"),
            LayoutPosition.LEFT: tr("Left"),
            LayoutPosition.RIGHT: tr("Right"),
            LayoutPosition.TOP_LEFT: tr("Top left"),
            LayoutPosition.TOP_RIGHT: tr("Top right"),
            LayoutPosition.BOTTOM_LEFT: tr("Bottom left"),
            LayoutPosition.BOTTOM_RIGHT: tr("Bottom right"),
        }
        with QSignalBlocker(self.position):
            self.position.clear()
            items(self.position, [labels[position] for position in positions.regions])
            for index, position in enumerate(positions.regions):
                self.position.setItemData(index, position.value)
            selected = positions.select(
                LayoutPosition(previous) if previous is not None else None,
                self.preview_positions.get(plugin.key),
            )
            self.position.setCurrentIndex(self.position.findData(selected.value))

    @Slot()
    def _browse(self) -> None:
        configured = self.encoder.text().strip()
        directory = ""
        if configured:
            candidate = Path(configured).expanduser()
            directory = str((candidate if candidate.is_dir() else candidate.parent).resolve())
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose FFmpeg"),
            directory,
            tr("All files (*)"),
        )
        if path:
            bind(self.encoder, path, "text")

    @Slot()
    def _start(self) -> None:
        if self.worker is not None or self.pages.currentIndex() != 1 or self.preview_result is None:
            return
        try:
            settings = self._settings()
            first, last = self._bounds()
            timeline = prepare_export(self.analysis, settings, first, last)
            encoder = find_ffmpeg(Path(self.encoder.text()) if self.encoder.text() else None)
        except (ValueError, OSError) as error:
            record_error("Export preparation", error)
            bind(self.status, tr(str(error)), "text")
            return
        suffix = ".mov" if settings.output == VideoOutput.TRANSPARENT else ".mp4"
        source_path = self.data.source.recording.source.provenance.path
        stem = source_path.stem if source_path is not None else "ride-forces"
        name = f"{stem} - {self.layout_profile.currentText()}{suffix}"
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

    @Slot(str)
    def _finished(self, message: str) -> None:
        bind(self.eta, "")
        self.worker = None
        for control in self.controls:
            control.setEnabled(True)
        self.flip_vertical.setEnabled(True)
        self.flip_lateral.setEnabled(False)
        self.start.setEnabled(True)
        self.back.setEnabled(True)
        bind(self.cancel, tr("Close"), "text")
        bind(self.status, message, "text")

    @Slot()
    def _cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancelled.set()
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
        if not self._close_batches():
            event.ignore()
            return
        if self.worker is not None:
            self._cancel()
            bind(self.status, tr("Cancelling export; close after completion."), "text")
            event.ignore()
        else:
            self.closing = True
            self.preview_timer.stop()
            super().closeEvent(event)

    def reject(self) -> None:
        """Close the dialog through its cancellation and worker-cleanup path.

        Returns:
            None.
        """
        if not self._close_batches():
            return
        if self.worker is not None:
            self._cancel()
            return
        self.closing = True
        self.preview_timer.stop()
        super().reject()
