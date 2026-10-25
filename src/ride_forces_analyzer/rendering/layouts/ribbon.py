"""Ribbon profile geometry and registration.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words segoeui segoeuib

from __future__ import annotations
from typing import TYPE_CHECKING
from .charts import ChartRenderer
from .contracts import ExportLayout, VideoAspect, LayoutPlugin, LayoutPosition, LayoutPositions

if TYPE_CHECKING:
    from ..model import ExportTimeline


NATIVE_SIZE = (3072, 360)  # Native landscape drawing size in pixels.
LANDSCAPE_POSITIONS = LayoutPositions(  # Landscape regions: x, y, width, height.
    {LayoutPosition.TOP: (384, 108, 3072, 360), LayoutPosition.BOTTOM: (384, 1692, 3072, 360)},
    default=LayoutPosition.BOTTOM,
)
PORTRAIT_POSITIONS = LayoutPositions(  # Portrait regions: x, y, width, height.
    {LayoutPosition.TOP: (240, 240, 1680, 2240), LayoutPosition.BOTTOM: (240, 1360, 1680, 2240)},
    default=LayoutPosition.BOTTOM,
)
PLOT_LEFT = 460  # Plot left inset inside a card.
STACKED = False  # Stack force cards vertically.
FONT_FILE = "segoeui.ttf"  # Regular Windows font file.
TICK_FONT_FILE = "segoeui.ttf"  # Scale label Windows font file.
LABEL_FONT_SIZE = 30  # Channel title and unavailable-value size in pixels.
NUMBER_FONT_SIZE = 76  # Main force readout size in pixels.
SMALL_FONT_SIZE = 24  # Hints and footer size in pixels.
TICK_FONT_SIZE = 19  # Scale and time-axis label size in pixels.
CHANNEL_COLORS = ("#00ceff", "#ebd36a", "#ffa044")  # Vertical, lateral and longitudinal colors.
PANEL_CORNER_RADIUS = 36  # Rounded panel corner radius in pixels.
PANEL_FILL = (7, 15, 25, 210)  # Translucent panel RGBA fill.
PANEL_OUTLINE = (200, 225, 245, 135)  # Panel border RGBA color.
PANEL_OUTLINE_WIDTH = 2  # Panel border thickness in pixels.
TEXT_OUTLINE_WIDTH = 1  # Glyph outline thickness in pixels.
TEXT_OUTLINE_COLOR = (0, 0, 0, 230)  # Glyph outline RGBA color.
CARD_SPACING = 348  # Vertical distance between stacked cards.
CARD_HEIGHT = 328  # Stacked card height.
CARD_BOTTOM_MARGIN = 70  # Bottom margin below horizontal cards.
PLOT_TOP = 40  # Plot top inset inside a card.
PLOT_RIGHT = 32  # Plot right inset inside a card.
PLOT_BOTTOM = 44  # Plot bottom inset inside a card.
TEXT_LEFT = 32  # Left inset for channel text and footer.
TITLE_TOP = 20  # Channel title top inset.
VALUE_TOP = 70  # Force value top inset.
HINT_TOP = 171  # Direction hint top inset.
HINT_COLOR = "#f3f7fc"  # Direction hint text color.
SEPARATOR_TOP = 28  # Vertical divider top inset.
SEPARATOR_BOTTOM = 80  # Vertical divider bottom inset.
SEPARATOR_COLOR = (190, 215, 235, 85)  # Vertical divider RGBA color.
RULE_WIDTH = 2  # Grid, divider and cursor line thickness.
GRID_COLOR = (210, 230, 245, 65)  # Ordinary force grid RGBA color.
ZERO_GRID_COLOR = (210, 230, 245, 150)  # Zero-force grid RGBA color.
SCALE_COLOR = "#e4edf5"  # Scale number color.
SCALE_LEFT_GAP = 12  # Gap before vertical-axis scale numbers.
SCALE_TOP_GAP = 5  # Gap above lateral-axis scale numbers.
CURSOR_COLOR = (255, 255, 255, 175)  # Current-time cursor RGBA color.
FOOTER_PANEL_BOTTOM = 58  # Footer panel reference distance from the bottom.
FOOTER_PORTRAIT_EXTRA = 32  # Extra portrait footer panel height.
FOOTER_LANDSCAPE_EXTRA = 10  # Extra landscape footer panel height.
FOOTER_RULE_INSET = 28  # Horizontal inset of footer divider.
FOOTER_RULE_OFFSET = 14  # Footer divider offset above its reference.
FOOTER_RULE_COLOR = (190, 215, 235, 65)  # Footer divider RGBA color.
FOOTER_TEXT_BOTTOM = 48  # Footer text distance from bottom.
FOOTER_TEXT_COLOR = "#ffffff"  # Replay and tilt text color.
TRACE_OUTLINE_COLOR = (0, 0, 0, 245)  # Trace outline RGBA color.
TRACE_OUTLINE_WIDTH = 11  # Trace outline thickness.
TRACE_WIDTH = 5  # Colored trace thickness.
MARKER_RADIUS = 7  # Current-sample marker radius.
MARKER_OUTLINE_COLOR = "#ffffff"  # Current-sample marker outline color.
MARKER_OUTLINE_WIDTH = 2  # Current-sample marker outline thickness.
TIME_TEXT_COLOR = "#dce9f5"  # Time-axis text color.
TIME_LEFT_GAP = 12  # Lateral time label gap before its plot.
TIME_BOTTOM_GAP = 5  # Horizontal time label gap below its plot.

PORTRAIT_STACKED = True  # Use vertical force-card stacking in portrait.
PORTRAIT_NATIVE_SIZE = (840, 1120)  # Native stacked portrait drawing size.
PORTRAIT_PLOT_LEFT = 390  # Stacked portrait plot left inset.
PORTRAIT_NUMBER_FONT_SIZE = 76  # Portrait force value font size.


LEFT_TEXT_ANCHOR = "rm"  # Right-middle anchor for labels before the plot.
RIGHT_TEXT_ANCHOR = "ra"  # Right-aligned anchor for labels at the plot end.
TOP_SCALE_ANCHOR = "ms"  # Centered baseline anchor above lateral plots.


class RibbonRenderer(ChartRenderer):
    """Ribbon renderer contract and owned data.

    Attributes:
        left_text_anchor: Horizontal anchor for left-aligned text.
        right_text_anchor: Horizontal anchor for right-aligned text.
        top_scale_anchor: Upper anchor for the instrument scale.
        native_size: Layout dimension for native size, in native pixels unless specified
            otherwise.
        plot_left: Layout coordinate for plot left in the owning view or renderer.
        stacked: Whether force cards use a vertical arrangement.
        font_file: Font resource used for the layout's main labels and values.
        tick_font_file: Font resource used for scale ticks.
        label_size: Layout dimension for label size, in native pixels unless specified
            otherwise.
        number_size: Layout dimension for number size, in native pixels unless specified
            otherwise.
        small_size: Layout dimension for small size, in native pixels unless specified
            otherwise.
        tick_size: Layout dimension for tick size, in native pixels unless specified
            otherwise.
        channel_colors: Drawing color or palette for channel colors.
        panel_radius: Layout dimension for panel radius, in native pixels unless specified
            otherwise.
        panel_fill: Drawing color or palette for panel fill.
        panel_outline: Drawing color or palette for panel outline.
        panel_outline_width: Layout dimension for panel outline width, in native pixels
            unless specified otherwise.
        text_stroke_width: Layout dimension for text stroke width, in native pixels unless
            specified otherwise.
        text_stroke_color: Drawing color or palette for text stroke color.
        card_spacing: Spacing between force cards in native pixels.
        card_height: Layout dimension for card height, in native pixels unless specified
            otherwise.
        card_bottom_margin: Layout dimension for card bottom margin, in native pixels
            unless specified otherwise.
        plot_top: Layout coordinate for plot top in the owning view or renderer.
        plot_right: Layout coordinate for plot right in the owning view or renderer.
        plot_bottom: Layout coordinate for plot bottom in the owning view or renderer.
        text_left: Layout coordinate for text left in the owning view or renderer.
        title_top: Layout coordinate for title top in the owning view or renderer.
        value_top: Layout coordinate for value top in the owning view or renderer.
        hint_top: Layout coordinate for hint top in the owning view or renderer.
        hint_color: Drawing color or palette for hint color.
        separator_top: Layout coordinate for separator top in the owning view or renderer.
        separator_bottom: Layout coordinate for separator bottom in the owning view or
            renderer.
        separator_color: Drawing color or palette for separator color.
        rule_width: Layout dimension for rule width, in native pixels unless specified
            otherwise.
        grid_color: Drawing color or palette for grid color.
        zero_grid_color: Drawing color or palette for zero grid color.
        scale_color: Drawing color or palette for scale color.
        scale_left_gap: Layout dimension for scale left gap, in native pixels unless
            specified otherwise.
        scale_top_gap: Layout dimension for scale top gap, in native pixels unless
            specified otherwise.
        cursor_color: Drawing color or palette for cursor color.
        footer_panel_bottom: Layout coordinate for footer panel bottom in the owning view
            or renderer.
        footer_portrait_extra: Additional footer space for portrait output, in native
            pixels.
        footer_landscape_extra: Additional footer space for landscape output, in native
            pixels.
        footer_rule_inset: Layout dimension for footer rule inset, in native pixels unless
            specified otherwise.
        footer_rule_offset: Layout dimension for footer rule offset, in native pixels
            unless specified otherwise.
        footer_rule_color: Drawing color or palette for footer rule color.
        footer_text_bottom: Layout coordinate for footer text bottom in the owning view or
            renderer.
        footer_text_color: Drawing color or palette for footer text color.
        trace_outline_color: Drawing color or palette for trace outline color.
        trace_outline_width: Layout dimension for trace outline width, in native pixels
            unless specified otherwise.
        trace_width: Layout dimension for trace width, in native pixels unless specified
            otherwise.
        marker_radius: Layout dimension for marker radius, in native pixels unless
            specified otherwise.
        marker_outline_color: Drawing color or palette for marker outline color.
        marker_outline_width: Layout dimension for marker outline width, in native pixels
            unless specified otherwise.
        time_text_color: Drawing color or palette for time text color.
        time_left_gap: Layout dimension for time left gap, in native pixels unless
            specified otherwise.
        time_bottom_gap: Layout dimension for time bottom gap, in native pixels unless
            specified otherwise.
    """

    left_text_anchor = LEFT_TEXT_ANCHOR
    right_text_anchor = RIGHT_TEXT_ANCHOR
    top_scale_anchor = TOP_SCALE_ANCHOR
    native_size = NATIVE_SIZE
    plot_left = PLOT_LEFT
    stacked = STACKED
    font_file = FONT_FILE
    tick_font_file = TICK_FONT_FILE
    label_size = LABEL_FONT_SIZE
    number_size = NUMBER_FONT_SIZE
    small_size = SMALL_FONT_SIZE
    tick_size = TICK_FONT_SIZE
    channel_colors = CHANNEL_COLORS
    panel_radius = PANEL_CORNER_RADIUS
    panel_fill = PANEL_FILL
    panel_outline = PANEL_OUTLINE
    panel_outline_width = PANEL_OUTLINE_WIDTH
    text_stroke_width = TEXT_OUTLINE_WIDTH
    text_stroke_color = TEXT_OUTLINE_COLOR
    card_spacing = CARD_SPACING
    card_height = CARD_HEIGHT
    card_bottom_margin = CARD_BOTTOM_MARGIN
    plot_top = PLOT_TOP
    plot_right = PLOT_RIGHT
    plot_bottom = PLOT_BOTTOM
    text_left = TEXT_LEFT
    title_top = TITLE_TOP
    value_top = VALUE_TOP
    hint_top = HINT_TOP
    hint_color = HINT_COLOR
    separator_top = SEPARATOR_TOP
    separator_bottom = SEPARATOR_BOTTOM
    separator_color = SEPARATOR_COLOR
    rule_width = RULE_WIDTH
    grid_color = GRID_COLOR
    zero_grid_color = ZERO_GRID_COLOR
    scale_color = SCALE_COLOR
    scale_left_gap = SCALE_LEFT_GAP
    scale_top_gap = SCALE_TOP_GAP
    cursor_color = CURSOR_COLOR
    footer_panel_bottom = FOOTER_PANEL_BOTTOM
    footer_portrait_extra = FOOTER_PORTRAIT_EXTRA
    footer_landscape_extra = FOOTER_LANDSCAPE_EXTRA
    footer_rule_inset = FOOTER_RULE_INSET
    footer_rule_offset = FOOTER_RULE_OFFSET
    footer_rule_color = FOOTER_RULE_COLOR
    footer_text_bottom = FOOTER_TEXT_BOTTOM
    footer_text_color = FOOTER_TEXT_COLOR
    trace_outline_color = TRACE_OUTLINE_COLOR
    trace_outline_width = TRACE_OUTLINE_WIDTH
    trace_width = TRACE_WIDTH
    marker_radius = MARKER_RADIUS
    marker_outline_color = MARKER_OUTLINE_COLOR
    marker_outline_width = MARKER_OUTLINE_WIDTH
    time_text_color = TIME_TEXT_COLOR
    time_left_gap = TIME_LEFT_GAP
    time_bottom_gap = TIME_BOTTOM_GAP


class PortraitRibbonRenderer(RibbonRenderer):
    """Portrait ribbon renderer contract and owned data.

    Attributes:
        native_size: Layout dimension for native size, in native pixels unless specified
            otherwise.
        plot_left: Layout coordinate for plot left in the owning view or renderer.
        stacked: Whether force cards use a vertical arrangement.
        number_size: Layout dimension for number size, in native pixels unless specified
            otherwise.
    """

    native_size = PORTRAIT_NATIVE_SIZE
    plot_left = PORTRAIT_PLOT_LEFT
    stacked = PORTRAIT_STACKED
    number_size = PORTRAIT_NUMBER_FONT_SIZE


def create_renderer(timeline: ExportTimeline) -> ChartRenderer:
    """Construct the production renderer for the bound export timeline.

    Args:
        timeline: Bound video timeline containing the source interval and export settings.

    Returns:
        Production layout renderer bound to the supplied timeline.
    """
    if timeline.settings.aspect is VideoAspect.PORTRAIT:
        return PortraitRibbonRenderer(timeline)
    return RibbonRenderer(timeline)


PLUGIN = LayoutPlugin(ExportLayout.RIBBON, LANDSCAPE_POSITIONS, PORTRAIT_POSITIONS, create_renderer)
