"""Full-screen HUD scales, waveform gaps, glow/shadows and independent frame rendering."""

# cspell:words getchannel getpixel getextrema getcolor getcolors getbbox

from dataclasses import replace
from typing import Any, Literal

from PIL import Image, ImageColor, ImageDraw
import pytest

from ride_forces_analyzer.i18n import Language
from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.rendering.frames import OverlayRenderer
from ride_forces_analyzer.rendering.layouts.hud import (
    CYAN,
    GREEN,
    HudRenderer,
    LANDSCAPE,
    PORTRAIT,
    MINOR_DIVISIONS,
    ORIENTATION_EDGE,
    ORIENTATION_STRIP_WIDTH,
    RED,
    WHITE,
    YELLOW,
)
from ride_forces_analyzer.rendering.model import ExportSettings, prepare_export
from tests.support.recordings import REAL_FIXTURE_DIRECTORY


@pytest.fixture(scope="module")
def seated() -> ExplorerData:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Taron-*.forces")))
    assert isinstance(data, ExplorerData)
    return data


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_detailed_scales_and_signed_directions(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3699,
    )
    renderer = HudRenderer(timeline)
    assert renderer.vertical_y(-1) < renderer.vertical_y(0) < renderer.vertical_y(1)
    assert renderer.longitudinal_y(1) < renderer.longitudinal_y(0) < renderer.longitudinal_y(-1)
    assert renderer.lateral_x(-1) < renderer.lateral_x(0) < renderer.lateral_x(1)
    for row, (low, high, step) in enumerate(renderer.scales):
        channel = timeline.channels[row]
        selected = [value for value in channel.values[3600:3700] if value is not None]
        assert low <= min(selected) <= max(selected) <= high
        assert 4 <= (high - low) / step <= (14 if row == 0 else 12)
        assert MINOR_DIVISIONS == 5
    wide = tuple(replace(channel, values=(1000.0,) * manta.count) for channel in timeline.channels)
    assert (
        max(
            (high - low) / step
            for low, high, step in HudRenderer(replace(timeline, channels=wide)).scales
        )
        <= 14
    )


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize(
    ("peak", "expected"),
    [
        (None, 1.5),
        (0.0, 1.5),
        (1.49, 1.5),
        (1.5, 1.5),
        (-1.5, 1.5),
        (1.50001, 2.0),
        (-2.1, 2.5),
        (3.344, 4.0),
    ],
)
def test_right_scale_fits_actual_selected_peaks_with_a_one_point_five_g_minimum(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    peak: float | None,
    expected: float,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3699,
    )
    longitudinal = replace(
        timeline.channels[2],
        low=-99.0,
        high=99.0,
        values=tuple(peak if 3600 <= index <= 3699 else 999.0 for index in range(manta.count)),
    )
    renderer = HudRenderer(
        replace(timeline, channels=(*timeline.channels[:2], longitudinal, timeline.channels[3])),
    )
    assert renderer.scales[2][:2] == (-expected, expected)
    if peak is not None:
        assert (
            renderer.geometry.scale_top
            <= renderer.longitudinal_y(peak)
            <= renderer.geometry.scale_bottom
        )


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize(
    ("peak", "expected"),
    [
        (None, 2.0),
        (1.99, 2.0),
        (2.0, 2.0),
        (-2.05, 2.5),
        (2.5, 2.5),
        (2.50001, 3.0),
        (3.01, 3.5),
        (1000.01, 1000.5),
    ],
)
def test_lateral_scale_fits_actual_peaks_in_fixed_half_g_steps(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    peak: float | None,
    expected: float,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3699,
    )
    lateral = replace(
        timeline.channels[1],
        low=-9999.0,
        high=9999.0,
        values=tuple(peak if 3600 <= index <= 3699 else 9999.0 for index in range(manta.count)),
    )
    renderer = HudRenderer(
        replace(timeline, channels=(timeline.channels[0], lateral, *timeline.channels[2:])),
    )
    low, high, step = renderer.scales[1]
    assert (low, high) == (-expected, expected)
    assert (high - low) / step <= 12
    if peak is not None:
        assert (
            renderer.geometry.lateral_left
            <= renderer.lateral_x(peak)
            <= renderer.geometry.lateral_right
        )
    if peak == 3.01:
        for position in (3699, 3600):
            renderer.render_position(position)
            assert renderer.scales[1][:2] == (-3.5, 3.5)


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize("inverted", [True, False])
@pytest.mark.parametrize(
    ("flying", "low", "high", "expected"),
    [
        (False, None, None, (-1.5, 5.0)),
        (False, -0.2, 2.0, (-1.5, 5.0)),
        (False, -1.5, 5.0, (-1.5, 5.0)),
        (False, -1.50001, 5.00001, (-2.0, 5.5)),
        (False, -0.2, 6.01, (-1.5, 6.5)),
        (True, None, None, (-4.0, 3.0)),
        (True, -4.0, 3.0, (-4.0, 3.0)),
        (True, -4.00001, 3.00001, (-4.5, 3.5)),
        (True, -5.01, 2.0, (-5.5, 3.0)),
        (False, -1000.01, 2000.01, (-1000.5, 2000.5)),
    ],
)
def test_vertical_range_uses_source_posture_and_independent_bounds(
    manta: ExplorerData,
    seated: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    inverted: bool,
    flying: bool,
    low: float | None,
    high: float | None,
    expected: tuple[float, float],
) -> None:
    data = manta if flying else seated
    assert data.analysis is not None
    posture = data.analysis.source.recording.metadata.riding_position
    assert posture is not None and posture.value == ("Flying" if flying else "Seated")
    timeline = prepare_export(
        data.analysis,
        ExportSettings(layout="hud", aspect=aspect, invert_vertical=inverted),
        3600,
        3699,
    )
    vertical = replace(
        timeline.channels[0],
        low=-9999.0,
        high=9999.0,
        values=tuple(
            (low if index % 2 else high) if 3600 <= index <= 3699 else 9999.0
            for index in range(data.count)
        ),
    )
    renderer = HudRenderer(replace(timeline, channels=(vertical, *timeline.channels[1:])))
    assert renderer.scales[0][:2] == expected
    assert (expected[1] - expected[0]) / renderer.scales[0][2] <= 14
    ends = [renderer.vertical_y(value) for value in expected]
    if not inverted:
        ends.reverse()
    assert ends == pytest.approx([renderer.geometry.scale_top, renderer.geometry.scale_bottom])
    assert renderer.vertical_y(1) - renderer.vertical_y(0) == pytest.approx(
        renderer.vertical_y(0) - renderer.vertical_y(-1),
    )
    assert renderer.vertical_y(0) != pytest.approx(
        (renderer.geometry.scale_top + renderer.geometry.scale_bottom) / 2,
    )


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize("inverted", [True, False])
@pytest.mark.parametrize("flying", [True, False])
def test_only_vertical_uses_whole_g_labels_and_three_tick_lengths(
    manta: ExplorerData,
    seated: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    inverted: bool,
    flying: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = manta if flying else seated
    assert data.analysis is not None
    timeline = prepare_export(
        data.analysis,
        ExportSettings(
            layout="hud",
            aspect=aspect,
            invert_vertical=inverted,
            language=Language.ENGLISH,
        ),
        3600,
        3699,
    )
    lines: list[tuple[float, float, float, float]] = []
    labels: list[tuple[tuple[float, float], str]] = []

    def record_line(
        _draw: ImageDraw.ImageDraw,
        xy: tuple[float, float, float, float],
        **_kwargs: Any,
    ) -> None:
        lines.append(xy)

    def record_text(
        _draw: ImageDraw.ImageDraw,
        xy: tuple[float, float],
        text: str,
        **_kwargs: Any,
    ) -> None:
        labels.append((xy, text))

    monkeypatch.setattr(ImageDraw.ImageDraw, "line", record_line)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record_text)
    renderer = HudRenderer(timeline)
    g = renderer.geometry
    direction = 1 if aspect == "portrait" else -1
    vertical_ticks = {
        y: abs(end_x - x) for x, y, end_x, end_y in lines if x == g.left_axis and y == end_y
    }
    low, high, _ = renderer.scales[0]
    for quarter in range(round(low * 4), round(high * 4) + 1):
        value = quarter / 4
        expected_length = 20 if quarter % 4 == 0 else 14 if quarter % 2 == 0 else 8
        assert vertical_ticks[renderer.vertical_y(value)] == expected_length
    assert {text for (x, _), text in labels if x == g.left_axis + direction * 30} == {
        "0" if value == 0 else f"{value:+d}"
        for value in range(-1 if not flying else -4, 4 if flying else 6)
    }

    # Longitudinal retains half-g labels and four equal minor marks per interval.
    right_ticks = {
        y: abs(end_x - x) for x, y, end_x, end_y in lines if x == g.right_axis and y == end_y
    }
    assert right_ticks[renderer.longitudinal_y(0.5)] == 20
    assert right_ticks[renderer.longitudinal_y(0.1)] == 9
    right_labels = {text for (x, _), text in labels if x == g.right_axis + 30}
    assert {"-0.5", "+0.5"} <= right_labels


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
@pytest.mark.parametrize("language", list(Language))
def test_fullscreen_hud_has_open_center_and_is_independent_of_seek_order(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    language: Language,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect, language=language),
        3600,
        3699,
    )
    renderer = HudRenderer(timeline)
    image = renderer.render_position(3650.5)
    renderer.render_position(3699)
    renderer.render_position(3600)
    assert renderer.render_position(3650.5).tobytes() == image.tobytes()
    assert (
        image.mode == "RGBA"
        and image.size == (PORTRAIT if aspect == "portrait" else LANDSCAPE).size
    )
    width, height = image.size
    center = image.crop(
        (round(width * 0.4), round(height * 0.3), round(width * 0.6), round(height * 0.6)),
    )
    assert center.getchannel("A").getbbox() is None
    assert image.getchannel("A").getextrema() == (0, 255)

    def reject_resize(*_args: Any, **_kwargs: Any) -> Image.Image:
        raise AssertionError("HUD export must retain its native pixels without resizing")

    monkeypatch.setattr(Image.Image, "resize", reject_resize)
    frame = OverlayRenderer(timeline).render_sample(3650.5)
    assert frame.size == timeline.settings.dimensions == image.size
    region = OverlayRenderer(timeline).render_region(0)
    assert region.size == image.size
    assert frame.getchannel("A").getpixel((0, 0)) == 0
    opaque = OverlayRenderer(
        replace(timeline, settings=replace(timeline.settings, output="opaque")),
    )
    assert opaque.render_sample(3650.5).getchannel("A").getextrema() == (255, 255)


