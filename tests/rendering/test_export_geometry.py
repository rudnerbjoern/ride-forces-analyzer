"""Fixed output geometry and plugin capabilities, independent of frame generation."""

from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from ride_forces_analyzer.rendering.layouts import registry, resolve_geometry
from ride_forces_analyzer.rendering.layouts.contracts import (
    ContentArea,
    LayoutPosition,
    LayoutPositions,
    Region,
)
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSettings,
    VideoAspect,
)


@pytest.mark.parametrize("layout", list(ExportLayout))
@pytest.mark.parametrize("aspect", list(VideoAspect))
def test_full_frame_geometry_preserves_registered_canvas_and_placement(
    layout: ExportLayout,
    aspect: VideoAspect,
) -> None:
    plugin = registry.PLUGINS[layout]
    if aspect not in plugin.supported_aspects:
        with pytest.raises(ValueError, match="Unsupported export format"):
            ExportSettings(layout=layout, aspect=aspect)
        return
    positions = plugin.positions(aspect)
    for position, (x, y, width, height) in positions.regions.items():
        settings = ExportSettings(layout=layout, aspect=aspect, position=position)
        geometry = resolve_geometry(settings)
        assert settings.extent is ExportExtent.FULL_FRAME
        assert geometry.output_size == settings.dimensions
        assert geometry.render_size == (width, height)
        assert geometry.crop == (0, 0, width, height)
        assert geometry.offset == (x, y)


@pytest.mark.parametrize(
    "layout,landscape,portrait",
    [
        (ExportLayout.RIBBON, (3110, 400), (1720, 2280)),
        (ExportLayout.CORNERS, (880, 1160), (1720, 2280)),
        (ExportLayout.ORBIT, (830, 830), (1220, 1220)),
    ],
)
def test_content_geometry_matches_approved_dimensions_and_ignores_retained_position(
    layout: ExportLayout,
    landscape: tuple[int, int],
    portrait: tuple[int, int],
) -> None:
    plugin = registry.PLUGINS[layout]
    for aspect, expected in ((VideoAspect.LANDSCAPE, landscape), (VideoAspect.PORTRAIT, portrait)):
        settings = ExportSettings(layout=layout, aspect=aspect, extent=ExportExtent.CONTENT_AREA)
        geometry = resolve_geometry(settings)
        content = plugin.content_area(aspect)
        assert content is not None
        assert geometry.output_size == expected
        assert geometry.crop == content.bounds
        assert geometry.offset == (16, 16)
        assert all(size % 10 == 0 and size % 2 == 0 for size in expected)
        assert geometry.output_size[0] - geometry.crop[2] - geometry.offset[0] >= 16
        assert geometry.output_size[1] - geometry.crop[3] - geometry.offset[1] >= 16
        for position in (None, *LayoutPosition):
            retained = replace(settings, position=position)
            assert retained.position == position
            assert resolve_geometry(retained) == geometry
        with pytest.raises(FrozenInstanceError):
            setattr(geometry, "offset", (0, 0))


@pytest.mark.parametrize("aspect", list(VideoAspect))
def test_full_frame_only_capability_rejects_content_area(aspect: VideoAspect) -> None:
    plugin = registry.PLUGINS[ExportLayout.HUD]
    assert plugin.supported_extents(aspect) == frozenset((ExportExtent.FULL_FRAME,))
    assert plugin.content_area(aspect) is None
    with pytest.raises(ValueError, match="Unsupported export extent"):
        ExportSettings(layout=plugin.key, aspect=aspect, extent=ExportExtent.CONTENT_AREA)


def test_landscape_only_rectangle_preserves_4k_height_without_any_padding() -> None:
    plugin = registry.PLUGINS[ExportLayout.COLUMN]
    assert plugin.supported_aspects == frozenset((VideoAspect.LANDSCAPE,))
    assert plugin.portrait is None
    assert not plugin.supported_extents(VideoAspect.PORTRAIT)
    assert plugin.landscape_content == ContentArea((0, 0, 960, 2160), margin=0)
    for extent in ExportExtent:
        settings = ExportSettings(layout=plugin.key, extent=extent)
        geometry = resolve_geometry(settings)
        assert geometry.render_size == (960, 2160)
        assert geometry.output_size[1] == settings.dimensions[1] == 2160
        assert geometry.crop == (0, 0, 960, 2160)
        if extent is ExportExtent.CONTENT_AREA:
            assert geometry.output_size == (960, 2160)
            assert geometry.offset == (0, 0)
        else:
            assert geometry.output_size == (3840, 2160)
        with pytest.raises(ValueError, match="Unsupported export format"):
            replace(settings, aspect=VideoAspect.PORTRAIT)


