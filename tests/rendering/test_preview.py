"""Actual export previews use exact graph samples, production frames and no encoder."""

from ride_forces_analyzer.rendering.model import StandardFrameRate

# cspell:words LANCZOS getpixel getchannel getbbox

from dataclasses import replace
from typing import Literal

from PIL import Image
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    FrameRate,
    ExportLayout,
    VideoAspect,
    ExportSettings,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.rendering.preview import PreviewBackground, build_previews


@pytest.mark.parametrize("layout", [profile[0] for profile in PROFILES])
def test_portrait_contains_complete_region(manta: ExplorerData, layout: ExportLayout) -> None:
    assert manta.analysis is not None
    from ride_forces_analyzer.rendering.model import ExportLayout
    from ride_forces_analyzer.rendering.layouts import export_region

    settings = ExportSettings(layout=ExportLayout(layout), aspect=VideoAspect.PORTRAIT)
    renderer = OverlayRenderer(prepare_export(manta.analysis, settings, 3500, 3700))
    frame = renderer.render_sample(3600)
    x, y, width, height = export_region(settings)
    if layout == ExportLayout.HUD:
        assert (x, y, width, height) == (0, 0, *frame.size)
    else:
        assert x > 0 and y > 0 and x + width < frame.width and y + height < frame.height
    region = renderer.render_region(0)
    assert region.size == (width, height)
    bounds = frame.getchannel("A").getbbox()
    if layout == ExportLayout.HUD:
        assert bounds is not None
        # The bottom gradient reaches the frame edges; the upper canvas stays open.
        assert bounds[0] == 0 and bounds[2:] == (width, height)
        assert 0 < bounds[1] < height
    elif layout == ExportLayout.ORBIT:
        assert width == height and bounds is not None
        assert x <= bounds[0] < x + 10 and y <= bounds[1] < y + 10
        assert x + width - 10 < bounds[2] <= x + width
        assert y + height - 10 < bounds[3] <= y + height
        assert frame.getchannel("A").getpixel((x, y)) == 0
        assert frame.getchannel("A").getpixel((x + width - 1, y + height - 1)) == 0
    else:
        assert bounds == (x, y, x + width, y + height)
    expected = renderer.render_sample(3500).crop((x, y, x + width, y + height))
    background = Image.new("RGBA", region.size, "black")
    assert (
        Image.alpha_composite(background, expected).tobytes()
        == Image.alpha_composite(
            background,
            region,
        ).tobytes()
    )


@pytest.mark.parametrize("aspect", list(VideoAspect))
@pytest.mark.parametrize("selected_layout", [ExportLayout.ORBIT, ExportLayout.HUD])
def test_previews_match_production_at_exact_graph_sample(
    manta: ExplorerData,
    aspect: VideoAspect,
    selected_layout: Literal[ExportLayout.ORBIT, ExportLayout.HUD],
) -> None:
    assert manta.analysis is not None
    sample = manta.source.recording.indices.start + 72 * 50 + 1
    settings = ExportSettings(
        layout=selected_layout,
        position=(
            LayoutPosition.FULL_SCREEN
            if selected_layout == ExportLayout.HUD
            else LayoutPosition.TOP_RIGHT
        ),
        fps=30,
        aspect=aspect,
        invert_vertical=False,
        invert_lateral=False,
    )
    first, last = sample - 101, sample + 100
    result = build_previews(manta.analysis, settings, first, last, sample, PreviewBackground.DARK)
    assert result.sample == sample and not result.outside_range
    assert tuple((p.layout, p.title) for p in result.profiles) == PROFILES
    timeline = prepare_export(manta.analysis, settings, first, last)
    for profile in result.profiles:
        chosen = (
            settings
            if profile.layout == selected_layout
            else replace(
                settings,
                layout=profile.layout,
                position={
                    ExportLayout.CORNERS: LayoutPosition.TOP_RIGHT,
                    ExportLayout.COLUMN: LayoutPosition.RIGHT,
                    ExportLayout.RIBBON: (
                        LayoutPosition.BOTTOM
                        if selected_layout == ExportLayout.HUD
                        else LayoutPosition.TOP
                    ),
                    ExportLayout.HUD: LayoutPosition.FULL_SCREEN,
                    ExportLayout.ORBIT: LayoutPosition.BOTTOM_LEFT,
                }[profile.layout],
                invert_vertical=True,
                invert_lateral=profile.layout == ExportLayout.COLUMN,
            )
        )
        actual = OverlayRenderer(prepare_export(manta.analysis, chosen, first, last)).render_sample(
            sample,
        )
        expected = (
            Image.alpha_composite(Image.new("RGBA", actual.size, "#162533"), actual)
            .resize(
                (540, 960) if aspect is VideoAspect.PORTRAIT else (960, 540),
                Image.Resampling.LANCZOS,
            )
            .convert("RGB")
        )
        assert profile.image.tobytes() == expected.tobytes()
    with pytest.raises(ValueError, match="outside"):
        OverlayRenderer(timeline).render_sample(last + 1)


