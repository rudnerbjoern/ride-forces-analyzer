"""Separate Library video-link dialog using the application's standard form layout.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.presentation.translation import bind, button_text


class LibraryVideosDialog(QDialog):
    """Edit one recording's links without occupying the narrow Library panel.

    Attributes:
        store: Library persistence boundary owning validation and transactions.
        preferences: Source of current label choices.
        source_sha256: Recording identity fixed for this dialog's lifetime.
        links: Saved links; selecting one prepares its individual edit form.
        url: User-supplied video URL editor.
        label: Non-editable dropdown including unset and retained saved values.
        add: Action preparing a new link without modifying existing ones.
        remove: Action deleting the selected saved link.
        error: Visible persistence/validation explanation.
        buttons: Standard Save and Cancel actions for the current edit.
    """

    def __init__(
        self,
        source_sha256: str,
        parent: QWidget,
        *,
        store: LibraryStore | None = None,
        preferences: Preferences | None = None,
    ) -> None:
        """Open a recording-bound form without loading sensor data or visiting URLs.

        Args:
            source_sha256: Archived source owning every link shown in the dialog.
            parent: Library panel owning the window.
            store: Explicit store for isolated use, or the application Library.
            preferences: Explicit preferences, or the application defaults.
        """
        super().__init__(parent)
        self.store = store if store is not None else LibraryStore()
        self.preferences = preferences if preferences is not None else Preferences()
        self.source_sha256 = source_sha256
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        bind(self, tr("Video links…"), "windowTitle")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        group = bind(QGroupBox(), tr("Video links"), "title")
        group_layout = QVBoxLayout(group)
        self.links = QListWidget()
        bind(self.links, tr("Video links"), "accessibleName")
        group_layout.addWidget(self.links)
        actions = QHBoxLayout()
        self.add = button_text(QPushButton(), tr("Add"))
        self.remove = button_text(QPushButton(), tr("Remove"))
        actions.addWidget(self.add)
        actions.addWidget(self.remove)
        actions.addStretch()
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        form_group = bind(QGroupBox(), tr("Video link"), "title")
        form = QFormLayout(form_group)
        self.url = QLineEdit()
        bind(self.url, tr("Video URL"), "accessibleName")
        self.label = QComboBox()
        bind(self.label, tr("Label"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Video URL")), self.url)
        form.addRow(bind(QLabel(), tr("Label")), self.label)
        layout.addWidget(form_group)
        self.error = QLabel()
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        for standard, text, icon in (
            (
                QDialogButtonBox.StandardButton.Save,
                "&Save",
                QStyle.StandardPixmap.SP_DialogSaveButton,
            ),
            (
                QDialogButtonBox.StandardButton.Cancel,
                "Cancel",
                QStyle.StandardPixmap.SP_DialogCancelButton,
            ),
        ):
            button = self.buttons.button(standard)
            bind(button, tr(text))
            bind(
                button,
                tr("Save video link")
                if standard == QDialogButtonBox.StandardButton.Save
                else tr(text),
                "toolTip",
            )
            bind(
                button,
                tr("Save video link")
                if standard == QDialogButtonBox.StandardButton.Save
                else tr(text),
                "accessibleName",
            )
            button.setIcon(self.style().standardIcon(icon))
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self.links.currentItemChanged.connect(self._selected)
        self.add.clicked.connect(self._new)
        self.remove.clicked.connect(self._remove)
        self._reload()

    def _reload(self, selected_id: int | None = None) -> None:
        try:
            links = self.store.video_links(self.source_sha256)
        except LibraryStoreError as error:
            self._show_error(error)
            return
        self.links.clear()
        for link in links:
            item = QListWidgetItem(f"{link.label or tr('No label')} · {link.url}")
            item.setToolTip(link.url)
            item.setData(Qt.ItemDataRole.UserRole, (link.id, link.url, link.label))
            self.links.addItem(item)
            if link.id == selected_id:
                self.links.setCurrentItem(item)
        if selected_id is None:
            self._new()

    def _choices(self, saved: str) -> None:
        self.label.clear()
        self.label.addItem(tr("No label"), "")
        choices = self.preferences.library_video_labels()
        for label in choices:
            self.label.addItem(label, label)
        if saved and saved not in choices:
            self.label.addItem(saved, saved)
        self.label.setCurrentIndex(max(0, self.label.findData(saved)))

    def _selected(self) -> None:
        item = self.links.currentItem()
        if self.links.currentRow() < 0:
            self.remove.setEnabled(False)
            return
        _, url, label = item.data(Qt.ItemDataRole.UserRole)
        self.url.setText(url)
        self._choices(label)
        self.remove.setEnabled(True)
        self.error.hide()

    def _new(self) -> None:
        self.links.setCurrentRow(-1)
        self.url.clear()
        self._choices("")
        self.remove.setEnabled(False)
        self.error.hide()
        self.url.setFocus()

    def _save(self) -> None:
        item = self.links.currentItem()
        link_id = item.data(Qt.ItemDataRole.UserRole)[0] if self.links.currentRow() >= 0 else None
        try:
            saved = self.store.save_video_link(
                self.source_sha256,
                self.url.text(),
                self.label.currentData(),
                link_id=link_id,
            )
        except (LibraryStoreError, ValueError) as error:
            self._show_error(error)
            return
        self._reload(saved)

    def _remove(self) -> None:
        item = self.links.currentItem()
        if self.links.currentRow() < 0:
            return
        try:
            self.store.remove_video_link(self.source_sha256, item.data(Qt.ItemDataRole.UserRole)[0])
        except LibraryStoreError as error:
            self._show_error(error)
            return
        self._reload()

    def _show_error(self, error: Exception) -> None:
        self.error.setText(tr("Could not save video links: {0}", tr(str(error))))
        self.error.show()
