"""Saved batch editor and Qt transport for sequential offline exports.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from .translation import bind, items, headers

from pathlib import Path
from threading import Event

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from ride_forces_analyzer.rendering.model import PROFILES
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.rendering.batches import BatchReport, build_jobs, run_batches
from ride_forces_analyzer.rendering.encoding import find_ffmpeg
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset, RangeMode
from ride_forces_analyzer.storage.exports import ExportStore, ExportStoreError


class BatchSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    status = Signal(str)
    progress = Signal(int, int, int, int, str)


class BuildWorker(QRunnable):
    def __init__(
        self,
        name: str,
        paths: tuple[Path, ...],
        presets: tuple[SavedPreset, ...],
        mode: RangeMode,
    ) -> None:
        super().__init__()
        self.name, self.paths, self.presets = name, paths, presets
        self.mode: RangeMode = mode
        self.signals = BatchSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = SavedBatch(
                name=self.name,
                jobs=build_jobs(self.paths, self.presets, self.mode),
                schema_version=1,
            )
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(result)


class BatchWorker(QRunnable):
    def __init__(self, batches: tuple[SavedBatch, ...], directory: Path, ffmpeg: Path) -> None:
        super().__init__()
        self.batches, self.directory, self.ffmpeg = batches, directory, ffmpeg
        self.cancelled = Event()
        self.signals = BatchSignals()

    @Slot()
    def run(self) -> None:
        try:
            report = run_batches(
                self.batches,
                self.directory,
                ffmpeg=self.ffmpeg,
                cancelled=self.cancelled,
                progress=self.signals.progress.emit,
                status=self.signals.status.emit,
            )
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.finished.emit(report)


class BatchDialog(QDialog):
    def __init__(self, store: ExportStore, parent: QWidget) -> None:
        super().__init__(parent)
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
        self.new = bind(QPushButton(), tr("New batch…"))
        self.new.clicked.connect(self._new)
        self.add = bind(QPushButton(), tr("Add recordings × presets…"))
        self.add.clicked.connect(self._add)
        self.remove = bind(QPushButton(), tr("Remove selected jobs"))
        self.remove.clicked.connect(self._remove)
        self.delete = bind(QPushButton(), tr("Delete empty batch"))
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
            self.encoder.setPlaceholderText(tr("Choose ffmpeg.exe"))
        encoder_row.addWidget(self.encoder)
        self.browse = bind(QPushButton(), tr("Browse…"))
        self.browse.clicked.connect(self._browse)
        encoder_row.addWidget(self.browse)
        root.addLayout(encoder_row)
        self.current_job = bind(QLabel(), tr("No export running"))
        self.current_job.setWordWrap(True)
        self.current_job.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self.current_job)
        self.progress = QProgressBar()
        root.addWidget(self.progress)
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
        self.run_selected = bind(QPushButton(), tr("Run selected batches…"))
        self.run_selected.clicked.connect(self._run_selected)
        self.run_all = bind(QPushButton(), tr("Run ALL saved batches…"))
        self.run_all.setObjectName("Primary")
        self.run_all.clicked.connect(self._run_all)
        self.close_button = bind(QPushButton(), tr("Close"))
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
        self.refresh()

    def refresh(self, select: str | None = None) -> None:
        try:
            batches, presets = self.store.batches(), self.store.presets()
        except ExportStoreError as error:
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
            bind(self.status, tr(str(error)), "text")
            return
        self.table.setRowCount(len(batch.jobs))
        for row, job in enumerate(batch.jobs):
            values = (
                job.ride,
                f"{job.preset.name} / {tr(dict(PROFILES)[job.preset.settings.layout])} / {tr('Portrait' if job.preset.settings.aspect == 'portrait' else 'Landscape')}",
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
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "batch_list"):
            self._show_batch(
                self.batch_list.currentItem().text() if self.batch_list.currentRow() >= 0 else "",
            )

    @Slot(str)
    def _status_message(self, message: str) -> None:
        bind(self.status, tr(message))

    @Slot()
    def _new(self) -> None:
        name, accepted = QInputDialog.getText(self, tr("New batch"), tr("Batch name"))
        if not accepted:
            return
        try:
            batch = self.store.create_batch(name)
            self.refresh(batch.name)
        except (ValueError, ExportStoreError) as error:
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _add(self) -> None:
        try:
            name = self._current_name()
            selected = {item.text() for item in self.presets.selectedItems()}
            presets = tuple(preset for preset in self.store.presets() if preset.name in selected)
            if not presets:
                raise ValueError(tr("Select at least one preset"))
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                tr("Add recordings"),
                "",
                "Ride Forces (*.forces)",
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
            bind(self.status, tr(str(error)), "text")

    @Slot()
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("FFmpeg executable"),
            "",
            "FFmpeg (ffmpeg.exe)",
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
            worker = BatchWorker(batches, Path(directory), encoder)
            worker.signals.progress.connect(self._progress)
            worker.signals.status.connect(self._status_message)
            worker.signals.finished.connect(self._finished)
            worker.signals.failed.connect(self._failed)
            self.worker = worker
            self.last_report = None
            self.progress.setValue(0)
            self._busy(True)
            bind(self.close_button, tr("Cancel remaining exports"), "text")
            QThreadPool.globalInstance().start(worker)
        except (ValueError, ExportStoreError) as error:
            bind(self.status, tr(str(error)), "text")

    def _busy(self, busy: bool) -> None:
        for control in self.controls:
            control.setEnabled(not busy)

    @Slot(int, int, int, int, str)
    def _progress(self, job: int, total: int, frame: int, frames: int, label: str) -> None:
        self.progress.setValue(int(((job - 1) + frame / max(1, frames)) / total * 100))
        bind(self.current_job, tr("Job {0}/{1}: {2}", job, total, label), "text")

    @Slot(object)
    def _finished(self, result: object) -> None:
        self.worker = None
        self._busy(False)
        bind(self.close_button, tr("Close"), "text")
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
                    result.directory / "run-report.json",
                ),
                "text",
            )

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.worker = None
        self.builder = None
        self._busy(False)
        bind(self.close_button, tr("Close"), "text")
        bind(self.status, tr("Batch operation failed: {0}", message), "text")

    @Slot()
    def _close_or_cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancelled.set()
            bind(self.status, tr("Cancelling current job; completed exports remain saved."), "text")
        else:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            self._close_or_cancel()
            event.ignore()
        else:
            self.closing = True
            super().closeEvent(event)

    def reject(self) -> None:
        if self.worker is not None:
            self._close_or_cancel()
        else:
            self.closing = True
            super().reject()
