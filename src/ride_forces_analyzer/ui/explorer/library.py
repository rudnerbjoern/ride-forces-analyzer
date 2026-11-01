"""Collapsible Library surface, toolbar toggle and explicit archive-import transport.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QWidget,
)

from ride_forces_analyzer.explorer.library import ArchiveImportResult, LibraryArchive
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.ui.presentation.translation import bind, button_text

from .controls import create_panel


class LibraryPanel(QSplitter):
    """Own the left Library surface beside the existing analysis workspace.

    Attributes:
        panel: Initially hidden Library content and explicit archive-import controls.
        toggle_button: Localized toolbar control with open/closed folder icons.
        import_button: Explicit multi-file archive import action.
        import_results: Read-only per-file outcomes from the latest import.
    """

    def __init__(self, parent: QWidget) -> None:
        """Build the Library import surface and its adjustable horizontal container.

        Args:
            parent: Widget owning this component's lifetime.
        """
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(10)
        self.panel, layout = create_panel()
        layout.addWidget(bind(QLabel(), tr("Library")))
        self.import_button = button_text(QPushButton(), tr("Import recordings…"))
        self.import_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
        )
        self.import_button.clicked.connect(self._choose_import)
        layout.addWidget(self.import_button)
        self.import_results = QPlainTextEdit()
        self.import_results.setReadOnly(True)
        self.import_results.setMinimumWidth(0)
        self.import_results.setMaximumHeight(160)
        bind(self.import_results, tr("Library import results"), "accessibleName")
        self.import_results.hide()
        layout.addWidget(self.import_results)
        layout.addStretch()
        self.addWidget(self.panel)
        self.panel.hide()
        self.toggle_button = button_text(QPushButton(), tr("Library"))
        self.toggle_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirClosedIcon),
        )
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        self._import_worker: ArchiveImportWorker | None = None

    @Slot()
    def _choose_import(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Import recordings into Library"),
            "",
            tr("Ride Forces (*.forces *.zforces);;All files (*)"),
        )
        if not filenames:
            return
        self.import_button.setEnabled(False)
        worker = ArchiveImportWorker(tuple(Path(filename) for filename in filenames))
        worker.signals.completed.connect(self._import_finished)
        worker.signals.failed.connect(self._import_failed)
        self._import_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _import_finished(self, results: tuple[ArchiveImportResult, ...]) -> None:
        lines: list[str] = []
        for result in results:
            message = (
                tr("Imported")
                if result.status == "imported"
                else tr("Already in Library")
                if result.status == "duplicate"
                else tr("Import failed: {0}", result.error or "")
            )
            lines.append(f"{result.path.name}: {message}")
        self.import_results.setPlainText("\n".join(lines))
        self.import_results.show()
        self.import_button.setEnabled(True)
        self._import_worker = None

    @Slot(str)
    def _import_failed(self, message: str) -> None:
        self.import_results.setPlainText(tr("Import failed: {0}", message))
        self.import_results.show()
        self.import_button.setEnabled(True)
        self._import_worker = None

    @Slot(bool)
    def _toggle(self, checked: bool) -> None:
        """Show or hide the content and match the folder icon to its visible state."""
        self.panel.setVisible(checked)
        self.toggle_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon
                if checked
                else QStyle.StandardPixmap.SP_DirClosedIcon,
            ),
        )


class ArchiveImportSignals(QObject):
    """Transport background archive outcomes without accessing widgets.

    Attributes:
        completed: Ordered per-file import results.
        failed: Explanation of an unexpected worker failure.
    """

    completed = Signal(object)
    failed = Signal(str)


class ArchiveImportWorker(QRunnable):
    """Run explicit archive imports off the GUI thread.

    Attributes:
        paths: Selected local recording paths.
        signals: Completion/error transport to the Library component.
    """

    def __init__(self, paths: tuple[Path, ...]) -> None:
        """Retain selected paths for processing by the archive service.

        Args:
            paths: Supported recordings selected through the file dialog.
        """
        super().__init__()
        self.paths = paths
        self.signals = ArchiveImportSignals()

    @Slot()
    def run(self) -> None:
        """Import files independently and report results through queued Qt signals."""
        try:
            results = LibraryArchive().import_paths(self.paths)
        except Exception as error:
            record_error("Library import worker", error)
            self.signals.failed.emit(str(error))
        else:
            self.signals.completed.emit(results)
