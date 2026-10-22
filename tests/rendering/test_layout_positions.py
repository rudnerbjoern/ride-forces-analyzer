"""Selected layout regions stay consistent across composition and encoding."""

# cspell:words getchannel getbbox

from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

from PIL import Image
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import encoder_command
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.layouts import COLORS, registry
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition, LayoutPositions
from ride_forces_analyzer.rendering.model import ExportSettings, ExportTimeline, prepare_export


@pytest.mark.parametrize(
    ("layout", "preferred", "expected"),
    [
        ("orbit", LayoutPosition.TOP, LayoutPosition.TOP_LEFT),
        ("orbit", LayoutPosition.BOTTOM, LayoutPosition.BOTTOM_LEFT),
        ("corners", LayoutPosition.BOTTOM, LayoutPosition.BOTTOM_RIGHT),
        ("corners", LayoutPosition.TOP_LEFT, LayoutPosition.TOP_LEFT),
        ("ribbon", LayoutPosition.TOP_LEFT, LayoutPosition.TOP),
        ("ribbon", LayoutPosition.BOTTOM_RIGHT, LayoutPosition.BOTTOM),
        ("column", LayoutPosition.TOP_LEFT, LayoutPosition.LEFT),
        ("ribbon", LayoutPosition.LEFT, LayoutPosition.BOTTOM),
        ("orbit", None, LayoutPosition.BOTTOM_LEFT),
    ],
)
def test_equivalent_position_keeps_shared_axis_and_uses_default_for_other_axis(
    layout: str,
    preferred: LayoutPosition | None,
    expected: LayoutPosition,
) -> None:
    from ride_forces_analyzer.rendering.model import ExportLayout

    plugin = registry.PLUGINS[cast(ExportLayout, layout)]
    for positions in (plugin.landscape, plugin.portrait):
        assert positions.select(preferred) == expected


@pytest.mark.parametrize("position", ["right", "missing", 1, False])
def test_export_settings_reject_untyped_positions(position: object) -> None:
    with pytest.raises(ValueError, match="export position"):
        ExportSettings(position=cast(LayoutPosition, position))


def test_export_settings_validate_positions_for_each_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = replace(
        registry.PLUGINS["orbit"],
        landscape=LayoutPositions({LayoutPosition.TOP: (0, 0, 40, 30)}, LayoutPosition.TOP),
        portrait=LayoutPositions({LayoutPosition.BOTTOM: (10, 20, 30, 40)}, LayoutPosition.BOTTOM),
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, "orbit": plugin})
    settings = ExportSettings(layout="orbit", position=LayoutPosition.TOP)
    assert registry.export_region(settings) == (0, 0, 40, 30)
    assert registry.export_region(ExportSettings(layout="orbit", aspect="portrait")) == (
        10,
        20,
        30,
        40,
    )
    with pytest.raises(ValueError, match="export position"):
        replace(settings, aspect="portrait")
    with pytest.raises(ValueError, match="export position"):
        ExportSettings(layout="column", position=LayoutPosition.TOP)


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize("output", ["transparent", "opaque"])
def test_selected_region_controls_frame_size_placement_and_encoder_padding(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    aspect: Literal["landscape", "portrait"],
    output: Literal["transparent", "opaque"],
) -> None:
    assert manta.analysis is not None

    class Renderer:
        def render_position(self, position: float) -> Image.Image:
            return Image.new("RGBA", (8, 8), COLORS[0])

    def create(timeline: ExportTimeline) -> Renderer:
        return Renderer()

    plugin = replace(
        registry.PLUGINS["orbit"],
        landscape=LayoutPositions(
            {LayoutPosition.TOP: (15, 25, 80, 60), LayoutPosition.BOTTOM: (200, 300, 40, 30)},
            LayoutPosition.BOTTOM,
        ),
        portrait=LayoutPositions(
            {LayoutPosition.TOP: (25, 35, 60, 80), LayoutPosition.BOTTOM: (300, 400, 30, 40)},
            LayoutPosition.BOTTOM,
        ),
        create=create,
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, "orbit": plugin})
    settings = ExportSettings(
        layout="orbit",
        aspect=aspect,
        output=output,
        position=LayoutPosition.TOP,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3601)
    default = prepare_export(manta.analysis, replace(settings, position=None), 3600, 3601)
    assert timeline.analysis is default.analysis is manta.analysis
    assert timeline.analysis.context is default.analysis.context
    x, y, width, height = (15, 25, 80, 60) if aspect == "landscape" else (25, 35, 60, 80)
    renderer = OverlayRenderer(timeline)
    region = renderer.render_region(0)
    frame = renderer.render_frame(0)
    assert region.size == (width, height)
    assert frame.size == settings.dimensions
    assert frame.crop((x, y, x + width, y + height)).tobytes() == region.tobytes()
    bounds = frame.getchannel("A").getbbox()
    assert bounds == (
        (x, y, x + width, y + height) if output == "transparent" else (0, 0, *settings.dimensions)
    )
    command = encoder_command(Path("ffmpeg"), timeline, Path("output.mov"))
    assert command[command.index("-video_size") + 1] == f"{width}x{height}"
    canvas_width, canvas_height = settings.dimensions
    assert command[command.index("-vf") + 1] == (
        f"pad={canvas_width}:{canvas_height}:{x}:{y}:color=black@"
        + ("0" if output == "transparent" else "1")
    )
