"""Shared three-channel time plots used by the ribbon and corners.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from ..model import ExportChannel, ExportTimeline

from math import ceil, floor
from .contracts import VideoAspect
from ride_forces_analyzer.rendering.airtime_colors import (
    VERTICAL_CONTEXT_COLORS as VERTICAL_CONTEXT_COLORS,
)
from ride_forces_analyzer.formatting.time import format_sample_time
from .common import ACCELERATION_COLOR, BRAKING_COLOR, Drawing, lateral_x


class ChartRenderer(Drawing):
    """Chart renderer contract and owned data.

    Attributes:
        native_size: Layout dimension for native size, in native pixels unless specified
            otherwise.
        left_text_anchor: Horizontal anchor for left-aligned text.
        right_text_anchor: Horizontal anchor for right-aligned text.
        top_scale_anchor: Upper anchor for the instrument scale.
        stacked: Whether force cards use a vertical arrangement.
        plot_left: Layout coordinate for plot left in the owning view or renderer.
        card_spacing: Spacing between force cards in native pixels.
        card_height: Layout dimension for card height, in native pixels unless specified
            otherwise.
        card_bottom_margin: Layout dimension for card bottom margin, in native pixels
            unless specified otherwise.
        plot_top: Layout coordinate for plot top in the owning view or renderer.
        plot_right: Layout coordinate for plot right in the owning view or renderer.
        plot_bottom: Layout coordinate for plot bottom in the owning view or renderer.
        text_left: Layout coordinate for text left in the owning view or renderer.
        title_top: Layout coordinate for title top in the owning view or renderer.
        value_top: Layout coordinate for value top in the owning view or renderer.
        hint_top: Layout coordinate for hint top in the owning view or renderer.
        hint_color: Drawing color or palette for hint color.
        separator_top: Layout coordinate for separator top in the owning view or renderer.
        separator_bottom: Layout coordinate for separator bottom in the owning view or
            renderer.
        separator_color: Drawing color or palette for separator color.
        rule_width: Layout dimension for rule width, in native pixels unless specified
            otherwise.
        grid_color: Drawing color or palette for grid color.
        zero_grid_color: Drawing color or palette for zero grid color.
        scale_color: Drawing color or palette for scale color.
        scale_left_gap: Layout dimension for scale left gap, in native pixels unless
            specified otherwise.
        scale_top_gap: Layout dimension for scale top gap, in native pixels unless
            specified otherwise.
        cursor_color: Drawing color or palette for cursor color.
        footer_panel_bottom: Layout coordinate for footer panel bottom in the owning view
            or renderer.
        footer_portrait_extra: Additional footer space for portrait output, in native
            pixels.
        footer_landscape_extra: Additional footer space for landscape output, in native
            pixels.
        footer_rule_inset: Layout dimension for footer rule inset, in native pixels unless
            specified otherwise.
        footer_rule_offset: Layout dimension for footer rule offset, in native pixels
            unless specified otherwise.
        footer_rule_color: Drawing color or palette for footer rule color.
        footer_text_bottom: Layout coordinate for footer text bottom in the owning view or
            renderer.
        footer_text_color: Drawing color or palette for footer text color.
        trace_outline_color: Drawing color or palette for trace outline color.
        trace_outline_width: Layout dimension for trace outline width, in native pixels
            unless specified otherwise.
        trace_width: Layout dimension for trace width, in native pixels unless specified
            otherwise.
        marker_radius: Layout dimension for marker radius, in native pixels unless
            specified otherwise.
        marker_outline_color: Drawing color or palette for marker outline color.
        marker_outline_width: Layout dimension for marker outline width, in native pixels
            unless specified otherwise.
        time_text_color: Drawing color or palette for time text color.
        time_left_gap: Layout dimension for time left gap, in native pixels unless
            specified otherwise.
        time_bottom_gap: Layout dimension for time bottom gap, in native pixels unless
            specified otherwise.
    """

    native_size: tuple[int, int]
    left_text_anchor: str
    right_text_anchor: str
    top_scale_anchor: str
    stacked: bool
    plot_left: int
    card_spacing: int
    card_height: int
    card_bottom_margin: int
    plot_top: int
    plot_right: int
    plot_bottom: int
    text_left: int
    title_top: int
    value_top: int
    hint_top: int
    hint_color: str
    separator_top: int
    separator_bottom: int
    separator_color: tuple[int, ...]
    rule_width: int
    grid_color: tuple[int, ...]
    zero_grid_color: tuple[int, ...]
    scale_color: str
    scale_left_gap: int
    scale_top_gap: int
    cursor_color: tuple[int, ...]
    footer_panel_bottom: int
    footer_portrait_extra: int
    footer_landscape_extra: int
    footer_rule_inset: int
    footer_rule_offset: int
    footer_rule_color: tuple[int, ...]
    footer_text_bottom: int
    footer_text_color: str
    trace_outline_color: tuple[int, ...]
    trace_outline_width: int
    trace_width: int
    marker_radius: int
    marker_outline_color: str
    marker_outline_width: int
    time_text_color: str
    time_left_gap: int
    time_bottom_gap: int

    def __init__(self, timeline: ExportTimeline) -> None:
        """Initialize chart renderer and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.

        Returns:
            None.
        """
        super().__init__(timeline, *self.native_size)
        draw = ImageDraw.Draw(self.base)
        if not self.stacked:
            self._panel(draw, (0, 0, self.width - 1, self.height - 1))
        for row, channel in enumerate(timeline.channels[:3]):
            x, y, w, h = self.card_box(row)
            if self.stacked:
                self._panel(draw, (x, y, x + w - 1, y + h - 1))
            elif row:
                draw.line(
                    (x, self.separator_top, x, self.height - self.separator_bottom),
                    fill=self.separator_color,
                    width=self.rule_width,
                )
            self._text(
                draw,
                (x + self.text_left, y + self.title_top),
                self._tr(channel.name).upper(),
                self.label,
                self.channel_colors[row],
            )
            box = self.plot_box(row)
            for tick in channel.ticks:
                if row == 1:
                    px = lateral_x(channel, tick, box[0], box[2])
                    draw.line(
                        (px, box[1], px, box[3]),
                        fill=(self.zero_grid_color if tick == 0 else self.grid_color),
                        width=self.rule_width,
                    )
                    self._text(
                        draw,
                        (px, box[1] - self.scale_top_gap),
                        f"{tick:g}",
                        self.tick,
                        self.scale_color,
                        self.top_scale_anchor,
                    )
                    continue
                py = self.value_y(channel, tick, row)
                draw.line(
                    (box[0], py, box[2], py),
                    fill=(self.zero_grid_color if tick == 0 else self.grid_color),
                    width=self.rule_width,
                )
                self._text(
                    draw,
                    (box[0] - self.scale_left_gap, py),
                    f"{tick:g}",
                    self.tick,
                    self.scale_color,
                    self.left_text_anchor,
                )
            if row == 1:
                cursor = (box[1] + box[3]) / 2
                draw.line(
                    (box[0], cursor, box[2], cursor),
                    fill=self.cursor_color,
                    width=self.rule_width,
                )
            else:
                cursor = (box[0] + box[2]) / 2
                draw.line(
                    (cursor, box[1], cursor, box[3]),
                    fill=self.cursor_color,
                    width=self.rule_width,
                )
        footer = self.height - self.footer_panel_bottom
        if self.stacked:
            top = footer - (
                self.footer_portrait_extra
                if timeline.settings.aspect is VideoAspect.PORTRAIT
                else self.footer_landscape_extra
            )
            self._panel(draw, (0, top, self.width - 1, self.height - 1))
        else:
            draw.line(
                (
                    self.footer_rule_inset,
                    footer - self.footer_rule_offset,
                    self.width - self.footer_rule_inset,
                    footer - self.footer_rule_offset,
                ),
                fill=self.footer_rule_color,
                width=self.rule_width,
            )

    def card_box(self, row: int) -> tuple[int, int, int, int]:
        """Return the channel card rectangle in layout pixels.

        Args:
            row: Channel or panel row selected for rendering.

        Returns:
            The channel card rectangle in layout pixels.
        """
        if self.stacked:
            return (0, row * self.card_spacing, self.width, self.card_height)
        return (row * (self.width // 3), 0, self.width // 3, self.height - self.card_bottom_margin)

    def plot_box(self, row: int) -> tuple[int, int, int, int]:
        """Return the channel plot rectangle in layout pixels.

        Args:
            row: Channel or panel row selected for rendering.

        Returns:
            The channel plot rectangle in layout pixels.
        """
        x, y, w, h = self.card_box(row)
        left = self.plot_left
        return (x + left, y + self.plot_top, x + w - self.plot_right, y + h - self.plot_bottom)

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
        return top + (fraction if channel.inverted else 1 - fraction) * (bottom - top)

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
        left, top, right, bottom = self.plot_box(row)
        if row == 1:
            return lateral_x(channel, value, left, right), bottom - fraction * (bottom - top)
        return left + fraction * (right - left), self.value_y(channel, value, row)

    def render_position(self, position: float) -> Image.Image:
        """Render the layout at a fractional source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        half = self.timeline.settings.window_seconds * self.timeline.sample_rate / 2
        left = position - half
        first = max(self.timeline.first, ceil(left))
        last = min(self.timeline.last, floor(position + half))
        for row, channel in enumerate(self.timeline.channels[:3]):
            value = self.timeline.value_at(channel, position)
            x, y, _, _ = self.card_box(row)
            readout = self._tr("Unavailable") if value is None else self._tr("{0:+.1f} g", value)
            self._text(
                draw,
                (x + self.text_left, y + self.value_top),
                readout,
                self.label if value is None else self.number,
                self.channel_colors[row],
            )
            hint = (
                ("Unavailable" if value is None else self.timeline.context_at(position))
                if row == 0
                else "Unavailable"
                if value is None
                else ("Right" if value >= 0 else "Left")
                if row == 1
                else ("Acceleration" if value >= 0 else "Braking")
            )
            self._text(
                draw,
                (x + self.text_left, y + self.hint_top),
                self._tr(hint),
                self.small,
                VERTICAL_CONTEXT_COLORS.get(hint, self.hint_color) if row == 0 else self.hint_color,
            )
            x0, _, x1, bottom = self.plot_box(row)
            points: list[tuple[float, float]] = []

            def paint() -> None:
                if len(points) > 1:
                    draw.line(points, fill=self.trace_outline_color, width=self.trace_outline_width)
                    if row != 2:
                        draw.line(points, fill=self.channel_colors[row], width=self.trace_width)
                        return
                    zero_y = self.value_y(channel, 0, row)
                    for start, end in zip(points, points[1:]):
                        start_color = ACCELERATION_COLOR if start[1] <= zero_y else BRAKING_COLOR
                        end_color = ACCELERATION_COLOR if end[1] <= zero_y else BRAKING_COLOR
                        if start_color == end_color:
                            draw.line((start, end), fill=start_color, width=self.trace_width)
                        else:
                            fraction = (zero_y - start[1]) / (end[1] - start[1])
                            zero = (start[0] + fraction * (end[0] - start[0]), zero_y)
                            draw.line((start, zero), fill=start_color, width=self.trace_width)
                            draw.line((zero, end), fill=end_color, width=self.trace_width)

            for index in range(first, last + 1):
                sample = channel.values[index]
                if sample is None:
                    paint()
                    points = []
                else:
                    points.append(
                        self.trace_point(channel, sample, (index - left) / (2 * half), row),
                    )
            paint()
            if value is not None:
                cx, cy = self.trace_point(channel, value, 0.5, row)
                draw.ellipse(
                    (
                        cx - self.marker_radius,
                        cy - self.marker_radius,
                        cx + self.marker_radius,
                        cy + self.marker_radius,
                    ),
                    fill=(
                        (ACCELERATION_COLOR if value >= 0 else BRAKING_COLOR)
                        if row == 2
                        else self.channel_colors[row]
                    ),
                    outline=self.marker_outline_color,
                    width=self.marker_outline_width,
                )
            if row == 1:
                box = self.plot_box(row)
                self._text(
                    draw,
                    (x0 - self.time_left_gap, (box[1] + bottom) / 2),
                    self._tr("Time ↑"),
                    self.tick,
                    self.time_text_color,
                    self.left_text_anchor,
                )
            else:
                self._text(
                    draw,
                    (x1, bottom + self.time_bottom_gap),
                    self._tr("Time →"),
                    self.tick,
                    self.time_text_color,
                    self.right_text_anchor,
                )
        footer = self.height - self.footer_text_bottom
        clock = format_sample_time(
            round(position) - self.timeline.replay_origin,
            self.timeline.sample_rate,
        )
        angle = self.timeline.value_at(self.timeline.channels[3], position)
        tilt = self._tr("Tilt unavailable") if angle is None else self._tr("Tilt {0:.1f}°", angle)
        self._text(
            draw,
            (self.text_left, footer),
            self._tr("Replay {0}", clock),
            self.small,
            self.footer_text_color,
        )
        self._text(
            draw,
            (self.width - self.text_left, footer),
            tilt,
            self.small,
            self.footer_text_color,
            self.right_text_anchor,
        )
        return image