@pytest.mark.parametrize(
    "bounds,margin,expected",
    [
        ((0, 0, 796, 796), 16, (830, 830)),
        ((2, 3, 798, 399), 16, (830, 440)),
        ((0, 0, 10, 20), 0, (10, 20)),
        ((0, 0, 11, 21), 0, (20, 30)),
    ],
)
def test_margin_then_rounding_keeps_exact_multiples_and_never_shrinks(
    bounds: Region,
    margin: int,
    expected: tuple[int, int],
) -> None:
    assert ContentArea(bounds, margin).dimensions == expected


@pytest.mark.parametrize("margin", [-1, True, 1.5])
def test_invalid_content_margins_are_rejected(margin: object) -> None:
    with pytest.raises(ValueError, match="Content margin"):
        ContentArea((0, 0, 1, 1), cast(int, margin))


def test_plugin_validates_crop_bounds_extent_rates_and_format_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = registry.PLUGINS[ExportLayout.ORBIT]
    with pytest.raises(ValueError, match="canonical render region"):
        replace(plugin, landscape_content=ContentArea((799, 0, 2, 1)))
    with pytest.raises(ValueError, match="typed ContentArea"):
        replace(plugin, landscape_content=cast(ContentArea, (0, 0, 1, 1)))
    rates = {ExportExtent.CONTENT_AREA: (0.1, 0.2)}
    changed = replace(plugin, landscape_content=None, prores_4444_size_rates=rates)
    rates[ExportExtent.CONTENT_AREA] = (0.2, 0.4)
    assert changed.prores_4444_size_rates[ExportExtent.CONTENT_AREA] == (0.1, 0.2)
    with pytest.raises(TypeError):
        cast(dict[ExportExtent, tuple[float, float] | None], changed.prores_4444_size_rates)[
            ExportExtent.CONTENT_AREA
        ] = None
    assert changed.supported_extents(VideoAspect.LANDSCAPE) == frozenset((ExportExtent.FULL_FRAME,))
    assert ExportExtent.CONTENT_AREA in changed.supported_extents(VideoAspect.PORTRAIT)
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: changed})
    with pytest.raises(ValueError, match="Unsupported export extent"):
        ExportSettings(layout=plugin.key, extent=ExportExtent.CONTENT_AREA)
    assert resolve_geometry(
        ExportSettings(
            layout=plugin.key,
            aspect=VideoAspect.PORTRAIT,
            extent=ExportExtent.CONTENT_AREA,
        ),
    ).output_size == (1220, 1220)
    with pytest.raises(ValueError, match="supported typed export extent"):
        replace(plugin, prores_4444_size_rates={cast(ExportExtent, "content_area"): (0.1, 0.2)})
    with pytest.raises(ValueError, match="extent mapping"):
        replace(plugin, prores_4444_size_rates=None)
    with pytest.raises(ValueError, match="supported typed export extent"):
        replace(
            registry.PLUGINS[ExportLayout.HUD],
            h264_size_rates={ExportExtent.CONTENT_AREA: None},
        )


def test_extent_and_aspect_require_enum_members_and_odd_output_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert ExportExtent("content_area") is ExportExtent.CONTENT_AREA
    with pytest.raises(ValueError, match="Unsupported export extent"):
        ExportSettings(extent=cast(ExportExtent, "content_area"))
    with pytest.raises(ValueError, match="Unsupported export position"):
        ExportSettings(extent=ExportExtent.CONTENT_AREA, position=cast(LayoutPosition, "left"))
    plugin = registry.PLUGINS[ExportLayout.ORBIT]
    with pytest.raises(ValueError, match="aspect"):
        plugin.supported_extents(cast(VideoAspect, "landscape"))
    settings = ExportSettings(layout=plugin.key)
    changed = replace(
        plugin,
        landscape=LayoutPositions({LayoutPosition.TOP: (0, 0, 20, 20)}, LayoutPosition.TOP),
        landscape_canvas=(101, 100),
        landscape_content=None,
    )
    monkeypatch.setattr(registry, "PLUGINS", {**registry.PLUGINS, plugin.key: changed})
    with pytest.raises(ValueError, match="must be even"):
        resolve_geometry(settings)
