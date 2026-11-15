"""Production Portrait arrangements, localized glyph bounds and scientific parity."""

# cspell:words getbbox textbbox

from dataclasses import replace
from typing import Any, cast

from PIL import ImageDraw
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.i18n import Language, tr
from ride_forces_analyzer.rendering.layouts import create_renderer, registry, resolve_geometry
from ride_forces_analyzer.rendering.layouts.hud import HudRenderer
from ride_forces_analyzer.rendering.model import (
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    VideoAspect,
    prepare_export,
)

LAYOUTS = (ExportLayout.HUD, ExportLayout.RIBBON, ExportLayout.CORNERS, ExportLayout.ORBIT)


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("mode", list(ExportSafeRegion))
@pytest.mark.parametrize("language", list(Language))
def test_production_portrait_layouts_fit_localized_values_and_missing_channels(
    manta: ExplorerData,
    monkeypatch: pytest.MonkeyPatch,
    layout: ExportLayout,
    mode: ExportSafeRegion,
    language: Language,
) -> None:
    assert manta.analysis is not None
    settings = ExportSettings(
        layout=layout,
        aspect=VideoAspect.PORTRAIT,
        safe_region=mode,
        language=language,
    )
    timeline = prepare_export(manta.analysis, settings, 3600, 3610)
    calls: list[str] = []
    original = ImageDraw.ImageDraw.text

    def checked_text(
        draw: ImageDraw.ImageDraw,
        xy: tuple[float, float],
        text: str,
        **kwargs: Any,
    ) -> None:
        bounds = draw.textbbox(xy, text, font=kwargs.get("font"), anchor=kwargs.get("anchor"))
        width, height = getattr(draw, "_image").size
        assert bounds[0] >= -1 and bounds[1] >= -1, (text, bounds, (width, height))
        assert bounds[2] <= width + 1 and bounds[3] <= height + 1, (text, bounds, (width, height))
        calls.append(text)
        original(draw, xy, text, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", checked_text)
    for state in ("fixture", "missing", "extremes"):
        current = timeline
        if state != "fixture":
            values: tuple[float | None, ...] = (
                (None,) * 4 if state == "missing" else (12.3, -9.8, 7.6, 180.0)
            )
            current = replace(
                timeline,
                channels=tuple(
                    replace(
                        channel,
                        values=(value,) * len(channel.values),
                        low=channel.low if value is None else min(channel.low, value),
                        high=channel.high if value is None else max(channel.high, value),
                    )
                    for channel, value in zip(timeline.channels, values, strict=True)
                ),
            )
        calls.clear()
        renderer = create_renderer(current)
        image = renderer.render_position(3605)
        assert image.getbbox() is not None
        native = registry.PLUGINS[layout].portrait_content
        assert image.size == ((1080, 1920) if native is None else native.dimensions)
        if state == "missing":
            assert tr("Unavailable", language=language) in calls
        else:
            for channel in current.channels[:3]:
                value = current.value_at(channel, 3605)
                assert value is not None
                assert tr("{0:+.1f} g", value, language=language) in calls
        if layout is ExportLayout.HUD:
            hud = cast(HudRenderer, renderer)
            assert hud.lateral_x(0) == 537.5
            assert hud.geometry.force_plot_row == 96
            assert hud.geometry.title_y == 280 and hud.geometry.value_y == 312
            offsets = resolve_geometry(settings).safe_region
            assert hud.geometry.force_plot_top == 1535 - offsets.force_plot_lift
            assert hud.edge == 40 + offsets.side_inset
            assert hud.geometry.scale_bottom == 1195 - offsets.force_plot_lift
            assert hud.geometry.lateral_y == 1435 - offsets.force_plot_lift
            assert hud.geometry.left_axis == 55 + offsets.side_inset
            assert hud.geometry.right_axis == 970 - offsets.side_inset
            assert hud.geometry.lateral_left == 130 + offsets.side_inset
            assert hud.geometry.lateral_right == 945 - offsets.side_inset
            assert hud.geometry.force_plot_left == 95 + offsets.side_inset
            off = cast(
                HudRenderer,
                create_renderer(
                    replace(current, settings=replace(settings, safe_region=ExportSafeRegion.OFF)),
                ),
            )
            assert hud.scales == off.scales and hud.force_plot_scales == off.force_plot_scales
            assert tuple(peak.at(3605, 1) for peak in hud.peaks) == tuple(
                peak.at(3605, 1) for peak in off.peaks
            )
        assert current.first == timeline.first and current.sample_rate == timeline.sample_rate
        if layout is not ExportLayout.HUD and mode is not ExportSafeRegion.OFF:
            off = create_renderer(
                replace(current, settings=replace(settings, safe_region=ExportSafeRegion.OFF)),
            )
            assert image.tobytes() == off.render_position(3605).tobytes()


def test_compact_force_plot_capability_is_typed() -> None:
    with pytest.raises(ValueError, match="force plot capability"):
        replace(registry.PLUGINS[ExportLayout.RIBBON], safe_region_force_plots=cast(bool, "yes"))
