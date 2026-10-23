"""Application entry point.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ride_forces_analyzer.config import AppSettings


def main(settings: AppSettings | None = None, *, recording: Path | None = None) -> int:
    from ride_forces_analyzer.error_reporting import initialize_error_reporting

    initialize_error_reporting()
    from ride_forces_analyzer.config import AppSettings
    from PySide6.QtCore import QThreadPool
    from ride_forces_analyzer.ui.application import RecordingApplication

    from ride_forces_analyzer.ui.window import ExplorerWindow

    settings = settings if settings is not None else AppSettings()
    application = RecordingApplication(sys.argv)
    application.setDesktopFileName("ride-forces-analyzer")
    window = ExplorerWindow(settings)
    application.window = window
    window.show()
    if recording is not None:
        application.pending_path = recording
    application.deliver_file()
    result = application.exec()
    QThreadPool.globalInstance().waitForDone()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", nargs="?", type=Path)
    raise SystemExit(main(recording=parser.parse_args().recording))