@pytest.mark.parametrize("position", [LayoutPosition.TOP, LayoutPosition.BOTTOM])
@pytest.mark.parametrize("previous", [LayoutPosition.TOP_LEFT, LayoutPosition.TOP_RIGHT])
def test_edge_choice_moves_corner_previews_to_equivalent_side(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    position: LayoutPosition,
    previous: LayoutPosition,
) -> None:
    assert manta.analysis is not None
    settings_by_layout: dict[str, ExportSettings] = {}

    def render(self: OverlayRenderer, sample: float) -> Image.Image:
        settings_by_layout[self.timeline.settings.layout] = self.timeline.settings
        return Image.new("RGBA", (8, 8))

    monkeypatch.setattr(OverlayRenderer, "render_sample", render)
    build_previews(
        manta.analysis,
        ExportSettings(layout=ExportLayout.RIBBON, position=position),
        3500,
        3700,
        3600,
        previous_positions={
            ExportLayout.ORBIT: previous,
            ExportLayout.COLUMN: LayoutPosition.LEFT,
        },
    )
    assert settings_by_layout[ExportLayout.COLUMN].position is LayoutPosition.LEFT
    assert settings_by_layout[ExportLayout.CORNERS].position == (
        LayoutPosition.TOP_RIGHT if position == LayoutPosition.TOP else LayoutPosition.BOTTOM_RIGHT
    )
    assert (
        settings_by_layout[ExportLayout.ORBIT].position
        == {
            (LayoutPosition.TOP, LayoutPosition.TOP_LEFT): LayoutPosition.TOP_LEFT,
            (LayoutPosition.BOTTOM, LayoutPosition.TOP_LEFT): LayoutPosition.BOTTOM_LEFT,
            (LayoutPosition.TOP, LayoutPosition.TOP_RIGHT): LayoutPosition.TOP_RIGHT,
            (LayoutPosition.BOTTOM, LayoutPosition.TOP_RIGHT): LayoutPosition.BOTTOM_RIGHT,
        }[position, previous]
    )


@pytest.mark.parametrize(
    "fps",
    [30, 50, 60, StandardFrameRate.FPS_23_976, StandardFrameRate.FPS_59_94],
)
def test_preview_sample_is_independent_of_video_rate(
    manta: ExplorerData,
    fps: FrameRate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    positions: list[float] = []

    def record_position(self: OverlayRenderer, position: float) -> Image.Image:
        positions.append(position)
        return Image.new("RGBA", (8, 8), (0, 0, 0, 0))

    monkeypatch.setattr(OverlayRenderer, "render_sample", record_position)
    sample = manta.source.recording.indices.start + 72 * 50 + 1
    result = build_previews(
        manta.analysis,
        ExportSettings(fps=fps),
        sample - 101,
        sample + 100,
        sample,
    )
    assert result.sample == sample
    assert positions == [sample] * len(PROFILES)


@pytest.mark.parametrize("mode", [VideoOutput.TRANSPARENT, VideoOutput.OPAQUE])
def test_outside_range_keeps_graph_sample_and_smoothing(
    manta: ExplorerData,
    mode: VideoOutput,
) -> None:
    data = manta.with_smoothing(3)
    assert data.analysis is not None
    sample = data.source.recording.indices.start + 72 * 50
    settings = ExportSettings(output=mode)
    original = data.source.source_sha256
    result = build_previews(data.analysis, settings, 0, 100, sample, PreviewBackground.LIGHT)
    assert result.outside_range and result.sample == sample
    assert data.source.source_sha256 == original and data.calibration_available
    assert data.smoothing_window == 3
    assert all(
        p.image.getpixel((0, 0)) == ((0, 0, 0) if mode == VideoOutput.OPAQUE else (228, 234, 240))
        for p in result.profiles
    )
    with pytest.raises(ValueError, match="outside"):
        build_previews(data.analysis, settings, 0, 100, -1)