def test_each_missing_force_hides_only_its_marker(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout="hud"), 3600, 3601)
    channels = tuple(replace(channel, values=(1.0,) * manta.count) for channel in timeline.channels)
    complete = replace(timeline, channels=channels)
    renderer = HudRenderer(complete)
    g = renderer.geometry
    points = (
        (g.left_axis + 9, round(renderer.vertical_y(1))),
        (round(renderer.lateral_x(1)), g.lateral_y + 15),
        (g.right_axis - 9, round(renderer.longitudinal_y(1))),
    )
    image = renderer.render_position(3600)
    for row, point in enumerate(points):
        changed = list(channels)
        changed[row] = replace(changed[row], values=(None,) * manta.count)
        missing = HudRenderer(replace(timeline, channels=tuple(changed))).render_position(3600)
        assert image.getchannel("A").getpixel(point) == 255
        missing_alpha = missing.getchannel("A").getpixel(point)
        assert isinstance(missing_alpha, int)
        assert missing_alpha < 255
    absent = HudRenderer(
        replace(
            timeline,
            channels=tuple(replace(channel, values=(None,) * manta.count) for channel in channels),
        ),
    )
    assert absent.render_position(3600).size == g.size


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_orientation_edge_scale_tracks_degrees_and_disappears_in_gaps(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3606,
    )
    values: list[float | None] = [None] * manta.count
    values[3600:3607] = [0.0, 45.0, 90.0, 135.0, 180.0, None, 90.0]
    orientation = replace(timeline.channels[3], values=tuple(values))
    absent = HudRenderer(
        replace(
            timeline,
            channels=(*timeline.channels[:3], replace(orientation, values=(None,) * manta.count)),
        ),
    )
    labels: list[str] = []
    original_text = ImageDraw.ImageDraw.text

    def record_orientation_text(
        draw: ImageDraw.ImageDraw,
        xy: tuple[float, float],
        text: str,
        **kwargs: Any,
    ) -> None:
        if text in {"0°", "45°", "90°", "135°", "180°"}:
            labels.append(text)
        original_text(draw, xy, text, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record_orientation_text)
    renderer = HudRenderer(replace(timeline, channels=(*timeline.channels[:3], orientation)))
    assert labels == ["0°", "45°", "90°", "135°", "180°"]
    g = renderer.geometry
    assert [renderer.orientation_y(v) for v in (0, 90, 180)] == pytest.approx(
        [g.scale_top, (g.scale_top + g.scale_bottom) / 2, g.scale_bottom],
    )
    for position, degrees in (
        (3604, 180),
        (3600, 0),
        (3601, 45),
        (3602, 90),
        (3603, 135),
        (3600.5, 22.5),
        (3606, 90),
    ):
        image = renderer.render_position(position)
        without = absent.render_position(position)
        # The force instruments and histories retain exactly the same pixels.
        unchanged = (0, 0, g.size[0] - ORIENTATION_STRIP_WIDTH, g.size[1])
        assert image.crop(unchanged).tobytes() == without.crop(unchanged).tobytes()
        bug = (g.size[0] - ORIENTATION_EDGE - 9, round(renderer.orientation_y(degrees)))
        assert image.getpixel(bug) == ImageColor.getcolor(WHITE, "RGBA")
        assert without.getpixel(bug) != image.getpixel(bug)
    assert labels == ["0°", "45°", "90°", "135°", "180°"]
    labels.clear()
    for position in (3605, 3604.5, 3605.5):
        assert (
            renderer.render_position(position).tobytes()
            == absent.render_position(position).tobytes()
        )
    assert labels == []


