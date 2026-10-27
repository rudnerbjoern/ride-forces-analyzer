"""Compose layout regions into transparent or opaque video frames; no layout drawing.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words LANCZOS

from PIL import Image
from .model import ExportExtent, VideoOutput, ExportTimeline
from .layouts import create_renderer, resolve_geometry

WIDTH, HEIGHT, COLUMN_WIDTH = 3840, 2160, 960
COLUMN_X = WIDTH - COLUMN_WIDTH


class OverlayRenderer:
    """Overlay renderer contract and owned data.

    Attributes:
        timeline: Bound video timeline containing the source interval and export settings.
        renderer: Layout renderer bound to this object's immutable video timeline.
        geometry: Fixed output dimensions and placement for the complete export.
    """

    def __init__(self, timeline: ExportTimeline) -> None:
        """Initialize overlay renderer and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.

        Returns:
            None.
        """
        self.timeline = timeline
        self.renderer = create_renderer(timeline)
        self.geometry = resolve_geometry(timeline.settings)

    def render_region(self, frame: int) -> Image.Image:
        """Render the active overlay region for an output frame.

        Args:
            frame: Zero-based output video frame index.

        Returns:
            Native RGBA content, or the scaled layout region for Full frame.

        Raises:
            ValueError: The plugin's image size differs from its native Content area metadata.
        """
        return self._render_region_at(self.timeline.sample_position(frame))

    def _render_region_at(self, position: float) -> Image.Image:
        image = self.renderer.render_position(position)
        if self.timeline.settings.extent is ExportExtent.CONTENT_AREA:
            if image.size != self.geometry.render_size:
                raise ValueError("Renderer output does not match native content dimensions")
        elif image.size != self.geometry.render_size:
            image = image.resize(self.geometry.render_size, Image.Resampling.LANCZOS)
        if self.timeline.settings.output == VideoOutput.OPAQUE:
            background = Image.new("RGBA", image.size, (0, 0, 0, 255))
            return Image.alpha_composite(background, image)
        return image

    def render_frame(self, frame: int) -> Image.Image:
        """Render an output frame on its resolved transparent or opaque canvas.

        Args:
            frame: Zero-based output video frame index.

        Returns:
            RGBA image at the selected extent's final output dimensions.

        Raises:
            ValueError: The frame is outside the timeline, or native dimensions mismatch.
        """
        return self.render_sample(self.timeline.sample_position(frame))

    def render_sample(self, position: float) -> Image.Image:
        """Render a production image at an exact source sample.

        Args:
            position: Fractional source-sample position.

        Returns:
            RGBA image at the selected extent's final output dimensions.

        Raises:
            ValueError: Sample is outside the prepared interval, or native dimensions mismatch.
        """
        if not self.timeline.first <= position <= self.timeline.last:
            raise ValueError("Preview sample outside prepared interval")
        region = self._render_region_at(position)
        if self.timeline.settings.extent is ExportExtent.CONTENT_AREA:
            return region
        alpha = 0 if self.timeline.settings.output == VideoOutput.TRANSPARENT else 255
        canvas = Image.new("RGBA", self.geometry.output_size, (0, 0, 0, alpha))
        canvas.alpha_composite(region, self.geometry.offset)
        return canvas
