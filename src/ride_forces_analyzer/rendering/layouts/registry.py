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
from .capsule import PLUGIN as CAPSULE
from .orbit import PLUGIN as ORBIT
from .column import PLUGIN as COLUMN
from .contracts import LayoutPlugin, LayoutPosition, LayoutRenderer, Region

if TYPE_CHECKING:
    from ..model import ExportLayout, ExportSettings, ExportTimeline

PLUGINS: Mapping[ExportLayout, LayoutPlugin] = MappingProxyType(
    {plugin.key: plugin for plugin in (RIBBON, CORNERS, CAPSULE, ORBIT, COLUMN)},
)
REGIONS = {
    key: plugin.landscape.regions[plugin.landscape.default] for key, plugin in PLUGINS.items()
}


def export_region(settings: ExportSettings) -> Region:
    plugin = PLUGINS[settings.layout]
    positions = plugin.landscape if settings.aspect == "landscape" else plugin.portrait
    position = positions.default if settings.position is None else settings.position
    if type(position) is not LayoutPosition or position not in positions.regions:
        raise ValueError("Unsupported export position for layout and format")
    return positions.regions[position]


def create_renderer(timeline: ExportTimeline) -> LayoutRenderer:
    return PLUGINS[timeline.settings.layout].create(timeline)
