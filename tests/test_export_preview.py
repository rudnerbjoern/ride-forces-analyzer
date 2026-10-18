"""Actual export previews use exact graph samples, production frames and no encoder."""

# cspell:words LANCZOS getpixel getchannel getbbox

from dataclasses import replace
from typing import Literal

from PIL import Image
import pytest

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.model import ExportSettings, PROFILES, prepare_export
from ride_forces_analyzer.rendering.preview import build_previews
from test_rendering import manta as manta


@pytest.mark.parametrize("layout", [profile[0] for profile in PROFILES])
def test_portrait_contains_complete_region(manta: ExplorerData, layout: str) -> None:
    from typing import cast
    from ride_forces_analyzer.rendering.model import ExportLayout
    from ride_forces_analyzer.rendering.layouts import export_region

    settings = ExportSettings(layout=cast(ExportLayout, layout), aspect="portrait")
    renderer = OverlayRenderer(prepare_export(manta, settings, 3500, 3700))
    frame = renderer.render_sample(3600)
    x, y, width, height = export_region(settings)
    assert x > 0 and y > 0 and x + width < frame.width and y + height < frame.height
    region = renderer.render_region(0)
    assert region.size == (width, height)
    bounds = frame.getchannel("A").getbbox()
    if layout == "orbit":
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


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_previews_match_production_at_exact_graph_sample(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    sample = manta.source.recording.indices.start + 72 * 50 + 1
    settings = ExportSettings(
        layout="orbit",
        fps=30,
        aspect=aspect,
        invert_vertical=False,
        invert_lateral=False,
    )
    first, last = sample - 101, sample + 100
    result = build_previews(manta, settings, first, last, sample, "dark")
    assert result.sample == sample and not result.outside_range
    assert tuple((p.layout, p.title) for p in result.profiles) == PROFILES
    timeline = prepare_export(manta, settings, first, last)
    for profile in result.profiles:
        chosen = (
            settings
            if profile.layout == "orbit"
            else replace(
                settings,
                layout=profile.layout,
                invert_vertical=True,
                invert_lateral=profile.layout == "column",
            )
        )
        actual = OverlayRenderer(prepare_export(manta, chosen, first, last)).render_sample(sample)
        expected = (
            Image.alpha_composite(Image.new("RGBA", actual.size, "#162533"), actual)
            .resize((540, 960) if aspect == "portrait" else (960, 540), Image.Resampling.LANCZOS)
            .convert("RGB")
        )
        assert profile.image.tobytes() == expected.tobytes()
    with pytest.raises(ValueError, match="outside"):
        OverlayRenderer(timeline).render_sample(last + 1)


@pytest.mark.parametrize("fps", [30, 50, 60, "60000/1001"])
def test_preview_sample_is_independent_of_video_rate(
    manta: ExplorerData,
    fps: int | Literal["60000/1001"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    positions: list[float] = []

    def record_position(self: OverlayRenderer, position: float) -> Image.Image:
        positions.append(position)
        return Image.new("RGBA", (8, 8), (0, 0, 0, 0))

    monkeypatch.setattr(OverlayRenderer, "render_sample", record_position)
    sample = manta.source.recording.indices.start + 72 * 50 + 1
    result = build_previews(manta, ExportSettings(fps=fps), sample - 101, sample + 100, sample)
    assert result.sample == sample
    assert positions == [sample] * len(PROFILES)


@pytest.mark.parametrize("mode", ["transparent", "opaque"])
def test_outside_range_keeps_graph_sample_and_smoothing(
    manta: ExplorerData,
    mode: Literal["transparent", "opaque"],
) -> None:
    data = manta.with_smoothing(3)
    sample = data.source.recording.indices.start + 72 * 50
    settings = ExportSettings(output=mode)
    original = data.source.source_sha256
    result = build_previews(data, settings, 0, 100, sample, "light")
    assert result.outside_range and result.sample == sample
    assert data.source.source_sha256 == original and data.reference is not None
    assert data.reference.smoothing_window == 3
    assert all(
        p.image.getpixel((0, 0)) == ((0, 0, 0) if mode == "opaque" else (228, 234, 240))
        for p in result.profiles
    )
    with pytest.raises(ValueError, match="outside"):
        build_previews(data, settings, 0, 100, -1)
