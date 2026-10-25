"""Shared drawing primitives; layout geometry stays with each profile.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words WINDIR segoeui segoeuib

from __future__ import annotations

from typing import TYPE_CHECKING
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from ..model import ExportChannel, ExportTimeline

import os
from pathlib import Path
from ride_forces_analyzer.i18n import tr

FONT_FILE = "segoeui.ttf"  # Regular Windows font file.
TICK_FONT_FILE = "segoeui.ttf"  # Scale label Windows font file.
LABEL_FONT_SIZE = 30  # Channel title and unavailable-value size in pixels.
NUMBER_FONT_SIZE = 76  # Main force readout size in pixels.
SMALL_FONT_SIZE = 24  # Hints and footer size in pixels.
TICK_FONT_SIZE = 19  # Scale and time-axis label size in pixels.
CHANNEL_COLORS = ("#00ceff", "#ebd36a", "#ffa044")  # Vertical, lateral and longitudinal colors.
PANEL_CORNER_RADIUS = 36  # Rounded panel corner radius in pixels.
PANEL_FILL = (7, 15, 25, 210)  # Translucent panel RGBA fill.
PANEL_OUTLINE = (200, 225, 245, 135)  # Panel border RGBA color.
PANEL_OUTLINE_WIDTH = 2  # Panel border thickness in pixels.
TEXT_OUTLINE_WIDTH = 1  # Glyph outline thickness in pixels.
TEXT_OUTLINE_COLOR = (0, 0, 0, 230)  # Glyph outline RGBA color.

COLORS = CHANNEL_COLORS
ACCELERATION_COLOR = "#35f58a"  # Positive longitudinal data.
BRAKING_COLOR = "#ff4545"  # Negative longitudinal data.


def lateral_x(channel: ExportChannel, value: float, left: float, right: float) -> float:
    """Use equal left/right scale with negative forces left of the center.

    Args:
        channel: Prepared channel whose units, bounds and availability govern the result.
        value: Candidate value to validate, format or store.
        left: Left boundary in the layout's coordinate system.
        right: Right boundary in the layout's coordinate system.

    Returns:
        Horizontal drawing coordinate on the lateral-force scale.
    """
    extent = max(abs(channel.low), abs(channel.high))
    return (left + right) / 2 + value / extent * (right - left) / 2


class Drawing:
    """Share layout typography and alpha-preserving drawing effects.

    Attributes:
        font_file: Font resource used for the layout's main labels and values.
        tick_font_file: Font resource used for scale ticks.
        label_size: Layout dimension for label size, in native pixels unless specified
            otherwise.
        number_size: Layout dimension for number size, in native pixels unless specified
            otherwise.
        small_size: Layout dimension for small size, in native pixels unless specified
            otherwise.
        tick_size: Layout dimension for tick size, in native pixels unless specified
            otherwise.
        channel_colors: Drawing color or palette for channel colors.
        panel_radius: Layout dimension for panel radius, in native pixels unless specified
            otherwise.
        panel_fill: Drawing color or palette for panel fill.
        panel_outline: Drawing color or palette for panel outline.
        panel_outline_width: Layout dimension for panel outline width, in native pixels
            unless specified otherwise.
        text_stroke_width: Layout dimension for text stroke width, in native pixels unless
            specified otherwise.
        text_stroke_color: Drawing color or palette for text stroke color.
        timeline: Bound video timeline containing the source interval and export settings.
        width: Width in the pixel or coordinate units declared by this operation.
        height: Height in the pixel or coordinate units declared by this operation.
        label: Human-readable label.
        number: Font used for numeric readouts.
        small: Font used for secondary text.
        tick: Font used for scale ticks.
        base: Prepared static layout image copied before per-frame drawing.
    """

    font_file = FONT_FILE
    tick_font_file = TICK_FONT_FILE
    label_size = LABEL_FONT_SIZE
    number_size = NUMBER_FONT_SIZE
    small_size = SMALL_FONT_SIZE
    tick_size = TICK_FONT_SIZE
    channel_colors = CHANNEL_COLORS
    panel_radius = PANEL_CORNER_RADIUS
    panel_fill = PANEL_FILL
    panel_outline = PANEL_OUTLINE
    panel_outline_width = PANEL_OUTLINE_WIDTH
    text_stroke_width = TEXT_OUTLINE_WIDTH
    text_stroke_color = TEXT_OUTLINE_COLOR

    def __init__(self, timeline: ExportTimeline, width: int, height: int) -> None:
        """Initialize drawing and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.
            width: Width in the pixel or coordinate units declared by this operation.
            height: Height in the pixel or coordinate units declared by this operation.

        Returns:
            None.
        """
        self.timeline = timeline
        self.width, self.height = width, height
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / self.font_file
        self.label = self._font(font, self.label_size)
        self.number = self._font(font, self.number_size)
        self.small = self._font(font, self.small_size)
        self.tick = self._font(font.with_name(self.tick_font_file), self.tick_size)
        self.base = Image.new("RGBA", (width, height))

    def _tr(self, source: str, *values: object) -> str:
        return tr(source, *values, language=self.timeline.settings.language)

    def render(self, frame: int) -> Image.Image:
        """Render the overlay at the requested source position.

        Args:
            frame: Zero-based output video frame index.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
        return self.render_position(self.timeline.sample_position(frame))

    def render_position(self, position: float) -> Image.Image:
        """Render the layout at a fractional source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.

        Raises:
            NotImplementedError: If the concrete layout does not implement this rendering
                operation.
        """
        raise NotImplementedError

    @staticmethod
    def _font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return (
            ImageFont.truetype(str(path), size)
            if path.is_file()
            else ImageFont.load_default(size=size)
        )

    @classmethod
    def _panel(cls, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
        draw.rounded_rectangle(
            box,
            radius=cls.panel_radius,
            fill=cls.panel_fill,
            outline=cls.panel_outline,
            width=cls.panel_outline_width,
        )

    @classmethod
    def _text(
        cls,
        draw: ImageDraw.ImageDraw,
        xy: tuple[float, float],
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        color: str,
        anchor: str | None = None,
    ) -> None:
        draw.text(
            xy,
            text,
            font=font,
            fill=color,
            anchor=anchor,
            stroke_width=cls.text_stroke_width,
            stroke_fill=cls.text_stroke_color,
        )
