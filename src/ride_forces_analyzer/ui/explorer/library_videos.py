"""Separate Library video-link dialog using the application's standard form layout.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import QEvent, QModelIndex, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QHeaderView,
    QPushButton,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.library import LibraryStore, LibraryStoreError, validate_video_url
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.explorer.library_workflow import LibraryIcon
from ride_forces_analyzer.ui.presentation.translation import bind, button_text
from ride_forces_analyzer.ui.presentation.icons import link_icon
from ride_forces_analyzer.runtime.error_logging import error_message, record_error


class LibraryVideosDialog(QDialog):
    """Edit one recording's links without occupying the narrow Library panel.

    Attributes:
        store: Library persistence boundary owning validation and transactions.
        preferences: Source of current label choices.
        source_sha256: Recording identity fixed for this dialog's lifetime.
        links: Saved links; selecting one prepares its individual edit form.
        url: User-supplied video URL editor.
        changed: Notification after a link is successfully saved or removed.
        label: Non-editable dropdown including unset and retained saved values.
        add: Action preparing a new link without modifying existing ones.
        remove: Action deleting the selected saved link.
        error: Visible persistence/validation explanation.
        buttons: Standard Save and Cancel actions for the current edit.
    """

    changed = Signal()

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
        self.links = QTreeWidget()
        self.links.setColumnCount(2)
        self.links.setHeaderHidden(True)
        self.links.setRootIsDecorated(False)
        self.links.header().setStretchLastSection(False)
        self.links.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.links.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.links.setColumnWidth(1, 32)
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

    def changeEvent(self, event: QEvent) -> None:
        """Redraw the browser icon when the dialog's theme changes.

        Args:
            event: Qt notification of a changed dialog property.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and hasattr(self, "links"):
            for index in range(self.links.topLevelItemCount()):
                item = self.links.topLevelItem(index)
                if item is None:
                    continue
                icon = self.links.itemWidget(item, 1)
                if isinstance(icon, LibraryIcon):
                    icon.button.setIcon(
                        link_icon(self.palette().color(QPalette.ColorRole.WindowText)),
                    )

    def _open_url(self, url: str) -> None:
        """Open a saved address without changing selection or unsaved edits."""
        try:
            url = validate_video_url(url)
        except ValueError as error:
            record_error("ui.explorer.library_videos._open_url", error)
            return
        if QDesktopServices.openUrl(QUrl(url)):
            self.error.hide()
        else:
            self.error.setText(tr("Could not open the video link in your browser."))
            self.error.show()

    def _reload(self, selected_id: int | None = None) -> None:
        try:
            links = self.store.video_links(self.source_sha256)
        except LibraryStoreError as error:
            record_error("ui.explorer.library_videos._reload", error)
            self._show_error(error)
            return
        self.links.clear()
        for link in links:
            item = QTreeWidgetItem([f"{link.label or tr('No label')} · {link.url}"])
            item.setToolTip(0, link.url)
            item.setData(0, Qt.ItemDataRole.UserRole, (link.id, link.url, link.label))
            self.links.addTopLevelItem(item)
            icon = LibraryIcon(link.url, self.links)
            icon.button.setIcon(link_icon(self.palette().color(QPalette.ColorRole.WindowText)))
            bind(icon.button, tr("Open in browser"), "toolTip")
            bind(icon.button, tr("Open in browser"), "accessibleName")
            try:
                validate_video_url(link.url)
            except ValueError as error:
                record_error("ui.explorer.library_videos._reload", error)
                icon.button.setEnabled(False)
            icon.clicked.connect(self._open_url)
            self.links.setItemWidget(item, 1, icon)
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
        if item is None:
            self.remove.setEnabled(False)
            return
        _, url, label = item.data(0, Qt.ItemDataRole.UserRole)
        self.url.setText(url)
        self._choices(label)
        self.remove.setEnabled(True)
        self.error.hide()

    def _new(self) -> None:
        self.links.setCurrentIndex(QModelIndex())
        self.links.clearSelection()
        self.url.clear()
        self._choices("")
        self.remove.setEnabled(False)
        self.error.hide()
        self.url.setFocus()

    def _save(self) -> None:
        item = self.links.currentItem()
        link_id = item.data(0, Qt.ItemDataRole.UserRole)[0] if item is not None else None
        try:
            saved = self.store.save_video_link(
                self.source_sha256,
                self.url.text(),
                self.label.currentData(),
                link_id=link_id,
            )
        except (LibraryStoreError, ValueError) as error:
            record_error("ui.explorer.library_videos._save", error)
            self._show_error(error)
            return
        self._reload(saved)
        self.changed.emit()

    def _remove(self) -> None:
        item = self.links.currentItem()
        if item is None:
            return
        try:
            self.store.remove_video_link(
                self.source_sha256,
                item.data(0, Qt.ItemDataRole.UserRole)[0],
            )
        except LibraryStoreError as error:
            record_error("ui.explorer.library_videos._remove", error)
            self._show_error(error)
            return
        self._reload()
        self.changed.emit()

    def _show_error(self, error: Exception) -> None:
        self.error.setText(tr("Could not save video links: {0}", error_message(error)))
        self.error.show()
