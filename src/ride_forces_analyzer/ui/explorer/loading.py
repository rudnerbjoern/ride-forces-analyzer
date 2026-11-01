"""Qt worker transport; parsing and presentation preparation live outside widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr

from pathlib import Path
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.explorer.library import LibraryArchive
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.importers import ImportFailure, Severity


class LoadSignals(QObject):
    """Load signals contract and owned data.

    Attributes:
        completed: Qt signal for completed notifications.
        failed: Qt signal for failed notifications.
    """

    completed = Signal(int, object)
    failed = Signal(int, str)


class LoadWorker(QRunnable):
    """Load worker contract and owned data.

    Attributes:
        path: External source path, or None when reopening an archived source.
        source_sha256: Archived source identity, or None for ordinary file opening.
        generation: Request generation used to reject late worker deliveries.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(
        self,
        path: Path | None,
        generation: int = 0,
        *,
        source_sha256: str | None = None,
    ) -> None:
        """Initialize load worker and its owned state.

        Args:
            path: External recording path, or None for an archived source.
            generation: Request generation used to reject late worker deliveries.
            source_sha256: Archive identity, supplied instead of a path.

        Returns:
            None.

        Raises:
            ValueError: Exactly one external path or archived identity is required.
        """
        super().__init__()
        if (path is None) == (source_sha256 is None):
            raise ValueError("Select one external path or archived source")
        self.path = path
        self.source_sha256 = source_sha256
        self.generation = generation
        self.signals = LoadSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            if self.source_sha256 is not None:
                outcome = LibraryArchive().reopen(self.source_sha256)
            else:
                assert self.path is not None
                outcome = load_recording(self.path)
                if isinstance(outcome, ExplorerData):
                    outcome = LibraryArchive().apply_metadata(outcome)
            if isinstance(outcome, ImportFailure):
                for diagnostic in outcome.diagnostics:
                    if diagnostic.severity is Severity.ERROR:
                        record_error("Import", message=f"{diagnostic.code}: {diagnostic.message}")
            if (
                self.source_sha256 is None
                and isinstance(outcome, ExplorerData)
                and outcome.analysis is not None
            ):
                snapshot = outcome.analysis
                now = datetime.now(UTC)
                configuration = LibraryArchive().recording_configuration(
                    outcome.source,
                    snapshot.configuration,
                    calculation_time=now,
                )
                if configuration != snapshot.configuration:
                    outcome = outcome.with_analysis(
                        snapshot.with_configuration(
                            configuration,
                            revision=snapshot.revision + 1,
                            calculation_time=now,
                        ),
                    )
        except Exception as error:
            record_error("Import worker", error)
            self.signals.failed.emit(
                self.generation,
                tr("Could not open archived recording: {0}", str(error))
                if self.source_sha256 is not None
                else tr("Unexpected load error. The previous recording is unchanged."),
            )
        else:
            self.signals.completed.emit(self.generation, outcome)
