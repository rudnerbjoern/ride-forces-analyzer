"""Shared Portrait offsets without changing region placement or output dimensions."""

# cspell:words getchannel getbbox

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from PIL import Image
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import encoder_command
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.layouts import registry, resolve_geometry
from ride_forces_analyzer.rendering.layouts.contracts import SafeRegionGeometry
from ride_forces_analyzer.rendering.layouts.hud import PORTRAIT
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    ExportTimeline,
    VideoAspect,
    prepare_export,
)
from ride_forces_analyzer.rendering.preview import (
    PreviewBackground,
    compose_preview,
    preview_rendered_region,
)


@pytest.mark.parametrize(
    "mode,lift",
    [
        (ExportSafeRegion.OFF, 0),
        (ExportSafeRegion.PORTRAIT_SOCIAL_A, 80),
        (ExportSafeRegion.PORTRAIT_SOCIAL_B, 160),
        (ExportSafeRegion.PORTRAIT_SOCIAL_C, 240),
    ],
)
@pytest.mark.parametrize(
    "layout,canvas,scale",
    [
        (ExportLayout.HUD, (1080, 1920), 1),
        (ExportLayout.RIBBON, (2160, 3840), 2),
        (ExportLayout.CORNERS, (2160, 3840), 2),
        (ExportLayout.ORBIT, (2160, 3840), 2),
    ],
)
def test_offsets_scale_to_the_canvas_and_preserve_every_supported_position(
    mode: ExportSafeRegion,
    lift: int,
    layout: ExportLayout,
    canvas: tuple[int, int],
    scale: int,
) -> None:
    positions = registry.PLUGINS[layout].positions(VideoAspect.PORTRAIT)
    for position in (None, *positions.regions):
        settings = ExportSettings(layout=layout, aspect=VideoAspect.PORTRAIT, position=position)
        original = resolve_geometry(settings)
        geometry = resolve_geometry(replace(settings, safe_region=mode))
        assert geometry.output_size == canvas
        assert geometry.render_size == original.render_size
        assert geometry.offset == original.offset
        assert geometry.safe_region == SafeRegionGeometry(
            0 if mode is ExportSafeRegion.OFF else 72 * scale,
            lift * scale,
        )
        if mode is ExportSafeRegion.OFF:
            assert geometry == original
        x, y = geometry.offset
        width, height = geometry.render_size
        assert 0 <= x <= canvas[0] - width
        assert 0 <= y <= canvas[1] - height
        assert registry.export_region(replace(settings, safe_region=mode)) == (x, y, width, height)
        with pytest.raises(FrozenInstanceError):
            setattr(geometry.safe_region, "side_inset", 0)


@pytest.mark.parametrize(
    "mode,history_top,lateral_y,scale_bottom",
    [
        (ExportSafeRegion.PORTRAIT_SOCIAL_A, 1455, 1355, 1115),
        (ExportSafeRegion.PORTRAIT_SOCIAL_B, 1375, 1275, 1035),
        (ExportSafeRegion.PORTRAIT_SOCIAL_C, 1295, 1195, 955),
    ],
)
def test_hud_offsets_match_the_reviewed_preview_anchors_and_crop_clearance(
    mode: ExportSafeRegion,
    history_top: int,
    lateral_y: int,
    scale_bottom: int,
) -> None:
    geometry = resolve_geometry(
        ExportSettings(layout=ExportLayout.HUD, aspect=VideoAspect.PORTRAIT, safe_region=mode),
    )
    offsets = geometry.safe_region
    assert PORTRAIT.history_top - offsets.history_lift == history_top
    assert PORTRAIT.lateral_y - offsets.history_lift == lateral_y
    assert PORTRAIT.scale_bottom - offsets.history_lift == scale_bottom
    assert PORTRAIT.left_axis + offsets.side_inset == 127
    assert PORTRAIT.right_axis - offsets.side_inset == 898
    assert PORTRAIT.lateral_left + offsets.side_inset == 202
    assert PORTRAIT.lateral_right - offsets.side_inset == 873
    assert PORTRAIT.history_left + offsets.side_inset == 167
    # The 112-pixel heading inset exceeds the screenshots' inferred 56-pixel crop.
    heading_inset = 40 + offsets.side_inset
    assert heading_inset == 112
    assert 56 < heading_inset < geometry.output_size[0] - 56
    assert PORTRAIT.scale_top < scale_bottom < lateral_y < history_top
    assert history_top + 3 * PORTRAIT.history_row < geometry.output_size[1]


@pytest.mark.parametrize("layout", [ExportLayout.HUD, ExportLayout.ORBIT])
def test_preview_composition_and_encoder_share_the_resolved_region(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    layout: ExportLayout,
) -> None:
    assert manta.analysis is not None

    class Renderer:
        def render_position(self, position: float) -> Image.Image:
            return Image.new("RGBA", (16, 16), (0, 200, 255, 255))

    def create(timeline: ExportTimeline) -> Renderer:
        return Renderer()

    plugin = replace(registry.PLUGINS[layout], create=create)
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, layout: plugin})
    settings = ExportSettings(
        layout=layout,
        aspect=VideoAspect.PORTRAIT,
        safe_region=ExportSafeRegion.PORTRAIT_SOCIAL_B,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3601)
    renderer = OverlayRenderer(timeline)
    geometry = resolve_geometry(settings)
    assert renderer.geometry == geometry
    region = renderer.render_region(0)
    frame = renderer.render_frame(0)
    x, y = geometry.offset
    width, height = geometry.render_size
    assert frame.getchannel("A").getbbox() == (x, y, x + width, y + height)
    expected_preview = compose_preview(frame, (540, 960), PreviewBackground.DARK)
    preview = preview_rendered_region(timeline, region.tobytes(), PreviewBackground.DARK)
    assert preview.tobytes() == expected_preview.tobytes()
    command = encoder_command(Path("ffmpeg"), timeline, Path("output.mov"))
    assert command[command.index("-video_size") + 1] == f"{width}x{height}"
    assert command[command.index("-vf") + 1] == (
        f"pad={geometry.output_size[0]}:{geometry.output_size[1]}:{x}:{y}:color=black@0"
    )
