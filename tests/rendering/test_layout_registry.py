"""Built-in coverage and extension dispatch use the same layout contract."""

# cspell:words getchannel getbbox getpixel getcolors

from types import MappingProxyType
from dataclasses import FrozenInstanceError, replace
import json
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
from ride_forces_analyzer.rendering.layouts.contracts import (
    LayoutPlugin,
    LayoutPosition,
    LayoutPositions,
    Region,
)
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
        for aspect, positions in (("landscape", plugin.landscape), ("portrait", plugin.portrait)):
            settings = ExportSettings(
                layout=key,
                aspect="landscape" if aspect == "landscape" else "portrait",
            )
            assert positions.default in positions.regions
            for x, y, width, height in positions.regions.values():
                assert x >= 0 and y >= 0 and width > 0 and height > 0
                assert x + width <= settings.dimensions[0] and y + height <= settings.dimensions[1]


@pytest.mark.parametrize(
    ("key", "default", "supported", "landscape", "portrait"),
    [
        (
            "ribbon",
            LayoutPosition.BOTTOM,
            {LayoutPosition.TOP, LayoutPosition.BOTTOM},
            (384, 1692, 3072, 360),
            (240, 1360, 1680, 2240),
        ),
        (
            "hud",
            LayoutPosition.FULL_SCREEN,
            {LayoutPosition.FULL_SCREEN},
            (0, 0, 1920, 1080),
            (0, 0, 1080, 1920),
        ),
        (
            "column",
            LayoutPosition.RIGHT,
            {LayoutPosition.LEFT, LayoutPosition.RIGHT},
            (2880, 0, 960, 2160),
            (612, 300, 1440, 3240),
        ),
        (
            "corners",
            LayoutPosition.TOP_RIGHT,
            {
                LayoutPosition.TOP_LEFT,
                LayoutPosition.TOP_RIGHT,
                LayoutPosition.BOTTOM_LEFT,
                LayoutPosition.BOTTOM_RIGHT,
            },
            (2808, 140, 840, 1120),
            (372, 240, 1680, 2240),
        ),
        (
            "orbit",
            LayoutPosition.BOTTOM_LEFT,
            {
                LayoutPosition.TOP_LEFT,
                LayoutPosition.TOP_RIGHT,
                LayoutPosition.BOTTOM_LEFT,
                LayoutPosition.BOTTOM_RIGHT,
            },
            (192, 1260, 800, 800),
            (240, 2412, 1188, 1188),
        ),
    ],
)
def test_builtin_positions_and_existing_default_placement(
    key: ExportLayout,
    default: LayoutPosition,
    supported: set[LayoutPosition],
    landscape: Region,
    portrait: Region,
) -> None:
    plugin = PLUGINS[key]
    for positions in (plugin.landscape, plugin.portrait):
        assert positions.default == default
        assert set(positions.regions) == supported
    assert registry.export_region(ExportSettings(layout=key)) == landscape
    assert registry.export_region(ExportSettings(layout=key, aspect="portrait")) == portrait


def test_layout_owns_positions_sizes_and_defaults_independently_per_format() -> None:
    regions: dict[LayoutPosition, Region] = {
        LayoutPosition.TOP: (10, 20, 30, 40),
        LayoutPosition.BOTTOM: (50, 60, 70, 80),
    }
    landscape = LayoutPositions(regions, default=LayoutPosition.TOP)
    portrait = LayoutPositions(
        {LayoutPosition.LEFT: (100, 200, 300, 400)},
        default=LayoutPosition.LEFT,
    )
    plugin = replace(PLUGINS["orbit"], landscape=landscape, portrait=portrait)
    regions[LayoutPosition.TOP] = (0, 0, 1, 1)
    assert plugin.landscape.regions[LayoutPosition.TOP] == (10, 20, 30, 40)
    assert plugin.landscape.regions[LayoutPosition.BOTTOM] == (50, 60, 70, 80)
    assert plugin.portrait.default == LayoutPosition.LEFT
    assert plugin.portrait.regions == {LayoutPosition.LEFT: (100, 200, 300, 400)}
    with pytest.raises(TypeError):
        cast(dict[LayoutPosition, Region], landscape.regions)[LayoutPosition.TOP] = (0, 0, 1, 1)
    with pytest.raises(FrozenInstanceError):
        setattr(landscape, "default", LayoutPosition.BOTTOM)


