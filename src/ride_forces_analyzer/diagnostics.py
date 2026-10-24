"""Offline support information without user paths or recording contents."""

# cspell:words creationflags

import platform
import re
import subprocess
import sys

from PySide6.QtCore import qVersion

from ride_forces_analyzer import __version__
from ride_forces_analyzer.cpu_resources import detect_cpu_resources
from ride_forces_analyzer.rendering.encoding import encoder_environment, find_ffmpeg


def collect_diagnostics() -> str:
    """Return English support fields; limit the external encoder probe to 3 seconds.

    Executable paths and raw encoder output/errors are never included. Call outside
    the UI thread. Only a numeric version is extracted from FFmpeg output.
    """
    fields = {
        "Ride Forces Analyzer": __version__,
        "Operating system": f"{platform.system()} {platform.release()}",
        "Architecture": platform.machine(),
        "Python": platform.python_version(),
        "Qt": qVersion(),
        "Distribution": "Packaged application" if getattr(sys, "frozen", False) else "Source",
    }
    fields.update(detect_cpu_resources().diagnostic_fields())
    try:
        executable = find_ffmpeg()
    except ValueError:
        fields["FFmpeg"] = "Not found"
    else:
        try:
            result = subprocess.run(
                [str(executable), "-version"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=3,
                check=False,
                env=encoder_environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                fields["FFmpeg"] = "Check failed"
            else:
                fields["FFmpeg"] = "Available"
                version = re.search(r"^ffmpeg version n?(\d+(?:\.\d+){0,3})", result.stdout)
                fields["FFmpeg version"] = version.group(1) if version else "Unknown"
        except OSError, subprocess.SubprocessError:
            fields["FFmpeg"] = "Check failed"
    return "\n".join(f"{key}: {value}" for key, value in fields.items())
