"""Reveal an external file with the native desktop file manager.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words dbus

from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from ride_forces_analyzer.runtime.error_logging import record_error


def show_in_folder(filename: str) -> None:
    """Reveal an existing file, selecting it where the desktop supports selection.

    Args:
        filename: Absolute filename to reveal without opening the file itself.

    Raises:
        FileNotFoundError: The reference no longer points to an existing file.
        OSError: The native file manager could not be started.
        subprocess.SubprocessError: The native reveal request failed.
    """
    path = Path(filename)
    if not path.is_absolute() or not path.is_file():
        raise FileNotFoundError(filename)
    if sys.platform == "win32":
        subprocess.Popen(f'explorer.exe /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)], check=True, capture_output=True)
    else:
        try:
            subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--print-reply",
                    "--reply-timeout=2000",
                    "--dest=org.freedesktop.FileManager1",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    f"array:string:{path.as_uri()}",
                    "string:",
                ],
                check=True,
                capture_output=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError) as error:
            record_error("ui.presentation.file_manager.show_in_folder", error, context=str(path))
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
                raise OSError("Could not open the containing folder") from error
