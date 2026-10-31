"""Saved batch editor and Qt transport for sequential offline exports.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.ui.presentation.translation import bind, button_text, items, headers

from pathlib import Path
from threading import Event

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from ride_forces_analyzer.rendering.model import PROFILES, VideoAspect, ExportExtent
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.exports.batches import BatchReport, build_jobs, run_batches
from ride_forces_analyzer.ui.presentation.icons import icon_with_plus
from ride_forces_analyzer.rendering.encoding import find_ffmpeg
from ride_forces_analyzer.rendering.progress import ExportProgress
from ride_forces_analyzer.ui.exports.progress import show_export_progress
from ride_forces_analyzer.ui.presentation.taskbar import taskbar_progress
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset, RangeMode
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError
from ride_forces_analyzer.storage.preferences import Preferences


class BatchSignals(QObject):
    """Batch signals contract and owned data.

    Attributes:
        finished: Qt signal for finished notifications.
        failed: Qt signal for failed notifications.
        progress: Qt signal for progress notifications.
        overall_progress: Qt signal carrying completed and planned queue frame counts.
    """

    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, object, str)
    overall_progress = Signal(int, int)


class BuildWorker(QRunnable):
    """Build worker contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        paths: Input paths to process.
        presets: Selected immutable export presets used to build jobs.
        mode: Selected operation mode.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        name: str,
        paths: tuple[Path, ...],
        presets: tuple[SavedPreset, ...],
        mode: RangeMode,
    ) -> None:
        """Initialize build worker and its owned state.

        Args:
            name: Display name or identifier used to select the requested item.
            paths: Input paths to process.
            presets: Selected immutable export presets used to build jobs.
            mode: Selected operation mode.

        Returns:
            None.
        """
        super().__init__()
        self.name, self.paths, self.presets = name, paths, presets
        self.mode: RangeMode = mode
        self.signals = BatchSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            result = SavedBatch(
                name=self.name,
                jobs=build_jobs(self.paths, self.presets, self.mode),
                schema_version=1,
            )
        except Exception as error:
            record_error("Batch preparation", error)
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(result)


