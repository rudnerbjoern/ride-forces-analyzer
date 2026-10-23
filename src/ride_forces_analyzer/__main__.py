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


def main(
    settings: AppSettings | None = None,
    *,
    recording: Path | None = None,
    new_window: bool = False,
) -> int:
    from ride_forces_analyzer.error_reporting import initialize_error_reporting

    initialize_error_reporting()
    from ride_forces_analyzer.config import AppSettings
    from PySide6.QtCore import QThreadPool
    from ride_forces_analyzer.ui.application import RecordingApplication

    from ride_forces_analyzer.instance import InstanceBroker, OpenRequest

    settings = settings if settings is not None else AppSettings()
    application = RecordingApplication(sys.argv)
    application.setDesktopFileName("ride-forces-analyzer")
    application.settings = settings
    broker = InstanceBroker(application)
    broker.requested.connect(application.receive_request)
    request = OpenRequest(
        path=str(recording.resolve()) if recording is not None else None,
        new_window=new_window,
    )
    if not broker.start_or_forward(request):
        return 0
    try:
        application.start(request)
        result = application.exec()
        QThreadPool.globalInstance().waitForDone()
        return result
    finally:
        broker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", nargs="?", type=Path)
    parser.add_argument("--new-window", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(main(recording=arguments.recording, new_window=arguments.new_window))
