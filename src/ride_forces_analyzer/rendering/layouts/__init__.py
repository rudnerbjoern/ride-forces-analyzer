"""Built-in layout plugins and their shared registry interface.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from .common import COLORS as COLORS, lateral_x as lateral_x
from .registry import (
    PLUGINS as PLUGINS,
    REGIONS as REGIONS,
    create_renderer as create_renderer,
    canvas_dimensions as canvas_dimensions,
    export_region as export_region,
)
