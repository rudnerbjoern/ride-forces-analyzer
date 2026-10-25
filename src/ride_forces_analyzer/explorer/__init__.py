"""Public Qt-independent explorer presentation and loading contracts.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from .selection import SampleRange
from .model import ExplorerData
from .loading import load_recording, present_recording
from .text import failure_text

__all__ = ["ExplorerData", "SampleRange", "failure_text", "load_recording", "present_recording"]
