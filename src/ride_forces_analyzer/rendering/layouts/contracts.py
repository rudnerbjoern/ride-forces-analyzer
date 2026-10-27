"""Minimal internal layout extension contract, without Qt or encoders.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol
from PIL import Image

if TYPE_CHECKING:
    from ..model import ExportTimeline

Region = tuple[int, int, int, int]


class ExportLayout(StrEnum):
    """Built-in overlay identifiers retained in saved export settings.

    Attributes:
        COLUMN: Four-panel column, stored as ``column``.
        RIBBON: Flow Ribbon, stored as ``ribbon``.
        CORNERS: Corner Instruments, stored as ``corners``.
        HUD: Full-screen HUD, stored as ``hud``.
        ORBIT: G-Orbit, stored as ``orbit``.
    """

    COLUMN = "column"
    RIBBON = "ribbon"
    CORNERS = "corners"
    HUD = "hud"
    ORBIT = "orbit"


class VideoAspect(StrEnum):
    """Video canvas orientation with stable values for saved export settings.

    Attributes:
        LANDSCAPE: Wide video canvas, stored as ``landscape``.
        PORTRAIT: Tall video canvas, stored as ``portrait``.
    """

    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


class LayoutPosition(StrEnum):
    """Named overlay positions with stable values for storage and UI binding.

    Attributes:
        TOP: Named value for top (`top`).
        BOTTOM: Named value for bottom (`bottom`).
        LEFT: Named value for left (`left`).
        RIGHT: Named value for right (`right`).
        TOP_LEFT: Named value for top left (`top_left`).
        TOP_RIGHT: Named value for top right (`top_right`).
        BOTTOM_LEFT: Named value for bottom left (`bottom_left`).
        BOTTOM_RIGHT: Named value for bottom right (`bottom_right`).
        FULL_SCREEN: Named value for full screen (`full_screen`).
    """

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    FULL_SCREEN = "full_screen"


@dataclass(frozen=True, slots=True)
class LayoutPositions:
    """Own position regions and their default for one export format.

    Regions contain integer pixel coordinates and dimensions. Invalid keys,
    missing defaults, negative coordinates or zero/negative sizes raise ValueError.
    The caller's mapping is copied and exposed read-only.

    Attributes:
        regions: Named placement regions supported by the layout.
        default: Fallback value used when no valid stored value is available.
    """

    regions: Mapping[LayoutPosition, Region]
    default: LayoutPosition

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Layout positions require a supported default. Unknown layout position.
                Layout region must contain four integer pixel values. Layout region requires
                nonnegative coordinates and positive size.
        """
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
        """Keep a supported position or equivalent side, then a retained choice or default.

        For an edge-to-corner change, the previous position supplies the unspecified
        axis, falling back to the default. With no equivalent side, preserve a
        supported previous position rather than replacing it with the default.

        Args:
            preferred: Preferred option when available.
            previous: Previously retained value or state.

        Returns:
            Inclusive selection admitted by this object's bounds or placement contract.

        Raises:
            AssertionError: If a required internal invariant does not hold.
        """
        if preferred in self.regions:
            assert preferred is not None
            return preferred
        if preferred is LayoutPosition.FULL_SCREEN and previous in self.regions:
            assert previous is not None
            return previous
        axes = {
            LayoutPosition.TOP: (0, None),
            LayoutPosition.BOTTOM: (1, None),
            LayoutPosition.LEFT: (None, 0),
            LayoutPosition.RIGHT: (None, 1),
            LayoutPosition.TOP_LEFT: (0, 0),
            LayoutPosition.TOP_RIGHT: (0, 1),
            LayoutPosition.BOTTOM_LEFT: (1, 0),
            LayoutPosition.BOTTOM_RIGHT: (1, 1),
            LayoutPosition.FULL_SCREEN: (None, None),
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
        return previous if previous in self.regions and previous is not None else self.default


class LayoutRenderer(Protocol):
    """Layout renderer contract and owned data."""

    def render_position(self, position: float) -> Image.Image:
        """Return the native RGBA region at an absolute source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
        ...


@dataclass(frozen=True, slots=True)
class LayoutPlugin:
    """Register layout-owned geometry, defaults and optional size-estimate rates.

    HUD uses a smaller native-resolution canvas. Regions exceeding the maximum
    landscape/portrait bounds raise ValueError at registration.

    Attributes:
        key: ExportLayout member identifying the registered renderer.
        landscape: Supported landscape regions and default placement.
        portrait: Supported portrait regions and default placement.
        create: Factory constructing a renderer bound to an export timeline.
        landscape_canvas: Full-frame landscape dimensions in pixels.
        portrait_canvas: Full-frame portrait dimensions in pixels.
        preferred_window_seconds: Time-window override when selecting the layout, or None.
        preview_invert_lateral: Lateral direction used for an unselected gallery preview.
        prores_4444_size_rates: Optional ProRes 4444 lower/upper bytes per canvas pixel per frame.
        h264_size_rates: Optional H.264 lower/upper bytes per canvas pixel per frame.
    """

    key: ExportLayout
    landscape: LayoutPositions
    portrait: LayoutPositions
    create: Callable[[ExportTimeline], LayoutRenderer]
    landscape_canvas: tuple[int, int] = (3840, 2160)
    portrait_canvas: tuple[int, int] = (2160, 3840)
    preferred_window_seconds: float | None = None
    preview_invert_lateral: bool = False
    prores_4444_size_rates: tuple[float, float] | None = None
    h264_size_rates: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: The key, canvas, defaults or rates are invalid, or a region
                exceeds its declared canvas.
        """
        if type(self.key) is not ExportLayout:
            raise ValueError("Unknown export layout")
        for positions, canvas, maximum in (
            (self.landscape, self.landscape_canvas, (3840, 2160)),
            (self.portrait, self.portrait_canvas, (2160, 3840)),
        ):
            if (
                type(canvas) is not tuple
                or len(canvas) != 2
                or any(
                    type(value) is not int or not 0 < value <= limit
                    for value, limit in zip(canvas, maximum, strict=True)
                )
            ):
                raise ValueError("Layout canvas must fit within the maximum export dimensions")
            for x, y, width, height in positions.regions.values():
                if x + width > canvas[0] or y + height > canvas[1]:
                    raise ValueError("Layout region must fit within its export canvas")
        window = self.preferred_window_seconds
        if window is not None and (
            type(window) not in (float, int) or not isfinite(window) or not 1 <= window <= 60
        ):
            raise ValueError("Layout time window must be from 1 to 60 seconds")
        if type(self.preview_invert_lateral) is not bool:
            raise ValueError("Layout preview direction must be a boolean")
        for rates in (self.prores_4444_size_rates, self.h264_size_rates):
            if rates is not None and (
                type(rates) is not tuple
                or len(rates) != 2
                or any(
                    type(value) not in (float, int) or not isfinite(value) or value <= 0
                    for value in rates
                )
                or rates[0] > rates[1]
            ):
                raise ValueError("Layout size rates must be positive ordered finite values")
