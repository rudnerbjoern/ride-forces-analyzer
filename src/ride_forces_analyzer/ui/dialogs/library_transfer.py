"""Settings actions for explicit Library ZIP backup and full restore.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from threading import Event
from typing import Literal

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStyle,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.storage.library_backup import LibraryBackup, LibraryTransferCancelled
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.presentation.translation import bind, button_text


class _TransferSignals(QObject):
    """Transport transfer outcomes back to the Settings thread.

    Attributes:
        finished: Whether the operation completed, plus an optional error explanation.
    """

    finished = Signal(bool, str)


class _TransferWorker(QRunnable):
    """Run ZIP/storage work away from the UI thread.

    Attributes:
        operation: Explicit backup or restore action.
        path: ZIP destination or selected source archive.
        service: Pure Library transfer boundary.
        overwrite: Permission to replace a previously confirmed backup destination.
        cancelled: Cooperative cancellation event.
        signals: Completion/error transport.
    """

    def __init__(
        self,
        operation: Literal["backup", "restore"],
        path: Path,
        preferences: Preferences,
        overwrite: bool,
    ) -> None:
        """Capture a confirmed transfer before entering the thread pool.

        Args:
            operation: User-selected transfer action.
            path: Selected ZIP path.
            preferences: Existing preferences; only Library labels can be restored.
            overwrite: Confirmed backup destination replacement.
        """
        super().__init__()
        self.operation, self.path, self.overwrite = operation, path, overwrite
        self.service = LibraryBackup(preferences=preferences)
        self.cancelled = Event()
        self.signals = _TransferSignals()

    @Slot()
    def run(self) -> None:
        """Execute the confirmed operation and report cancellation without a failure dialog."""
        try:
            if self.operation == "backup":
                self.service.backup(
                    self.path,
                    overwrite=self.overwrite,
                    cancelled=self.cancelled.is_set,
                )
            else:
                self.service.restore(self.path, replace=True, cancelled=self.cancelled.is_set)
        except LibraryTransferCancelled:
            self.signals.finished.emit(False, "")
        except Exception as error:
            record_error("Library transfer", error)
            self.signals.finished.emit(False, str(error))
        else:
            self.signals.finished.emit(True, "")


class LibraryTransferControls(QWidget):
    """Offer paired Settings actions with existing native pickers and progress UI.

    Attributes:
        backup_button: Action creating a complete portable Library ZIP.
        restore_button: Action restoring a ZIP after explicit replacement confirmation.
        preferences: Existing application preferences.
        worker: Active transfer, otherwise None.
        progress: Existing-style cancellable busy indicator.
        busy_changed: Notification used to protect the owning Settings dialog.
        restored: Notification after a committed full restore.
        status: User-facing completion/cancellation/error message.
    """

    busy_changed = Signal(bool)
    restored = Signal()
    status = Signal(str)

    def __init__(self, preferences: Preferences, parent: QWidget) -> None:
        """Create actions inside the existing Settings Library group.

        Args:
            preferences: Saved application preferences, independent of the label draft.
            parent: Settings Library section owning these controls.
        """
        super().__init__(parent)
        self.preferences = preferences
        self.worker: _TransferWorker | None = None
        self.progress: QProgressDialog | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.backup_button = button_text(
            QPushButton(),
            tr("Backup…"),
            tooltip=tr("Back up the saved Library to one ZIP archive"),
        )
        self.restore_button = button_text(
            QPushButton(),
            tr("Restore…"),
            tooltip=tr("Replace the Library from a ZIP archive"),
        )
        for button, icon in (
            (self.backup_button, QStyle.StandardPixmap.SP_DialogSaveButton),
            (self.restore_button, QStyle.StandardPixmap.SP_DialogOpenButton),
        ):
            button.setIcon(self.style().standardIcon(icon))
            layout.addWidget(button, 1)
        self.backup_button.clicked.connect(self._backup)
        self.restore_button.clicked.connect(self._restore)

    @property
    def busy(self) -> bool:
        """Return whether a transfer must finish before Settings can close.

        Returns:
            True while the worker still owns a transfer operation.
        """
        return self.worker is not None

    def cancel(self) -> None:
        """Request cancellation while retaining the worker until it safely finishes."""
        if self.worker is not None:
            self.worker.cancelled.set()

    def _backup(self) -> None:
        suggested = Path(self.preferences.export_directory() or Path.home()) / "Library-backup.zip"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Back up Library"),
            str(suggested),
            tr("ZIP archives (*.zip)"),
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".zip":
            path = path.with_name(path.name + ".zip")
        overwrite = path.exists()
        if (
            overwrite
            and QMessageBox.question(
                self,
                tr("Replace existing file?"),
                tr("The file already exists:\n{0}\n\nDo you want to replace it?", str(path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._start("backup", path, overwrite)

    def _restore(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Restore Library"),
            "",
            tr("ZIP archives (*.zip)"),
        )
        if not filename:
            return
        if (
            QMessageBox.question(
                self,
                tr("Replace Library?"),
                tr("This replaces the entire Library and its video-label choices. Continue?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._start("restore", Path(filename), False)

    def _start(self, operation: Literal["backup", "restore"], path: Path, overwrite: bool) -> None:
        if self.worker is not None:
            return
        worker = _TransferWorker(operation, path, self.preferences, overwrite)
        self.worker = worker
        self.backup_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.busy_changed.emit(True)
        self.status.emit("")
        self.progress = QProgressDialog(self)
        bind(
            self.progress,
            tr("Backing up Library…") if operation == "backup" else tr("Restoring Library…"),
            "labelText",
        )
        bind(self.progress, tr("Library"), "windowTitle")
        self.progress.setCancelButtonText(tr("Cancel"))
        self.progress.setRange(0, 0)
        self.progress.setMinimumDuration(0)
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.canceled.connect(worker.cancelled.set)
        worker.signals.finished.connect(self._finished)
        self.progress.show()
        QThreadPool.globalInstance().start(worker)

    @Slot(bool, str)
    def _finished(self, success: bool, message: str) -> None:
        worker = self.worker
        self.worker = None
        if self.progress is not None:
            self.progress.reset()
            self.progress.close()
            self.progress.deleteLater()
            self.progress = None
        self.backup_button.setEnabled(True)
        self.restore_button.setEnabled(True)
        self.busy_changed.emit(False)
        if message:
            self.status.emit(tr("Library transfer failed: {0}", message))
        elif not success:
            self.status.emit(tr("Library transfer cancelled."))
        elif worker is not None and worker.operation == "restore":
            self.restored.emit()
            self.status.emit(tr("Library restored."))
        else:
            self.status.emit(tr("Library backup saved."))
