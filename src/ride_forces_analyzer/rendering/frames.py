"""Compose layout regions into transparent or opaque video frames; no layout drawing.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words LANCZOS

from PIL import Image
from .model import ExportTimeline
from .layouts import create_renderer, export_region

WIDTH, HEIGHT, COLUMN_WIDTH = 3840, 2160, 960
COLUMN_X = WIDTH - COLUMN_WIDTH


class OverlayRenderer:
    def __init__(self, timeline: ExportTimeline) -> None:
        self.timeline = timeline
        self.renderer = create_renderer(timeline)

    def render_region(self, frame: int) -> Image.Image:
        return self._render_region_at(self.timeline.sample_position(frame))

    def _render_region_at(self, position: float) -> Image.Image:
        image = self.renderer.render_position(position)
        _, _, width, height = export_region(self.timeline.settings)
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        if self.timeline.settings.output == "opaque":
            background = Image.new("RGBA", image.size, (0, 0, 0, 255))
            return Image.alpha_composite(background, image)
        return image

    def render_frame(self, frame: int) -> Image.Image:
        return self.render_sample(self.timeline.sample_position(frame))

    def render_sample(self, position: float) -> Image.Image:
        if not self.timeline.first <= position <= self.timeline.last:
            raise ValueError("Preview sample outside prepared interval")
        alpha = 0 if self.timeline.settings.output == "transparent" else 255
        canvas = Image.new("RGBA", self.timeline.settings.dimensions, (0, 0, 0, alpha))
        x, y, _, _ = export_region(self.timeline.settings)
        canvas.alpha_composite(self._render_region_at(position), (x, y))
        return canvas
