"""Pillow RGBA frames; independent of FFmpeg, video files and the live Qt chart."""

# cspell:words WINDIR segoeui LANCZOS

from math import ceil, floor
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ride_forces_analyzer.explorer import format_sample_time
from ride_forces_analyzer.i18n import tr
from .model import ExportChannel, ExportTimeline
from .layouts import CompactRenderer, export_region

WIDTH, HEIGHT, COLUMN_WIDTH = 3840, 2160, 960
COLUMN_X = WIDTH - COLUMN_WIDTH


class OverlayRenderer:
    def __init__(self, timeline: ExportTimeline) -> None:
        self.timeline = timeline
        self.compact = CompactRenderer(timeline) if timeline.settings.layout != "column" else None
        if self.compact is not None:
            return
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        self.font = (
            ImageFont.truetype(str(font), 25) if font.is_file() else ImageFont.load_default(size=25)
        )
        self.large = (
            ImageFont.truetype(str(font), 37) if font.is_file() else ImageFont.load_default(size=37)
        )
        self.base = Image.new("RGBA", (COLUMN_WIDTH, HEIGHT), (0, 0, 0, 255))
        draw = ImageDraw.Draw(self.base)
        for row, channel in enumerate(timeline.channels):
            y = row * 540
            draw.line((26, y + 37, 63, y + 37), fill=channel.color, width=4)
            draw.text(
                (76, y + 15),
                tr(channel.name, language=timeline.settings.language),
                font=self.large,
                fill=channel.color,
            )
            draw.text(
                (76, y + 64),
                tr(channel.hint, language=timeline.settings.language),
                font=self.font,
                fill="#9da2a8",
            )
            box = self.plot_box(row)
            draw.rectangle(box, fill="#141214", outline="#85858a", width=2)
            for tick in channel.ticks:
                py = self.value_y(channel, tick, row)
                draw.line((box[0], py, box[2], py), fill="#3b393e", width=2)
                draw.text(
                    (box[0] - 12, py),
                    f"{tick:g}{channel.unit}",
                    font=self.font,
                    fill="#dddddd",
                    anchor="rm",
                )
            cursor = (box[0] + box[2]) / 2
            draw.line((cursor, box[1], cursor, box[3]), fill="#dddddd", width=2)

    @staticmethod
    def plot_box(row: int) -> tuple[int, int, int, int]:
        y = row * 540
        return (94, y + 116, 934, y + 474)

    def value_y(self, channel: ExportChannel, value: float, row: int) -> float:
        _, top, _, bottom = self.plot_box(row)
        fraction = (value - channel.low) / (channel.high - channel.low)
        if not channel.inverted:
            fraction = 1 - fraction
        return top + fraction * (bottom - top)

    def render_column(self, frame: int) -> Image.Image:
        return self._render_column_at(self.timeline.sample_position(frame))

    def _render_column_at(self, position: float) -> Image.Image:
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
                    "{0:.2f} {1}",
                    value,
                    channel.unit,
                    language=self.timeline.settings.language,
                )
            )
            draw.text((934, row * 540 + 17), text, font=self.large, fill="#eeeeee", anchor="ra")
            x0, _, x1, _ = self.plot_box(row)
            points: list[tuple[float, float]] = []
            for index in range(first, last + 1):
                sample = channel.values[index]
                if sample is None:
                    if len(points) > 1:
                        draw.line(points, fill=channel.color, width=3)
                    points = []
                    continue
                x = x0 + (index - left) / (2 * half) * (x1 - x0)
                points.append((x, self.value_y(channel, sample, row)))
            if len(points) > 1:
                draw.line(points, fill=channel.color, width=3)
            elif points:
                px, py = points[0]
                draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=channel.color)
            clock = format_sample_time(round(position) - self.timeline.replay_origin, rate)
            draw.text(
                ((x0 + x1) / 2, row * 540 + 484),
                clock,
                font=self.font,
                fill="#dddddd",
                anchor="ma",
            )
            draw.text(
                (934, row * 540 + 484),
                f"{rate:g} Hz · {self.timeline.settings.fps} fps",
                font=self.font,
                fill="#89858b",
                anchor="ra",
            )
        return image

    def render_region(self, frame: int) -> Image.Image:
        return self._render_region_at(self.timeline.sample_position(frame))

    def _render_region_at(self, position: float) -> Image.Image:
        image = (
            self.compact.render_position(position)
            if self.compact is not None
            else self._render_column_at(position)
        )
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
