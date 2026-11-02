"""Inline Library workflow icons and a transient horizontal selection bar.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QStyle,
    QToolButton,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.library import WORKFLOW_STATUSES


WORKFLOW_ICONS = {
    "imported": ("Imported", QStyle.StandardPixmap.SP_FileIcon),
    "markers_verified": ("Markers verified", QStyle.StandardPixmap.SP_DialogApplyButton),
    "overlays_created": ("Overlays created", QStyle.StandardPixmap.SP_FileDialogContentsView),
    "video_ready": ("Video ready", QStyle.StandardPixmap.SP_MediaPlay),
    "uploaded": ("Uploaded", QStyle.StandardPixmap.SP_ArrowUp),
    "completed": ("Completed", QStyle.StandardPixmap.SP_DialogYesButton),
}

_ICON_STYLE = """
QToolButton, QToolButton:hover, QToolButton:pressed, QToolButton:checked {
    background: transparent; border: none; padding: 4px;
}
QToolButton:checked { border-bottom: 2px solid palette(highlight); }
"""


class WorkflowIcon(QWidget):
    """Keep a clickable status icon centered in its existing recording cell.

    Attributes:
        button: Native icon-only control that does not select or load the recording.
        clicked: Signal identifying the recording whose status selector is requested.
        source_sha256: Recording identity represented by this icon.
    """

    clicked = Signal(str)

    def __init__(self, source_sha256: str, parent: QWidget) -> None:
        """Create the compact trigger without reading a source or changing selection.

        Args:
            source_sha256: Recording identity carried by clicks.
            parent: Recording view owning the cell widget.
        """
        super().__init__(parent)
        self.source_sha256 = source_sha256
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.button = QToolButton()
        self.button.setAutoRaise(True)
        self.button.setFixedSize(28, 28)
        self.button.setStyleSheet(_ICON_STYLE)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._clicked)
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)

    def refresh_labels(self, status: str) -> None:
        """Apply the current theme's native icon and localized status description.

        Args:
            status: Persisted workflow state represented by this trigger.
        """
        label, icon = WORKFLOW_ICONS[status]
        self.button.setIcon(self.style().standardIcon(icon))
        self.button.setToolTip(tr(label))
        self.button.setAccessibleName(tr(label))

    def _clicked(self) -> None:
        self.clicked.emit(self.source_sha256)


class WorkflowSelector(QFrame):
    """Offer every manual status as an icon-only foreground layer anchored to the entry.

    Attributes:
        buttons: Status controls keyed in left-to-right workflow order.
        group: Exclusive group highlighting the persisted current state.
        chosen: Signal requesting immediate persistence of a chosen status.
        dismissed: Signal requesting closure without a change.
        trigger: The entry's status button, also allowed to toggle the bar closed.
    """

    chosen = Signal(str)
    dismissed = Signal()

    def __init__(self, trigger: QWidget, parent: QWidget) -> None:
        """Build the foreground icon row and observe Escape/outside clicks while visible.

        Args:
            trigger: Current-status button opening this selector.
            parent: Main window owning the foreground layer.
        """
        super().__init__(parent)
        self.trigger = trigger
        self.setObjectName("LibraryWorkflowSelector")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        for index, status in enumerate(WORKFLOW_STATUSES):
            button = QToolButton()
            button.setAutoRaise(True)
            button.setCheckable(True)
            button.setFixedSize(28, 28)
            button.setStyleSheet(_ICON_STYLE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(button, index)
            self.buttons[status] = button
            layout.addWidget(button)
        layout.addStretch()
        self.group.idClicked.connect(self._choose)
        application = QApplication.instance()
        assert isinstance(application, QApplication)
        application.installEventFilter(self)

    def refresh_labels(self, status: str) -> None:
        """Refresh theme/locale and restore the persisted check on failed writes.

        Args:
            status: Persisted current status, independent of the requested next state.
        """
        for key, button in self.buttons.items():
            label, icon = WORKFLOW_ICONS[key]
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(tr(label))
            button.setAccessibleName(tr(label))
            button.setChecked(key == status)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Dismiss the visible selector on Escape or a click outside its controls.

        Args:
            watched: Original target of the application event.
            event: Native Qt event being delivered.

        Returns:
            True only for Escape consumed by the visible selector.
        """
        if self.isVisible():
            if (
                isinstance(event, QKeyEvent)
                and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape
            ):
                self.dismissed.emit()
                return True
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(watched, QWidget):
                if (
                    watched is not self.trigger
                    and watched is not self
                    and not self.isAncestorOf(watched)
                ):
                    self.dismissed.emit()
        return False

    def _choose(self, index: int) -> None:
        self.chosen.emit(WORKFLOW_STATUSES[index])
