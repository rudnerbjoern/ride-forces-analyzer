"""Validated bootstrap configuration, separate from recording/domain models.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pydantic import BaseModel, Field
from ride_forces_analyzer.i18n import Language

# Qt's documented maximum widget size; reject unsupported sizes before startup.
MAX_WINDOW_DIMENSION = 16_777_215


class AppSettings(BaseModel, frozen=True, strict=True, extra="forbid", validate_default=True):
    """Immutable window settings with strict runtime and static typing.

    Attributes:
        window_title: Configured application window title.
        window_width: Layout dimension for window width, in native pixels unless specified
            otherwise.
        window_height: Layout dimension for window height, in native pixels unless
            specified otherwise.
        language: Language member used for presentation; JSON retains its stable text code.
    """

    window_title: str = Field(default="Ride Forces Analyzer", min_length=1)
    window_width: int = Field(default=1280, gt=0, le=MAX_WINDOW_DIMENSION)
    window_height: int = Field(default=820, gt=0, le=MAX_WINDOW_DIMENSION)
    language: Language = Language.ENGLISH
