"""Single-sample export previews using the production renderer, without encoding.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words LANCZOS

from dataclasses import dataclass, replace
from collections.abc import Mapping
from enum import StrEnum

from PIL import Image, ImageDraw

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from .frames import OverlayRenderer
from .layouts import registry
from .layouts.contracts import LayoutPosition
from .model import ExportLayout, ExportSettings, PROFILES, prepare_export


class PreviewBackground(StrEnum):
    """Preview-only backgrounds with stable UI values."""

    CHECKER = "checker"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class ProfilePreview:
    layout: ExportLayout
    title: str
    image: Image.Image


@dataclass(frozen=True, slots=True)
class ExportPreview:
    sample: int
    outside_range: bool
    profiles: tuple[ProfilePreview, ...]


def build_previews(
    analysis: RecordingAnalysis,
    settings: ExportSettings,
    first: int,
    last: int,
    sample: int,
    background: PreviewBackground = PreviewBackground.CHECKER,
    previous_positions: Mapping[ExportLayout, LayoutPosition] | None = None,
) -> ExportPreview:
    count = len(analysis.time.source_indices)
    if not 0 <= sample < count:
        raise ValueError("Preview sample outside recording")
    if type(first) is not int or type(last) is not int or not 0 <= first <= last < count:
        raise ValueError("Invalid export sample interval")
    outside = not first <= sample <= last
    timeline = prepare_export(
        analysis,
        settings,
        0 if outside else first,
        count - 1 if outside else last,
    )
    previews: list[ProfilePreview] = []
    width, height = settings.dimensions
    size = (width // 4, height // 4)
    selected_plugin = registry.PLUGINS[settings.layout]
    selected_positions = (
        selected_plugin.landscape if settings.aspect == "landscape" else selected_plugin.portrait
    )
    selected_position = settings.position or selected_positions.default
    backdrop = Image.new(
        "RGBA",
        size,
        "#162533" if background == PreviewBackground.DARK else "#e4eaf0",
    )
    if background == PreviewBackground.CHECKER:
        draw = ImageDraw.Draw(backdrop)
        for y in range(0, size[1], 30):
            for x in range(0, size[0], 30):
                if (x // 30 + y // 30) % 2:
                    draw.rectangle((x, y, x + 29, y + 29), fill="#aebfce")
    for layout, title in PROFILES:
        plugin = registry.PLUGINS[layout]
        positions = plugin.landscape if settings.aspect == "landscape" else plugin.portrait
        profile = (
            settings
            if layout == settings.layout
            else replace(
                settings,
                layout=layout,
                position=positions.select(
                    selected_position,
                    previous_positions.get(layout) if previous_positions is not None else None,
                ),
                invert_vertical=True,
                invert_lateral=layout == "column",
            )
        )
        channels = tuple(
            replace(channel, inverted=profile.invert_vertical)
            if index == 0
            else replace(channel, inverted=profile.invert_lateral)
            if index == 1
            else channel
            for index, channel in enumerate(timeline.channels)
        )
        frame = OverlayRenderer(
            replace(timeline, settings=profile, channels=channels),
        ).render_sample(sample)
        canvas = backdrop.resize(frame.size, Image.Resampling.NEAREST)
        image = (
            Image.alpha_composite(canvas, frame)
            .resize(size, Image.Resampling.LANCZOS)
            .convert("RGB")
        )
        previews.append(ProfilePreview(layout, title, image))
    return ExportPreview(sample, outside, tuple(previews))
