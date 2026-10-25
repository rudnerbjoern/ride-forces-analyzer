"""Original four-panel force/orientation column.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words WINDIR segoeui

from __future__ import annotations

from typing import TYPE_CHECKING
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from ..model import ExportChannel, ExportTimeline

from math import ceil, floor
import os
from pathlib import Path
from ride_forces_analyzer.formatting.time import format_sample_time
from ride_forces_analyzer.i18n import tr
from .common import ACCELERATION_COLOR, BRAKING_COLOR
from .contracts import ExportLayout, LayoutPlugin, LayoutPosition, LayoutPositions

FONT_FILE = "segoeui.ttf"  # Regular Windows font file.
FONT_SIZE = 25  # Hint, scale and clock text size.
LARGE_FONT_SIZE = 37  # Channel title and current-value text size.
CANVAS_WIDTH = 3840  # Reference landscape canvas width.
NATIVE_SIZE = (960, 2160)  # Native column drawing dimensions.
LANDSCAPE_POSITIONS = LayoutPositions(  # Landscape regions: x, y, width, height.
    {LayoutPosition.LEFT: (0, 0, 960, 2160), LayoutPosition.RIGHT: (2880, 0, 960, 2160)},
    default=LayoutPosition.RIGHT,
)
PORTRAIT_POSITIONS = LayoutPositions(  # Portrait regions: x, y, width, height.
    {LayoutPosition.LEFT: (108, 300, 1440, 3240), LayoutPosition.RIGHT: (612, 300, 1440, 3240)},
    default=LayoutPosition.RIGHT,
)
BACKGROUND_COLOR = (0, 0, 0, 255)  # Opaque column background RGBA.
CHANNEL_COLORS = (
    "#8edce1",
    "#ebd36a",
    "#dba8e0",
    "#e9a571",
)  # Vertical, lateral, longitudinal and orientation colors.
PANEL_HEIGHT = 540  # Vertical spacing and height per instrument.
LEGEND_LINE = (26, 37, 63, 37)  # Color legend line relative to panel top.
LEGEND_WIDTH = 4  # Color legend line thickness.
TITLE_POSITION = (76, 15)  # Channel title relative to panel top.
HINT_POSITION = (76, 64)  # Channel hint relative to panel top.
HINT_COLOR = "#9da2a8"  # Channel hint text color.
PLOT_BOUNDS = (94, 116, 934, 474)  # Plot rectangle relative to panel top.
PLOT_COLOR = "#141214"  # Plot fill color.
PLOT_OUTLINE_COLOR = "#85858a"  # Plot border color.
RULE_WIDTH = 2  # Plot border, grid and cursor thickness.
GRID_COLOR = "#3b393e"  # Force grid color.
SCALE_COLOR = "#dddddd"  # Scale and clock text color.
SCALE_LEFT_GAP = 12  # Gap before vertical-axis numbers and time label.
CURSOR_COLOR = "#dddddd"  # Current-time cursor color.
VALUE_POSITION = (934, 17)  # Current-value anchor relative to panel top.
VALUE_COLOR = "#eeeeee"  # Current-value text color.
TRACE_WIDTH = 3  # Force trace thickness.
SINGLE_POINT_RADIUS = 2  # Marker radius for a single available sample.
CLOCK_TOP = 484  # Clock text offset from panel top.

WIDTH = CANVAS_WIDTH
COLUMN_WIDTH, HEIGHT = NATIVE_SIZE
COLUMN_X = WIDTH - COLUMN_WIDTH


LEFT_TEXT_ANCHOR = "rm"  # Right-middle anchor for labels before plots.
VALUE_TEXT_ANCHOR = "ra"  # Right-aligned current value anchor.
CLOCK_TEXT_ANCHOR = "ma"  # Centered clock label anchor.


class ColumnRenderer:
    """Column renderer contract and owned data.

    Attributes:
        timeline: Bound video timeline containing the source interval and export settings.
        font: Font used for regular layout text.
        large: Font used for prominent values.
        base: Prepared static layout image copied before per-frame drawing.
    """

    def __init__(self, timeline: ExportTimeline) -> None:
        """Initialize column renderer and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.

        Returns:
            None.
        """
        self.timeline = timeline
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / FONT_FILE
        self.font = (
            ImageFont.truetype(str(font), FONT_SIZE)
            if font.is_file()
            else ImageFont.load_default(size=FONT_SIZE)
        )
        self.large = (
            ImageFont.truetype(str(font), LARGE_FONT_SIZE)
            if font.is_file()
            else ImageFont.load_default(size=LARGE_FONT_SIZE)
        )
        self.base = Image.new("RGBA", NATIVE_SIZE, BACKGROUND_COLOR)
        draw = ImageDraw.Draw(self.base)
        for row, channel in enumerate(timeline.channels):
            y = row * PANEL_HEIGHT
            draw.line(
                (LEGEND_LINE[0], y + LEGEND_LINE[1], LEGEND_LINE[2], y + LEGEND_LINE[3]),
                fill=CHANNEL_COLORS[row],
                width=LEGEND_WIDTH,
            )
            draw.text(
                (TITLE_POSITION[0], y + TITLE_POSITION[1]),
                tr(channel.name, language=timeline.settings.language),
                font=self.large,
                fill=CHANNEL_COLORS[row],
            )
            draw.text(
                (HINT_POSITION[0], y + HINT_POSITION[1]),
                tr(
                    "− Left / + Right" if row == 1 else channel.hint,
                    language=timeline.settings.language,
                ),
                font=self.font,
                fill=HINT_COLOR,
            )
            box = self.plot_box(row)
            draw.rectangle(box, fill=PLOT_COLOR, outline=PLOT_OUTLINE_COLOR, width=RULE_WIDTH)
            for tick in channel.ticks:
                py = self.value_y(channel, tick, row)
                draw.line(
                    (box[0], py, box[2], py),
                    fill=SCALE_COLOR if row == 0 and tick == channel.reference else GRID_COLOR,
                    width=RULE_WIDTH,
                )
                draw.text(
                    (box[0] - SCALE_LEFT_GAP, py),
                    f"{tick:g}{channel.unit}",
                    font=self.font,
                    fill=SCALE_COLOR,
                    anchor=LEFT_TEXT_ANCHOR,
                )
            cursor = (box[0] + box[2]) / 2
            draw.line((cursor, box[1], cursor, box[3]), fill=CURSOR_COLOR, width=RULE_WIDTH)

    @staticmethod
    def plot_box(row: int) -> tuple[int, int, int, int]:
        """Return the channel plot rectangle in layout pixels.

        Args:
            row: Channel or panel row selected for rendering.

        Returns:
            The channel plot rectangle in layout pixels.
        """
        y = row * PANEL_HEIGHT
        return (PLOT_BOUNDS[0], y + PLOT_BOUNDS[1], PLOT_BOUNDS[2], y + PLOT_BOUNDS[3])

    def value_y(self, channel: ExportChannel, value: float, row: int) -> float:
        """Map a channel value to its vertical layout coordinate.

        Args:
            channel: Prepared channel whose units, bounds and availability govern the result.
            value: Candidate value to validate, format or store.
            row: Channel or panel row selected for rendering.

        Returns:
            Vertical drawing coordinate for the supplied channel value.
        """
        _, top, _, bottom = self.plot_box(row)
        fraction = (value - channel.low) / (channel.high - channel.low)
        if not channel.inverted:
            fraction = 1 - fraction
        return top + fraction * (bottom - top)

    def render_column(self, frame: int) -> Image.Image:
        """Render the four-panel column at the requested source position.

        Args:
            frame: Zero-based output video frame index.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
        return self.render_position(self.timeline.sample_position(frame))

    def trace_point(
        self,
        channel: ExportChannel,
        value: float,
        fraction: float,
        row: int,
    ) -> tuple[float, float]:
        """Map a channel value and normalized time coordinate to a plotted point.

        Args:
            channel: Prepared channel whose units, bounds and availability govern the result.
            value: Candidate value to validate, format or store.
            fraction: Normalized time coordinate within the plotted interval.
            row: Channel or panel row selected for rendering.

        Returns:
            Horizontal and vertical drawing coordinates of the plotted sample.
        """
        left, _, right, _ = self.plot_box(row)
        return left + fraction * (right - left), self.value_y(channel, value, row)

    def render_position(self, position: float) -> Image.Image:
        """Render the layout at a fractional source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.

        Raises:
            AssertionError: If a required internal invariant does not hold.
        """
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        rate = self.timeline.sample_rate
        half = self.timeline.settings.window_seconds * rate / 2
        left = position - half
        first = max(self.timeline.first, ceil(left))
        last = min(self.timeline.last, floor(position + half))
        for row, channel in enumerate(self.timeline.channels):
            value = self.timeline.value_at(channel, position)
            text = (
                tr("Unavailable", language=self.timeline.settings.language)
                if value is None
                else tr(
                    "{0:.1f} {1}" if channel.unit == "g" else "{0:.2f} {1}",
                    value,
                    channel.unit,
                    language=self.timeline.settings.language,
                )
            )
            draw.text(
                (VALUE_POSITION[0], row * PANEL_HEIGHT + VALUE_POSITION[1]),
                text,
                font=self.large,
                fill=VALUE_COLOR,
                anchor=VALUE_TEXT_ANCHOR,
            )
            x0, _, x1, _ = self.plot_box(row)
            points: list[tuple[float, float]] = []
            for index in range(first, last + 1):
                sample = channel.values[index]
                if sample is None:
                    if len(points) > 1:
                        draw.line(points, fill=CHANNEL_COLORS[row], width=TRACE_WIDTH)
                    points = []
                    continue
                point = self.trace_point(channel, sample, (index - left) / (2 * half), row)
                if row == 2:
                    color = ACCELERATION_COLOR if sample >= 0 else BRAKING_COLOR
                    if points:
                        previous = channel.values[index - 1]
                        assert previous is not None
                        previous_color = ACCELERATION_COLOR if previous >= 0 else BRAKING_COLOR
                        if previous_color != color:
                            fraction = previous / (previous - sample)
                            zero = (
                                points[-1][0] + fraction * (point[0] - points[-1][0]),
                                self.value_y(channel, 0, row),
                            )
                            draw.line((points[-1], zero), fill=previous_color, width=TRACE_WIDTH)
                            draw.line((zero, point), fill=color, width=TRACE_WIDTH)
                        else:
                            draw.line((points[-1], point), fill=color, width=TRACE_WIDTH)
                    else:
                        px, py = point
                        draw.ellipse(
                            (
                                px - SINGLE_POINT_RADIUS,
                                py - SINGLE_POINT_RADIUS,
                                px + SINGLE_POINT_RADIUS,
                                py + SINGLE_POINT_RADIUS,
                            ),
                            fill=color,
                        )
                    points = [point]
                    continue
                points.append(point)
            if len(points) > 1:
                draw.line(points, fill=CHANNEL_COLORS[row], width=TRACE_WIDTH)
            elif points and row != 2:
                px, py = points[0]
                draw.ellipse(
                    (
                        px - SINGLE_POINT_RADIUS,
                        py - SINGLE_POINT_RADIUS,
                        px + SINGLE_POINT_RADIUS,
                        py + SINGLE_POINT_RADIUS,
                    ),
                    fill=CHANNEL_COLORS[row],
                )
            clock = format_sample_time(round(position) - self.timeline.replay_origin, rate)
            draw.text(
                ((x0 + x1) / 2, row * PANEL_HEIGHT + CLOCK_TOP),
                clock,
                font=self.font,
                fill=SCALE_COLOR,
                anchor=CLOCK_TEXT_ANCHOR,
            )
        return image


PLUGIN = LayoutPlugin(ExportLayout.COLUMN, LANDSCAPE_POSITIONS, PORTRAIT_POSITIONS, ColumnRenderer)
