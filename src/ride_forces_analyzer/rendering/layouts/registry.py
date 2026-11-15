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
    SafeRegionGeometry,
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
    """Return the selected Full-frame layout region as x, y, width and height.

    Content area resolves the default placement, ignoring retained position;
    resolve_geometry provides its independent native output dimensions.
    Safe Region fits compact Full-frame regions inside added side clearance,
    retaining the selected anchor and bounding force plot lifts by top headroom.

    Args:
        settings: Validated settings controlling this operation.

    Returns:
        The selected layout region as x, y, width and height in pixels.

    Raises:
        ValueError: Unsupported placement or Safe Region mode, or insets leave
            no positive compact region.
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
    region = positions.regions[position]
    offsets, maximum_lift = _safe_region_geometry(settings)
    if not offsets.side_inset or position is LayoutPosition.FULL_SCREEN:
        return region
    x, y, width, height = region
    fitted_width = width - 2 * offsets.side_inset
    if fitted_width <= 0:
        raise ValueError("Safe Region side insets leave no layout width")
    fitted_height = round(height * fitted_width / width)
    if fitted_height <= 0:
        raise ValueError("Safe Region fitting leaves no layout height")
    if position in (LayoutPosition.BOTTOM, LayoutPosition.BOTTOM_LEFT, LayoutPosition.BOTTOM_RIGHT):
        y += height - fitted_height
    if plugin.safe_region_force_plots:
        y -= round(offsets.force_plot_lift * min(1, y / maximum_lift))
    return (x + offsets.side_inset, y, fitted_width, fitted_height)


def _safe_region_geometry(settings: ExportSettings) -> tuple[SafeRegionGeometry, int]:
    """Validate the profile and scale its offsets from the 1080 × 1920 reference.

    Args:
        settings: Typed profile, format and extent with registered layout geometry.

    Returns:
        Additional offsets and the maximum profile lift in output-canvas pixels,
        rounded to the nearest integer. Native Portrait canvases scale exactly.
        Off returns zero offsets and a zero maximum lift.

    Raises:
        ValueError: The mode is untyped or requires an unsupported format/extent.
    """
    from ..model import ExportSafeRegion

    if type(settings.safe_region) is not ExportSafeRegion:
        raise ValueError("Unknown export Safe Region mode")
    if settings.safe_region is ExportSafeRegion.OFF:
        return SafeRegionGeometry(), 0
    if (
        settings.aspect is not VideoAspect.PORTRAIT
        or settings.extent is not ExportExtent.FULL_FRAME
    ):
        raise ValueError("Safe Region requires Portrait Full frame")
    force_plot_lifts = {
        ExportSafeRegion.PORTRAIT_SOCIAL_A: 80,
        ExportSafeRegion.PORTRAIT_SOCIAL_B: 160,
        ExportSafeRegion.PORTRAIT_SOCIAL_C: 240,
    }
    width, height = canvas_dimensions(settings)
    return SafeRegionGeometry(
        side_inset=round(72 * width / 1080),
        force_plot_lift=round(force_plot_lifts[settings.safe_region] * height / 1920),
    ), round(max(force_plot_lifts.values()) * height / 1920)


def resolve_geometry(settings: ExportSettings) -> ExportGeometry:
    """Resolve native content size or Full-frame scaling and placement from metadata.

    Args:
        settings: Typed layout, aspect, extent and optional retained placement.

    Returns:
        Immutable pixel geometry and scaled Safe Region instrument offsets.
        Content area retains exact native dimensions, with zero offsets and no
        cropping, scaling, rounding or padding. Compact profiles retain their
        named edge/corner while fitting additional side clearance and force plot lift.

    Raises:
        ValueError: Format, extent, placement or Safe Region mode is unsupported,
            or dimensions are not even.
    """
    plugin = PLUGINS[settings.layout]
    plugin.positions(settings.aspect)
    if type(settings.extent) is not ExportExtent or settings.extent not in plugin.supported_extents(
        settings.aspect,
    ):
        raise ValueError("Unsupported export extent for layout and format")
    safe_region, _ = _safe_region_geometry(settings)
    x, y, width, height = export_region(settings)
    content = plugin.content_area(settings.aspect)
    if settings.extent is ExportExtent.CONTENT_AREA:
        assert content is not None
        geometry = ExportGeometry(
            content.dimensions,
            content.dimensions,
            (0, 0),
            safe_region,
        )
    else:
        geometry = ExportGeometry(
            canvas_dimensions(settings),
            (width, height),
            (x, y),
            safe_region,
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
