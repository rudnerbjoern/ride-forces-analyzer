"""Qt worker transport; parsing and presentation preparation live outside widgets.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ride_forces_analyzer.explorer import load_recording


class LoadSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class LoadWorker(QRunnable):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = LoadSignals()

    @Slot()
    def run(self) -> None:
        try:
            outcome = load_recording(self.path)
        except Exception:
            self.signals.failed.emit(
                tr("Unexpected load error. The previous recording is unchanged."),
            )
        else:
            self.signals.completed.emit(outcome)
