"""Separate Library video-link dialog using the application's standard form layout.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
import subprocess
from typing import cast

from PySide6.QtCore import QEvent, QModelIndex, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QHeaderView,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.storage.library import (
    LibraryStore,
    LibraryStoreError,
    VideoLinkDraft,
    validate_video_url,
)
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.explorer.library_workflow import LibraryIcon
from ride_forces_analyzer.ui.presentation.translation import bind
from ride_forces_analyzer.ui.presentation.icons import link_action_icon, link_icon, search_icon
from ride_forces_analyzer.ui.presentation.file_manager import show_in_folder
from ride_forces_analyzer.runtime.error_logging import error_message, record_error


class LibraryVideosDialog(QDialog):
    """Edit one recording's links without occupying the narrow Library panel.

    Attributes:
        store: Library persistence boundary owning validation and transactions.
        preferences: Source of current label choices.
        source_sha256: Recording identity fixed for this dialog's lifetime.
        links: Draft links; selecting one loads its individual edit form.
        url: User-supplied video URL editor.
        video_file: Draft full path for this recording's single external video file.
        file_browse: Icon-only native file-selection action.
        file_reveal: Icon-only action revealing the file in the native file manager.
        changed: Notification after the entire dialog draft is saved.
        label: Non-editable dropdown including unset and retained saved values.
        add: Plus/check mark action adding or applying an edit to the draft list.
        remove: Minus action removing the selected draft link.
        editor_group: Group caption identifying new-link and edit modes.
        url_error: Inline explanation for an invalid editor address.
        error: Visible persistence/validation explanation.
        buttons: Standard Save and Cancel actions for the complete dialog draft.
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
        self.resize(720, 500)
        layout = QVBoxLayout(self)
        file_group = bind(QGroupBox(), tr("Video file"), "title")
        file_layout = QHBoxLayout(file_group)
        self.video_file = QLineEdit()
        bind(self.video_file, tr("Video file path"), "accessibleName")
        self.file_browse = QToolButton()
        self.file_reveal = QToolButton()
        file_layout.addWidget(self.video_file, 1)
        for file_button, description in (
            (self.file_browse, "Select video file…"),
            (self.file_reveal, "Show in folder"),
        ):
            bind(file_button, tr(description), "toolTip")
            bind(file_button, tr(description), "accessibleName")
            file_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            file_button.setIconSize(QSize(20, 20))
            file_button.setStyleSheet("QToolButton { padding: 0; }")
            file_layout.addWidget(file_button)
        self._file_controls()
        self.video_file.textChanged.connect(self._file_changed)
        self.file_browse.clicked.connect(self._browse_file)
        self.file_reveal.clicked.connect(self._reveal_file)
        layout.addWidget(file_group)
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
        layout.addWidget(group, 1)
        self.editor_group = QGroupBox()
        form = QFormLayout(self.editor_group)
        self._form = form
        self.url = QLineEdit()
        bind(self.url, tr("Video URL"), "accessibleName")
        self.url_error = QLabel()
        self.url_error.setTextFormat(Qt.TextFormat.PlainText)
        self.url_error.setWordWrap(True)
        self.label = QComboBox()
        bind(self.label, tr("Label"), "accessibleName")
        self.add = QToolButton()
        self.remove = QToolButton()
        for action in (self.add, self.remove):
            action.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            action.setIconSize(QSize(20, 20))
            action.setStyleSheet("QToolButton { padding: 0; }")
        url_row = QHBoxLayout()
        url_row.addWidget(self.url, 1)
        url_row.addWidget(self.add)
        form.addRow(bind(QLabel(), tr("Video URL")), url_row)
        form.addRow("", self.url_error)
        form.setRowVisible(self.url_error, False)
        label_row = QHBoxLayout()
        label_row.addWidget(self.label, 1)
        label_row.addWidget(self.remove)
        form.addRow(bind(QLabel(), tr("Label")), label_row)
        layout.addWidget(self.editor_group)
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
                tr("Save video links")
                if standard == QDialogButtonBox.StandardButton.Save
                else tr(text),
                "toolTip",
            )
            bind(
                button,
                tr("Save video links")
                if standard == QDialogButtonBox.StandardButton.Save
                else tr(text),
                "accessibleName",
            )
            button.setIcon(self.style().standardIcon(icon))
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self.links.currentItemChanged.connect(self._selected)
        self.add.clicked.connect(self._apply)
        self.remove.clicked.connect(self._remove)
        self.url.textChanged.connect(self._editor_changed)
        self._load()

    def changeEvent(self, event: QEvent) -> None:
        """Redraw the browser icon when the dialog's theme changes.

        Args:
            event: Qt notification of a changed dialog property.
        """
        super().changeEvent(event)
        if event.type() in {
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
            QEvent.Type.FontChange,
        } and hasattr(self, "file_reveal"):
            self._file_controls()
            if hasattr(self, "label"):
                self._link_controls()
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

    def _file_controls(self) -> None:
        """Keep both file buttons aligned with the path field and current theme."""
        height = max(28, self.video_file.sizeHint().height())
        self.video_file.setFixedHeight(height)
        for button in (self.file_browse, self.file_reveal):
            button.setFixedSize(height, height)
        self.file_browse.setIcon(search_icon(self.palette().color(QPalette.ColorRole.WindowText)))
        self.file_reveal.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.file_reveal.setEnabled(bool(self.video_file.text()))

    def _file_changed(self, text: str) -> None:
        """Enable revealing a nonempty draft without saving or opening it.

        Args:
            text: Current path draft.
        """
        self.file_reveal.setEnabled(bool(text))

    def _browse_file(self) -> None:
        """Choose one video path without saving or modifying the file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select video file…"),
            self.video_file.text(),
            tr("Video files (*.mp4 *.mov *.mkv *.webm *.avi *.m4v);;All files (*)"),
        )
        if filename:
            self.video_file.setText(str(Path(filename)))

    def _reveal_file(self) -> None:
        """Reveal the draft reference while retaining all unsaved edits."""
        try:
            show_in_folder(self.video_file.text())
        except (OSError, subprocess.SubprocessError) as error:
            record_error(
                "ui.explorer.library_videos._reveal_file",
                error,
                context=f"Path: {self.video_file.text()}",
            )
            self.error.setText(
                tr("Video file not found. Check the path.")
                if isinstance(error, FileNotFoundError)
                else tr("Could not show the video file: {0}", error_message(error)),
            )
            self.error.show()
        else:
            self.error.hide()

    def _load(self) -> None:
        """Load saved references once, leaving all subsequent edits in the dialog."""
        try:
            links = self.store.video_links(self.source_sha256)
            self.video_file.setText(self.store.video_file_path(self.source_sha256) or "")
            self.video_file.setCursorPosition(0)
        except LibraryStoreError as error:
            record_error("ui.explorer.library_videos._load", error)
            self._show_error(error)
            self._link_controls()
            self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            return
        for link in links:
            item = QTreeWidgetItem()
            self.links.addTopLevelItem(item)
            self._render_link(item, VideoLinkDraft(link.id, link.url, link.label))
        self._new()

    def _render_link(self, item: QTreeWidgetItem, draft: VideoLinkDraft) -> None:
        """Display a draft's label, address and independent browser action.

        Args:
            item: List row to populate or replace.
            draft: Pending values, including an optional saved identity.
        """
        item.setText(0, f"{draft.label or tr('No label')} · {draft.url}")
        item.setToolTip(0, draft.url)
        item.setData(0, Qt.ItemDataRole.UserRole, draft)
        icon = LibraryIcon(draft.url, self.links)
        icon.button.setIcon(link_icon(self.palette().color(QPalette.ColorRole.WindowText)))
        bind(icon.button, tr("Open in browser"), "toolTip")
        bind(icon.button, tr("Open in browser"), "accessibleName")
        try:
            validate_video_url(draft.url)
        except ValueError as error:
            record_error("ui.explorer.library_videos._render_link", error)
            icon.button.setEnabled(False)
        icon.clicked.connect(self._open_url)
        self.links.setItemWidget(item, 1, icon)

    def _link_controls(self) -> None:
        """Align the icon controls and identify new-link versus edit mode."""
        editing = self.links.currentItem() is not None
        bind(self.editor_group, tr("Edit link") if editing else tr("New link"), "title")
        description = tr("Apply link changes") if editing else tr("Add video link")
        bind(self.add, description, "toolTip")
        bind(self.add, description, "accessibleName")
        bind(self.remove, tr("Remove video link"), "toolTip")
        bind(self.remove, tr("Remove video link"), "accessibleName")
        color = self.palette().color(QPalette.ColorRole.WindowText)
        self.add.setIcon(link_action_icon("apply" if editing else "add", color))
        self.remove.setIcon(link_action_icon("remove", color))
        height = max(28, self.url.sizeHint().height())
        self.url.setFixedHeight(height)
        self.label.setFixedHeight(height)
        for action in (self.add, self.remove):
            action.setFixedSize(height, height)
        self.add.setEnabled(bool(self.url.text()))
        self.remove.setEnabled(editing)

    def _editor_changed(self) -> None:
        """Update field feedback without changing any list entry or saved value."""
        self._form.setRowVisible(self.url_error, False)
        self.error.hide()
        self.add.setEnabled(bool(self.url.text()))

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
            self._link_controls()
            return
        draft = cast(VideoLinkDraft, item.data(0, Qt.ItemDataRole.UserRole))
        self.url.setText(draft.url)
        self._choices(draft.label)
        self._link_controls()
        self.error.hide()

    def _new(self) -> None:
        self.links.setCurrentIndex(QModelIndex())
        self.links.clearSelection()
        self.url.clear()
        self._choices("")
        self._link_controls()
        self.error.hide()
        self._form.setRowVisible(self.url_error, False)
        self.url.setFocus()

    def _form_draft(self) -> VideoLinkDraft:
        """Read the editor through the shared URL validator.

        Returns:
            A valid new link or an edit retaining the selected row's identity.

        Raises:
            ValueError: The editor address is invalid.
        """
        item = self.links.currentItem()
        identity = (
            cast(VideoLinkDraft, item.data(0, Qt.ItemDataRole.UserRole)).id
            if item is not None
            else None
        )
        return VideoLinkDraft(
            identity,
            validate_video_url(self.url.text()),
            self.label.currentData(),
        )

    def _apply(self) -> None:
        """Add or update one list draft, then prepare an empty new-link form."""
        try:
            draft = self._form_draft()
        except ValueError as error:
            record_error("ui.explorer.library_videos._apply", error)
            self.url_error.setText(error_message(error))
            self._form.setRowVisible(self.url_error, True)
            self.url.setFocus()
            return
        item = self.links.currentItem()
        if item is None:
            item = QTreeWidgetItem()
            self.links.addTopLevelItem(item)
        self._render_link(item, draft)
        self._new()

    def _save(self) -> None:
        """Commit the full list and pending editor once, closing only on success."""
        drafts: list[VideoLinkDraft] = []
        for index in range(self.links.topLevelItemCount()):
            row = self.links.topLevelItem(index)
            assert row is not None
            drafts.append(cast(VideoLinkDraft, row.data(0, Qt.ItemDataRole.UserRole)))
        item = self.links.currentItem()
        if item is not None or self.url.text() or self.label.currentData():
            try:
                draft = self._form_draft()
            except ValueError as error:
                record_error("ui.explorer.library_videos._save", error)
                self.url_error.setText(error_message(error))
                self._form.setRowVisible(self.url_error, True)
                self.url.setFocus()
                return
            if item is None:
                drafts.append(draft)
            else:
                drafts[self.links.indexOfTopLevelItem(item)] = draft
        try:
            self.store.save_video_links(
                self.source_sha256,
                drafts,
                video_file_path=self.video_file.text(),
            )
        except (LibraryStoreError, ValueError) as error:
            record_error("ui.explorer.library_videos._save", error)
            self._show_error(error)
            return
        self.changed.emit()
        self.accept()

    def _remove(self) -> None:
        """Remove the selected list draft without writing to the Library."""
        item = self.links.currentItem()
        if item is None:
            return
        self.links.takeTopLevelItem(self.links.indexOfTopLevelItem(item))
        self._new()

    def _show_error(self, error: Exception) -> None:
        self.error.setText(tr("Could not save video links: {0}", error_message(error)))
        self.error.show()
