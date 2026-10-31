"""Single-sample export previews using the production renderer, without encoding.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.validation.checks import validate_sample_range

# cspell:words LANCZOS

from dataclasses import dataclass, replace
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from .frames import OverlayRenderer
from .layouts import registry
from .layouts.contracts import LayoutPosition
from .model import ExportExtent, VideoAspect, ExportLayout, ExportSettings, PROFILES, prepare_export

DARK_BACKGROUND = "#162533"
LIGHT_BACKGROUND = "#e4eaf0"
CHECKER_COLOR = "#aebfce"
CHECKER_SIZE = 30  # Approximate checker width/height in preview pixels.


class PreviewBackground(StrEnum):
    """Preview-only backgrounds with stable UI values.

    Attributes:
        CHECKER: Named value for checker (`checker`).
        LIGHT: Named value for light (`light`).
        DARK: Named value for dark (`dark`).
        POV_LOUP_GAROU: Bundled Loup-Garou video still.
        POV_GOUDURIX: Bundled Goudurix video still.
        POV_TONNERRE_2_ZEUS: Bundled Tonnerre 2 Zeus video still.
        POV_TOUTATIS: Bundled Toutatis video still.
    """

    CHECKER = "checker"
    LIGHT = "light"
    DARK = "dark"
    POV_LOUP_GAROU = "pov-loup-garou"
    POV_GOUDURIX = "pov-goudurix"
    POV_TONNERRE_2_ZEUS = "pov-tonnerre-2-zeus"
    POV_TOUTATIS = "pov-toutatis"


POV_BACKGROUNDS = {
    PreviewBackground.POV_LOUP_GAROU: "Loup-Garou",
    PreviewBackground.POV_GOUDURIX: "Goudurix",
    PreviewBackground.POV_TONNERRE_2_ZEUS: "Tonnerre 2 Zeus",
    PreviewBackground.POV_TOUTATIS: "Toutatis",
}


@dataclass(frozen=True, slots=True)
class ProfilePreview:
    """Profile preview contract and owned data.

    Attributes:
        layout: Stable key selecting the overlay renderer.
        title: Recording or layout title shown without interpreting its contents.
        image: RGB display image fitted to the preview limit without stretching
            its resolved export aspect ratio. Background is presentation-only.
    """

    layout: ExportLayout
    title: str
    image: Image.Image


def compose_preview(
    frame: Image.Image,
    maximum: tuple[int, int],
    background: PreviewBackground,
    photo: Image.Image | None = None,
) -> Image.Image:
    """Composite an export frame and fit its complete geometry for display.

    Args:
        frame: Complete RGBA export frame at its resolved output dimensions.
        maximum: Display width/height limits; never crop or stretch the frame.
        background: Preview-only backdrop, including square checker cells when selected.
        photo: Decoded POV image, fitted and center-cropped behind the complete frame.

    Returns:
        RGB display image preserving the export aspect ratio within the limits.
    """
    canvas = (
        ImageOps.fit(photo, frame.size, Image.Resampling.LANCZOS)
        if photo is not None
        else Image.new(
            "RGBA",
            frame.size,
            DARK_BACKGROUND if background is PreviewBackground.DARK else LIGHT_BACKGROUND,
        )
    )
    if background is PreviewBackground.CHECKER:
        scale = min(maximum[0] / frame.width, maximum[1] / frame.height)
        tile = max(1, round(CHECKER_SIZE / scale))
        draw = ImageDraw.Draw(canvas)
        for y in range(0, frame.height, tile):
            for x in range(0, frame.width, tile):
                if (x // tile + y // tile) % 2:
                    draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=CHECKER_COLOR)
    return ImageOps.contain(
        Image.alpha_composite(canvas, frame),
        maximum,
        Image.Resampling.LANCZOS,
    ).convert("RGB")


@dataclass(frozen=True, slots=True)
class ExportPreview:
    """Export preview contract and owned data.

    Attributes:
        sample: Source sample index to inspect or present.
        outside_range: Whether the selected preview sample is outside the export interval.
        profiles: Preview images indexed by layout profile.
    """

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
    """Build all layout previews from one bound analysis and exact source sample.

    Args:
        analysis: Prepared recording-analysis snapshot used by this operation.
        settings: Validated settings controlling this operation.
        first: First included source sample index.
        last: Last included source sample index.
        sample: Source sample index to inspect or present.
        background: Preview background, excluded from exported overlays.
        previous_positions: Previously selected positions keyed by layout.

    Returns:
        All selectable layout previews and selected-frame metadata. Images retain
        the output aspect ratio within 960 × 540 landscape or 540 × 960 portrait.
        Layouts without the requested extent use Full frame in the gallery.

    Raises:
        ValueError: Preview sample outside recording. Invalid export sample interval.
        OSError: A bundled POV photograph cannot be read.
    """
    count = len(analysis.time.source_indices)
    if not 0 <= sample < count:
        raise ValueError("Preview sample outside recording")
    validate_sample_range(first, last, count, "Invalid export sample interval")
    photo = None
    if background in POV_BACKGROUNDS:
        with Image.open(Path(__file__).with_name("pov") / f"{background.value}.jpg") as source:
            photo = source.convert("RGBA")
    outside = not first <= sample <= last
    timeline = prepare_export(
        analysis,
        settings,
        0 if outside else first,
        count - 1 if outside else last,
    )
    previews: list[ProfilePreview] = []
    size = (540, 960) if settings.aspect is VideoAspect.PORTRAIT else (960, 540)
    selected_plugin = registry.PLUGINS[settings.layout]
    selected_positions = selected_plugin.positions(settings.aspect)
    selected_position = settings.position or selected_positions.default
    for layout, title in PROFILES:
        plugin = registry.PLUGINS[layout]
        if settings.aspect not in plugin.supported_aspects:
            continue
        positions = plugin.positions(settings.aspect)
        profile = (
            settings
            if layout == settings.layout
            else replace(
                settings,
                layout=layout,
                extent=settings.extent
                if settings.extent in plugin.supported_extents(settings.aspect)
                else ExportExtent.FULL_FRAME,
                position=positions.select(
                    selected_position,
                    previous_positions.get(layout) if previous_positions is not None else None,
                ),
                invert_vertical=True,
                invert_lateral=plugin.preview_invert_lateral,
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
        image = compose_preview(frame, size, background, photo)
        previews.append(ProfilePreview(layout, title, image))
    return ExportPreview(sample, outside, tuple(previews))