def _held_bar_point(renderer: HudRenderer, row: int, value: float) -> tuple[int, int]:
    g = renderer.geometry
    if row == 1:
        return round(renderer.lateral_x(value)), g.lateral_y - 1
    mapping = renderer.vertical_y if row == 0 else renderer.longitudinal_y
    return (g.left_axis if row == 0 else g.right_axis) - 1, round(mapping(value))


def _current_marker_points(renderer: HudRenderer) -> tuple[tuple[int, int], ...]:
    g = renderer.geometry
    return (
        (g.left_axis + 14, round(renderer.vertical_y(0.25)) + 4),
        (round(renderer.lateral_x(0.25)), g.lateral_y + 17),
        (g.right_axis - 14, round(renderer.longitudinal_y(0.25)) + 4),
    )


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_scale_bars_hold_both_peaks_and_release_while_markers_stay_current(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3799,
    )
    values = tuple(
        2.0 if index == 3600 else -1.0 if index == 3601 else 0.25 for index in range(manta.count)
    )
    channels = tuple(replace(channel, values=values) for channel in timeline.channels[:3])
    renderer = HudRenderer(replace(timeline, channels=(*channels, timeline.channels[3])))
    snapshots = [renderer.render_position(position) for position in (3625, 3700, 3750)]
    assert renderer.render_position(3625).tobytes() == snapshots[0].tobytes()
    for row, colors in enumerate(((CYAN, CYAN), (YELLOW, YELLOW), (GREEN, RED))):
        positive, negative = [(*bytes.fromhex(color[1:]), 255) for color in colors]
        a, b = _held_bar_point(renderer, row, 1.37), _held_bar_point(renderer, row, -0.67)
        assert snapshots[0].getpixel(a) == snapshots[1].getpixel(a) == positive
        assert snapshots[0].getpixel(b) == negative
        assert snapshots[1].getpixel(b) != negative
        assert snapshots[2].getpixel(a) != positive and snapshots[2].getpixel(b) != negative
    for snapshot in snapshots:
        for point, color in zip(_current_marker_points(renderer), (CYAN, YELLOW, GREEN)):
            assert snapshot.getpixel(point) == (*bytes.fromhex(color[1:]), 255)


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_scale_peak_bars_reset_at_missing_samples(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3799,
    )
    values = tuple(
        None if index == 3650 else 2.0 if index == 3600 else -1.0 if index == 3601 else 0.25
        for index in range(manta.count)
    )
    channels = tuple(replace(channel, values=values) for channel in timeline.channels[:3])
    renderer = HudRenderer(replace(timeline, channels=(*channels, timeline.channels[3])))
    renderer.render_position(3625)
    gap, after = renderer.render_position(3650), renderer.render_position(3651)
    for row, colors in enumerate(((CYAN, CYAN), (YELLOW, YELLOW), (GREEN, RED))):
        for value, color in zip((1.37, -0.67), colors):
            rgba = (*bytes.fromhex(color[1:]), 255)
            point = _held_bar_point(renderer, row, value)
            assert gap.getpixel(point) != rgba and after.getpixel(point) != rgba
    for point, color in zip(_current_marker_points(renderer), (CYAN, YELLOW, GREEN)):
        assert after.getpixel(point) == (*bytes.fromhex(color[1:]), 255)


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_history_time_zero_aligns_exactly_with_lateral_zero(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect),
        3600,
        3699,
    )
    renderer = HudRenderer(timeline)
    zero = renderer.lateral_x(0)
    for row in range(3):
        left, _ = renderer.history_point(row, 0, 0)
        cursor, _ = renderer.history_point(row, 0, 0.5)
        right, _ = renderer.history_point(row, 0, 1)
        assert cursor == zero
        assert zero - left == right - zero
        assert left == renderer.geometry.history_left
        assert 0 < left < right < renderer.width


