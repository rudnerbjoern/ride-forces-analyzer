"""Library export history and saved-settings review, separate from the narrow panel.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.exports.history import RepeatedExport, prepare_repeat
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.rendering.model import ExportSnapshot, PROFILES
from ride_forces_analyzer.storage.library import LibraryStoreError
from ride_forces_analyzer.storage.library_history import ExportRequest, HistoryEntry, LibraryHistory
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.exports.data_controller import DataExportController
from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.ui.presentation.translation import bind, button_text


class _RepeatSignals(QObject):
    """Transport a prepared saved recipe or an unsupported/unavailable explanation.

    Attributes:
        ready: Prepared repeat data delivered to the UI thread.
        failed: Failure explanation, leaving stored history unchanged.
    """

    ready = Signal(object)
    failed = Signal(str)


class _RepeatWorker(QRunnable):
    """Prepare one immutable attempt's archived source away from the UI thread.

    Attributes:
        entry: Selected immutable attempt.
        history: Library persistence boundary.
        signals: Result transport owned for the worker's lifetime.
    """

    def __init__(self, entry: HistoryEntry, history: LibraryHistory) -> None:
        """Capture the selected attempt before starting work.

        Args:
            entry: Attempt whose saved recipe is requested.
            history: Library owning the archived source and history.
        """
        super().__init__()
        self.entry, self.history = entry, history
        self.signals = _RepeatSignals()

    @Slot()
    def run(self) -> None:
        """Prepare the recipe and report success or failure without editing history."""
        try:
            result = prepare_repeat(self.entry, self.history)
        except Exception as error:
            self.signals.failed.emit(str(error))
        else:
            self.signals.ready.emit(result)


class LibraryExportsDialog(QDialog):
    """Show distinct attempts and repeat a supported frozen recipe through existing exports.

    Attributes:
        history: Persistence boundary supplying recording-bound attempts.
        source_sha256: Recording identity fixed for this dialog.
        attempts: Newest-first attempt list.
        details: Read-only result and saved-settings summary.
        repeat: Action preparing the selected saved recipe in a worker.
        error: Visible unsupported-recipe or persistence explanation.
        buttons: Standard Close action and repeat action.
        data_exports: Existing destination/cancellation flow for repeated data exports.
        export_dialog: Existing video review, when opened.
        worker: Current repeat preparation worker, otherwise None.
    """

    def __init__(self, source_sha256: str, parent: QWidget) -> None:
        """Create a themed recording-bound history view without reopening every source.

        Args:
            source_sha256: Recording whose attempts are displayed.
            parent: Library panel owning the dialog.
        """
        super().__init__(parent)
        self.source_sha256 = source_sha256
        self.history = LibraryHistory()
        self.worker: _RepeatWorker | None = None
        self.export_dialog: ExportDialog | None = None
        self._entries: dict[int, HistoryEntry] = {}
        self.data_exports = DataExportController(Preferences(), self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        bind(self, tr("Export history…"), "windowTitle")
        self.resize(680, 580)
        layout = QVBoxLayout(self)
        group = bind(QGroupBox(), tr("Export history"), "title")
        group_layout = QVBoxLayout(group)
        self.attempts = QListWidget()
        bind(self.attempts, tr("Export attempts"), "accessibleName")
        group_layout.addWidget(self.attempts)
        layout.addWidget(group, 1)
        settings = bind(QGroupBox(), tr("Saved settings"), "title")
        settings_layout = QVBoxLayout(settings)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        settings_layout.addWidget(self.details)
        layout.addWidget(settings, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close = self.buttons.button(QDialogButtonBox.StandardButton.Close)
        button_text(close, tr("Close"))
        close.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        self.repeat = button_text(QPushButton(), tr("Repeat export…"))
        self.repeat.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.buttons.addButton(self.repeat, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.rejected.connect(self.reject)
        self.repeat.clicked.connect(self._repeat)
        self.attempts.currentItemChanged.connect(self._selected)
        layout.addWidget(self.buttons)
        self.refresh()

    def refresh(self) -> None:
        """Reload history after a repeated export without changing recording state."""
        try:
            entries = self.history.entries(self.source_sha256)
        except LibraryStoreError as error:
            self._failed(str(error))
            return
        self._entries = {entry.id: entry for entry in entries}
        self.attempts.clear()
        for entry in entries:
            try:
                started = (
                    datetime.fromisoformat(entry.started_at).astimezone().strftime("%Y-%m-%d %H:%M")
                )
            except ValueError:
                started = entry.started_at
            item = QListWidgetItem(f"{started} · {entry.kind} · {tr(entry.status)}")
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.attempts.addItem(item)
        self.attempts.setCurrentRow(0)
        if not entries:
            self.details.setPlainText(tr("No export attempts yet."))
            self.repeat.setEnabled(False)

    def changeEvent(self, event: QEvent) -> None:
        """Refresh dynamic attempt text when the shared application language changes.

        Args:
            event: Native Qt change notification.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "attempts"):
            row = self.attempts.currentRow()
            self.refresh()
            self.attempts.setCurrentRow(row)

    def _selected(self) -> None:
        self.repeat.setEnabled(False)
        self.error.hide()
        if self.attempts.currentRow() < 0:
            return
        entry = self._entries[self.attempts.currentItem().data(Qt.ItemDataRole.UserRole)]
        duration = f"{entry.duration:.1f} s" if entry.duration is not None else "—"
        lines = [
            f"{tr('Status')}: {tr(entry.status)}",
            f"{tr('Duration')}: {duration}",
            f"{tr('Destination')}: {entry.output_path or '—'}",
            f"{tr('File size')}: {tr('{0} bytes', entry.file_size) if entry.file_size is not None else '—'}",
            f"{tr('Encoder')}: {'GPU' if entry.gpu_encoding else 'CPU' if entry.gpu_encoding is not None else '—'}",
        ]
        if entry.error:
            lines.append(entry.error)
        try:
            request = ExportRequest.model_validate_json(entry.request_json)
            video = (
                ExportSnapshot.model_validate_json(entry.snapshot_json)
                if entry.kind == "video" and entry.snapshot_json is not None
                else None
            )
            if video is None and entry.snapshot_json is not None:
                request = ExportRequest.model_validate_json(entry.snapshot_json)
            configuration = (
                video.analysis_configuration
                if video is not None
                else request.analysis_configuration
            )
            first = video.first_sample if video is not None else request.first_sample
            last = video.last_sample_inclusive if video is not None else request.last_sample
            calibration = configuration.calibration
            gravity = (
                str(calibration.gravity_index)
                if calibration.gravity_index is not None
                else tr("Source value")
            )
            incline = (
                str(calibration.incline_index)
                if calibration.incline_index is not None
                else tr("Source value")
            )
            lines.extend(
                (
                    f"{tr('Samples')}: {first}–{last}",
                    f"{tr('Smoothing')}: {dict(configuration.smoothing.parameters).get('window_samples', 11)}",
                    f"{tr('Gravity')}: {gravity}",
                    f"{tr('Incline')}: {incline}",
                ),
            )
            if video is not None:
                lines.extend(
                    (
                        f"{tr('Layout profile')}: {tr(dict(PROFILES)[video.settings.layout])}",
                        f"{tr('Frame rate')}: {video.settings.fps_label}",
                        f"{tr('Output dimensions')}: {video.output_dimensions[0]} × {video.output_dimensions[1]}",
                    ),
                )
            labels = video.recording_metadata if video is not None else request.recording_metadata
            if labels is not None:
                lines.extend(
                    f"{tr(label)}: {value or '—'}"
                    for label, value in (
                        ("Ride", labels.ride_name),
                        ("Park", labels.park_name),
                        ("Row", labels.row),
                        ("Seat", labels.seat),
                        ("Train", labels.train),
                        ("Notes", labels.notes),
                    )
                )
            self.repeat.setEnabled(self.worker is None and entry.snapshot_json is not None)
            if entry.snapshot_json is None:
                self.error.setText(tr("No effective export settings were saved for this attempt."))
                self.error.show()
        except ValueError:
            self.error.setText(tr("Saved export settings are unavailable or unsupported."))
            self.error.show()
        self.details.setPlainText("\n".join(lines))

    def _repeat(self) -> None:
        if self.worker is not None or self.attempts.currentRow() < 0:
            return
        entry = self._entries[self.attempts.currentItem().data(Qt.ItemDataRole.UserRole)]
        self.worker = _RepeatWorker(entry, self.history)
        self.worker.signals.ready.connect(self._ready)
        self.worker.signals.failed.connect(self._failed)
        self.attempts.setEnabled(False)
        self.repeat.setEnabled(False)
        QThreadPool.globalInstance().start(self.worker)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.worker = None
        self.attempts.setEnabled(True)
        self.repeat.setEnabled(False)
        self.error.setText(tr("Cannot repeat this export: {0}", message))
        self.error.show()

    @Slot(object)
    def _ready(self, result: RepeatedExport) -> None:
        self.worker = None
        self.attempts.setEnabled(True)
        if not self.isVisible() or result.data.analysis is None:
            return
        request = result.request
        if result.video_snapshot is not None:
            self.export_dialog = ExportDialog(
                result.data,
                request.first_sample,
                request.last_sample,
                self,
            )
            self.export_dialog.restore_snapshot(result.video_snapshot)
            self.export_dialog.finished.connect(self.refresh)
            self.export_dialog.open()
        else:
            self.data_exports.start(
                result.data.analysis,
                request.first_sample,
                request.last_sample,
                DataExportFormat(request.kind),
            )
            if self.data_exports.dialog is not None:
                self.data_exports.dialog.finished.connect(self.refresh)
        self.repeat.setEnabled(True)
