"""Draft Library video-label choices for the existing Settings Save/Cancel flow.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.translation import bind, button_text


class LibraryLabelsEditor(QGroupBox):
    """Edit a local draft; only the owning Settings dialog persists its values.

    Attributes:
        choices: Ordered list of draft label texts.
        name: Text used for adding or renaming an option.
        add: Action appending a new choice.
        rename: Action replacing the selected choice.
        remove: Action deleting the selected choice from the draft.
    """

    def __init__(self, labels: tuple[str, ...], parent: QWidget) -> None:
        """Create controls matching the existing Settings groups.

        Args:
            labels: Current preference choices, including an intentionally empty list.
            parent: Settings dialog owning the draft.
        """
        super().__init__(parent)
        bind(self, tr("Library"), "title")
        layout = QVBoxLayout(self)
        layout.addWidget(bind(QLabel(), tr("Video labels")))
        self.choices = QListWidget()
        self.choices.setMaximumHeight(100)
        self.choices.addItems(labels)
        bind(self.choices, tr("Video labels"), "accessibleName")
        layout.addWidget(self.choices)
        self.name = QLineEdit()
        bind(self.name, tr("Label"), "accessibleName")
        bind(self.name, tr("Label"), "placeholderText")
        layout.addWidget(self.name)
        row = QHBoxLayout()
        self.add = button_text(QPushButton(), tr("Add"))
        self.rename = button_text(QPushButton(), tr("Rename"))
        self.remove = button_text(QPushButton(), tr("Remove"))
        for button in (self.add, self.rename, self.remove):
            row.addWidget(button)
        layout.addLayout(row)
        self.choices.currentRowChanged.connect(self._selected)
        self.name.textChanged.connect(self._update_actions)
        self.add.clicked.connect(self._add)
        self.rename.clicked.connect(self._rename)
        self.remove.clicked.connect(self._remove)
        self._update_actions()

    def labels(self) -> tuple[str, ...]:
        """Return the ordered draft choices without changing preferences.

        Returns:
            Current label texts, including an empty tuple after removing all choices.
        """
        return tuple(self.choices.item(index).text() for index in range(self.choices.count()))

    def _selected(self) -> None:
        item = self.choices.currentItem()
        self.name.setText(item.text() if self.choices.currentRow() >= 0 else "")
        self._update_actions()

    def _update_actions(self) -> None:
        selected = self.choices.currentRow() >= 0
        self.add.setEnabled(bool(self.name.text().strip()))
        self.rename.setEnabled(selected and bool(self.name.text().strip()))
        self.remove.setEnabled(selected)

    def _add(self) -> None:
        self.choices.addItem(self.name.text().strip())
        self.choices.setCurrentRow(self.choices.count() - 1)

    def _rename(self) -> None:
        item = self.choices.currentItem()
        if self.choices.currentRow() >= 0:
            item.setText(self.name.text().strip())

    def _remove(self) -> None:
        self.choices.takeItem(self.choices.currentRow())
        self._selected()
