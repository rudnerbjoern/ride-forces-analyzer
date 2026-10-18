"""Built-in layout plugins and their shared registry interface."""

from .common import COLORS as COLORS, lateral_x as lateral_x
from .registry import (
    PLUGINS as PLUGINS,
    REGIONS as REGIONS,
    create_renderer as create_renderer,
    export_region as export_region,
)