def test_histories_share_time_axis_and_do_not_bridge_missing_samples(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", window_seconds=2),
        3600,
        3699,
    )
    channels = tuple(replace(channel, values=(1.0,) * manta.count) for channel in timeline.channels)
    complete = replace(timeline, channels=channels)
    renderer = HudRenderer(complete)
    assert len({renderer.history_point(row, 1, 0.75)[0] for row in range(3)}) == 1
    assert renderer.history_point(0, 1, 0.2)[0] < renderer.history_point(0, 1, 0.8)[0]
    for row in (1, 2):
        assert renderer.history_point(row, 1, 0.5)[1] < renderer.history_point(row, 0, 0.5)[1]
    value = replace(
        channels[0],
        values=tuple(None if 3670 <= index < 3680 else 1.0 for index in range(manta.count)),
    )
    gapped = HudRenderer(replace(timeline, channels=(value, *channels[1:])))
    empty = HudRenderer(
        replace(
            timeline,
            channels=(
                replace(value, values=(None,) * manta.count),
                *channels[1:],
            ),
        ),
    )
    x, _ = renderer.history_point(0, 1, 0.75)
    g = renderer.geometry
    box = (round(x) - 3, g.history_top, round(x) + 3, g.history_top + g.history_row)
    blank = empty.render_position(3650).crop(box).tobytes()
    assert renderer.render_position(3650).crop(box).tobytes() != blank
    assert gapped.render_position(3650).crop(box).tobytes() == blank


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_histories_fit_each_selected_channel_without_changing_instruments(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(
        manta.analysis,
        ExportSettings(layout="hud", aspect=aspect, window_seconds=30),
        3600,
        3699,
    )
    instruments = HudRenderer(timeline).scales
    channels = tuple(
        replace(
            channel,
            values=tuple(
                None
                if index == 3602
                else peak * (-1 if index % 2 else 1)
                if 3600 <= index <= 3699
                else 999.0
                for index in range(manta.count)
            ),
        )
        for channel, peak in zip(timeline.channels[:3], (0.2, 0.6, 0.04))
    )
    selected = replace(timeline, channels=(*channels, timeline.channels[3]))
    renderer = HudRenderer(selected)
    assert renderer.scales == instruments
    assert renderer.history_scales == pytest.approx((0.3, 0.7, 0.1))
    ranges = renderer.history_scales
    for position in (3699, 3600, 3650.5):
        renderer.render_position(position)
        assert renderer.history_scales == ranges
    shorter_window = HudRenderer(
        replace(selected, settings=replace(selected.settings, window_seconds=2)),
    )
    assert shorter_window.history_scales == ranges
    including_outlier = HudRenderer(replace(selected, last=3700))
    assert min(including_outlier.history_scales) > 999


def test_history_ranges_remain_usable_for_zero_missing_and_tiny_values(manta: ExplorerData) -> None:
    assert manta.analysis is not None
    timeline = prepare_export(manta.analysis, ExportSettings(layout="hud"), 3600, 3699)
    channels = tuple(
        replace(channel, values=(value,) * manta.count)
        for channel, value in zip(timeline.channels[:3], (0.0, None, -0.01))
    )
    renderer = HudRenderer(replace(timeline, channels=(*channels, timeline.channels[3])))
    assert renderer.history_scales == pytest.approx((0.1, 0.1, 0.1))
    for row in range(3):
        assert renderer.history_point(row, 0, 0.5)[1] == (
            renderer.geometry.history_top + (row + 0.5) * renderer.geometry.history_row
        )


def test_glow_and_shadow_have_soft_alpha_without_a_filled_panel() -> None:
    ink = Image.new("RGBA", (80, 80))
    ImageDraw.Draw(ink).line((35, 20, 35, 60), fill=CYAN, width=2)
    before = ink.tobytes()
    image = HudRenderer.effects(ink)
    assert ink.tobytes() == before
    alpha = image.getchannel("A")
    glow_alpha = alpha.getpixel((40, 40))
    assert isinstance(glow_alpha, int)
    assert 0 < glow_alpha < 255
    assert alpha.getpixel((35, 40)) == 255
    assert alpha.getpixel((0, 0)) == 0
    colors = image.getcolors(80 * 80)
    assert colors is not None
    assert any(
        isinstance(color, tuple) and len(color) == 4 and color[:3] == (0, 0, 0) and color[3] > 0
        for _, color in colors
    )


def test_cropped_effects_preserve_pixels_and_tile_edges() -> None:
    # Include soft ink, separated marks and clipping at each original tile edge.
    for bounds in ((100, 60, 125, 85), (0, 0, 4, 4), (295, 175, 299, 179), None):
        ink = Image.new("RGBA", (300, 180))
        if bounds is not None:
            draw = ImageDraw.Draw(ink)
            draw.rectangle(bounds, fill=CYAN)
            draw.line((bounds[0], 90, bounds[2], 95), fill=(255, 90, 40, 80), width=2)
        before = ink.tobytes()
        expected = Image.new("RGBA", (330, 210), (70, 110, 145, 150))
        actual = expected.copy()
        expected.alpha_composite(HudRenderer.effects(ink), (13, 17))
        HudRenderer.composite_effects(actual, ink, (13, 17))
        assert actual.tobytes() == expected.tobytes(), bounds
        assert ink.tobytes() == before


@pytest.mark.parametrize("aspect", ["landscape", "portrait"])
def test_history_background_fades_to_black_and_leaves_center_clear(
    manta: ExplorerData,
    aspect: Literal["landscape", "portrait"],
) -> None:
    assert manta.analysis is not None
    renderer = HudRenderer(
        prepare_export(manta.analysis, ExportSettings(layout="hud", aspect=aspect), 3600, 3699),
    )
    image = renderer.render_position(3650)
    top = renderer.geometry.history_top - 40
    samples = [image.getpixel((0, y)) for y in (top, top + 20, image.height - 1)]
    assert all(isinstance(pixel, tuple) and pixel[:3] == (0, 0, 0) for pixel in samples)
    assert samples[0] == (0, 0, 0, 0)
    assert isinstance(samples[1], tuple) and isinstance(samples[2], tuple)
    assert 0 < samples[1][3] < samples[2][3] < 255
    assert image.getpixel((image.width // 2, image.height // 2)) == (0, 0, 0, 0)
