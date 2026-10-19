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
    """Use equal left/right scale with negative forces left of the center."""
    extent = max(abs(channel.low), abs(channel.high))
    return (left + right) / 2 + value / extent * (right - left) / 2


class Drawing:
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
        return self.render_position(self.timeline.sample_position(frame))

    def render_position(self, position: float) -> Image.Image:
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
