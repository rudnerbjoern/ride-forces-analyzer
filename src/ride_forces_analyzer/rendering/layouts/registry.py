"""Explicit offline layout registry; add built-in plugins here."""

from __future__ import annotations
from types import MappingProxyType
from typing import TYPE_CHECKING
from collections.abc import Mapping
from .ribbon import PLUGIN as RIBBON
from .corners import PLUGIN as CORNERS
from .capsule import PLUGIN as CAPSULE
from .orbit import PLUGIN as ORBIT
from .column import PLUGIN as COLUMN
from .contracts import LayoutPlugin, LayoutRenderer, Region

if TYPE_CHECKING:
    from ..model import ExportLayout, ExportSettings, ExportTimeline

PLUGINS: Mapping[ExportLayout, LayoutPlugin] = MappingProxyType(
    {plugin.key: plugin for plugin in (RIBBON, CORNERS, CAPSULE, ORBIT, COLUMN)},
)
REGIONS = {key: plugin.landscape for key, plugin in PLUGINS.items()}


def export_region(settings: ExportSettings) -> Region:
    plugin = PLUGINS[settings.layout]
    return plugin.landscape if settings.aspect == "landscape" else plugin.portrait


def create_renderer(timeline: ExportTimeline) -> LayoutRenderer:
    return PLUGINS[timeline.settings.layout].create(timeline)
