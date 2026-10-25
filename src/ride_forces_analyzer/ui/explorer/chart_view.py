"""Chart gestures translated into sample, zoom and marker-menu signals.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap

from PySide6.QtCharts import QChart, QChartView
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
)


class TimeChartView(QChartView):
    """Time chart view contract and owned data.

    Attributes:
        zoom_requested: Qt signal for zoom requested notifications.
        sample_requested: Qt signal for sample requested notifications.
        marker_menu_requested: Qt signal for marker menu requested notifications.
        _press_position: Pointer position at the start of the current gesture.
        _dragged: Whether pointer motion has become a drag gesture.
    """

    zoom_requested = Signal(float, float)
    sample_requested = Signal(float)
    marker_menu_requested = Signal(float, QPoint)

    def __init__(self, chart: QChart) -> None:
        """Initialize time chart view and its owned state.

        Args:
            chart: Chart owned by this view.

        Returns:
            None.
        """
        super().__init__(chart)
        self._press_position: QPointF | None = None
        self._dragged = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle a mouse press and retain the state needed by the interaction.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if event.button() == Qt.MouseButton.RightButton:
            self._press_position = None
            event.accept()
            return
        self._press_position = (
            event.position() if event.button() == Qt.MouseButton.LeftButton else None
        )
        self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Update the active chart interaction for the pointer position.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if self._press_position is not None:
            self._dragged |= (
                event.position() - self._press_position
            ).manhattanLength() >= QApplication.startDragDistance()
            if not self._dragged:
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Complete the active mouse interaction and release its state.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if event.button() == Qt.MouseButton.RightButton:
            chart = self.chart()
            point = chart.mapFromScene(self.mapToScene(event.position().toPoint()))
            plot = chart.plotArea()
            if plot.contains(point) and plot.width() > 0:
                self.marker_menu_requested.emit(
                    (point.x() - plot.left()) / plot.width(),
                    self.mapToGlobal(event.position().toPoint()),
                )
            event.accept()
            return
        clicked = (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_position is not None
            and not self._dragged
            and (event.position() - self._press_position).manhattanLength()
            < QApplication.startDragDistance()
        )
        self._press_position = None
        chart = self.chart()
        point = chart.mapFromScene(self.mapToScene(event.position().toPoint()))
        plot = chart.plotArea()
        super().mouseReleaseEvent(event)
        if clicked and plot.contains(point) and plot.width() > 0:
            self.sample_requested.emit((point.x() - plot.left()) / plot.width())

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Translate wheel input into the view's zoom or navigation request.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        chart = self.chart()
        point = chart.mapFromScene(self.mapToScene(event.position().toPoint()))
        plot = chart.plotArea()
        delta = event.angleDelta().y()
        if plot.contains(point) and plot.width() > 0 and delta:
            fraction = (point.x() - plot.left()) / plot.width()
            self.zoom_requested.emit(fraction, delta / 120)
            event.accept()
        else:
            event.ignore()
