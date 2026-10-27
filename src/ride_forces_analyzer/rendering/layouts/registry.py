"""Explicit offline layout registry; add built-in plugins here.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations
from types import MappingProxyType
from typing import TYPE_CHECKING
from collections.abc import Mapping
from .ribbon import PLUGIN as RIBBON
from .corners import PLUGIN as CORNERS
from .hud import PLUGIN as HUD
from .orbit import PLUGIN as ORBIT
from .column import PLUGIN as COLUMN
from .contracts import (
    ExportExtent,
    ExportGeometry,
    VideoAspect,
    LayoutPlugin,
    LayoutPosition,
    LayoutRenderer,
    Region,
)

if TYPE_CHECKING:
    from ..model import ExportLayout, ExportSettings, ExportTimeline

PLUGINS: Mapping[ExportLayout, LayoutPlugin] = MappingProxyType(
    {plugin.key: plugin for plugin in (RIBBON, CORNERS, HUD, ORBIT, COLUMN)},
)
REGIONS = {
    key: plugin.landscape.regions[plugin.landscape.default] for key, plugin in PLUGINS.items()
}


def canvas_dimensions(settings: ExportSettings) -> tuple[int, int]:
    """Resolve the full-frame canvas from the registered layout's metadata.

    Args:
        settings: Validated layout and aspect selection.

    Returns:
        Landscape or portrait canvas dimensions in pixels.

    Raises:
        ValueError: The selected format is unsupported by the plugin.
    """
    plugin = PLUGINS[settings.layout]
    plugin.positions(settings.aspect)
    return (
        plugin.landscape_canvas
        if settings.aspect is VideoAspect.LANDSCAPE
        else plugin.portrait_canvas
    )


def export_region(settings: ExportSettings) -> Region:
    """Return the selected layout region as x, y, width and height in pixels.

    Content area uses the format's canonical render region, ignoring retained placement.

    Args:
        settings: Validated settings controlling this operation.

    Returns:
        The selected layout region as x, y, width and height in pixels.

    Raises:
        ValueError: Unsupported export position for layout and format.
    """
    plugin = PLUGINS[settings.layout]
    positions = plugin.positions(settings.aspect)
    if settings.position is not None and type(settings.position) is not LayoutPosition:
        raise ValueError("Unsupported export position for layout and format")
    position = (
        positions.default
        if settings.position is None or settings.extent is ExportExtent.CONTENT_AREA
        else settings.position
    )
    if type(position) is not LayoutPosition or position not in positions.regions:
        raise ValueError("Unsupported export position for layout and format")
    return positions.regions[position]


def resolve_geometry(settings: ExportSettings) -> ExportGeometry:
    """Resolve fixed crop, render size, padding and output size from plugin metadata.

    Args:
        settings: Typed layout, aspect, extent and optional retained placement.

    Returns:
        Immutable pixel geometry. Content-area padding starts at the declared margin;
        ten-pixel rounding adds pixels only to the right and bottom.

    Raises:
        ValueError: Format, extent or placement is unsupported, or dimensions are not even.
    """
    plugin = PLUGINS[settings.layout]
    plugin.positions(settings.aspect)
    if type(settings.extent) is not ExportExtent or settings.extent not in plugin.supported_extents(
        settings.aspect,
    ):
        raise ValueError("Unsupported export extent for layout and format")
    x, y, width, height = export_region(settings)
    content = plugin.content_area(settings.aspect)
    if settings.extent is ExportExtent.CONTENT_AREA:
        assert content is not None
        geometry = ExportGeometry(
            content.dimensions,
            (width, height),
            content.bounds,
            (content.margin, content.margin),
        )
    else:
        geometry = ExportGeometry(
            canvas_dimensions(settings),
            (width, height),
            (0, 0, width, height),
            (x, y),
        )
    if any(size % 2 for size in geometry.output_size):
        raise ValueError("Export dimensions must be even for the supported codecs")
    return geometry


def create_renderer(timeline: ExportTimeline) -> LayoutRenderer:
    """Construct the production renderer for the bound export timeline.

    Args:
        timeline: Bound video timeline containing the source interval and export settings.

    Returns:
        Production layout renderer bound to the supplied timeline.
    """
    return PLUGINS[timeline.settings.layout].create(timeline)
