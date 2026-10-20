"""Shared frozen desktop entry point and explicit offline package self-test.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from pathlib import Path

from ride_forces_analyzer.__main__ import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", type=Path)
    parser.add_argument("--recording", type=Path)
    parser.add_argument("--with-ffmpeg", action="store_true")
    parser.add_argument("--ffmpeg", type=Path)
    arguments = parser.parse_args()
    if arguments.self_test:
        from scripts.windows_smoke import smoke_test

        try:
            smoke_test(
                arguments.self_test,
                arguments.recording,
                arguments.with_ffmpeg,
                arguments.ffmpeg,
            )
        except Exception:
            # The report contains diagnostics; a CI self-test must not open a
            # windowed bootloader traceback dialog and wait for user input.
            raise SystemExit(1) from None
    else:
        raise SystemExit(main())
