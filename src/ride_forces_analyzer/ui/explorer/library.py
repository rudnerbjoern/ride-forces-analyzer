"""Collapsible Library surface and its toolbar toggle.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QPushButton, QSplitter, QStyle, QWidget

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.translation import bind, button_text

from .controls import create_panel


class LibraryPanel(QSplitter):
    """Own the left Library surface beside the existing analysis workspace.

    Attributes:
        panel: Initially hidden Library content, currently containing only a title.
        toggle_button: Localized toolbar control with open/closed folder icons.
    """

    def __init__(self, parent: QWidget) -> None:
        """Build the empty Library and its adjustable horizontal container.

        Args:
            parent: Widget owning this component's lifetime.
        """
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(10)
        self.panel, layout = create_panel()
        layout.addWidget(bind(QLabel(), tr("Library")))
        layout.addStretch()
        self.addWidget(self.panel)
        self.panel.hide()
        self.toggle_button = button_text(QPushButton(), tr("Library"))
        self.toggle_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirClosedIcon),
        )
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)

    @Slot(bool)
    def _toggle(self, checked: bool) -> None:
        """Show or hide the content and match the folder icon to its visible state."""
        self.panel.setVisible(checked)
        self.toggle_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon
                if checked
                else QStyle.StandardPixmap.SP_DirClosedIcon,
            ),
        )
