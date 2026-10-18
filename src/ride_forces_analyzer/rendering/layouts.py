"""Compact overlay profiles: explicit geometry, strong colors and straight RGBA."""

# cspell:words WINDIR segoeui

from math import ceil, floor, cos, sin, radians
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ride_forces_analyzer.explorer import format_sample_time
from ride_forces_analyzer.i18n import tr
from .model import ExportChannel, ExportTimeline, ExportSettings

REGIONS = {
    "column": (2880, 0, 960, 2160),
    "ribbon": (384, 1692, 3072, 360),
    "corners": (2808, 140, 840, 1120),
    "capsule": (768, 108, 2304, 300),
    "orbit": (192, 1260, 1120, 792),
}
COLORS = ("#00ceff", "#35f58a", "#ffa044")


def export_region(settings: ExportSettings) -> tuple[int, int, int, int]:
    """Output geometry shared by preview, frame composition and encoding."""
    if settings.aspect == "landscape":
        return REGIONS[settings.layout]
    return {
        "column": (612, 300, 1440, 3240),
        "ribbon": (240, 1360, 1680, 2240),
        "corners": (372, 240, 1680, 2240),
        "capsule": (240, 240, 1680, 2240),
        "orbit": (240, 2412, 1680, 1188),
    }[settings.layout]


