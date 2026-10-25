"""Source-bound data-export launch, destination selection and dialog lifetime.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ride_forces_analyzer.exports.formats import DataExportFormat
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.preferences import Preferences

if TYPE_CHECKING:
    from ride_forces_analyzer.analysis.recording import RecordingAnalysis
    from .data import DataExportDialog


class DataExportController(QObject):
    """Own destination selection and one active sample-export dialog.

    Attributes:
        starting: Signal requesting playback pause before choosing a destination.
        saved: Signal carrying the selected format and successfully written path.
        dialog: Current data-export dialog, or None before its first use.
        preferences: Local directory memory used by data export.
        _window: Parent widget for destination prompts and the export dialog.
    """

    starting = Signal()
    saved = Signal(object, str)

    def __init__(self, preferences: Preferences, parent: QWidget) -> None:
        """Create launch transport without importing optional analysis/render code.

        Args:
            preferences: Existing application preferences for destination memory.
            parent: Widget owning prompts, dialogs and this controller.

        Returns:
            None.
        """
        super().__init__(parent)
        self.preferences = preferences
        self._window = parent
        self.dialog: DataExportDialog | None = None

    def start(
        self,
        analysis: "RecordingAnalysis",
        first: int,
        last: int,
        format: DataExportFormat,
    ) -> None:
        """Choose a destination and open an export bound to the supplied snapshot.

        Args:
            analysis: Existing analysis snapshot retained by the export worker.
            first: First included source sample.
            last: Last included source sample.
            format: Selected CSV or JSON data-export format.

        Returns:
            None; reuse an active dialog or stop when destination prompts are cancelled.
        """
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.raise_()
            return
        self.starting.emit()
        source_path = analysis.source.recording.source.provenance.path
        suffix = ".csv" if format is DataExportFormat.CSV else ".json"
        stem = source_path.stem if source_path else "recording"
        name = f"{stem}{'.analyzer' if format is DataExportFormat.ANALYZER_JSON else ''}{suffix}"
        directory = self.preferences.export_directory()
        suggested = (
            Path(directory) / name
            if directory
            else source_path.with_name(name)
            if source_path
            else Path(name)
        )
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            tr("Export Analyzer JSON")
            if format is DataExportFormat.ANALYZER_JSON
            else tr("Export JSON")
            if format is DataExportFormat.JSON
            else tr("Export CSV"),
            str(suggested),
            tr("CSV files (*.csv)")
            if format is DataExportFormat.CSV
            else tr("JSON files (*.json)"),
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
                self._window,
                tr("Replace existing file?"),
                tr("The file already exists:\n{0}\n\nDo you want to replace it?", str(path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.dialog is not None:
            self.dialog.deleteLater()
        from ride_forces_analyzer.ui.exports.data import DataExportDialog

        dialog = DataExportDialog(
            analysis,
            path,
            first,
            last,
            self.preferences,
            self._window,
            format,
            overwrite,
        )

        def saved(path: str) -> None:
            self.saved.emit(format, path)

        dialog.saved.connect(saved)
        self.dialog = dialog
        dialog.show()

    def close(self) -> None:
        """Close the owned export dialog using its existing cancellation lifecycle.

        Returns:
            None.
        """
        if self.dialog is not None:
            self.dialog.close()
