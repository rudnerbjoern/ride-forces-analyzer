"""G-Orbit: force arcs, signed peak hold and a 0–180 degree tilt instrument.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words segoeui segoeuib

from __future__ import annotations

from typing import TYPE_CHECKING
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from ..model import ExportTimeline

from math import cos, sin, radians
from ..peaks import PeakEnvelope
from .common import ACCELERATION_COLOR, BRAKING_COLOR, Drawing
from .contracts import LayoutPlugin


FONT_FILE = "segoeui.ttf"  # Regular Windows font file.
TICK_FONT_FILE = "segoeuib.ttf"  # Scale label Windows font file.
LABEL_FONT_SIZE = 30  # Channel title and unavailable-value size in pixels.
NUMBER_FONT_SIZE = 54  # Main force readout size in pixels.
SMALL_FONT_SIZE = 24  # Hints and footer size in pixels.
TICK_FONT_SIZE = 19  # Scale and time-axis label size in pixels.
CHANNEL_COLORS = ("#00ceff", "#ebd36a", "#ffa044")  # Vertical, lateral and longitudinal colors.
PANEL_CORNER_RADIUS = 36  # Rounded panel corner radius in pixels.
PANEL_FILL = (7, 15, 25, 210)  # Translucent panel RGBA fill.
PANEL_OUTLINE = (200, 225, 245, 135)  # Panel border RGBA color.
PANEL_OUTLINE_WIDTH = 2  # Panel border thickness in pixels.
TEXT_OUTLINE_WIDTH = 1  # Glyph outline thickness in pixels.
TEXT_OUTLINE_COLOR = (0, 0, 0, 230)  # Glyph outline RGBA color.
NATIVE_SIZE = (800, 800)  # Square native drawing dimensions.
LANDSCAPE_REGION = (192, 1260, 800, 800)  # Landscape placement: x, y, width, height.
PORTRAIT_REGION = (240, 2412, 1188, 1188)  # Portrait placement: x, y, width, height.
CENTER = (400, 400)  # Shared center of all circular instruments.
BACKGROUND_INSET = 2  # Circular background inset from the square canvas.
FORCE_ARCS = (
    (0, 290, 94, 266),
    (2, 290, -86, 86),
    (1, 212, 180, 360),
)  # Channel, outer radius, start and end angle per track.
FORCE_STROKE_WIDTH = 30  # Force track thickness; Pillow grows inward.
TRACK_COLOR = (210, 230, 245, 75)  # Inactive force track RGBA color.
PEAK_COLORS = ("#008cac", "#a8974c", "#ad6c2e")  # Muted signed peak colors per force channel.
PEAK_FILL_ALPHA = 65  # Peak segment overlay opacity from 0 to 255.
PEAK_HOLD_SECONDS = 1.5  # Source-time hold duration before release.
PEAK_RELEASE_G_PER_SECOND = 1.0  # Peak return speed toward zero.
PEAK_VISIBLE_THRESHOLD = 0.001  # Hide peak markers below this magnitude in g.
PEAK_MARKER_EXTENSION = 1  # Peak bar extension beyond each track edge.
PEAK_MARKER_WIDTH = 4  # Colored peak bar thickness.
PEAK_MARKER_OUTLINE_WIDTH = 8  # Peak bar dark outline thickness.
PEAK_MARKER_OUTLINE_COLOR = (0, 0, 0, 220)  # Peak bar outline RGBA color.
CURRENT_MARKER_EXTENSION = 3  # Current bar extension beyond each track edge.
CURRENT_MARKER_WIDTH = 6  # White current bar thickness.
CURRENT_MARKER_COLOR = "#ffffff"  # Current bar color.
CURRENT_MARKER_OUTLINE_WIDTH = 12  # Current bar dark outline thickness.
CURRENT_MARKER_OUTLINE_COLOR = (0, 0, 0, 245)  # Current bar outline RGBA color.
FORCE_TICK_INSET = 12  # Force scale tick extension inward from outer radius.
FORCE_TICK_OUTSET = 10  # Force scale tick extension outward from outer radius.
FORCE_TICK_WIDTH = 2  # Force scale tick thickness.
SCALE_COLOR = "#e4edf5"  # Scale numbers and ticks color.
FORCE_TICK_LABEL_OFFSET = 29  # Force scale number offset beyond outer radius.
READOUT_POSITIONS = (
    (280, 464),
    (400, 314),
    (520, 464),
)  # Vertical, lateral and longitudinal readout anchors.
TITLE_OFFSET_Y = -45  # Channel title offset from its readout anchor.
VALUE_OFFSET_Y = 10  # Force value offset from its readout anchor.
ORIENTATION_RADIUS = 338  # Outer radius of the orientation semicircle.
ORIENTATION_ARC_ANGLES = (-90, 90)  # Pillow angles spanning the right semicircle.
ORIENTATION_TICKS = (0, 90, 180)  # Visible measured orientation values in degrees.
ORIENTATION_COLOR = (235, 240, 250, 105)  # Orientation reference track RGBA color.
ORIENTATION_STROKE_WIDTH = 3  # Orientation reference track thickness.
ORIENTATION_TICK_EXTENSION = 5  # Orientation tick length on each side of the ring.
ORIENTATION_TICK_WIDTH = 2  # Orientation tick thickness.
ORIENTATION_LABEL_OFFSET = 20  # Degree label offset outside the ring.
ORIENTATION_BUG_INSET = 14  # Orientation bug tip distance inward.
ORIENTATION_BUG_OUTSET = 12  # Orientation bug base distance outward.
ORIENTATION_BUG_HALF_ANGLE = 2.5  # Half angular width of the triangular bug.
ORIENTATION_BUG_COLOR = "#ffffff"  # Orientation bug color.
TILT_TEXT_Y = 614  # Vertical position of the numeric tilt readout.
TILT_TEXT_COLOR = "#ffffff"  # Numeric tilt readout color.
QUADRANT_DEGREES = 90  # Angular travel per signed force direction.
VERTICAL_ZERO_ANGLE = 180  # Zero-force angle of the left track.
LATERAL_ZERO_ANGLE = 270  # Zero-force angle of the upper track.


TEXT_ANCHOR = "mm"  # Centered anchor for all instrument labels.


class OrbitRenderer(Drawing):
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

    def __init__(self, timeline: ExportTimeline) -> None:
        super().__init__(timeline, *NATIVE_SIZE)
        self.peaks = tuple(
            PeakEnvelope.prepare(
                channel.values,
                timeline.first,
                timeline.last,
                timeline.sample_rate,
                hold_seconds=PEAK_HOLD_SECONDS,
                release_g_per_second=PEAK_RELEASE_G_PER_SECOND,
            )
            for channel in timeline.channels[:3]
        )

    def orbit_angle(self, value: float, row: int = 0) -> float:
        """Map signed forces to their physical display direction on shared rings."""
        channel = self.timeline.channels[row]
        if row == 1:
            return LATERAL_ZERO_ANGLE + QUADRANT_DEGREES * value / max(
                abs(channel.low),
                abs(channel.high),
            )
        extent = channel.high if value >= 0 else -channel.low
        angle = QUADRANT_DEGREES * value / extent
        if row == 2:
            return -angle
        return VERTICAL_ZERO_ANGLE - angle if channel.inverted else VERTICAL_ZERO_ANGLE + angle

    @staticmethod
    def orientation_angle(value: float) -> float:
        """Keep measured 0–180 degrees on the right orientation semicircle."""
        return value - QUADRANT_DEGREES

    def render_position(self, position: float) -> Image.Image:
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (
                BACKGROUND_INSET,
                BACKGROUND_INSET,
                self.width - BACKGROUND_INSET - 1,
                self.height - BACKGROUND_INSET - 1,
            ),
            fill=PANEL_FILL,
            outline=PANEL_OUTLINE,
            width=PANEL_OUTLINE_WIDTH,
        )
        cx, cy = CENTER

        def point(radius: float, angle: float) -> tuple[float, float]:
            a = radians(angle)
            return cx + radius * cos(a), cy + radius * sin(a)

        # Two outer force halves and an upper inner half share one center.
        for row, radius, start, end in FORCE_ARCS:
            channel = self.timeline.channels[row]
            circle = (cx - radius, cy - radius, cx + radius, cy + radius)
            # Pillow strokes inward from this bounding circle, preserving the outer radius.
            stroke = FORCE_STROKE_WIDTH
            draw.arc(circle, start, end, fill=TRACK_COLOR, width=stroke)
            current = self.timeline.value_at(channel, position)
            if current is not None:
                peak_color = PEAK_COLORS[row]
                peaks = self.peaks[row].at(position, current)
                peak_layer = Image.new("RGBA", image.size)
                peak_draw = ImageDraw.Draw(peak_layer)
                for peak in peaks:
                    if abs(peak) < PEAK_VISIBLE_THRESHOLD:
                        continue
                    a, b = sorted((self.orbit_angle(0, row), self.orbit_angle(peak, row)))
                    color = (
                        (ACCELERATION_COLOR if peak >= 0 else BRAKING_COLOR)
                        if row == 2
                        else peak_color
                    )
                    peak_fill = (*bytes.fromhex(color[1:]), PEAK_FILL_ALPHA)
                    peak_draw.arc(circle, a, b, fill=peak_fill, width=stroke)
                image.alpha_composite(peak_layer)
                a, b = sorted((self.orbit_angle(0, row), self.orbit_angle(current, row)))
                color = (
                    (ACCELERATION_COLOR if current >= 0 else BRAKING_COLOR)
                    if row == 2
                    else CHANNEL_COLORS[row]
                )
                draw.arc(circle, a, b, fill=color, width=stroke)
                for peak in peaks:
                    if abs(peak) < PEAK_VISIBLE_THRESHOLD:
                        continue
                    peak_angle = self.orbit_angle(peak, row)
                    marker = (
                        *point(radius - stroke - PEAK_MARKER_EXTENSION, peak_angle),
                        *point(radius + PEAK_MARKER_EXTENSION, peak_angle),
                    )
                    draw.line(
                        marker,
                        fill=PEAK_MARKER_OUTLINE_COLOR,
                        width=PEAK_MARKER_OUTLINE_WIDTH,
                    )
                    color = (
                        (ACCELERATION_COLOR if peak >= 0 else BRAKING_COLOR)
                        if row == 2
                        else peak_color
                    )
                    draw.line(marker, fill=color, width=PEAK_MARKER_WIDTH)
                marker_angle = self.orbit_angle(current, row)
                marker = (
                    *point(radius - stroke - CURRENT_MARKER_EXTENSION, marker_angle),
                    *point(radius + CURRENT_MARKER_EXTENSION, marker_angle),
                )
                draw.line(
                    marker,
                    fill=CURRENT_MARKER_OUTLINE_COLOR,
                    width=CURRENT_MARKER_OUTLINE_WIDTH,
                )
                draw.line(marker, fill=CURRENT_MARKER_COLOR, width=CURRENT_MARKER_WIDTH)
            for tick in channel.ticks:
                a = self.orbit_angle(tick, row)
                draw.line(
                    (*point(radius - FORCE_TICK_INSET, a), *point(radius + FORCE_TICK_OUTSET, a)),
                    fill=SCALE_COLOR,
                    width=FORCE_TICK_WIDTH,
                )
                self._text(
                    draw,
                    point(radius + FORCE_TICK_LABEL_OFFSET, a),
                    f"{tick:g}",
                    self.tick,
                    SCALE_COLOR,
                    TEXT_ANCHOR,
                )
            x, y = READOUT_POSITIONS[row]
            self._text(
                draw,
                (x, y + TITLE_OFFSET_Y),
                self._tr(channel.name).upper(),
                self.small,
                CHANNEL_COLORS[row],
                TEXT_ANCHOR,
            )
            self._text(
                draw,
                (x, y + VALUE_OFFSET_Y),
                self._tr("Unavailable") if current is None else self._tr("{0:+.2f} g", current),
                self.label if current is None else self.number,
                CHANNEL_COLORS[row],
                TEXT_ANCHOR,
            )

        # A separate semicircle covers the measured orientation range of 0–180°.
        radius = ORIENTATION_RADIUS
        draw.arc(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            *ORIENTATION_ARC_ANGLES,
            fill=ORIENTATION_COLOR,
            width=ORIENTATION_STROKE_WIDTH,
        )
        for degrees in ORIENTATION_TICKS:
            a = self.orientation_angle(degrees)
            draw.line(
                (
                    *point(radius - ORIENTATION_TICK_EXTENSION, a),
                    *point(radius + ORIENTATION_TICK_EXTENSION, a),
                ),
                fill=SCALE_COLOR,
                width=ORIENTATION_TICK_WIDTH,
            )
            self._text(
                draw,
                point(radius + ORIENTATION_LABEL_OFFSET, a),
                f"{degrees}°",
                self.tick,
                SCALE_COLOR,
                TEXT_ANCHOR,
            )
        tilt = self.timeline.value_at(self.timeline.channels[3], position)
        if tilt is not None:
            a = self.orientation_angle(tilt)
            draw.polygon(
                (
                    point(radius - ORIENTATION_BUG_INSET, a),
                    point(radius + ORIENTATION_BUG_OUTSET, a - ORIENTATION_BUG_HALF_ANGLE),
                    point(radius + ORIENTATION_BUG_OUTSET, a + ORIENTATION_BUG_HALF_ANGLE),
                ),
                fill=ORIENTATION_BUG_COLOR,
            )
        self._text(
            draw,
            (cx, TILT_TEXT_Y),
            self._tr("Tilt unavailable") if tilt is None else self._tr("Tilt {0:.1f}°", tilt),
            self.small,
            TILT_TEXT_COLOR,
            TEXT_ANCHOR,
        )
        return image


PLUGIN = LayoutPlugin("orbit", LANDSCAPE_REGION, PORTRAIT_REGION, OrbitRenderer)