class CompactRenderer:
    def _tr(self, source: str, *values: object) -> str:
        return tr(source, *values, language=self.timeline.settings.language)

    def __init__(self, timeline: ExportTimeline) -> None:
        self.timeline = timeline
        self.layout = timeline.settings.layout
        if timeline.settings.aspect == "portrait" and self.layout in ("ribbon", "capsule"):
            self.layout = "corners"
        _, _, self.width, self.height = REGIONS[self.layout]
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        self.label = self._font(font, 30)
        self.number = self._font(font, 76 if self.layout != "capsule" else 64)
        self.small = self._font(font, 24)
        self.tick = self._font(font, 19)
        self.base = Image.new("RGBA", (self.width, self.height))
        if self.layout == "orbit":
            return
        draw = ImageDraw.Draw(self.base)
        if self.layout != "corners":
            self._panel(draw, (0, 0, self.width - 1, self.height - 1))
        for row, channel in enumerate(timeline.channels[:3]):
            x, y, w, h = self.card_box(row)
            if self.layout == "corners":
                self._panel(draw, (x, y, x + w - 1, y + h - 1))
            elif row:
                draw.line((x, 28, x, self.height - 80), fill=(190, 215, 235, 85), width=2)
            self._text(
                draw,
                (x + 32, y + 20),
                self._tr(channel.name).upper(),
                self.label,
                COLORS[row],
            )
            box = self.plot_box(row)
            for tick in channel.ticks:
                py = self.value_y(channel, tick, row)
                draw.line(
                    (box[0], py, box[2], py),
                    fill=(210, 230, 245, 150 if tick == 0 else 65),
                    width=2,
                )
                self._text(draw, (box[0] - 12, py), f"{tick:g}", self.tick, "#e4edf5", "rm")
            cursor = (box[0] + box[2]) / 2
            draw.line((cursor, box[1], cursor, box[3]), fill=(255, 255, 255, 175), width=2)
        footer = self.height - 58
        if self.layout == "corners":
            top = footer - (32 if timeline.settings.aspect == "portrait" else 10)
            self._panel(draw, (0, top, self.width - 1, self.height - 1))
        else:
            draw.line(
                (28, footer - 14, self.width - 28, footer - 14),
                fill=(190, 215, 235, 65),
                width=2,
            )

    @staticmethod
    def _font(path: Path, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return (
            ImageFont.truetype(str(path), size)
            if path.is_file()
            else ImageFont.load_default(size=size)
        )

    @staticmethod
    def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
        draw.rounded_rectangle(
            box,
            radius=36,
            fill=(7, 15, 25, 210),
            outline=(200, 225, 245, 135),
            width=2,
        )

    @staticmethod
    def _text(
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
            stroke_width=1,
            stroke_fill=(0, 0, 0, 230),
        )

    def card_box(self, row: int) -> tuple[int, int, int, int]:
        if self.layout == "corners":
            return (0, row * 348, 840, 328)
        return (row * (self.width // 3), 0, self.width // 3, self.height - 70)

    def plot_box(self, row: int) -> tuple[int, int, int, int]:
        x, y, w, h = self.card_box(row)
        left = 460 if self.layout == "ribbon" else 390 if self.layout == "corners" else 370
        return (x + left, y + 40, x + w - 32, y + h - 44)

    def value_y(self, channel: ExportChannel, value: float, row: int) -> float:
        _, top, _, bottom = self.plot_box(row)
        fraction = (value - channel.low) / (channel.high - channel.low)
        return top + (fraction if channel.inverted else 1 - fraction) * (bottom - top)

    def render(self, frame: int) -> Image.Image:
        return self.render_position(self.timeline.sample_position(frame))

    def render_position(self, position: float) -> Image.Image:
        if self.layout == "orbit":
            return self._render_orbit(position)
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        half = self.timeline.settings.window_seconds * self.timeline.sample_rate / 2
        left = position - half
        first = max(self.timeline.first, ceil(left))
        last = min(self.timeline.last, floor(position + half))
        for row, channel in enumerate(self.timeline.channels[:3]):
            value = self.timeline.value_at(channel, position)
            x, y, _, _ = self.card_box(row)
            readout = self._tr("Unavailable") if value is None else self._tr("{0:+.2f} g", value)
            self._text(
                draw,
                (x + 32, y + 70),
                readout,
                self.label if value is None else self.number,
                COLORS[row],
            )
            hint = (
                "Vertical force"
                if row == 0
                else "Unavailable"
                if value is None
                else ("Right" if value >= 0 else "Left")
                if row == 1
                else ("Acceleration" if value >= 0 else "Braking")
            )
            self._text(draw, (x + 32, y + 171), self._tr(hint), self.small, "#f3f7fc")
            x0, _, x1, bottom = self.plot_box(row)
            points: list[tuple[float, float]] = []

            def paint() -> None:
                if len(points) > 1:
                    draw.line(points, fill=(0, 0, 0, 245), width=11)
                    draw.line(points, fill=COLORS[row], width=5)

            for index in range(first, last + 1):
                sample = channel.values[index]
                if sample is None:
                    paint()
                    points = []
                else:
                    points.append(
                        (
                            x0 + (index - left) / (2 * half) * (x1 - x0),
                            self.value_y(channel, sample, row),
                        ),
                    )
            paint()
            if value is not None:
                cx, cy = (x0 + x1) / 2, self.value_y(channel, value, row)
                draw.ellipse(
                    (cx - 7, cy - 7, cx + 7, cy + 7),
                    fill=COLORS[row],
                    outline="#ffffff",
                    width=2,
                )
            self._text(draw, (x1, bottom + 5), self._tr("Time →"), self.tick, "#dce9f5", "ra")
        footer = self.height - 48
        clock = format_sample_time(
            round(position) - self.timeline.replay_origin,
            self.timeline.sample_rate,
        )
        angle = self.timeline.value_at(self.timeline.channels[3], position)
        tilt = self._tr("Tilt unavailable") if angle is None else self._tr("Tilt {0:.1f}°", angle)
        self._text(draw, (32, footer), self._tr("Replay {0}", clock), self.small, "#ffffff")
        self._text(draw, (self.width - 32, footer), tilt, self.small, "#ffffff", "ra")
        if self.layout != "corners":
            self._text(
                draw,
                (self.width / 2, footer),
                f"{self.timeline.sample_rate:g} Hz · {self.timeline.settings.fps} fps",
                self.small,
                "#dce9f5",
                "ma",
            )
        elif self.timeline.settings.aspect == "portrait":
            self._text(
                draw,
                (self.width / 2, footer - 35),
                f"{self.timeline.sample_rate:g} Hz · {self.timeline.settings.fps} fps",
                self.small,
                "#dce9f5",
                "ma",
            )
        return image

    def _render_orbit(self, position: float) -> Image.Image:
        image = self.base.copy()
        draw = ImageDraw.Draw(image)
        self._panel(draw, (0, 0, self.width - 1, self.height - 1))
        vertical = self.timeline.channels[0]
        value = self.timeline.value_at(vertical, position)
        cx, cy, radius = 330, 350, 225
        circle = (cx - radius, cy - radius, cx + radius, cy + radius)
        draw.arc(circle, 135, 405, fill=(210, 230, 245, 100), width=22)

        def angle(v: float) -> float:
            return 135 + (v - vertical.low) / (vertical.high - vertical.low) * 270

        if value is not None:
            draw.arc(
                circle,
                min(angle(0), angle(value)),
                max(angle(0), angle(value)),
                fill=COLORS[0],
                width=22,
            )
        for tick in vertical.ticks:
            a = radians(angle(tick))
            draw.line(
                (
                    cx + (radius - 12) * cos(a),
                    cy + (radius - 12) * sin(a),
                    cx + (radius + 15) * cos(a),
                    cy + (radius + 15) * sin(a),
                ),
                fill="#ffffff",
                width=3,
            )
            self._text(
                draw,
                (cx + (radius + 48) * cos(a), cy + (radius + 48) * sin(a)),
                f"{tick:g}",
                self.small,
                "#f3f7fc",
                "mm",
            )
        self._text(draw, (cx, cy - 70), self._tr("VERTICAL"), self.label, COLORS[0], "mm")
        self._text(
            draw,
            (cx, cy + 10),
            self._tr("Unavailable") if value is None else self._tr("{0:+.2f}", value),
            self.number,
            COLORS[0],
            "mm",
        )
        self._text(draw, (cx, cy + 75), "g", self.label, "#ffffff", "mm")
        self._text(draw, (cx, 635), "G-ORBIT", self.label, "#f3f7fc", "mm")
        for row in (1, 2):
            channel = self.timeline.channels[row]
            current = self.timeline.value_at(channel, position)
            x = 700 + (row - 1) * 250
            top, bottom = 190, 480

            def bar_y(v: float) -> float:
                return bottom - (v - channel.low) / (channel.high - channel.low) * (bottom - top)

            draw.rounded_rectangle(
                (x - 12, top, x + 12, bottom),
                radius=12,
                fill=(200, 225, 245, 90),
            )
            if current is not None:
                a, b = sorted((bar_y(0), bar_y(current)))
                draw.rounded_rectangle(
                    (x - 10, a, x + 10, max(a + 1, b)),
                    radius=6,
                    fill=COLORS[row],
                )
            for tick in (-1, 0, 1):
                py = bar_y(tick)
                draw.line((x - 19, py, x + 19, py), fill="#ffffff", width=2)
                self._text(draw, (x + 32, py), str(tick), self.tick, "#ffffff", "lm")
            self._text(
                draw,
                (x, 112),
                self._tr("LATERAL" if row == 1 else "LONG."),
                self.small,
                COLORS[row],
                "mm",
            )
            self._text(
                draw,
                (x, 545),
                self._tr("Unavailable") if current is None else self._tr("{0:+.2f} g", current),
                self.label,
                COLORS[row],
                "mm",
            )
            hint = (
                "Unavailable"
                if current is None
                else ("Right" if current >= 0 else "Left")
                if row == 1
                else ("Acceleration" if current >= 0 else "Braking")
            )
            self._text(draw, (x, 594), self._tr(hint), self.tick, "#ffffff", "mm")
        draw.line((32, 704, self.width - 32, 704), fill=(190, 215, 235, 85), width=2)
        clock = format_sample_time(
            round(position) - self.timeline.replay_origin,
            self.timeline.sample_rate,
        )
        tilt = self.timeline.value_at(self.timeline.channels[3], position)
        self._text(draw, (32, 730), self._tr("Replay {0}", clock), self.small, "#ffffff")
        self._text(
            draw,
            (self.width - 32, 730),
            self._tr("Tilt unavailable") if tilt is None else self._tr("Tilt {0:.1f}°", tilt),
            self.small,
            "#ffffff",
            "ra",
        )
        return image
