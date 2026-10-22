"""Minimal internal layout extension contract, without Qt or encoders.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol
from PIL import Image

if TYPE_CHECKING:
    from ..model import ExportLayout, ExportTimeline

Region = tuple[int, int, int, int]


class LayoutPosition(StrEnum):
    """Named overlay positions with stable values for storage and UI binding."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


@dataclass(frozen=True, slots=True)
class LayoutPositions:
    """Own position regions and their default for one export format.

    Regions contain integer pixel coordinates and dimensions. Invalid keys,
    missing defaults, negative coordinates or zero/negative sizes raise ValueError.
    The caller's mapping is copied and exposed read-only.
    """

    regions: Mapping[LayoutPosition, Region]
    default: LayoutPosition

    def __post_init__(self) -> None:
        regions = dict(self.regions)
        if type(self.default) is not LayoutPosition or not regions or self.default not in regions:
            raise ValueError("Layout positions require a supported default")
        for position, region in regions.items():
            if type(position) is not LayoutPosition:
                raise ValueError("Unknown layout position")
            if (
                type(region) is not tuple
                or len(region) != 4
                or any(type(value) is not int for value in region)
            ):
                raise ValueError("Layout region must contain four integer pixel values")
            x, y, width, height = region
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise ValueError("Layout region requires nonnegative coordinates and positive size")
        object.__setattr__(self, "regions", MappingProxyType(regions))

    def select(
        self,
        preferred: LayoutPosition | None,
        previous: LayoutPosition | None = None,
    ) -> LayoutPosition:
        """Keep a supported position or its equivalent side; otherwise use the default.

        For an edge-to-corner change, the previous position supplies the unspecified
        axis, falling back to the default.
        """
        if preferred in self.regions:
            assert preferred is not None
            return preferred
        axes = {
            LayoutPosition.TOP: (0, None),
            LayoutPosition.BOTTOM: (1, None),
            LayoutPosition.LEFT: (None, 0),
            LayoutPosition.RIGHT: (None, 1),
            LayoutPosition.TOP_LEFT: (0, 0),
            LayoutPosition.TOP_RIGHT: (0, 1),
            LayoutPosition.BOTTOM_LEFT: (1, 0),
            LayoutPosition.BOTTOM_RIGHT: (1, 1),
        }
        if preferred is not None:
            anchor = previous if previous in self.regions else self.default
            assert anchor is not None
            candidates = sorted(
                self.regions,
                key=lambda candidate: sum(
                    offered == default for offered, default in zip(axes[candidate], axes[anchor])
                ),
                reverse=True,
            )
            for candidate in candidates:
                shared = [
                    (requested, offered)
                    for requested, offered in zip(axes[preferred], axes[candidate])
                    if requested is not None and offered is not None
                ]
                if shared and all(requested == offered for requested, offered in shared):
                    return candidate
        return self.default


class LayoutRenderer(Protocol):
    def render_position(self, position: float) -> Image.Image:
        """Return the native RGBA region at an absolute source-sample position."""
        ...


@dataclass(frozen=True, slots=True)
class LayoutPlugin:
    """Register a renderer and validated position regions for both 4K formats.

    Regions outside their format's canvas raise ValueError at registration.
    """

    key: ExportLayout
    landscape: LayoutPositions
    portrait: LayoutPositions
    create: Callable[[ExportTimeline], LayoutRenderer]

    def __post_init__(self) -> None:
        for positions, canvas in ((self.landscape, (3840, 2160)), (self.portrait, (2160, 3840))):
            for x, y, width, height in positions.regions.values():
                if x + width > canvas[0] or y + height > canvas[1]:
                    raise ValueError("Layout region must fit within its export canvas")
