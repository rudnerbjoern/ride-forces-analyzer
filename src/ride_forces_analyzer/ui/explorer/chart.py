"""Own explorer curves, axes and overlays independently of window controls.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import ceil

from PySide6.QtCharts import QCategoryAxis, QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QObject, QPointF, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QLabel,
    QSizePolicy,
    QWidget,
)

from ride_forces_analyzer.explorer import ExplorerData, SampleRange
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.theme import Theme
from ride_forces_analyzer.ui.presentation.translation import bind
from .chart_view import TimeChartView


class ExplorerChart(QObject):
    """Display a prepared recording snapshot and independent chart view state.

    Attributes:
        range_changed: Signal emitted when the visible time interval changes.
        data: Prepared explorer snapshot, or None before a recording is loaded.
        theme: Palette used for chart surfaces, curves and overlays.
        chart: Qt chart owning axes, series and overlay graphics.
        chart_view: Widget exposing chart gestures and rendering the chart.
        axis_x: Recording-time axis, replaced with replay labels on recording load.
        axis_y: Force or raw-value axis, fixed to the snapshot's value range.
        series: Three source-aligned force or raw-channel curves.
        selection_band: Shaded inclusive export selection.
        vertical_context_bars: Visible provisional vertical-context graphics.
        vertical_context_ranges: Prepared intervals corresponding to the graphics.
        airtime_legend: Label explaining the displayed vertical-context colors.
        source_marker_lines: Lines for effective ride and calibration markers.
        source_marker_labels: Labels bound to the corresponding source markers.
        sample_cursor: Line at the current integer or fractional sample position.
        _cursor_position: Source-sample position supplied by the window.
        _selection: Inclusive source selection supplied by the window.
    """

    range_changed = Signal()

    def __init__(self, theme: Theme, parent: QWidget) -> None:
        """Create chart graphics and connect their internal view updates.

        Args:
            theme: Initial chart palette.
            parent: Window owning the component's Qt lifetime.

        Returns:
            None.
        """
        super().__init__(parent)
        self.data: ExplorerData | None = None
        self.theme = theme
        self._cursor_position = 0.0
        self._selection: SampleRange | None = None
        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setBackgroundBrush(QColor("#182330"))
        self.chart.setBackgroundRoundness(0)
        self.chart.legend().hide()
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        chart_margins = self.chart.margins()
        chart_margins.setBottom(0)
        self.chart.setMargins(chart_margins)
        self.chart_view = TimeChartView(self.chart)
        self.chart_view.zoom_requested.connect(self.zoom_wheel)
        self.chart_view.setObjectName("recordingChart")
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setRubberBand(QChartView.RubberBand.HorizontalRubberBand)
        self.chart_view.setMinimumSize(0, 240)
        # Let the plot shrink instead of reusing its previous viewport height.
        self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.selection_band = QGraphicsRectItem(self.chart)
        self.selection_band.setPen(QPen(Qt.PenStyle.NoPen))
        self.selection_band.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.selection_band.setZValue(1)
        self.selection_band.hide()
        self.chart.plotAreaChanged.connect(self._redraw_selection)
        self.axis_x = QValueAxis()
        bind(self.axis_x, tr("Elapsed time (s)"), "titleText")
        self.axis_x.setLabelFormat("%.3f")
        self.axis_y = QValueAxis()
        bind(self.axis_y, tr("Source value (unit unknown)"), "titleText")
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series: list[QLineSeries] = []
        self.vertical_context_bars: list[QGraphicsRectItem] = []
        self.vertical_context_ranges: tuple[tuple[str, int, int], ...] = ()
        for name, color in (("x", "#2563eb"), ("y", "#ea580c"), ("z", "#059669")):
            line = QLineSeries()
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5))
            self.chart.addSeries(line)
            line.attachAxis(self.axis_x)
            line.attachAxis(self.axis_y)
            self.series.append(line)
        self.airtime_legend = QLabel()
        self.airtime_legend.setObjectName("airtimeLegend")
        self.airtime_legend.setWordWrap(True)
        self.airtime_legend.hide()
        self.chart.plotAreaChanged.connect(self._redraw_vertical_context)
        self.axis_x.rangeChanged.connect(self._redraw_vertical_context)
        self.source_marker_lines: dict[str, QLineSeries] = {}
        self.source_marker_labels: dict[str, QGraphicsSimpleTextItem] = {}
        for name, color in (
            ("startIndex", "#bb9aff"),
            ("endIndex", "#ff8ca8"),
            ("gravityIndex", "#50c4d4"),
            ("inclineIndex", "#ffd07b"),
        ):
            line = QLineSeries()
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.DashDotLine))
            self.chart.addSeries(line)
            line.attachAxis(self.axis_x)
            line.attachAxis(self.axis_y)
            for marker in self.chart.legend().markers(line):
                marker.setVisible(False)
            label = QGraphicsSimpleTextItem(self.chart)
            label.setBrush(QColor(color))
            label.hide()
            self.source_marker_lines[name] = line
            self.source_marker_labels[name] = label
        self.chart.plotAreaChanged.connect(self.redraw_source_markers)
        self.sample_cursor = QLineSeries()
        self.sample_cursor.setPen(QPen(QColor("#64748b"), 1, Qt.PenStyle.DashLine))
        self.chart.addSeries(self.sample_cursor)
        self.sample_cursor.attachAxis(self.axis_x)
        self.sample_cursor.attachAxis(self.axis_y)
        for marker in self.chart.legend().markers(self.sample_cursor):
            marker.setVisible(False)
        self.axis_y.rangeChanged.connect(self._redraw_cursor)

        self.set_theme(theme)

    def set_theme(self, theme: Theme) -> None:
        """Apply colors while retaining axes, viewport, cursor and selection.

        Args:
            theme: Palette to use for existing chart graphics.

        Returns:
            None.
        """
        self.theme = theme
        background = QColor(self.theme.chart_background or self.theme.panel)
        self.chart.setBackgroundBrush(background)
        self.chart_view.setBackgroundBrush(background)
        self._style_axes()
        self._redraw_selection()
        for (name, line), color in zip(
            self.source_marker_lines.items(),
            self.theme.markers,
            strict=True,
        ):
            line.setPen(QPen(QColor(color), 1.5, Qt.PenStyle.DashDotLine))
            self.source_marker_labels[name].setBrush(QColor(color))

    def _style_axes(self) -> None:
        for axis in (self.axis_x, self.axis_y):
            foreground = QColor(self.theme.chart_foreground or self.theme.muted)
            axis.setLabelsBrush(foreground)
            axis.setTitleBrush(foreground)
            axis.setGridLinePen(QPen(QColor(self.theme.grid), 1))
            axis.setLinePen(QPen(QColor(self.theme.border), 1))

    def set_data(self, data: ExplorerData) -> None:
        """Draw existing prepared channels without calculating analysis stages.

        Args:
            data: Snapshot supplying source-aligned channels and context intervals.

        Returns:
            None.
        """
        self.data = data
        active = data.calibrated_enabled
        colors = (
            (self.theme.chart_forces or self.theme.forces)
            if active
            else (self.theme.chart_raw or self.theme.raw)
        )
        for line, values, name, color in zip(
            self.series,
            self.data.plotted_channels,
            self.data.channel_names,
            colors,
            strict=True,
        ):
            line.setName(name)
            line.setPen(QPen(QColor(color), 1.5))
            line.replace(
                [QPointF(self.data.time_at(index), value) for index, value in enumerate(values)],
            )
        self.chart.setTitle("")
        self._draw_vertical_context()

    def reset_axes(self) -> None:
        """Install replay/value labels and restore the bound recording's default view.

        Returns:
            None; leave the empty chart unchanged when no snapshot is bound.

        Raises:
            AssertionError: Qt created axes with unexpected types.
        """
        data = self.data
        if data is None:
            return
        self.sample_cursor.clear()
        for line in self.source_marker_lines.values():
            line.clear()
        self.chart.createDefaultAxes()
        # Keep explicit axis labels and references after the chart has all data.
        current_x = self.chart.axes(Qt.Orientation.Horizontal)[0]
        current_y = self.chart.axes(Qt.Orientation.Vertical)[0]
        assert isinstance(current_x, QValueAxis) and isinstance(current_y, QValueAxis)
        self.chart.removeAxis(current_x)
        self.axis_x = QCategoryAxis()
        self.axis_x.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)
        for chart_series in self.chart.series():
            chart_series.attachAxis(self.axis_x)
        current_x.deleteLater()
        self.chart.removeAxis(current_y)
        self.axis_y = QCategoryAxis()
        self.axis_y.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        for chart_series in self.chart.series():
            chart_series.attachAxis(self.axis_y)
        current_y.deleteLater()
        self._style_axes()
        bind(self.axis_x, data.replay_time_label, "titleText")
        self.axis_x.rangeChanged.connect(self.redraw_time_labels)
        self.axis_x.rangeChanged.connect(self._redraw_selection)
        self.axis_x.rangeChanged.connect(self._range_changed)
        self.axis_x.rangeChanged.connect(self._bound_time_view)
        self.axis_x.rangeChanged.connect(self.redraw_source_markers)
        self.axis_x.rangeChanged.connect(self._redraw_vertical_context)
        self.axis_x.setRange(*data.default_time_range)
        bind(
            self.axis_y,
            tr("G-force (g)") if data.calibrated_enabled else tr("Source value (unit unknown)"),
            "titleText",
        )
        self.axis_y.rangeChanged.connect(self._fix_value_view)
        self.axis_y.setRange(*data.value_range)
        self.axis_y.rangeChanged.connect(self._redraw_cursor)
        self.axis_y.rangeChanged.connect(self.redraw_value_labels)
        self.redraw_value_labels()
        self.redraw_time_labels()
        self.redraw_source_markers()

    def set_channel_visible(self, index: int, visible: bool) -> None:
        """Apply channel visibility and keep vertical-context graphics consistent.

        Args:
            index: Channel index from zero through two.
            visible: Whether the corresponding curve is displayed.

        Returns:
            None.

        Raises:
            IndexError: The channel index is outside the three displayed curves.
        """
        self.series[index].setVisible(visible)
        if index == 0:
            self._set_vertical_context_visible(visible)

    def set_cursor(self, position: float) -> None:
        """Display the source-sample position supplied by playback or selection.

        Args:
            position: Integer or fractional source-sample coordinate.

        Returns:
            None.
        """
        self._cursor_position = position
        self._redraw_cursor()

    def set_selection(self, selection: SampleRange) -> None:
        """Display a validated inclusive export selection without changing the view.

        Args:
            selection: Source-sample interval selected by the window controls.

        Returns:
            None.
        """
        self._selection = selection
        self._redraw_selection()

    def _draw_vertical_context(self) -> None:
        for bar in self.vertical_context_bars:
            self.chart.scene().removeItem(bar)
        self.vertical_context_bars.clear()
        self.vertical_context_ranges = ()
        self.airtime_legend.hide()
        if self.data is None or not self.data.calibrated_enabled:
            return
        colors = self.theme.vertical_context_colors
        self.vertical_context_ranges = self.data.vertical_context_segments
        for label, _, _ in self.vertical_context_ranges:
            bar = QGraphicsRectItem(self.chart)
            bar.setPen(QPen(Qt.PenStyle.NoPen))
            bar.setBrush(QColor(colors.get(label, self.theme.muted)))
            bar.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            bar.setZValue(10)
            self.vertical_context_bars.append(bar)
        self.airtime_legend.setText(
            " &nbsp; ".join(
                f'<span style="color:{color}">● {tr(label)}</span>'
                for label, color in colors.items()
            ),
        )
        bind(
            self.airtime_legend,
            tr("Airtime context uses provisional thresholds."),
            "toolTip",
        )
        self._set_vertical_context_visible(self.series[0].isVisible())

    @Slot(bool)
    def _set_vertical_context_visible(self, visible: bool) -> None:
        self.airtime_legend.setVisible(visible and bool(self.vertical_context_bars))
        self._redraw_vertical_context()

    def _redraw_vertical_context(self) -> None:
        if self.data is None:
            return
        plot = self.chart.plotArea()
        low, high = self.axis_x.min(), self.axis_x.max()
        enabled = self.data.calibrated_enabled and self.series[0].isVisible()
        for bar, (_, first, last) in zip(
            self.vertical_context_bars,
            self.vertical_context_ranges,
            strict=True,
        ):
            start = max(low, self.data.time_at(first))
            end = min(high, self.data.time_at(last))
            visible = enabled and high > low and end > start and plot.height() > 10
            bar.setVisible(visible)
            if visible:
                left = plot.left() + (start - low) / (high - low) * plot.width()
                right = plot.left() + (end - low) / (high - low) * plot.width()
                bar.setRect(left, plot.bottom() - 10, right - left, 10)

    @Slot(float, float)
    def zoom_wheel(self, fraction: float, steps: float) -> None:
        """Apply the chart's wheel-zoom request around its anchor.

        Args:
            fraction: Normalized time coordinate within the plotted interval.
            steps: Number of increments to apply.

        Returns:
            None.
        """
        if self.data is None or self.data.duration <= 0:
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        anchor = low + fraction * (high - low)
        scale = 1.25 ** -max(-20.0, min(20.0, steps))
        width = min(self.data.duration, max(1 / self.data.sample_rate, (high - low) * scale))
        first = max(0.0, min(anchor - fraction * width, self.data.duration - width))
        self.axis_x.setRange(first, first + width)

    @Slot()
    def _fix_value_view(self) -> None:
        if self.data is not None:
            low, high = self.data.value_range
            if self.axis_y.min() != low or self.axis_y.max() != high:
                self.axis_y.setRange(low, high)

    @Slot()
    def _bound_time_view(self) -> None:
        """Keep every chart interaction within the available sample timeline."""
        if self.data is None or self.data.duration <= 0:
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        if 0 <= low < high <= self.data.duration:
            return
        width = min(high - low, self.data.duration)
        first = max(0.0, min(low, self.data.duration - width))
        last = min(self.data.duration, first + width)
        if low != first or high != last:
            self.axis_x.setRange(first, last)

    @Slot()
    def redraw_value_labels(self) -> None:
        """Refresh value ticks from the existing snapshot and interface language.

        Returns:
            None without changing the snapshot or marker choices.
        """
        if self.data is None or not isinstance(self.axis_y, QCategoryAxis):
            return
        low, high = self.data.value_range
        self.axis_y.blockSignals(True)
        for label in self.axis_y.categoriesLabels():
            self.axis_y.remove(label)
        self.axis_y.setStartValue(low - max(1, abs(low)) * 1e-6)
        for value in self.data.value_ticks:
            label = str(tr("{0:.3g}", value)) + (" g" if self.data.calibrated_enabled else "")
            self.axis_y.append(label, value)
        self.axis_y.setRange(low, high)
        self.axis_y.blockSignals(False)

    @Slot()
    def redraw_time_labels(self) -> None:
        """Refresh replay-time ticks for the current viewport and interface language.

        Returns:
            None without changing the snapshot or marker choices.
        """
        if self.data is None or not isinstance(self.axis_x, QCategoryAxis):
            return
        low, high = self.axis_x.min(), self.axis_x.max()
        stride = max(1, round(round((high - low) * self.data.sample_rate / 5, 9)))
        anchor = self.data.ride_bounds[0]
        first_tick = ceil((max(0.0, low * self.data.sample_rate) - anchor - 1e-9) / stride)
        first = anchor + first_tick * stride
        indices = range(
            first,
            min(self.data.count, int(high * self.data.sample_rate + 1e-9) + 1),
            stride,
        )
        labels = [self.data.replay_text(index) for index in indices]
        if self.axis_x.categoriesLabels() == labels:
            return
        self.axis_x.blockSignals(True)
        for label in self.axis_x.categoriesLabels():
            self.axis_x.remove(label)
        self.axis_x.setStartValue(low - 1 / self.data.sample_rate)
        for index in indices:
            time = self.data.time_at(index)
            self.axis_x.append(self.data.replay_text(index), time)
        self.axis_x.setRange(low, high)
        self.axis_x.blockSignals(False)

    @Slot()
    def redraw_source_markers(self) -> None:
        """Refresh retained marker lines and labels within the visible interval.

        Returns:
            None without changing the snapshot or marker choices.
        """
        if self.data is None:
            return
        for line in self.source_marker_lines.values():
            line.clear()
        for label in self.source_marker_labels.values():
            label.hide()
        plot = self.chart.plotArea()
        for row, (name, index) in enumerate(self.data.markers):
            time = self.data.time_at(index)
            line = self.source_marker_lines[name]
            line.replace(
                [QPointF(time, self.data.value_range[0]), QPointF(time, self.data.value_range[1])],
            )
            label = self.source_marker_labels[name]
            marker_names = {
                "startIndex": "Start marker",
                "endIndex": "End marker",
                "gravityIndex": "Gravity marker",
                "inclineIndex": "Incline marker",
            }
            display_name = tr(marker_names[name])
            bind(label, f"{display_name} · {self.data.replay_text(index)}", "text")
            bind(
                label,
                tr("{0}: sample {1}; recording {2:.3f} s", display_name, index, time),
                "toolTip",
            )
            if self.axis_x.min() <= time <= self.axis_x.max() and plot.width() > 0:
                x = self.chart.mapToPosition(QPointF(time, self.axis_y.max()), line).x()
                x = max(plot.left(), min(x + 3, plot.right() - label.boundingRect().width()))
                label.setPos(x, plot.top() + row * (label.boundingRect().height() + 2))
                label.show()

    @Slot()
    def _redraw_selection(self) -> None:
        selected = self._selection
        if self.data is None or selected is None or selected.last >= self.data.count:
            self.selection_band.hide()
            return
        plot = self.chart.plotArea()
        low, high = self.axis_x.min(), self.axis_x.max()
        first = max(low, self.data.time_at(selected.first))
        last = min(high, self.data.time_at(selected.last))
        visible = high > low and last >= first and plot.width() > 0 and plot.height() > 0
        self.selection_band.setVisible(visible)
        if visible:
            left = plot.left() + (first - low) / (high - low) * plot.width()
            right = plot.left() + (last - low) / (high - low) * plot.width()
            if right - left < 2:
                left = max(plot.left(), min(left - 1, plot.right() - 2))
                right = min(plot.right(), left + 2)
            color = self.chart_view.palette().highlight().color()
            color.setAlpha(32)
            self.selection_band.setBrush(color)
            self.selection_band.setRect(left, plot.top(), right - left, plot.height())

    @Slot()
    def reset_view(self) -> None:
        """Restore the recording's effective default chart interval.

        Returns:
            None.
        """
        self.chart.zoomReset()
        if self.data is not None:
            self.axis_x.setRange(*self.data.default_time_range)
            self.axis_y.setRange(*self.data.value_range)

    @Slot()
    def _redraw_cursor(self) -> None:
        if self.data is not None:
            time = self._cursor_position / self.data.sample_rate
            self.sample_cursor.replace(
                [QPointF(time, self.axis_y.min()), QPointF(time, self.axis_y.max())],
            )

    @Slot()
    def _range_changed(self) -> None:
        self.range_changed.emit()
