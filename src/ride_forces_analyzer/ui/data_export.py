"""CSV/JSON export worker and cancellation UI; serialization stays outside Qt.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from threading import Event
from typing import Literal

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.csv_export import CsvExportCancelled, export_csv
from ride_forces_analyzer.json_export import JsonExportCancelled, export_json, export_analyzer_json
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.preferences import Preferences
from .translation import bind


class DataSignals(QObject):
    progress = Signal(int)
    completed = Signal(object)
    failed = Signal(str)


class DataWorker(QRunnable):
    def __init__(
        self,
        analysis: RecordingAnalysis,
        path: Path,
        first: int,
        last: int,
        format: Literal["csv", "json", "analyzer_json"],
        overwrite: bool = False,
    ) -> None:
        super().__init__()
        self.analysis, self.path, self.first, self.last = analysis, path, first, last
        self.format = format
        self.overwrite = overwrite
        self.cancelled = Event()
        self.signals = DataSignals()

    @Slot()
    def run(self) -> None:
        try:
            exporter = {
                "csv": export_csv,
                "json": export_json,
                "analyzer_json": export_analyzer_json,
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
            self.signals.failed.emit(str(error))
        else:
            self.signals.completed.emit(self.path)


class DataExportDialog(QProgressDialog):
    """Keep a bound snapshot alive while writing, independent of workspace updates."""

    saved = Signal(str)

    def __init__(
        self,
        analysis: RecordingAnalysis,
        path: Path,
        first: int,
        last: int,
        preferences: Preferences,
        parent: QWidget,
        format: Literal["csv", "json", "analyzer_json"],
        overwrite: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{format}ExportProgress")
        self.format = format
        self.preferences = preferences
        bind(
            self,
            tr("Export Analyzer JSON")
            if format == "analyzer_json"
            else tr("Export JSON")
            if format == "json"
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
                tr("CSV export failed") if self.format == "csv" else tr("JSON export failed"),
                message,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.worker.cancelled.set()
        super().closeEvent(event)
