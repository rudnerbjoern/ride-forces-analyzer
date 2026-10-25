"""CSV/JSON export worker and cancellation UI; serialization stays outside Qt.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.exports.csv import CsvExportCancelled, export_csv
from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.exports.json import JsonExportCancelled, export_json, export_analyzer_json
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.storage.preferences import Preferences
from .translation import bind


class DataSignals(QObject):
    """Data signals contract and owned data.

    Attributes:
        progress: Qt signal for progress notifications.
        completed: Qt signal for completed notifications.
        failed: Qt signal for failed notifications.
    """

    progress = Signal(int)
    completed = Signal(object)
    failed = Signal(str)


class DataWorker(QRunnable):
    """Data worker contract and owned data.

    Attributes:
        analysis: Prepared recording-analysis snapshot used by this operation.
        path: Filesystem path read or written by this operation.
        first: First included source index or the control selecting that bound.
        last: Last included source index or the control selecting that bound.
        format: DataExportFormat member selecting the serializer.
        overwrite: Whether the caller explicitly permits replacing an existing
            destination.
        cancelled: Event used to request cancellation without publishing partial output.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        analysis: RecordingAnalysis,
        path: Path,
        first: int,
        last: int,
        format: DataExportFormat,
        overwrite: bool = False,
    ) -> None:
        """Initialize data worker and its owned state.

        Args:
            analysis: Prepared recording-analysis snapshot used by this operation.
            path: Filesystem path read or written by this operation.
            first: First included source sample index.
            last: Last included source sample index.
            format: DataExportFormat member selecting the serializer.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.

        Returns:
            None.
        """
        super().__init__()
        self.analysis, self.path, self.first, self.last = analysis, path, first, last
        self.format = format
        self.overwrite = overwrite
        self.cancelled = Event()
        self.signals = DataSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            exporter = {
                DataExportFormat.CSV: export_csv,
                DataExportFormat.JSON: export_json,
                DataExportFormat.ANALYZER_JSON: export_analyzer_json,
            }[self.format]
            exporter(
                self.analysis,
                self.path,
                self.first,
                self.last,
                overwrite=self.overwrite,
                cancelled=self.cancelled.is_set,
                progress=self.signals.progress.emit,
            )
        except CsvExportCancelled, JsonExportCancelled:
            self.signals.completed.emit(None)
        except Exception as error:
            record_error("Data export", error)
            self.signals.failed.emit(str(error))
        else:
            self.signals.completed.emit(self.path)


class DataExportDialog(QProgressDialog):
    """Keep a bound snapshot alive while writing, independent of workspace updates.

    Attributes:
        saved: Qt signal for saved notifications.
        format: DataExportFormat member selecting the serializer and dialog title.
        preferences: Local application preference access for this window or controller.
        worker: Current background worker, or None when no task is active.
    """

    saved = Signal(str)

    def __init__(
        self,
        analysis: RecordingAnalysis,
        path: Path,
        first: int,
        last: int,
        preferences: Preferences,
        parent: QWidget,
        format: DataExportFormat,
        overwrite: bool = False,
    ) -> None:
        """Initialize data export dialog and its owned state.

        Args:
            analysis: Prepared recording-analysis snapshot used by this operation.
            path: Filesystem path read or written by this operation.
            first: First included source sample index.
            last: Last included source sample index.
            preferences: Local application preference access.
            parent: Qt parent that owns this object's lifetime.
            format: DataExportFormat member selecting the serializer and dialog title.
            overwrite: Whether the caller explicitly permits replacing an existing
                destination.

        Returns:
            None.
        """
        super().__init__(parent)
        self.setObjectName(f"{format}ExportProgress")
        self.format = format
        self.preferences = preferences
        bind(
            self,
            tr("Export Analyzer JSON")
            if format is DataExportFormat.ANALYZER_JSON
            else tr("Export JSON")
            if format is DataExportFormat.JSON
            else tr("Export CSV"),
            "windowTitle",
        )
        bind(self, tr("Exporting {0:,} samples…", last - first + 1), "labelText")
        self.setCancelButtonText(tr("Cancel"))
        self.setRange(0, last - first + 1)
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.worker = DataWorker(analysis, path, first, last, format, overwrite)
        self.worker.signals.progress.connect(self.setValue)
        self.worker.signals.completed.connect(self._completed)
        self.worker.signals.failed.connect(self._failed)
        self.canceled.connect(self.worker.cancelled.set)
        QTimer.singleShot(0, lambda: QThreadPool.globalInstance().start(self.worker))

    @Slot(object)
    def _completed(self, path: object) -> None:
        if isinstance(path, Path):
            self.preferences.remember_export(path)
            self.saved.emit(str(path))
            self.accept()
        else:
            self.reject()

    @Slot(str)
    def _failed(self, message: str) -> None:
        cancelled = self.wasCanceled()
        self.reject()
        parent = self.parentWidget()
        if not cancelled and parent is not None and parent.isVisible():
            QMessageBox.warning(
                parent,
                tr("CSV export failed")
                if self.format is DataExportFormat.CSV
                else tr("JSON export failed"),
                message,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window closure while preserving the owned worker lifecycle.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        self.worker.cancelled.set()
        super().closeEvent(event)
