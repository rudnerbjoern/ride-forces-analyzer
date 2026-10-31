"""G-Orbit: force arcs, signed peak hold and a 0–180 degree tilt instrument.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words segoeui segoeuib qscale libx

from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import replace
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from ..model import ExportTimeline

from math import cos, sin, radians
from ..peaks import PeakEnvelope
from ..scales import selected_bounds, vertical_scale
from .common import ACCELERATION_COLOR, BRAKING_COLOR, Drawing
from .contracts import (
    ContentArea,
    ExportExtent,
    ExportLayout,
    LayoutPlugin,
    LayoutPosition,
    LayoutPositions,
)


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
LANDSCAPE_POSITIONS = LayoutPositions(  # Landscape regions: x, y, width, height.
    {
        LayoutPosition.TOP_LEFT: (192, 100, 800, 800),
        LayoutPosition.TOP_RIGHT: (2848, 100, 800, 800),
        LayoutPosition.BOTTOM_LEFT: (192, 1260, 800, 800),
        LayoutPosition.BOTTOM_RIGHT: (2848, 1260, 800, 800),
    },
    default=LayoutPosition.BOTTOM_LEFT,
)
PORTRAIT_POSITIONS = LayoutPositions(  # Portrait regions: x, y, width, height.
    {
        LayoutPosition.TOP_LEFT: (240, 240, 1188, 1188),
        LayoutPosition.TOP_RIGHT: (732, 240, 1188, 1188),
        LayoutPosition.BOTTOM_LEFT: (240, 2412, 1188, 1188),
        LayoutPosition.BOTTOM_RIGHT: (732, 2412, 1188, 1188),
    },
    default=LayoutPosition.BOTTOM_LEFT,
)
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
    """Orbit renderer contract and owned data.

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
        peaks: Prepared source-time peak envelopes, independent of render query order.
        vertical: Vertical instrument channel with posture-dependent absolute bounds.
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

    def __init__(self, timeline: ExportTimeline) -> None:
        """Initialize orbit renderer and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.

        Returns:
            None.
        """
        super().__init__(timeline, *NATIVE_SIZE)
        vertical = timeline.channels[0]
        posture = timeline.analysis.source.recording.metadata.riding_position
        low, high = selected_bounds(
            vertical.values,
            timeline.first,
            timeline.last,
            vertical.reference,
        )
        low, high, _ = vertical_scale(
            low,
            high,
            flying=posture is not None and posture.value == "Flying",
        )
        self.vertical = replace(vertical, low=low, high=high)
        self.peaks = tuple(
            PeakEnvelope.prepare(
                channel.values,
                timeline.first,
                timeline.last,
                timeline.sample_rate,
                hold_seconds=PEAK_HOLD_SECONDS,
                release_g_per_second=PEAK_RELEASE_G_PER_SECOND,
                reference=channel.reference,
            )
            for channel in timeline.channels[:3]
        )

    def orbit_angle(self, value: float, row: int = 0) -> float:
        """Map signed forces to their physical display direction on shared rings.

        Args:
            value: Candidate value to validate, format or store.
            row: Channel or panel row selected for rendering.

        Returns:
            Drawing angle for the signed force on its ring.
        """
        channel = self.vertical if row == 0 else self.timeline.channels[row]
        if row == 1:
            return LATERAL_ZERO_ANGLE + QUADRANT_DEGREES * value / max(
                abs(channel.low),
                abs(channel.high),
            )
        deviation = value - channel.reference
        extent = (
            channel.high - channel.reference if deviation >= 0 else channel.reference - channel.low
        )
        angle = QUADRANT_DEGREES * deviation / extent
        if row == 2:
            return -angle
        return VERTICAL_ZERO_ANGLE - angle if channel.inverted else VERTICAL_ZERO_ANGLE + angle

    @staticmethod
    def orientation_angle(value: float) -> float:
        """Keep measured 0–180 degrees on the right orientation semicircle.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            Drawing angle for the measured tilt on the orientation semicircle.
        """
        return value - QUADRANT_DEGREES

    def render_position(self, position: float) -> Image.Image:
        """Render the layout at a fractional source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
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
            channel = self.vertical if row == 0 else self.timeline.channels[row]
            reference = channel.reference
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
                    if abs(peak - reference) < PEAK_VISIBLE_THRESHOLD:
                        continue
                    a, b = sorted((self.orbit_angle(reference, row), self.orbit_angle(peak, row)))
                    color = (
                        (ACCELERATION_COLOR if peak >= 0 else BRAKING_COLOR)
                        if row == 2
                        else peak_color
                    )
                    peak_fill = (*bytes.fromhex(color[1:]), PEAK_FILL_ALPHA)
                    peak_draw.arc(circle, a, b, fill=peak_fill, width=stroke)
                image.alpha_composite(peak_layer)
                a, b = sorted((self.orbit_angle(reference, row), self.orbit_angle(current, row)))
                color = (
                    (ACCELERATION_COLOR if current >= 0 else BRAKING_COLOR)
                    if row == 2
                    else CHANNEL_COLORS[row]
                )
                draw.arc(circle, a, b, fill=color, width=stroke)
                for peak in peaks:
                    if abs(peak - reference) < PEAK_VISIBLE_THRESHOLD:
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
                    width=FORCE_TICK_WIDTH * 2
                    if row == 0 and tick == reference
                    else FORCE_TICK_WIDTH,
                )
                label_x, label_y = point(radius + FORCE_TICK_LABEL_OFFSET, a)
                anchor = TEXT_ANCHOR
                if row in (0, 2) and tick in (channel.low, channel.high):
                    # Both outer scales meet at the poles; keep their labels on their own side.
                    label_x += -12 if row == 0 else 12
                    anchor = "rm" if row == 0 else "lm"
                self._text(
                    draw,
                    (label_x, label_y),
                    f"{tick:g}",
                    self.tick,
                    SCALE_COLOR,
                    anchor,
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
                self._tr("Unavailable") if current is None else self._tr("{0:+.1f} g", current),
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


# Content-area H.264 bytes/output pixel/frame including container overhead. FFmpeg 9.0.2 CPU:
# libx264 fast CRF 18. Ten frames at 50 fps,
# Manta 3600..3609 / Voltron 4960..4969, English, 11-sample smoothing, both formats.
# Native content: 800x800 in both formats.
# Rounded outward from half the observed minimum to 1.5 times the maximum.
# Short clips include first-frame overhead; other scenes, durations, languages
# and GPU encoders are unqualified. These are planning ranges, not guarantees.
H264_CONTENT_SIZE_RATES = (0.00316, 0.01137)  # Observed 0.0063234..0.0075772.
# Full-frame H.264 uses the owner-provided Kraken CPU export reference:
# 3840x2160, 60000/1001 fps, 9,544 frames, libx264, 8,061,387 bytes including MP4.
# Observed 0.000101834 bytes/pixel/frame; round to 0.000102 with +/-50%.
# Applies to both backend preferences; portrait, other scenes and GPU encoders
# remain unqualified by this reference. These are planning ranges, not guarantees.
H264_SIZE_RATES = (0.000051, 0.000153)
# Full-frame ProRes uses the owner-provided Kraken GPU export reference:
# 3840x2160, 60000/1001 fps, 9,544 frames, prores_ks_vulkan, 10,236,947,676 bytes.
# Including MOV overhead: 0.12932 bytes/pixel/frame, rounded to 0.13 with +/-10%.
# Applies to both backend preferences; CPU, portrait and other scenes remain
# unqualified by this reference. These are planning ranges, not guarantees.
PRORES_4444_SIZE_RATES = (0.117, 0.143)
# Content-area ProRes uses the owner-provided Kraken GPU export reference:
# 800x800, 60000/1001 fps, 9,544 frames, prores_ks_vulkan, 9,153,051,038 bytes.
# Including MOV overhead: 1.49850 bytes/pixel/frame, rounded to 1.50 with +/-10%.
# Applies to both backend preferences; CPU, unmeasured aspects and other scenes
# remain unqualified by this reference. These are planning ranges, not guarantees.
PRORES_4444_CONTENT_SIZE_RATES = (1.35, 1.65)
LANDSCAPE_CONTENT = ContentArea(NATIVE_SIZE)
PORTRAIT_CONTENT = ContentArea(NATIVE_SIZE)

PLUGIN = LayoutPlugin(
    ExportLayout.ORBIT,
    LANDSCAPE_POSITIONS,
    PORTRAIT_POSITIONS,
    OrbitRenderer,
    landscape_content=LANDSCAPE_CONTENT,
    portrait_content=PORTRAIT_CONTENT,
    prores_4444_size_rates={
        ExportExtent.FULL_FRAME: PRORES_4444_SIZE_RATES,
        ExportExtent.CONTENT_AREA: PRORES_4444_CONTENT_SIZE_RATES,
    },
    h264_size_rates={
        ExportExtent.FULL_FRAME: H264_SIZE_RATES,
        ExportExtent.CONTENT_AREA: H264_CONTENT_SIZE_RATES,
    },
)
