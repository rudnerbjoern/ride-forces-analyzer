"""Platform-specific local storage paths without a Qt dependency.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import platform
from pathlib import Path
import sys


def data_directory() -> Path:
    """Return the application data directory without creating it.

    Preserve the Windows location; use Application Support on macOS and an
    absolute XDG_DATA_HOME (or its standard fallback) on Linux.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        root = Path(local) if local else Path.home() / "AppData" / "Local"
        return root / "Ride Forces Analyzer"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Ride Forces Analyzer"
    configured = Path(os.environ.get("XDG_DATA_HOME", ""))
    root = configured if configured.is_absolute() else Path.home() / ".local" / "share"
    return root / "ride-forces-analyzer"


def ffmpeg_name() -> str:
    """Return the native encoder filename."""
    return "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def runtime_target() -> str | None:
    """Identify the supported native distribution; never infer emulation support."""
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return {"win32": "windows-x64", "linux": "linux-x64", "darwin": "macos-x64"}.get(
            sys.platform,
        )
    if sys.platform == "darwin" and machine == "arm64":
        return "macos-arm64"
    return None
