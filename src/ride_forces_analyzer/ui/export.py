"""Export dialog and Qt worker transport; rendering/encoding stay in their subsystem."""

from ride_forces_analyzer.i18n import get_language, tr
from .translation import bind, items

# cspell:words pixmap Deutsch

from pathlib import Path
from functools import partial
from threading import Event

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot, QSize, QTimer
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

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import ExportCancelled, export_video, find_ffmpeg
from ride_forces_analyzer.rendering.model import (
    ExportSettings,
    ExportTimeline,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.rendering.preview import ExportPreview, build_previews
from ride_forces_analyzer.rendering.batches import make_job
from ride_forces_analyzer.storage.export_models import SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import (
    ExportStore,
    ExportStoreError,
    default_database_path,
)


class PreviewSignals(QObject):
    ready = Signal(int, object)
    failed = Signal(int, str)


class PreviewWorker(QRunnable):
    def __init__(
        self,
        revision: int,
        data: ExplorerData,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: str,
    ) -> None:
        super().__init__()
        self.revision, self.data, self.settings = revision, data, settings
        self.first, self.last, self.sample, self.background = first, last, sample, background
        self.signals = PreviewSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = build_previews(
                self.data,
                self.settings,
                self.first,
                self.last,
                self.sample,
                "light"
                if self.background == "light"
                else "dark"
                if self.background == "dark"
                else "checker",
            )
        except Exception as error:
            self.signals.failed.emit(self.revision, str(error))
        else:
            self.signals.ready.emit(self.revision, result)


def _pixmap(image: Image.Image) -> QPixmap:
    raw = image.tobytes()
    return QPixmap.fromImage(
        QImage(raw, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy(),
    )


class PreviewView(QLabel):
    def __init__(self) -> None:
        super().__init__(tr("Preparing preview…"))
        self.source = QPixmap()
        self.setMinimumSize(440, 248)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_image(self, image: Image.Image) -> None:
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
        super().resizeEvent(event)
        self._fit()


class ExportSignals(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)
    status = Signal(str)


class ExportWorker(QRunnable):
    def __init__(self, timeline: ExportTimeline, destination: Path, ffmpeg: Path) -> None:
        super().__init__()
        self.timeline = timeline
        self.destination = destination
        self.ffmpeg = ffmpeg
        self.cancelled = Event()
        self.signals = ExportSignals()

    @Slot()
    def run(self) -> None:
        try:
            path = export_video(
                self.timeline,
                self.destination,
                ffmpeg=self.ffmpeg,
                cancelled=self.cancelled,
                progress=self.signals.progress.emit,
                status=self.signals.status.emit,
            )
        except ExportCancelled:
            self.signals.finished.emit(tr("Export cancelled. No incomplete output was kept."))
        except Exception as error:
            self.signals.failed.emit(tr("Export failed: {0}", error))
        else:
            self.signals.finished.emit(tr("Saved {0}", path))


class ExportDialog(QDialog):
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
        super().__init__(parent)
        bind(self, tr("Export assistant · {0}", data.title), "windowTitle")
        self.resize(1240, 820)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.data, self.first, self.last = data, first, last
        self.store = store if store is not None else ExportStore(default_database_path())
        self.saved: tuple[SavedPreset, ...] = ()
        self.batch_window: QDialog | None = None
        self.current_sample = (
            data.source.recording.indices.start if current_sample is None else current_sample
        )
        self.worker: ExportWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self.preview_result: ExportPreview | None = None
        self.preview_revision = 0
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
        self.step_label = bind(QLabel(), tr("1 · Choose layout and check the current graph sample"))
        layout.addWidget(self.step_label)
        intro = bind(
            QLabel(),
            tr(
                "{0}\nOne landscape or portrait video · selectable overlay layout\nVertical · Lateral · Longitudinal · Orientation",
                data.title,
            ),
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(intro)
        presets_row = QHBoxLayout()
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
        for preset_button in (
            self.load_preset,
            self.save_preset,
            self.update_preset,
            self.queue,
            self.manage_batches,
        ):
            presets_row.addWidget(preset_button)
        layout.addLayout(presets_row)
        self.profile_buttons: list[QToolButton] = []
        gallery = QScrollArea()
        gallery.setWidgetResizable(True)
        gallery.setFixedHeight(157)
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        for index, (_, title) in enumerate(PROFILES):
            button = QToolButton()
            bind(button, tr(title), "text")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(184, 104))
            button.setMinimumSize(198, 132)
            button.clicked.connect(partial(self._choose_profile, index))
            strip_layout.addWidget(button)
            self.profile_buttons.append(button)
        gallery.setWidget(strip)
        layout.addWidget(gallery)
        self.pages = QStackedWidget()
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        form = QFormLayout()
        self.layout_profile = QComboBox()
        items(self.layout_profile, [tr(title) for _, title in PROFILES])
        self.layout_profile.currentIndexChanged.connect(self._layout_changed)
        form.addRow(bind(QLabel(), tr("Layout profile")), self.layout_profile)
        self.aspect = QComboBox()
        items(self.aspect, [tr("Landscape · 16:9 · 3840×2160"), tr("Portrait · 9:16 · 2160×3840")])
        form.addRow(bind(QLabel(), tr("Video format")), self.aspect)
        self.overlay_language = QComboBox()
        items(self.overlay_language, ["English", "Deutsch"])
        self.overlay_language.setCurrentIndex(1 if get_language() == "de" else 0)
        form.addRow(bind(QLabel(), tr("Overlay language")), self.overlay_language)
        self.mode = QComboBox()
        items(
            self.mode,
            [tr("Transparent overlay · ProRes 4444 MOV"), tr("Opaque video · H.264 MP4")],
        )
        form.addRow(bind(QLabel(), tr("Output")), self.mode)
        self.fps = QComboBox()
        items(self.fps, ["24", "25", "30", "50", "60"])
        self.fps.setCurrentText("50")
        form.addRow(bind(QLabel(), tr("Video frame rate")), self.fps)
        self.interval = QComboBox()
        items(
            self.interval,
            [tr("Start/end markers (default)"), tr("Current selection"), tr("Entire recording")],
        )
        form.addRow(bind(QLabel(), tr("Range")), self.interval)
        self.seconds = QDoubleSpinBox()
        self.seconds.setDecimals(3)
        self.seconds.setRange(1, 60)
        self.seconds.setValue(12)
        bind(self.seconds, " s", "suffix")
        form.addRow(bind(QLabel(), tr("Visible time window")), self.seconds)
        self.smoothing = QComboBox()
        items(self.smoothing, [tr("{0} samples", count) for count in range(1, 52, 2)])
        self.smoothing.setCurrentIndex(
            (data.reference.smoothing_window if data.reference else 11) // 2,
        )
        form.addRow(bind(QLabel(), tr("Smoothing")), self.smoothing)
        self.flip_vertical = bind(
            QCheckBox(),
            tr("Positive values below zero, as in the reference"),
        )
        self.flip_vertical.setChecked(True)
        form.addRow(bind(QLabel(), tr("Vertical")), self.flip_vertical)
        self.flip_lateral = bind(QCheckBox(), tr("+ Right / − Left"))
        self.flip_lateral.setChecked(False)
        self.flip_lateral.setEnabled(False)
        form.addRow(bind(QLabel(), tr("Lateral")), self.flip_lateral)
        self.gpu = bind(QCheckBox(), tr("Use NVIDIA GPU when supported; CPU fallback otherwise"))
        self.gpu.setChecked(True)
        form.addRow(bind(QLabel(), tr("Acceleration")), self.gpu)
        self.encoder = QLineEdit()
        try:
            bind(self.encoder, str(find_ffmpeg()), "text")
        except ValueError:
            self.encoder.setPlaceholderText(tr("Choose installed ffmpeg.exe"))
        browse = bind(QPushButton(), tr("Browse…"))
        browse.clicked.connect(self._browse)
        encoder_row = QHBoxLayout()
        encoder_row.addWidget(self.encoder)
        encoder_row.addWidget(browse)
        form.addRow("FFmpeg", encoder_row)
        settings_layout.addLayout(form)
        settings_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings_page)
        self.pages.addWidget(scroll)
        review_page = QWidget()
        review_layout = QVBoxLayout(review_page)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        review_layout.addWidget(self.summary)
        review_layout.addStretch()
        self.pages.addWidget(review_page)
        self.pages.setMaximumWidth(500)
        body = QHBoxLayout()
        body.addWidget(self.pages, 2)
        right = QVBoxLayout()
        self.preview_caption = QLabel()
        self.preview_caption.setMinimumHeight(44)
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
        right.addWidget(self.background)
        self.preview_note = QLabel()
        self.preview_note.setWordWrap(True)
        self.preview_note.setTextFormat(Qt.TextFormat.PlainText)
        right.addWidget(self.preview_note)
        body.addLayout(right, 3)
        layout.addLayout(body, 1)
        self.context = bind(
            QLabel(),
            tr(
                "Calibrated forces · {0}\nOrientation uses recorded gravity; absent values remain gaps.\nAlign the exported clip with your Onride video in Resolve.",
                data.smoothing_text,
            ),
        )
        self.context.setWordWrap(True)
        layout.addWidget(self.context)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.status = bind(QLabel(), tr("Ready. Original recording remains unchanged."))
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
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
            bind(self.status, tr(str(error)), "text")

    def _preset(self, name: str) -> SavedPreset:
        mode = ("markers", "selection", "entire")[self.interval.currentIndex()]
        return make_preset(
            name,
            self._settings(),
            self.smoothing.currentIndex() * 2 + 1,
            "selection" if mode == "selection" else "entire" if mode == "entire" else "markers",
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
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _load_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            bind(self.status, tr("Choose a saved preset first"), "text")
            return
        preset = self.saved[index]
        settings = preset.settings
        self.overlay_language.setCurrentIndex(1 if settings.language == "de" else 0)
        self.aspect.setCurrentIndex(0 if settings.aspect == "landscape" else 1)
        self.layout_profile.setCurrentIndex(
            next(i for i, (key, _) in enumerate(PROFILES) if key == settings.layout),
        )
        self.mode.setCurrentIndex(0 if settings.output == "transparent" else 1)
        if self.fps.findText(str(settings.fps)) < 0:
            self.fps.addItem(str(settings.fps))
        self.fps.setCurrentText(str(settings.fps))
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
        bind(
            self.context,
            tr(
                "Calibrated forces · {0}\nAlign the exported clip with your Onride video in Resolve.",
                self.data.smoothing_text,
            ),
            "text",
        )
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
            job = make_job(self.data, self._preset(preset_name), first=first, last=last)
            if name.strip() not in names:
                name = self.store.create_batch(name).name
            self.store.append_jobs(name, (job,))
            bind(
                self.status,
                tr("Saved this recording/preset in batch: {0}. No video was rendered.", name),
                "text",
            )
        except (ValueError, ExportStoreError) as error:
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
            language="de" if self.overlay_language.currentIndex() == 1 else "en",
            aspect="landscape" if self.aspect.currentIndex() == 0 else "portrait",
            fps=int(self.fps.currentText()),
            window_seconds=float(self.seconds.value()),
            output="transparent" if self.mode.currentIndex() == 0 else "opaque",
            invert_vertical=self.flip_vertical.isChecked(),
            invert_lateral=self.flip_lateral.isChecked(),
            prefer_gpu=self.gpu.isChecked(),
            layout=PROFILES[self.layout_profile.currentIndex()][0],
        )

    def _bounds(self) -> tuple[int, int]:
        indices = self.data.source.recording.indices
        return ((indices.start, indices.end), (self.first, self.last), (0, self.data.count - 1))[
            self.interval.currentIndex()
        ]

    @Slot()
    def _schedule_preview(self) -> None:
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
            self.data,
            self._settings(),
            first,
            last,
            self.current_sample,
            ("checker", "light", "dark")[self.background.currentIndex()],
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
        bind(
            self.preview_caption,
            tr(
                "{0} · Graph sample {1:,} · Replay {2}\n{3}",
                tr(result.profiles[selected].title),
                result.sample,
                self.data.replay_text(result.sample),
                self.data.smoothing_text,
            ),
            "text",
        )
        bind(
            self.preview_note,
            tr(
                "Graph sample is OUTSIDE the export interval. Preview shows that exact sample with full-recording context; it is not part of this export.",
            )
            if result.outside_range
            else tr(
                "Exact selected graph sample · production renderer · preview background is not exported.",
            ),
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
        first, last = self._bounds()
        width, height = self._settings().dimensions
        bind(
            self.summary,
            tr(
                "{0}\n\n{1}\n{2}\n{3}×{4} · {5} fps\n\nRange: {6}–{7}\nSamples {8:,}–{9:,} (inclusive)\n\n{10}\nVisible context: {11} s\n\nPreview: graph sample {12:,}\nReplay {13}\n\nThe full clip is rendered only after choosing Export video and a destination.",
                self.data.title,
                self.layout_profile.currentText(),
                self.mode.currentText(),
                width,
                height,
                self.fps.currentText(),
                self.data.replay_text(first),
                self.data.replay_text(last),
                first,
                last,
                self.data.smoothing_text,
                self.seconds.value(),
                self.current_sample,
                self.data.replay_text(self.current_sample),
            ),
            "text",
        )

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "preview_timer"):
            self._update_summary()

    @Slot()
    def _review(self) -> None:
        if self.preview_result is None:
            return
        self._update_summary()
        self.pages.setCurrentIndex(1)
        bind(self.step_label, tr("2 · Review the preview and export"), "text")
        self.back.setVisible(True)
        self.next.setVisible(False)
        self.start.setVisible(True)

    @Slot()
    def _back(self) -> None:
        self.pages.setCurrentIndex(0)
        bind(self.step_label, tr("1 · Choose layout and check the current graph sample"), "text")
        self.back.setVisible(False)
        self.next.setVisible(True)
        self.start.setVisible(False)

    @Slot(int)
    def _layout_changed(self, index: int) -> None:
        self.flip_vertical.setChecked(True)
        self.flip_lateral.setChecked(False)
        self.flip_vertical.setEnabled(True)
        self.flip_lateral.setEnabled(False)

    @Slot()
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose FFmpeg"),
            "",
            tr("FFmpeg (ffmpeg.exe);;All files (*)"),
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
            timeline = prepare_export(self.data, settings, first, last)
            encoder = find_ffmpeg(Path(self.encoder.text()) if self.encoder.text() else None)
        except (ValueError, OSError) as error:
            bind(self.status, tr(str(error)), "text")
            return
        suffix = ".mov" if settings.output == "transparent" else ".mp4"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save 4K video"),
            f"ride-forces-4k{suffix}",
            tr("Video (*{0})", suffix),
        )
        if not filename:
            return
        worker = ExportWorker(timeline, Path(filename), encoder)
        worker.signals.progress.connect(self._progress)
        worker.signals.status.connect(self._status_message)
        worker.signals.finished.connect(self._finished)
        worker.signals.failed.connect(self._finished)
        self.worker = worker
        self.progress.setValue(0)
        for control in self.controls:
            control.setEnabled(False)
        self.start.setEnabled(False)
        self.back.setEnabled(False)
        bind(self.cancel, tr("Cancel export"), "text")
        bind(self.status, tr("Exporting 4K video…"), "text")
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _status_message(self, message: str) -> None:
        bind(self.status, tr(message))

    @Slot(int, int)
    def _progress(self, current: int, total: int) -> None:
        self.progress.setValue(current * 100 // total)
        if current == total:
            bind(self.status, tr("Finalizing video…"), "text")

    @Slot(str)
    def _finished(self, message: str) -> None:
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
            bind(self.status, tr("Cancelling export…"), "text")
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._close_batches():
            event.ignore()
            return
        if self.worker is not None:
            self.worker.cancelled.set()
            bind(self.status, tr("Cancelling export; close after completion."), "text")
            event.ignore()
        else:
            self.closing = True
            self.preview_timer.stop()
            super().closeEvent(event)

    def reject(self) -> None:
        if not self._close_batches():
            return
        if self.worker is not None:
            self._cancel()
            return
        self.closing = True
        self.preview_timer.stop()
        super().reject()
