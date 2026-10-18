"""Built-in coverage and extension dispatch use the same layout contract."""

# cspell:words getchannel getbbox getpixel getcolors

from types import MappingProxyType
from typing import cast

from PIL import Image
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSettings,
    ExportTimeline,
    PROFILES,
    prepare_export,
)
from ride_forces_analyzer.rendering.layouts import PLUGINS
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPlugin
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.rendering.layouts.charts import ChartRenderer
from ride_forces_analyzer.rendering.layouts.ribbon import RibbonRenderer
from ride_forces_analyzer.rendering.layouts.corners import CornersRenderer


def test_every_persisted_profile_has_registered_geometry() -> None:
    assert tuple(PLUGINS) == tuple(key for key, _ in PROFILES)
    with pytest.raises(ValueError, match="Unknown export layout"):
        ExportSettings(layout=cast(ExportLayout, "unregistered"))
    for key, plugin in PLUGINS.items():
        assert plugin.key == key
        for aspect, region in (("landscape", plugin.landscape), ("portrait", plugin.portrait)):
            settings = ExportSettings(
                layout=key,
                aspect="landscape" if aspect == "landscape" else "portrait",
            )
            x, y, width, height = region
            assert x >= 0 and y >= 0 and width > 0 and height > 0
            assert x + width <= settings.dimensions[0] and y + height <= settings.dimensions[1]


def test_compositor_accepts_a_registered_renderer_without_layout_branches(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline = prepare_export(manta, ExportSettings(layout="orbit"), 3600, 3601)
    positions: list[float] = []

    class CustomRenderer:
        def render_position(self, position: float) -> Image.Image:
            positions.append(position)
            return Image.new("RGBA", (8, 8), (255, 0, 0, 180))

    def create(actual: ExportTimeline) -> CustomRenderer:
        assert actual is timeline
        return CustomRenderer()

    region = (100, 200, 40, 30)
    monkeypatch.setattr(
        registry,
        "PLUGINS",
        MappingProxyType(
            {
                "orbit": LayoutPlugin("orbit", region, region, create),
            },
        ),
    )
    image = OverlayRenderer(timeline).render_sample(3600.5)
    assert positions == [3600.5]
    assert image.getchannel("A").getbbox() == (100, 200, 140, 230)
    assert image.getpixel((100, 200)) == (255, 0, 0, 180)
    assert image.getpixel((99, 200)) == (0, 0, 0, 0)


def test_individual_chart_style_applies_in_both_aspects_without_leaking(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    palette = ("#ff00ff", "#00ffff", "#ffff00")
    monkeypatch.setattr(RibbonRenderer, "channel_colors", palette)
    monkeypatch.setattr(RibbonRenderer, "label_size", 42)
    for aspect in ("landscape", "portrait"):
        settings = ExportSettings(
            layout="ribbon",
            aspect=aspect,
        )
        timeline = prepare_export(manta, settings, 3600, 3601)
        renderer = registry.create_renderer(timeline)
        assert isinstance(renderer, ChartRenderer)
        assert renderer.channel_colors == palette
        unchanged = CornersRenderer(timeline)
        assert unchanged.channel_colors != palette
        assert renderer.label.getlength("LATERAL") > unchanged.label.getlength("LATERAL")
        image = renderer.render_position(3600)
        colors = image.getcolors(image.width * image.height)
        assert colors is not None
        assert any(color == (255, 0, 255, 255) for _, color in colors)
