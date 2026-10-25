"""Sample-selection and smoothing controls with native mouse interactions.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Pixmap

from ride_forces_analyzer.ui.presentation.translation import bind

from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtGui import (
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QSlider,
    QStyle,
    QStyleOptionSpinBox,
    QSpinBox,
)


class SmoothingSlider(QSlider):
    """Right click restores the default 11-sample window (slider position five)."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle a mouse press and retain the state needed by the interaction.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        if event.button() == Qt.MouseButton.RightButton:
            self.setValue(5)
            event.accept()
            return
        super().mousePressEvent(event)


class SelectionSpinBox(QSpinBox):
    """Use 1/5/10/20/50-sample steps after 0/1/2/3/5 seconds holding an arrow.

    Attributes:
        _hold_timer: Timer repeating the held sample-selection action.
    """

    def __init__(self) -> None:
        """Initialize selection spin box and its owned state.

        Returns:
            None.
        """
        super().__init__()
        self._hold_timer = QElapsedTimer()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle a mouse press and retain the state needed by the interaction.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        self._hold_timer.invalidate()
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        button = self.style().hitTestComplexControl(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            event.position().toPoint(),
            self,
        )
        if event.button() == Qt.MouseButton.LeftButton and button in (
            QStyle.SubControl.SC_SpinBoxUp,
            QStyle.SubControl.SC_SpinBoxDown,
        ):
            self._hold_timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Complete the active mouse interaction and release its state.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        self._hold_timer.invalidate()
        super().mouseReleaseEvent(event)

    def stepBy(self, steps: int) -> None:
        """Step the sample control while respecting its range and hold behavior.

        Args:
            steps: Number of increments to apply.

        Returns:
            None.
        """
        elapsed = self._hold_timer.elapsed() if self._hold_timer.isValid() else 0
        stride = (
            50
            if elapsed >= 5000
            else 20
            if elapsed >= 3000
            else 10
            if elapsed >= 2000
            else 5
            if elapsed >= 1000
            else 1
        )
        super().stepBy(steps * stride)


def create_panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Create a consistently styled panel and its vertical content layout.

    Args:
        title: Optional translated section heading.

    Returns:
        The new panel and its content layout.
    """
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(6)
    if title:
        label = bind(QLabel(), title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
    return panel, layout
