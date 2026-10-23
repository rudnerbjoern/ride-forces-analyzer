"""Qt worker transport; parsing and presentation preparation live outside widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr

from pathlib import Path
from dataclasses import replace
from datetime import UTC, datetime

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.storage.preferences import Preferences


class LoadSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, str)


class LoadWorker(QRunnable):
    def __init__(self, path: Path, generation: int = 0) -> None:
        super().__init__()
        self.path = path
        self.generation = generation
        self.signals = LoadSignals()

    @Slot()
    def run(self) -> None:
        try:
            outcome = load_recording(self.path)
            if isinstance(outcome, ExplorerData) and outcome.analysis is not None:
                bounds = Preferences().recording_bounds(outcome.source.source_sha256)
                if bounds is not None and bounds[1] < outcome.count:
                    snapshot = outcome.analysis
                    outcome = outcome.with_analysis(
                        snapshot.with_configuration(
                            replace(snapshot.configuration, ride_bounds=bounds),
                            revision=snapshot.revision + 1,
                            calculation_time=datetime.now(UTC),
                        ),
                    )
        except Exception:
            self.signals.failed.emit(
                self.generation,
                tr("Unexpected load error. The previous recording is unchanged."),
            )
        else:
            self.signals.completed.emit(self.generation, outcome)
