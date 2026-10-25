"""Qt worker transport; parsing and presentation preparation live outside widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr

from pathlib import Path
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.error_reporting import record_error
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
        path: Filesystem path read or written by this operation.
        generation: Request generation used to reject late worker deliveries.
        signals: Qt result, failure and progress signal transport owned by the worker.
    """

    def __init__(self, path: Path, generation: int = 0) -> None:
        """Initialize load worker and its owned state.

        Args:
            path: Filesystem path read or written by this operation.
            generation: Request generation used to reject late worker deliveries.

        Returns:
            None.
        """
        super().__init__()
        self.path = path
        self.generation = generation
        self.signals = LoadSignals()

    @Slot()
    def run(self) -> None:
        """Execute the worker task and deliver completion or failure through its signals.

        Returns:
            None.
        """
        try:
            outcome = load_recording(self.path)
            if isinstance(outcome, ImportFailure):
                for diagnostic in outcome.diagnostics:
                    if diagnostic.severity is Severity.ERROR:
                        record_error("Import", message=f"{diagnostic.code}: {diagnostic.message}")
            if isinstance(outcome, ExplorerData) and outcome.analysis is not None:
                snapshot = outcome.analysis
                now = datetime.now(UTC)
                configuration = Preferences().recording_configuration(
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
                tr("Unexpected load error. The previous recording is unchanged."),
            )
        else:
            self.signals.completed.emit(self.generation, outcome)