@pytest.mark.parametrize(
    "region",
    [
        (-1, 0, 1, 1),
        (0, -1, 1, 1),
        (0, 0, 0, 1),
        (0, 0, 1, -1),
        (False, 0, 1, 1),
        (0, 0, 1.5, 1),
        (0, 0, 1),
        [0, 0, 1, 1],
    ],
)
def test_invalid_region_geometry_is_rejected(region: object) -> None:
    with pytest.raises(ValueError, match="Layout region"):
        LayoutPositions({LayoutPosition.TOP: cast(Region, region)}, default=LayoutPosition.TOP)


def test_missing_default_and_unknown_positions_are_rejected() -> None:
    with pytest.raises(ValueError, match="supported default"):
        LayoutPositions({}, default=LayoutPosition.TOP)
    with pytest.raises(ValueError, match="supported default"):
        LayoutPositions({LayoutPosition.TOP: (0, 0, 1, 1)}, default=LayoutPosition.BOTTOM)
    invalid = cast(LayoutPosition, "middle")
    with pytest.raises(ValueError, match="Unknown layout position"):
        LayoutPositions(
            {LayoutPosition.TOP: (0, 0, 1, 1), invalid: (0, 0, 1, 1)},
            default=LayoutPosition.TOP,
        )


@pytest.mark.parametrize("position", list(LayoutPosition))
def test_position_enum_round_trips_stable_json_values(position: LayoutPosition) -> None:
    value = json.loads(json.dumps(position))
    assert type(value) is str and value == position.value
    assert LayoutPosition(value) is position


def test_position_enum_values_are_explicit_and_unknown_values_fail() -> None:
    assert {position.name: position.value for position in LayoutPosition} == {
        "TOP": "top",
        "BOTTOM": "bottom",
        "LEFT": "left",
        "RIGHT": "right",
        "TOP_LEFT": "top_left",
        "TOP_RIGHT": "top_right",
        "BOTTOM_LEFT": "bottom_left",
        "BOTTOM_RIGHT": "bottom_right",
        "FULL_SCREEN": "full_screen",
    }
    with pytest.raises(ValueError):
        LayoutPosition("middle")


def test_layout_metadata_requires_enum_keys_and_default() -> None:
    # StrEnum compares equal to its string value; require actual enum members.
    raw = cast(LayoutPosition, "top")
    with pytest.raises(ValueError, match="Unknown layout position"):
        LayoutPositions({raw: (0, 0, 1, 1)}, default=LayoutPosition.TOP)
    with pytest.raises(ValueError, match="supported default"):
        LayoutPositions({LayoutPosition.TOP: (0, 0, 1, 1)}, default=raw)


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_all_position_regions_must_fit_their_format_canvas(aspect: str) -> None:
    width, height = (3840, 2160) if aspect == "landscape" else (2160, 3840)
    exact = LayoutPositions({LayoutPosition.TOP: (0, 0, width, height)}, default=LayoutPosition.TOP)
    plugin = PLUGINS["orbit"]
    if aspect == "landscape":
        assert replace(plugin, landscape=exact).landscape == exact
    else:
        assert replace(plugin, portrait=exact).portrait == exact
    # Validate the nondefault entry as well as the selected default.
    for overflow in ((1, 0, width, 1), (0, 1, 1, height)):
        positions = LayoutPositions(
            {LayoutPosition.TOP: (0, 0, 1, 1), LayoutPosition.BOTTOM: overflow},
            default=LayoutPosition.TOP,
        )
        with pytest.raises(ValueError, match="fit within"):
            if aspect == "landscape":
                replace(plugin, landscape=positions)
            else:
                replace(plugin, portrait=positions)


def test_compositor_accepts_a_registered_renderer_without_layout_branches(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout="orbit"), 3600, 3601)
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
                "orbit": LayoutPlugin(
                    "orbit",
                    LayoutPositions({LayoutPosition.TOP: region}, default=LayoutPosition.TOP),
                    LayoutPositions({LayoutPosition.TOP: region}, default=LayoutPosition.TOP),
                    create,
                ),
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
    assert manta.analysis is not None
    palette = ("#ff00ff", "#00ffff", "#ffff00")
    monkeypatch.setattr(RibbonRenderer, "channel_colors", palette)
    monkeypatch.setattr(RibbonRenderer, "label_size", 42)
    for aspect in ("landscape", "portrait"):
        settings = ExportSettings(
            layout="ribbon",
            aspect=aspect,
        )
        timeline = prepare_export(manta.analysis, settings, 3600, 3601)
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