class BatchWorker(QRunnable):
    """Batch worker contract and owned data.

    Attributes:
        batches: Selected saved batches in execution order.
        directory: Directory used by the operation.
        ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
        render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
            availability.
        cancelled: Event used to request cancellation without publishing partial output.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        batches: tuple[SavedBatch, ...],
        directory: Path,
        ffmpeg: Path,
        *,
        render_jobs: int = 1,
    ) -> None:
        """Initialize batch worker and its owned state.

        Args:
            batches: Selected saved batches in execution order.
            directory: Directory used by the operation.
            ffmpeg: Explicit encoder executable; None permits the documented discovery policy.
            render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
                availability.

        Returns:
            None.
        """
        super().__init__()
        self.batches, self.directory, self.ffmpeg = batches, directory, ffmpeg
        self.render_jobs = render_jobs
        self.cancelled = Event()
        self.signals = BatchSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            report = run_batches(
                self.batches,
                self.directory,
                ffmpeg=self.ffmpeg,
                cancelled=self.cancelled,
                progress=self.signals.progress.emit,
                overall_progress=self.signals.overall_progress.emit,
                render_jobs=self.render_jobs,
            )
        except Exception as error:
            record_error("Batch execution", error)
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(report)


class BatchDialog(QDialog):
    """Batch dialog contract and owned data.

    Attributes:
        store: Local export-definition repository used by this view or service.
        worker: Current background worker, or None when no task is active.
        builder: Background worker preparing the batch queue.
        closing: Whether shutdown has started and late results must be ignored.
        last_report: Result of the most recently completed batch.
        batch_list: List of saved batch definitions.
        table: Table control containing the displayed rows.
        presets: Selected immutable export presets used to build jobs.
        range_mode: Choice control for range mode.
        new: Button for new.
        add: Button for add.
        remove: Button for remove.
        delete: Button for delete.
        encoder: Text input for encoder.
        browse: Button for browse.
        current_job: Label displaying current job.
        progress: Overall equally weighted job progress.
        export_progress: Submitted-frame progress of the current video.
        eta: Remaining-frame estimate for the current video.
        status: Label displaying status.
        run_selected: Button for run selected.
        run_all: Button for run all.
        close_button: Button for close button.
        controls: Controls enabled or disabled together during background processing.
    """

    def __init__(self, store: ExportStore, parent: QWidget) -> None:
        """Initialize batch dialog and its owned state.

        Args:
            store: Local export-definition storage.
            parent: Qt parent that owns this object's lifetime.

        Returns:
            None.
        """
        super().__init__(parent)
        self._taskbar = taskbar_progress(self)
        self.store = store
        self.worker: BatchWorker | None = None
        self.builder: BuildWorker | None = None
        self.closing = False
        self.last_report: BatchReport | None = None
        bind(self, tr("Saved export batches"), "windowTitle")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(1160, 720)
        root = QVBoxLayout(self)
        heading = bind(QLabel(), tr("Saved batches · one run for multiple rides and presets"))
        heading.setObjectName("recordingHeading")
        root.addWidget(heading)
        root.addWidget(
            bind(
                QLabel(),
                tr(
                    "Select a batch to edit it. Select several batches, or run all saved batches in one queue.",
                ),
            ),
        )
        row = QHBoxLayout()
        self.batch_list = QListWidget()
        self.batch_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.batch_list.setMaximumWidth(260)
        self.batch_list.currentTextChanged.connect(self._show_batch)
        row.addWidget(self.batch_list)
        right = QVBoxLayout()
        self.table = QTableWidget(0, 5)
        headers(
            self.table,
            [
                tr("Ride"),
                tr("Preset / layout"),
                tr("Range (samples)"),
                tr("Smoothing"),
                tr("Recording"),
            ],
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right.addWidget(self.table)
        self.presets = QListWidget()
        self.presets.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.presets.setMaximumHeight(115)
        right.addWidget(
            bind(
                QLabel(),
                tr(
                    "Choose one or more saved presets, then add recordings (every recording × every selected preset).",
                ),
            ),
        )
        right.addWidget(self.presets)
        self.range_mode = QComboBox()
        items(self.range_mode, [tr("Start/end markers for each recording"), tr("Entire recording")])
        right.addWidget(self.range_mode)
        row.addLayout(right, 1)
        root.addLayout(row, 1)
        actions = QHBoxLayout()
        self.new = button_text(QPushButton(), tr("New batch…"))
        self.new.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder),
        )
        self.new.clicked.connect(self._new)
        self.add = button_text(QPushButton(), tr("Add recordings × presets…"))
        self.add.setIcon(
            icon_with_plus(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)),
        )
        self.add.clicked.connect(self._add)
        self.remove = button_text(QPushButton(), tr("Remove selected jobs"))
        self.remove.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton),
        )
        self.remove.clicked.connect(self._remove)
        self.delete = button_text(QPushButton(), tr("Delete empty batch"))
        self.delete.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
        )
        self.delete.clicked.connect(self._delete)
        for button in (self.new, self.add, self.remove, self.delete):
            actions.addWidget(button)
        root.addLayout(actions)
        encoder_row = QHBoxLayout()
        encoder_row.addWidget(bind(QLabel(), "FFmpeg"))
        self.encoder = QLineEdit()
        try:
            bind(self.encoder, str(find_ffmpeg()), "text")
        except ValueError:
            self.encoder.setPlaceholderText(tr("Choose FFmpeg executable"))
        encoder_row.addWidget(self.encoder)
        self.browse = button_text(
            QPushButton(),
            tr("Browse…"),
            tooltip=tr("Choose FFmpeg executable"),
            caption=tr("&Browse…"),
        )
        self.browse.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
        )
        self.browse.clicked.connect(self._browse)
        encoder_row.addWidget(self.browse)
        root.addLayout(encoder_row)
        self.current_job = bind(QLabel(), tr("No export running"))
        self.current_job.setWordWrap(True)
        self.current_job.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self.current_job)
        root.addWidget(bind(QLabel(), tr("Overall batch")))
        self.progress = QProgressBar()
        root.addWidget(self.progress)
        root.addWidget(bind(QLabel(), tr("Current export")))
        self.export_progress = QProgressBar()
        root.addWidget(self.export_progress)
        self.eta = QLabel()
        self.eta.setWordWrap(True)
        root.addWidget(self.eta)
        self.status = bind(
            QLabel(),
            tr(
                "Presets and batch definitions are saved locally. Completed videos are retained on cancellation.",
            ),
        )
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        bind(self.status, str(store.path), "toolTip")
        root.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.run_selected = button_text(QPushButton(), tr("Run selected…"))
        self.run_selected.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
        )
        bind(
            self.run_selected,
            tr("Export all jobs in the selected batches. Job-row selection is ignored."),
            "toolTip",
        )
        self.run_selected.clicked.connect(self._run_selected)
        self.run_all = button_text(QPushButton(), tr("Run all…"))
        self.run_all.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward),
        )
        bind(
            self.run_all,
            tr("Export all jobs in all saved batches, regardless of batch or job-row selection."),
            "toolTip",
        )
        self.run_all.setObjectName("Primary")
        self.run_all.clicked.connect(self._run_all)
        self.close_button = button_text(QPushButton(), tr("Close"))
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
        )
        self.close_button.clicked.connect(self._close_or_cancel)
        for button in (self.run_selected, self.run_all, self.close_button):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.controls = (
            self.batch_list,
            self.table,
            self.presets,
            self.range_mode,
            self.new,
            self.add,
            self.remove,
            self.delete,
            self.encoder,
            self.browse,
            self.run_selected,
            self.run_all,
        )
        self.batch_list.itemSelectionChanged.connect(self._update_add_enabled)
        self.presets.itemSelectionChanged.connect(self._update_add_enabled)
        self._update_add_enabled()
        self.refresh()

    @Slot()
    def _update_add_enabled(self) -> None:
        """Enable adding recordings only with an idle batch and preset selection."""
        self.add.setEnabled(
            self.worker is None
            and self.builder is None
            and bool(self.batch_list.selectedItems())
            and bool(self.presets.selectedItems()),
        )

    def refresh(self, select: str | None = None) -> None:
        """Reload the displayed batch definitions from local storage.

        Args:
            select: Saved item name to select after refreshing, or None to retain the current
                choice.

        Returns:
            None.
        """
        try:
            batches, presets = self.store.batches(), self.store.presets()
        except ExportStoreError as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")
            return
        self.batch_list.clear()
        items(self.batch_list, [batch.name for batch in batches])
        self.presets.clear()
        items(self.presets, [preset.name for preset in presets])
        if select is not None:
            matches = self.batch_list.findItems(select, Qt.MatchFlag.MatchExactly)
            if matches:
                self.batch_list.setCurrentItem(matches[0])
        elif self.batch_list.count():
            self.batch_list.setCurrentRow(0)

    @Slot(str)
    def _show_batch(self, name: str) -> None:
        self.table.setRowCount(0)
        if not name:
            return
        try:
            batch = self.store.batch(name)
        except ExportStoreError as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")
            return
        self.table.setRowCount(len(batch.jobs))
        for row, job in enumerate(batch.jobs):
            settings = job.preset.settings
            width, height = resolve_geometry(settings).output_size
            values = (
                job.ride,
                " / ".join(
                    (
                        job.preset.name,
                        tr(dict(PROFILES)[settings.layout]),
                        tr("Portrait" if settings.aspect is VideoAspect.PORTRAIT else "Landscape"),
                        tr(
                            "Content area"
                            if settings.extent is ExportExtent.CONTENT_AREA
                            else "Full frame",
                        ),
                        f"{width}×{height}",
                    ),
                ),
                f"{job.first_sample}–{job.last_sample}",
                tr("{0} samples", job.preset.smoothing_window),
                str(job.recording_path),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        for column in range(self.table.columnCount()):
            self.table.setColumnWidth(column, min(420, self.table.columnWidth(column)))

    def _current_name(self) -> str:
        if self.batch_list.currentRow() < 0:
            raise ValueError(tr("Choose or create a batch first"))
        return self.batch_list.currentItem().text()

    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated or themed controls after a Qt change event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "batch_list"):
            self._show_batch(
                self.batch_list.currentItem().text() if self.batch_list.currentRow() >= 0 else "",
            )

    @Slot()
    def _new(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("New batch"), tr("Batch name"))
        if not accepted:
            return
        try:
            batch = self.store.create_batch(name)
            self.refresh(batch.name)
        except (ValueError, ExportStoreError) as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _add(self) -> None:
        try:
            name = self._current_name()
            selected = {item.text() for item in self.presets.selectedItems()}
            presets = tuple(preset for preset in self.store.presets() if preset.name in selected)
            if not presets:
                bind(self.status, tr("Select at least one preset"), "text")
                return
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                tr("Add recordings"),
                "",
                "Ride Forces (*.forces *.zforces)",
            )
            if not paths:
                return
            worker = BuildWorker(
                name,
                tuple(Path(path) for path in paths),
                presets,
                "markers" if self.range_mode.currentIndex() == 0 else "entire",
            )
            worker.signals.finished.connect(self._built)
            worker.signals.failed.connect(self._failed)
            self.builder = worker
            self._busy(True)
            bind(self.status, tr("Reading originals and preparing the saved queue…"), "text")
            QThreadPool.globalInstance().start(worker)
        except (ValueError, ExportStoreError) as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot(object)
    def _built(self, result: object) -> None:
        self.builder = None
        if self.closing:
            return
        self._busy(False)
        if not isinstance(result, SavedBatch):
            return
        try:
            self.store.append_jobs(result.name, result.jobs)
            self.refresh(result.name)
            bind(
                self.status,
                tr("Saved {0} additional export jobs in {1}.", len(result.jobs), result.name),
                "text",
            )
        except ExportStoreError as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _remove(self) -> None:
        try:
            name = self._current_name()
            rows = tuple(
                sorted({index.row() for index in self.table.selectionModel().selectedRows()}),
            )
            self.store.remove_jobs(name, rows)
            self._show_batch(name)
        except (ValueError, ExportStoreError) as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _delete(self) -> None:
        try:
            name = self._current_name()
            if self.store.batch(name).jobs:
                raise ValueError(tr("Remove the jobs before deleting this batch"))
            self.store.delete_batch(name)
            self.refresh()
        except (ValueError, ExportStoreError) as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("FFmpeg executable"),
            "",
            tr("All files (*)"),
        )
        if path:
            bind(self.encoder, path, "text")

    @Slot()
    def _run_selected(self) -> None:
        self._run(False)

    @Slot()
    def _run_all(self) -> None:
        self._run(True)

    def _run(self, all_batches: bool) -> None:
        if self.worker is not None or self.builder is not None:
            return
        try:
            selected = {item.text() for item in self.batch_list.selectedItems()}
            batches = tuple(
                batch for batch in self.store.batches() if all_batches or batch.name in selected
            )
            if not any(batch.jobs for batch in batches):
                raise ValueError(tr("Choose saved batches that contain export jobs"))
            encoder = find_ffmpeg(Path(self.encoder.text()) if self.encoder.text() else None)
            directory = QFileDialog.getExistingDirectory(self, tr("Choose batch output folder"))
            if not directory:
                return
            worker = BatchWorker(
                batches,
                Path(directory),
                encoder,
                render_jobs=Preferences().render_jobs(),
            )
            worker.signals.progress.connect(self._progress)
            worker.signals.overall_progress.connect(self._overall_progress)
            worker.signals.finished.connect(self._finished)
            worker.signals.failed.connect(self._failed)
            self.worker = worker
            self._taskbar.start()
            self.last_report = None
            self.progress.setValue(0)
            self.export_progress.setValue(0)
            self.export_progress.setFormat("%p%")
            bind(self.eta, "", "text")
            self._busy(True)
            button_text(self.close_button, tr("Cancel remaining exports"))
            self.close_button.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
            )
            QThreadPool.globalInstance().start(worker)
        except (ValueError, ExportStoreError) as error:
            record_error("Batch configuration", error)
            bind(self.status, tr(str(error)), "text")

    def _busy(self, busy: bool) -> None:
        for control in self.controls:
            control.setEnabled(not busy)
        if not busy:
            self._update_add_enabled()

    @Slot(int, int, object, str)
    def _progress(
        self,
        job: int,
        total: int,
        update: ExportProgress | None,
        label: str,
    ) -> None:
        if self.worker is None or self.worker.cancelled.is_set():
            return
        bind(self.current_job, tr("Job {0}/{1}: {2}", job, total, label), "text")
        if update is not None:
            show_export_progress(update, self.export_progress, self.status, self.eta)
        else:
            bind(self.eta, "", "text")

    @Slot(int, int)
    def _overall_progress(self, completed: int, total: int) -> None:
        """Show frame-weighted queue progress in the dialog and taskbar.

        Args:
            completed: Frame budgets settled or submitted so far.
            total: Planned output frames across every selected batch.
        """
        if self.worker is None or self.worker.cancelled.is_set():
            return
        self.progress.setValue(completed * 100 // max(1, total))
        self._taskbar.set_value(self.progress.value())

    @Slot(object)
    def _finished(self, result: object) -> None:
        self._taskbar.clear()
        bind(self.eta, "", "text")
        self.worker = None
        self._busy(False)
        button_text(self.close_button, tr("Close"))
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
        )
        if isinstance(result, BatchReport):
            self.last_report = result
            completed = sum(item.status == "completed" for item in result.results)
            failed = sum(item.status == "failed" for item in result.results)
            cancelled = sum(item.status in ("cancelled", "skipped") for item in result.results)
            bind(
                self.status,
                tr(
                    "Finished: {0} completed, {1} failed, {2} cancelled/not started. Report: {3}",
                    completed,
                    failed,
                    cancelled,
                    result.report_path,
                ),
                "text",
            )

    @Slot(str)
    def _failed(self, message: str) -> None:
        self._taskbar.clear()
        bind(self.eta, "", "text")
        self.worker = None
        self.builder = None
        self._busy(False)
        button_text(self.close_button, tr("Close"))
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
        )
        bind(self.status, tr("Batch operation failed: {0}", message), "text")

    @Slot()
    def _close_or_cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancelled.set()
            self._taskbar.clear()
            bind(self.eta, "", "text")
            bind(self.status, tr("Cancelling current job; completed exports remain saved."), "text")
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window closure while preserving the owned worker lifecycle.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if self.worker is not None:
            self._close_or_cancel()
            event.ignore()
        else:
            self.closing = True
            super().closeEvent(event)

    def reject(self) -> None:
        """Close the dialog through its cancellation and worker-cleanup path.

        Returns:
            None.
        """
        if self.worker is not None:
            self._close_or_cancel()
        else:
            self.closing = True
            super().reject()
