"""Minimal internal layout extension contract, without Qt or encoders.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol
from PIL import Image

if TYPE_CHECKING:
    from ..model import ExportLayout, ExportTimeline

Region = tuple[int, int, int, int]


class LayoutRenderer(Protocol):
    def render_position(self, position: float) -> Image.Image:
        """Return the native RGBA region at an absolute source-sample position."""
        ...


@dataclass(frozen=True, slots=True)
class LayoutPlugin:
    key: ExportLayout
    landscape: Region
    portrait: Region
    create: Callable[[ExportTimeline], LayoutRenderer]
