"""Frameless full-screen HUD with fine scales, glow and shared-time force histories.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words bahnschrift RGBa getbbox getchannel putalpha WINDIR

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ride_forces_analyzer.rendering.airtime_colors import VERTICAL_CONTEXT_COLORS
from ..peaks import PeakEnvelope
from ..scales import (
    lateral_scale,
    longitudinal_scale,
    selected_bounds,
    vertical_scale,
)
from .common import Drawing
from .contracts import (
    ExportExtent,
    ExportLayout,
    VideoAspect,
    LayoutPlugin,
    LayoutPosition,
    LayoutPositions,
)

if TYPE_CHECKING:
    from ..model import ExportTimeline


FONT_FILE = "bahnschrift.ttf"  # Native Windows technical typeface; Drawing retains its fallback.
LABEL_SIZE = 20  # Instrument headings.
NUMBER_SIZE = 54  # Large signed current values.
CONTEXT_SIZE = 23  # Airtime category beneath the vertical value.
TICK_SIZE = 18  # Major scale labels and time ticks.
HISTORY_LABEL_SIZE = 16  # Small channel names beside/before the traces.
CYAN = "#67efff"  # Vertical force, cursor and cool instrument light.
YELLOW = "#ffed51"  # Signed lateral force.
GREEN = "#73ffad"  # Positive longitudinal force.
RED = "#ff6265"  # Negative longitudinal force.
WHITE = "#d9f8ff"  # Neutral scale ticks and labels.
BASELINE_COLOR = (181, 228, 238, 75)  # Quiet zero references and separators.
GLOW_RADIUS = 5.5  # Broad native-pixel bloom; export retains the native resolution.
GLOW_ALPHA = tuple(round(value * 0.85) for value in range(256))
SHADOW_RADIUS = 6.0  # Soft contrast halo on bright footage.
SHADOW_OFFSET = 3  # Downward shadow displacement.
SHADOW_ALPHA = tuple(round(value * 0.95) for value in range(256))
EDGE_ALPHA = tuple(round(value * 0.35) for value in range(256))  # Fine dark contrast edge.
HISTORY_SHADE_ALPHA = 105  # Soft bottom gradient behind the three histories.
ORIENTATION_TICKS = (0, 45, 90, 135, 180)  # Fixed degrees down the outer right edge.
ORIENTATION_TICK_SIZE = 12  # Compact labels beside the existing right instrument.
ORIENTATION_STRIP_WIDTH = 48  # Native pixels reserved for the conditional edge scale.
ORIENTATION_EDGE = 2  # Keep the fine line immediately inside the canvas edge.
PEAK_HOLD_SECONDS = 1.5  # Source-time hold, matching G-Orbit.
PEAK_RELEASE_G_PER_SECOND = 1.0  # Return toward zero after the hold.
LINE_WIDTH = 2  # Crisp core of scales, markers and curves.
MINOR_DIVISIONS = 5  # Four fine subdivisions between neighboring major ticks.
EFFECT_MARGIN = 24  # Keep tile bloom/shadows away from clipped edges.


@dataclass(frozen=True, slots=True)
class HudGeometry:
    """Format-specific native pixel geometry; the center has no painted background.

    Attributes:
        size: Required dimensions or capacity.
        title_y: Layout coordinate for title y in the owning view or renderer.
        value_y: Layout coordinate for value y in the owning view or renderer.
        context_y: Layout coordinate for context y in the owning view or renderer.
        scale_top: Layout coordinate for scale top in the owning view or renderer.
        scale_bottom: Layout coordinate for scale bottom in the owning view or renderer.
        left_axis: Geometry of the left vertical-force instrument.
        right_axis: Geometry of the right acceleration instrument.
        lateral_y: Layout coordinate for lateral y in the owning view or renderer.
        lateral_left: Layout coordinate for lateral left in the owning view or renderer.
        lateral_right: Layout coordinate for lateral right in the owning view or renderer.
        history_top: Layout coordinate for history top in the owning view or renderer.
        history_left: Layout coordinate for history left in the owning view or renderer.
        history_row: Geometry of the force-history rows.
    """

    size: tuple[int, int]
    title_y: int
    value_y: int
    context_y: int
    scale_top: int
    scale_bottom: int
    left_axis: int
    right_axis: int
    lateral_y: int
    lateral_left: int
    lateral_right: int
    history_top: int
    history_left: int
    history_row: int


LANDSCAPE = HudGeometry(
    size=(1920, 1080),
    title_y=122,
    value_y=153,
    context_y=216,
    scale_top=250,
    scale_bottom=670,
    left_axis=128,
    right_axis=1792,
    lateral_y=760,
    lateral_left=590,
    lateral_right=1330,
    history_top=835,
    history_left=175,
    history_row=65,
)
PORTRAIT = HudGeometry(
    size=(1080, 1920),
    title_y=280,
    value_y=312,
    context_y=385,
    scale_top=440,
    scale_bottom=1195,
    left_axis=55,
    right_axis=970,
    lateral_y=1435,
    lateral_left=130,
    lateral_right=945,
    history_top=1535,
    history_left=95,
    history_row=96,
)
LANDSCAPE_POSITIONS = LayoutPositions(
    {LayoutPosition.FULL_SCREEN: (0, 0, *LANDSCAPE.size)},
    default=LayoutPosition.FULL_SCREEN,
)
PORTRAIT_POSITIONS = LayoutPositions(
    {LayoutPosition.FULL_SCREEN: (0, 0, *PORTRAIT.size)},
    default=LayoutPosition.FULL_SCREEN,
)


def _ticks(
    low: float,
    high: float,
    step: float,
    *,
    divisions: int = MINOR_DIVISIONS,
) -> list[tuple[float, bool]]:
    """Include exact endpoints alongside bounded major/minor subdivisions."""
    ticks = {
        index * step / divisions: index % divisions == 0
        for index in range(
            ceil(low / step * divisions),
            floor(high / step * divisions) + 1,
        )
    }
    ticks[low] = ticks[high] = True
    return sorted(ticks.items())


class HudRenderer(Drawing):
    """Hud renderer contract and owned data.

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
        text_stroke_width: Layout dimension for text stroke width, in native pixels unless
            specified otherwise.
        geometry: Aspect-specific positions and dimensions for layout drawing.
        portrait: Whether the selected layout uses portrait geometry.
        history_label: Font used for force-history labels.
        orientation_tick: Font used for orientation-scale labels.
        scales: Fixed instrument ranges fitted to the selected export interval.
        references: Neutral force levels; vertical uses 1 g, other channels use zero.
        history_scales: Fixed per-channel deviations around the neutral references.
        vertical_history_bounds: Selected vertical extrema including the 1 g reference.
        peaks: Prepared source-time peak envelopes, independent of render query order.
        base: Prepared static layout image copied before per-frame drawing.
        orientation_base: Prepared static orientation-scale image.
    """

    font_file = FONT_FILE
    tick_font_file = FONT_FILE
    label_size = LABEL_SIZE
    number_size = NUMBER_SIZE
    small_size = CONTEXT_SIZE
    tick_size = TICK_SIZE
    text_stroke_width = 0

    def __init__(self, timeline: ExportTimeline) -> None:
        """Initialize hud renderer and its owned state.

        Args:
            timeline: Bound video timeline containing the source interval and export settings.

        Returns:
            None.
        """
        self.geometry = PORTRAIT if timeline.settings.aspect is VideoAspect.PORTRAIT else LANDSCAPE
        super().__init__(timeline, *self.geometry.size)
        if isinstance(self.number, ImageFont.FreeTypeFont) and self._font_path().is_file():
            self.number.set_variation_by_name("Bold")
        self.portrait = timeline.settings.aspect is VideoAspect.PORTRAIT
        self.history_label = self._font(
            self._font_path(),
            HISTORY_LABEL_SIZE,
        )
        self.orientation_tick = self._font(self._font_path(), ORIENTATION_TICK_SIZE)
        posture = timeline.analysis.source.recording.metadata.riding_position
        self.references = tuple(channel.reference for channel in timeline.channels[:3])
        bounds = tuple(
            selected_bounds(channel.values, timeline.first, timeline.last, reference)
            for channel, reference in zip(timeline.channels[:3], self.references, strict=True)
        )
        peaks = tuple(
            max(abs(low - reference), abs(high - reference))
            for (low, high), reference in zip(bounds, self.references, strict=True)
        )
        self.scales = (
            vertical_scale(*bounds[0], flying=posture is not None and posture.value == "Flying"),
            lateral_scale(peaks[1]),
            longitudinal_scale(peaks[2]),
        )
        self.history_scales = tuple(peak or 1.0 for peak in peaks)
        self.vertical_history_bounds = bounds[0]
        self.peaks = tuple(
            PeakEnvelope.prepare(
                channel.values,
                timeline.first,
                timeline.last,
                timeline.sample_rate,
                hold_seconds=PEAK_HOLD_SECONDS,
                release_g_per_second=PEAK_RELEASE_G_PER_SECOND,
                reference=reference,
            )
            for channel, reference in zip(timeline.channels[:3], self.references, strict=True)
        )
        self._draw_static(ImageDraw.Draw(self.base))
        ink = self.effects(self.base)
        self.base = Image.new("RGBA", self.geometry.size)
        draw = ImageDraw.Draw(self.base)
        top = self.geometry.history_top - 40
        for y in range(top, self.height):
            alpha = round(HISTORY_SHADE_ALPHA * (y - top) / (self.height - top - 1))
            draw.line((0, y, self.width, y), fill=(0, 0, 0, alpha))
        self.base.alpha_composite(ink)
        self.orientation_base = self._orientation_scale()

    @staticmethod
    def _font_path() -> Path:
        import os

        return Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / FONT_FILE

    @staticmethod
    def effects(ink: Image.Image) -> Image.Image:
        """Composite soft black shadow, colored bloom and crisp ink, preserving alpha.

        Args:
            ink: RGBA image containing the sharp foreground drawing.

        Returns:
            RGBA image containing the composited glow, shadow and sharp ink.
        """
        alpha = ink.getchannel("A")
        shadow_mask = Image.new("L", ink.size)
        shadow_mask.paste(
            alpha.filter(ImageFilter.GaussianBlur(SHADOW_RADIUS)).point(SHADOW_ALPHA),
            (0, SHADOW_OFFSET),
        )
        result = Image.new("RGBA", ink.size, (0, 0, 0, 0))
        result.putalpha(shadow_mask)
        # Premultiplied blur retains saturated light rather than dark RGB fringes.
        glow = ink.convert("RGBa").filter(ImageFilter.GaussianBlur(GLOW_RADIUS)).convert("RGBA")
        glow.putalpha(glow.getchannel("A").point(GLOW_ALPHA))
        result.alpha_composite(glow)
        edge = Image.new("RGBA", ink.size, (0, 0, 0, 0))
        edge.putalpha(alpha.filter(ImageFilter.MaxFilter(3)).point(EDGE_ALPHA))
        result.alpha_composite(edge)
        result.alpha_composite(ink)
        return result

    @classmethod
    def composite_effects(
        cls,
        image: Image.Image,
        ink: Image.Image,
        position: tuple[int, int],
    ) -> None:
        """Filter painted pixels and their halo, preserving the original tile's clipping.

        Args:
            image: Raster image to inspect or draw into.
            ink: RGBA image containing the sharp foreground drawing.
            position: Horizontal and vertical drawing origin in pixels.

        Returns:
            None.
        """
        bounds = ink.getbbox()
        if bounds is None:
            return
        left, top, right, bottom = bounds
        left, top = max(0, left - EFFECT_MARGIN), max(0, top - EFFECT_MARGIN)
        right = min(ink.width, right + EFFECT_MARGIN)
        bottom = min(ink.height, bottom + EFFECT_MARGIN)
        image.alpha_composite(
            cls.effects(ink.crop((left, top, right, bottom))),
            (position[0] + left, position[1] + top),
        )

    def vertical_y(self, value: float) -> float:
        """Negative lifting is above zero by default; honor the vertical display override.

        Args:
            value: Measured value in the selected instrument's declared units.

        Returns:
            Vertical drawing coordinate on the vertical-force scale.
        """
        g = self.geometry
        low, high, _ = self.scales[0]
        fraction = (value - low) / (high - low)
        if not self.timeline.channels[0].inverted:
            fraction = 1 - fraction
        return g.scale_top + fraction * (g.scale_bottom - g.scale_top)

    def longitudinal_y(self, value: float) -> float:
        """Map longitudinal force to the HUD's acceleration/braking scale.

        Args:
            value: Measured value in the selected instrument's declared units.

        Returns:
            Vertical drawing coordinate on the acceleration scale.
        """
        g = self.geometry
        return (g.scale_top + g.scale_bottom) / 2 - (
            value / self.scales[2][1] * (g.scale_bottom - g.scale_top) / 2
        )

    def orientation_y(self, value: float) -> float:
        """Map the prepared tilt from 0° at the top to 180° at the bottom.

        Args:
            value: Measured value in the selected instrument's declared units.

        Returns:
            Vertical drawing coordinate on the orientation scale.
        """
        g = self.geometry
        return g.scale_top + value / 180 * (g.scale_bottom - g.scale_top)

    def lateral_x(self, value: float) -> float:
        """Map lateral force to its layout coordinate and direction policy.

        Args:
            value: Measured value in the selected instrument's declared units.

        Returns:
            Horizontal drawing coordinate on the lateral-force scale.
        """
        g = self.geometry
        return (g.lateral_left + g.lateral_right) / 2 + (
            value / self.scales[1][1] * (g.lateral_right - g.lateral_left) / 2
        )

    def history_point(self, row: int, value: float, fraction: float) -> tuple[float, float]:
        """Map absolute forces around their neutral reference on the shared time axis.

        Time zero aligns with the lateral instrument's zero; vertical history
        fits its selected extrema including 1 g, while the other histories center on zero.
        Lateral and longitudinal peaks fill their rows symmetrically without
        headroom; a channel containing only zeros remains on its reference.

        Args:
            row: Channel or panel row selected for rendering.
            value: Measured value in the selected instrument's declared units.
            fraction: Normalized time coordinate within the plotted interval.

        Returns:
            Horizontal and vertical drawing coordinates on the force-history chart.
        """
        g = self.geometry
        top = g.history_top + row * g.history_row
        center = top + g.history_row / 2
        if row == 0:
            low, high = self.vertical_history_bounds
            relative = (value - low) / (high - low) if high != low else 0.5
            if not self.timeline.channels[0].inverted:
                relative = 1 - relative
            y = top + 1 + relative * (g.history_row - 2)
        else:
            y = center - value / self.history_scales[row] * (g.history_row / 2 - 1)
        return (
            g.history_left + fraction * 2 * (self.lateral_x(0) - g.history_left),
            y,
        )

    def _tick_text(self, value: float) -> str:
        if abs(value) < 1e-10:
            return "0"
        if self.portrait:
            return self._tr(
                "{0:+.2f}" if abs(value - round(value, 1)) > 1e-9 else "{0:+.1f}",
                value,
            )
        return self._tr("{0:+g}", value)

    def _draw_static(self, draw: ImageDraw.ImageDraw) -> None:
        x: float
        g = self.geometry
        edge = 40 if self.portrait else 68
        self._text(draw, (edge, g.title_y), self._tr("Vertical").upper(), self.label, CYAN)
        self._text(
            draw,
            (self.width - edge, g.title_y),
            self._tr("Acceleration").upper(),
            self.label,
            GREEN,
            "rt",
        )
        for row, x in ((0, g.left_axis), (2, g.right_axis)):
            low, high, step = self.scales[row]
            mapping = self.vertical_y if row == 0 else self.longitudinal_y
            zero = mapping(0)
            if row == 0:
                draw.line((x, g.scale_top, x, g.scale_bottom), fill=CYAN, width=LINE_WIDTH)
            else:
                draw.line((x, g.scale_top, x, zero), fill=GREEN, width=LINE_WIDTH)
                draw.line((x, zero, x, g.scale_bottom), fill=RED, width=LINE_WIDTH)
            for value, major in _ticks(
                low,
                high,
                step,
                divisions=4 if row == 0 else MINOR_DIVISIONS,
            ):
                y = mapping(value)
                if row == 0:
                    major = value.is_integer()
                    length = 20 if major else 14 if (value * 2).is_integer() else 8
                else:
                    length = 20 if major else 9
                direction = 1 if row == 2 or self.portrait else -1
                color = CYAN if row == 0 else GREEN if value > 0 else RED if value < 0 else WHITE
                draw.line(
                    (x, y, x + direction * length, y),
                    fill=color,
                    width=LINE_WIDTH if major else 1,
                )
                if major:
                    self._text(
                        draw,
                        (x + direction * 30, y),
                        ("0" if value == 0 else self._tr("{0:+g}", value))
                        if row == 0
                        else self._tick_text(value),
                        self.tick,
                        WHITE if row == 0 else color,
                        "lm" if direction > 0 else "rm",
                    )
            neutral = mapping(self.references[row])
            draw.line((x - 12, neutral, x + 12, neutral), fill=WHITE, width=LINE_WIDTH)

        if self.portrait:
            self._text(
                draw,
                (self.width / 2, g.lateral_y - 94),
                self._tr("Lateral").upper(),
                self.label,
                WHITE,
                "mm",
            )
        self._text(
            draw,
            (g.lateral_left - 24, g.lateral_y),
            self._tr("Left").upper(),
            self.label,
            YELLOW if self.portrait else WHITE,
            "rm",
        )
        self._text(
            draw,
            (g.lateral_right + 24, g.lateral_y),
            self._tr("Right").upper(),
            self.label,
            YELLOW if self.portrait else WHITE,
            "lm",
        )
        draw.line(
            (g.lateral_left, g.lateral_y, g.lateral_right, g.lateral_y),
            fill=YELLOW if self.portrait else WHITE,
            width=LINE_WIDTH,
        )
        for value, major in _ticks(*self.scales[1]):
            x = self.lateral_x(value)
            length = 10 if major else 5
            draw.line((x, g.lateral_y - length, x, g.lateral_y + length), fill=WHITE, width=1)
            if (self.portrait and major) or value == 0:
                self._text(
                    draw,
                    (x, g.lateral_y + 28),
                    self._tick_text(value),
                    self.tick,
                    WHITE,
                    "mt",
                )

        history_right, _ = self.history_point(0, 0, 1)
        for row, channel in enumerate(self.timeline.channels[:3]):
            top = g.history_top + row * g.history_row
            center = top + g.history_row / 2
            self._text(
                draw,
                (40, top - 10 if self.portrait else center),
                self._tr(channel.name).upper(),
                self.history_label,
                (CYAN, YELLOW, GREEN)[row],
                "lt" if self.portrait else "lm",
            )
            reference_y = self.history_point(row, self.references[row], 0)[1]
            draw.line(
                (g.history_left, reference_y, history_right, reference_y),
                fill=BASELINE_COLOR,
                width=1,
            )
            reference = self.references[row]
            self._text(
                draw,
                (g.history_left - 4, reference_y),
                f"{reference:g} g",
                self.history_label,
                WHITE,
                "rm",
            )
            draw.line(
                (g.history_left, top + g.history_row - 1, history_right, top + g.history_row - 1),
                fill=BASELINE_COLOR,
                width=1,
            )
            if self.portrait:
                limits = (
                    self.vertical_history_bounds
                    if row == 0
                    else (
                        reference - self.history_scales[row],
                        reference + self.history_scales[row],
                    )
                )
                for index, value in enumerate(limits):
                    if row == 0:
                        sign = 1 if self.timeline.channels[0].inverted else -1
                        y = center + sign * (2 * index - 1) * g.history_row * 0.32
                    else:
                        _, y = self.history_point(row, value, 0)
                    self._text(
                        draw,
                        (g.history_left - 14, y),
                        self._tick_text(value),
                        self.history_label,
                        WHITE,
                        "rm",
                    )
        cursor, _ = self.history_point(0, 0, 0.5)
        bottom = g.history_top + 3 * g.history_row
        draw.line(
            (cursor, g.history_top - 12, cursor, bottom + 7),
            fill=CYAN,
            width=LINE_WIDTH,
        )
        half_window = self.timeline.settings.window_seconds / 2
        for seconds in range(ceil(-half_window), floor(half_window) + 1):
            fraction = (seconds + half_window) / (2 * half_window)
            x, _ = self.history_point(0, 0, fraction)
            major = seconds % 5 == 0
            draw.line((x, bottom, x, bottom + (10 if major else 5)), fill=WHITE, width=1)
            if major:
                self._text(
                    draw,
                    (x, bottom + 22),
                    f"{seconds} s",
                    self.tick,
                    WHITE,
                    "mt",
                )

    def _gauges(self, image: Image.Image, position: float) -> None:
        x: float
        g = self.geometry
        edge = 40 if self.portrait else 68
        values = tuple(
            self.timeline.value_at(channel, position) for channel in self.timeline.channels[:3]
        )
        for row in (0, 2):
            value = values[row]
            color = WHITE if value is None else CYAN if row == 0 else GREEN if value >= 0 else RED
            # Only a narrow side strip is blurred per frame; the empty center is untouched.
            left, right = (
                (0, 430 if not self.portrait else 390)
                if row == 0
                else (
                    self.width - (430 if not self.portrait else 390),
                    self.width,
                )
            )
            top = g.value_y - EFFECT_MARGIN
            tile = Image.new("RGBA", (right - left, g.scale_bottom + 100 - top))
            draw = ImageDraw.Draw(tile)
            anchor_x = edge if row == 0 else self.width - edge
            self._text(
                draw,
                (anchor_x - left, g.value_y - top),
                self._tr("Unavailable") if value is None else self._tr("{0:+.1f} g", value),
                self.label if value is None else self.number,
                color,
                "lt" if row == 0 else "rt",
            )
            if row == 0:
                context = "Unavailable" if value is None else self.timeline.context_at(position)
                self._text(
                    draw,
                    (anchor_x - left, g.context_y - top),
                    self._tr(context).upper(),
                    self.small,
                    VERTICAL_CONTEXT_COLORS.get(context, WHITE),
                )
            if value is not None:
                x = (g.left_axis if row == 0 else g.right_axis) - left
                mapping = self.vertical_y if row == 0 else self.longitudinal_y
                reference = self.references[row]
                y, zero = mapping(value) - top, mapping(reference) - top
                for peak in self.peaks[row].at(position, value):
                    if peak != reference:
                        peak_color = CYAN if row == 0 else GREEN if peak > 0 else RED
                        draw.line((x, zero, x, mapping(peak) - top), fill=peak_color, width=4)
                direction = 1 if row == 0 else -1
                draw.polygon(
                    ((x, y), (x + direction * 17, y - 9), (x + direction * 17, y + 9)),
                    fill=color,
                )
            self.composite_effects(image, tile, (left, top))

        value = values[1]
        top = g.lateral_y - 78
        tile = Image.new("RGBA", (self.width, 110))
        draw = ImageDraw.Draw(tile)
        self._text(
            draw,
            (self.width / 2, 4),
            self._tr("Unavailable") if value is None else self._tr("{0:+.1f} g", value),
            self.label if value is None else self.number,
            YELLOW,
            "mt",
        )
        if value is not None:
            x = self.lateral_x(value)
            zero = self.lateral_x(0)
            y = g.lateral_y - top
            for peak in self.peaks[1].at(position, value):
                if peak != 0:
                    draw.line((zero, y, self.lateral_x(peak), y), fill=YELLOW, width=3)
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=YELLOW)
            draw.polygon(((x, y + 9), (x - 7, y + 21), (x + 7, y + 21)), fill=YELLOW)
        self.composite_effects(image, tile, (0, top))

    def _orientation_scale(self) -> Image.Image:
        """Prepare the conditional orientation strip's unchanging ink once."""
        g = self.geometry
        top = g.scale_top - EFFECT_MARGIN
        tile = Image.new(
            "RGBA",
            (ORIENTATION_STRIP_WIDTH, g.scale_bottom - g.scale_top + 2 * EFFECT_MARGIN),
        )
        draw = ImageDraw.Draw(tile)
        x = ORIENTATION_STRIP_WIDTH - ORIENTATION_EDGE
        draw.line((x, g.scale_top - top, x, g.scale_bottom - top), fill=WHITE, width=1)
        for degrees in ORIENTATION_TICKS:
            y = self.orientation_y(degrees) - top
            draw.line((x - 7, y, x, y), fill=WHITE, width=1)
            self._text(
                draw,
                (x - 12, y),
                f"{degrees}°",
                self.orientation_tick,
                WHITE,
                "rm",
            )
        return tile

    def _orientation(self, image: Image.Image, position: float) -> None:
        value = self.timeline.value_at(self.timeline.channels[3], position)
        if value is None:
            return
        g = self.geometry
        top = g.scale_top - EFFECT_MARGIN
        tile = self.orientation_base.copy()
        draw = ImageDraw.Draw(tile)
        x = ORIENTATION_STRIP_WIDTH - ORIENTATION_EDGE
        y = self.orientation_y(value) - top
        draw.polygon(((x, y), (x - 10, y - 5), (x - 10, y + 5)), fill=WHITE)
        self.composite_effects(image, tile, (self.width - ORIENTATION_STRIP_WIDTH, top))

    def _histories(self, image: Image.Image, position: float) -> None:
        g = self.geometry
        tile = Image.new("RGBA", (self.width, 3 * g.history_row + 2 * EFFECT_MARGIN))
        draw = ImageDraw.Draw(tile)
        top = g.history_top - EFFECT_MARGIN
        half = self.timeline.settings.window_seconds * self.timeline.sample_rate / 2
        start = position - half
        first, last = (
            max(self.timeline.first, ceil(start)),
            min(self.timeline.last, floor(position + half)),
        )
        for row, channel in enumerate(self.timeline.channels[:3]):
            points: list[tuple[float, float]] = []

            def paint() -> None:
                if len(points) < 2:
                    return
                if row != 2:
                    draw.line(points, fill=CYAN if row == 0 else YELLOW, width=LINE_WIDTH)
                    return
                zero_y = self.history_point(row, 0, 0)[1] - top
                for a, b in zip(points, points[1:]):
                    color_a = GREEN if a[1] <= zero_y else RED
                    color_b = GREEN if b[1] <= zero_y else RED
                    if color_a == color_b:
                        draw.line((a, b), fill=color_a, width=LINE_WIDTH)
                    else:
                        fraction = (zero_y - a[1]) / (b[1] - a[1])
                        crossing = (a[0] + fraction * (b[0] - a[0]), zero_y)
                        draw.line((a, crossing), fill=color_a, width=LINE_WIDTH)
                        draw.line((crossing, b), fill=color_b, width=LINE_WIDTH)

            for index in range(first, last + 1):
                value = channel.values[index]
                if value is None:
                    paint()
                    points = []
                else:
                    x, y = self.history_point(row, value, (index - start) / (2 * half))
                    points.append((x, y - top))
            paint()
        self.composite_effects(image, tile, (0, top))

    def render_position(self, position: float) -> Image.Image:
        """Render the layout at a fractional source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            The rendered image in the layout or canvas dimensions declared by the timeline.
        """
        image = self.base.copy()
        self._histories(image, position)
        self._gauges(image, position)
        self._orientation(image, position)
        return image


# Kraken, Iron Gwazi and Voltron GPU ProRes measurements span 0.734–0.764 bytes
# per pixel/frame including MOV overhead; retain a 10% planning margin around 0.75.
PRORES_4444_SIZE_RATES = (0.675, 0.825)
# Kraken CPU H.264: 17,181,504 bytes, about 0.00085 bytes/pixel/frame including
# MP4 overhead; allow 50% for content/encoder variation.
H264_SIZE_RATES = (0.000425, 0.001275)

PLUGIN = LayoutPlugin(
    ExportLayout.HUD,
    LANDSCAPE_POSITIONS,
    PORTRAIT_POSITIONS,
    HudRenderer,
    landscape_canvas=LANDSCAPE.size,
    portrait_canvas=PORTRAIT.size,
    preferred_window_seconds=30.0,
    prores_4444_size_rates={ExportExtent.FULL_FRAME: PRORES_4444_SIZE_RATES},
    h264_size_rates={ExportExtent.FULL_FRAME: H264_SIZE_RATES},
)
