"""Shared frozen desktop entry point and explicit offline package self-test.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Explore ride recordings and export video overlays.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="Open a .forces or .zforces recording.")
    parser.add_argument(
        "--new-window",
        action="store_true",
        help="Open a separate recording window in the running application; without a file, open an empty window.",
    )
    parser.add_argument(
        "--self-test",
        type=Path,
        metavar="REPORT",
        help="Run the offline package self-test instead of normal startup and write its JSON report to REPORT.",
    )
    parser.add_argument(
        "--recording",
        type=Path,
        metavar="FILE",
        help="Self-test only: import FILE and render a 4K frame (requires --self-test).",
    )
    parser.add_argument(
        "--with-ffmpeg",
        action="store_true",
        help="Self-test only: also encode a short video (requires --self-test and --recording).",
    )
    parser.add_argument(
        "--ffmpeg",
        type=Path,
        metavar="EXECUTABLE",
        help="Self-test only: use this FFmpeg executable for encoding; does not configure the normal export dialog.",
    )
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
        from ride_forces_analyzer.runtime.error_reporting import initialize_error_reporting

        initialize_error_reporting()
        from ride_forces_analyzer.__main__ import main

        raise SystemExit(main(recording=arguments.file, new_window=arguments.new_window))
