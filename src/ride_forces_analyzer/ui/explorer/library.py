"""Collapsible Library list, recording actions and toolbar toggle.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Demi

from dataclasses import replace
from html import escape

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPoint,
    QPersistentModelIndex,
    QSize,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QFont, QFontMetrics, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTextEdit,
    QTreeWidgetItem,
    QToolButton,
    QWidget,
)

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.explorer.library import (
    library_details,
    library_row_text,
)
from ride_forces_analyzer.storage.library import LibraryEntry, LibraryStore, LibraryStoreError
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.ui.presentation.translation import bind, button_text

from .controls import create_panel
from .library_editor import LibraryMetadataDialog
from .library_videos import LibraryVideosDialog
from .library_exports import LibraryExportsDialog
from ride_forces_analyzer.ui.presentation.icons import link_icon, metadata_icon
from .library_workflow import WORKFLOW_ICONS, WorkflowIcon, WorkflowSelector


class LibraryFilter(QComboBox):
    """Open Library filter popups without the transient Qt scroll-animation window."""

    def showPopup(self) -> None:
        """Show this popup immediately, restoring the shared animation preference afterward."""
        effect = Qt.UIEffect.UI_AnimateCombo
        enabled = QApplication.isEffectEnabled(effect)
        QApplication.setEffectEnabled(effect, False)
        try:
            super().showPopup()
        finally:
            QApplication.setEffectEnabled(effect, enabled)


class LibraryRecordingTree(QTreeWidget):
    """Defer right-click selection until the context menu can start the source load."""

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Keep a right-click from disabling the list before its context-menu event.

        Args:
            event: Mouse press delivered to the recording viewport.
        """
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)


class LibraryRowDelegate(QStyledItemDelegate):
    """Paint recording rows with the shared body font and Inspector muted style.

    Attributes:
        muted: Existing hint label supplying the current theme's muted text color.
    """

    def __init__(self, muted: QLabel, parent: QObject) -> None:
        """Use the existing styled hint as the color reference.

        Args:
            muted: Library hint using the same Muted style as Inspector hints.
            parent: View owning the delegate's lifetime.
        """
        super().__init__(parent)
        self.muted = muted

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Draw an elided three-line recording row using the current theme.

        Args:
            painter: View-owned painter.
            option: Current row geometry, palette and selection state.
            index: Recording cell or ordinary day heading.
        """
        if not isinstance(index.data(Qt.ItemDataRole.UserRole), str):
            super().paint(painter, option, index)
            return
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        lines = styled.text.splitlines()
        styled.text = ""
        style = styled.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        rect = option.rect.adjusted(8, 7, -8, -7)
        height = option.fontMetrics.height()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        for number, text in enumerate(lines):
            font = QFont(option.font)
            font.setWeight(QFont.Weight.DemiBold if number == 0 else QFont.Weight.Normal)
            painter.setFont(font)
            color = (
                option.palette.color(QPalette.ColorRole.HighlightedText)
                if selected
                else option.palette.color(QPalette.ColorRole.Text)
                if number == 0
                else self.muted.palette().color(QPalette.ColorRole.WindowText)
            )
            painter.setPen(color)
            line = rect.adjusted(0, number * height, 0, 0)
            line.setHeight(height)
            painter.drawText(
                line,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, line.width()),
            )
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QSize:
        """Reserve three text lines for recordings and the normal height for day headings.

        Args:
            option: Current view font and style.
            index: Recording cell or day heading.

        Returns:
            Compact row height independent of the recording name's length.
        """
        if isinstance(index.data(Qt.ItemDataRole.UserRole), str):
            return QSize(0, option.fontMetrics.height() * 3 + 14)
        return super().sizeHint(option, index)


class LibraryPanel(QSplitter):
    """Own the left Library surface beside the existing analysis workspace.

    Attributes:
        panel: Initially hidden Library list, filters and recording actions.
        toggle_button: Localized toolbar control with open/closed folder icons.
        recordings: Newest-first recording rows under day headers that cannot be selected.
        details: Read-only source/date/import details for the selected recording.
        empty_label: Empty-Library explanation.
        park_filter: Effective park selection, including all and unknown parks.
        workflow_filter: Manual workflow state selection, including all states.
        search: Combined ride/park name search.
        clear_filters: Action restoring all recordings.
        editor: Dialog for the selected recording's additions.
        context_menu: Recording actions opened by right-clicking a Library row.
        new_window_action: Action opening the recording in another explorer window.
        edit_action: Action opening the metadata dialog after the source loads.
        videos_action: Action opening the selected recording's separate video-link dialog.
        history_action: Action opening its export attempts and saved-settings review.
        remove_action: Action removing the recording after explicit confirmation.
        workflow_selector: Foreground status selection layer, or None while closed.
        open_requested: Signal carrying the selected archived source digest.
        new_window_requested: Signal requesting a separate window for the selected archive.
        changed: Committed removal notification carrying this panel as its origin.
    """

    open_requested = Signal(str)
    new_window_requested = Signal(str)
    changed = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        """Build the Library import surface and its adjustable horizontal container.

        Args:
            parent: Widget owning this component's lifetime.
        """
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(10)
        self.panel, layout = create_panel(tr("LIBRARY"))
        heading = self.panel.findChild(QLabel, "SectionTitle")
        assert heading is not None
        self._heading = heading
        self.park_filter = LibraryFilter()
        self.workflow_filter = LibraryFilter()
        for control, label in ((self.park_filter, "Park"), (self.workflow_filter, "Status")):
            control.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
            )
            control.setMinimumContentsLength(10)
            control.setMinimumWidth(0)
            bind(control, tr(label), "accessibleName")
            bind(control, tr(label), "toolTip")
            layout.addWidget(control)
        self.workflow_filter.addItem(tr("All statuses"), None)
        for status, (label, _) in WORKFLOW_ICONS.items():
            self.workflow_filter.addItem(tr(label), status)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setMinimumWidth(0)
        self.search.setClearButtonEnabled(True)
        bind(self.search, tr("Search ride or park…"), "placeholderText")
        bind(self.search, tr("Search ride or park…"), "accessibleName")
        search_row.addWidget(self.search, 1)
        self.clear_filters = QToolButton()
        self.clear_filters.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton),
        )
        bind(self.clear_filters, tr("Clear filters"), "toolTip")
        bind(self.clear_filters, tr("Clear filters"), "accessibleName")
        self.clear_filters.clicked.connect(self._clear_filters)
        search_row.addWidget(self.clear_filters)
        layout.addLayout(search_row)
        self.recordings = LibraryRecordingTree()
        self.recordings.setColumnCount(2)
        self.recordings.setHeaderHidden(True)
        self.recordings.setFrameShape(QFrame.Shape.NoFrame)
        self.recordings.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recordings.setRootIsDecorated(False)
        self.recordings.setIndentation(0)
        self.recordings.setItemsExpandable(False)
        self.recordings.setUniformRowHeights(False)
        self.recordings.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.recordings.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recordings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recordings.setMinimumWidth(0)
        header = self.recordings.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.recordings.setColumnWidth(1, 32)
        bind(self.recordings, tr("Archived recordings"), "accessibleName")
        self.recordings.currentItemChanged.connect(self._selected)
        self.recordings.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recordings.customContextMenuRequested.connect(self._show_context_menu)
        self.recordings.verticalScrollBar().valueChanged.connect(self._close_workflow)
        self.empty_label = bind(QLabel(), tr("No recordings in Library"))
        self.empty_label.setObjectName("Muted")
        self.recordings.setItemDelegateForColumn(
            0,
            LibraryRowDelegate(self.empty_label, self.recordings),
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumWidth(1)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.recordings, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumWidth(0)
        self.details.setMaximumHeight(200)
        bind(self.details, tr("Recording details"), "accessibleName")
        self.details.hide()
        layout.addWidget(self.details)
        self.context_menu = QMenu(self.recordings)
        self.new_window_action = bind(QAction(self.context_menu), tr("Open in new window…"))
        self.new_window_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton),
        )
        self.new_window_action.triggered.connect(self._open_in_new_window)
        self.context_menu.addAction(self.new_window_action)
        self.edit_action = bind(QAction(self.context_menu), tr("Edit metadata…"))
        self.editor = LibraryMetadataDialog(self.panel)
        self.edit_action.triggered.connect(self._edit_metadata)
        self.editor.save_requested.connect(self._save_metadata)
        self.editor.reset_requested.connect(lambda: self._save_metadata({}))
        self.videos_action = bind(QAction(self.context_menu), tr("Video links…"))
        self.videos_action.triggered.connect(self._edit_videos)
        self.history_action = bind(QAction(self.context_menu), tr("Export history…"))
        self.history_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        self.history_action.triggered.connect(self._show_history)
        for action in (self.edit_action, self.videos_action, self.history_action):
            self.context_menu.addAction(action)
        self.context_menu.addSeparator()
        self.remove_action = bind(QAction(self.context_menu), tr("Remove…"))
        self.remove_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.remove_action.triggered.connect(self._remove_recording)
        self.context_menu.addAction(self.remove_action)
        self.editor.hide()
        self.addWidget(self.panel)
        self.panel.hide()
        self.toggle_button = button_text(QPushButton(), tr("Library"))
        self.toggle_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirClosedIcon),
        )
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        self._entries: dict[str, LibraryEntry] = {}
        self._items: dict[str, QTreeWidgetItem] = {}
        self.workflow_selector: WorkflowSelector | None = None
        self._workflow_digest: str | None = None
        self._details_data: ExplorerData | None = None
        self._error: str | None = None
        self.refresh_labels()
        self.park_filter.currentIndexChanged.connect(self.refresh)
        self.workflow_filter.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)

    @property
    def selected_entry(self) -> LibraryEntry | None:
        """Return the selected recording's lightweight metadata.

        Returns:
            Selected entry, or None for an empty list/day header.
        """
        item = self.recordings.currentItem()
        digest = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        return self._entries.get(digest) if isinstance(digest, str) else None

    def refresh(self) -> None:
        """Reload lightweight list metadata without opening a recording or losing selection."""
        self._close_workflow()
        selected = self.selected_entry
        try:
            store = LibraryStore()
            park = self.park_filter.currentData()
            parks = store.parks()
            if [self.park_filter.itemData(index) for index in range(self.park_filter.count())] != [
                None,
                "",
                *parks,
            ]:
                blocked = self.park_filter.blockSignals(True)
                try:
                    self.park_filter.clear()
                    self.park_filter.addItem(tr("All parks"), None)
                    self.park_filter.addItem(tr("Unknown park"), "")
                    for name in parks:
                        self.park_filter.addItem(name, name)
                    index = self.park_filter.findData(park)
                    self.park_filter.setCurrentIndex(max(0, index))
                finally:
                    self.park_filter.blockSignals(blocked)
            park = self.park_filter.currentData()
            workflow = self.workflow_filter.currentData()
            entries = store.entries(
                park=park if isinstance(park, str) else None,
                search=self.search.text(),
                workflow_status=workflow if isinstance(workflow, str) else None,
            )
        except LibraryStoreError as error:
            record_error("Library list", error)
            self.show_error(tr("Could not read Library: {0}", str(error)))
            return
        self._entries = {entry.source_sha256: entry for entry in entries}
        blocked = self.recordings.blockSignals(True)
        try:
            self.recordings.clear()
            self._items.clear()
            group: QTreeWidgetItem | None = None
            day: str | None = None
            for entry in entries:
                if group is None or day != entry.recorded_day:
                    day = entry.recorded_day
                    group = QTreeWidgetItem([day if day is not None else tr("Unknown date")])
                    group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    group.setData(0, Qt.ItemDataRole.UserRole + 1, day)
                    self.recordings.addTopLevelItem(group)
                    group.setFirstColumnSpanned(True)
                    group.setExpanded(True)
                item = QTreeWidgetItem(group)
                item.setData(0, Qt.ItemDataRole.UserRole, entry.source_sha256)
                self._items[entry.source_sha256] = item
                icon = WorkflowIcon(entry.source_sha256, self.recordings)
                icon.clicked.connect(self._toggle_workflow)
                self.recordings.setItemWidget(item, 1, icon)
                icon.links_icon.clicked.connect(self._open_video_links)
                if selected is not None and selected.source_sha256 == entry.source_sha256:
                    self.recordings.setCurrentItem(item)
                elif (
                    selected is not None
                    and selected.source_uuid is not None
                    and selected.source_uuid == entry.source_uuid
                ):
                    self._details_data = None
                    self.recordings.setCurrentItem(item)
        finally:
            self.recordings.blockSignals(blocked)
        self.empty_label.setVisible(not entries)
        self.refresh_labels()

    @Slot(object)
    def refresh_after_change(self, origin: object) -> None:
        """Refresh another window's Library change without reloading the current chart.

        Args:
            origin: Panel that already refreshed after committing the change.
        """
        if origin is not self:
            self.refresh()

    def refresh_labels(self) -> None:
        """Refresh translated headings and details while keeping selection and chart state."""
        self._heading.ensurePolished()
        self.empty_label.ensurePolished()
        if self.park_filter.count():
            self.park_filter.setItemText(0, tr("All parks"))
            self.park_filter.setItemText(1, tr("Unknown park"))
        self.workflow_filter.setItemText(0, tr("All statuses"))
        for index, (label, _) in enumerate(WORKFLOW_ICONS.values(), 1):
            self.workflow_filter.setItemText(index, tr(label))
        filtered = (
            self.park_filter.currentIndex() > 0
            or self.workflow_filter.currentIndex() > 0
            or bool(self.search.text().strip())
        )
        self.clear_filters.setEnabled(filtered)
        self.empty_label.setText(
            tr("No matching recordings") if filtered else tr("No recordings in Library"),
        )
        for index in range(self.recordings.topLevelItemCount()):
            group = self.recordings.topLevelItem(index)
            assert group is not None
            group.setFont(0, self._heading.font())
            group.setForeground(0, self._heading.palette().color(QPalette.ColorRole.WindowText))
            if group.data(0, Qt.ItemDataRole.UserRole + 1) is None:
                group.setText(0, tr("Unknown date"))
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                assert item is not None
                entry = self._entries[item.data(0, Qt.ItemDataRole.UserRole)]
                text = library_row_text(entry)
                item.setText(0, text)
                item.setToolTip(0, text)
                label, _ = WORKFLOW_ICONS[entry.workflow_status]
                icon = self.recordings.itemWidget(item, 1)
                assert isinstance(icon, WorkflowIcon)
                icon.refresh_labels(entry.workflow_status)
                links_icon = icon.links_icon
                color_role = QPalette.ColorRole.PlaceholderText
                if entry.video_link_count:
                    color_role = (
                        QPalette.ColorRole.HighlightedText
                        if item.isSelected()
                        else QPalette.ColorRole.Highlight
                    )
                links_icon.button.setIcon(link_icon(self.recordings.palette().color(color_role)))
                links_icon.button.setToolTip(tr("Video links…"))
                links_icon.button.setAccessibleName(tr("Video links…"))
                item.setToolTip(1, tr(label))
                item.setData(1, Qt.ItemDataRole.AccessibleTextRole, tr(label))
        selected = self.selected_entry
        text = (
            library_details(selected, self._details_data, rich=True) if selected is not None else ""
        )
        if self._error is not None:
            text = f"{text}<div>{escape(self._error)}</div>"
        self.details.setHtml(text)
        self.details.setVisible(bool(text))
        editable = (
            selected is not None
            and self._details_data is not None
            and selected.source_sha256 == self._details_data.source.source_sha256
        )
        self.edit_action.setEnabled(editable and self.editor.isEnabled())
        color = self.context_menu.palette().color(QPalette.ColorRole.WindowText)
        self.edit_action.setIcon(
            metadata_icon(color),
        )
        self.videos_action.setIcon(
            link_icon(color),
        )
        self.videos_action.setEnabled(selected is not None)
        self.history_action.setEnabled(selected is not None)
        self.new_window_action.setEnabled(selected is not None)
        self.remove_action.setEnabled(selected is not None and self.recordings.isEnabled())
        self.editor.refresh_labels()
        if self.workflow_selector is not None and self._workflow_digest is not None:
            self.workflow_selector.refresh_labels(
                self._entries[self._workflow_digest].workflow_status,
            )

    def show_recording(self, data: ExplorerData) -> None:
        """Select and reveal the loaded Library recording and display its metadata.

        Args:
            data: Successfully loaded explorer data from the existing load lifecycle.
        """
        if data.source.source_sha256 not in self._entries:
            self.refresh()
        blocked = self.recordings.blockSignals(True)
        try:
            item = self._items.get(data.source.source_sha256)
            if item is not None:
                self.recordings.setCurrentItem(item)
            else:
                self.recordings.setCurrentIndex(QModelIndex())
        finally:
            self.recordings.blockSignals(blocked)
        self._details_data = data
        self.editor.bind_source(data.source)
        self._error = None
        self.refresh_labels()
        self._scroll_to_selection()

    def _scroll_to_selection(self) -> None:
        """Reveal the selected row after the details area and panel geometry settle."""
        item = self.recordings.currentItem()
        if item is not None:
            layout = self.panel.layout()
            if layout is not None:
                layout.activate()
            self.recordings.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)

    def show_error(self, message: str) -> None:
        """Explain a list/open failure inside the panel without changing the current chart.

        Args:
            message: Existing import/storage failure explanation.
        """
        self._error = message
        self.refresh_labels()

    @Slot(QTreeWidgetItem, QTreeWidgetItem)
    def _selected(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        self._close_workflow()
        self._details_data = None
        self._error = None
        self.refresh_labels()
        entry = self.selected_entry
        if entry is not None:
            self.open_requested.emit(entry.source_sha256)

    @Slot()
    def _clear_filters(self) -> None:
        blocked_park = self.park_filter.blockSignals(True)
        blocked_workflow = self.workflow_filter.blockSignals(True)
        blocked_search = self.search.blockSignals(True)
        self.park_filter.setCurrentIndex(0)
        self.workflow_filter.setCurrentIndex(0)
        self.search.clear()
        self.park_filter.blockSignals(blocked_park)
        self.workflow_filter.blockSignals(blocked_workflow)
        self.search.blockSignals(blocked_search)
        self.refresh()

    @Slot(QPoint)
    def _show_context_menu(self, position: QPoint) -> None:
        """Open recording actions for the clicked row, excluding headings and empty space.

        Args:
            position: Context-menu position in recording viewport coordinates.
        """
        item = self.recordings.itemAt(position)
        if item is None or not isinstance(item.data(0, Qt.ItemDataRole.UserRole), str):
            return
        self._close_workflow()
        self.recordings.setCurrentItem(item)
        self.context_menu.popup(self.recordings.viewport().mapToGlobal(position))

    @Slot()
    def _open_in_new_window(self) -> None:
        """Request another explorer window for the selected archived recording."""
        entry = self.selected_entry
        if entry is not None:
            self.new_window_requested.emit(entry.source_sha256)

    @Slot()
    def _remove_recording(self) -> None:
        """Confirm removal of the selected archive entry and refresh the Library list."""
        entry = self.selected_entry
        if entry is None:
            return
        confirmation = QMessageBox(
            QMessageBox.Icon.Question,
            tr("Remove recording?"),
            tr(
                'Remove "{0}" from the Library?\n\n'
                "The archived recording, metadata, markers, video links and export history "
                "will be permanently removed. Original files and exported videos remain unchanged.",
                entry.ride_name or entry.filename,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        for standard, icon in (
            (QMessageBox.StandardButton.Yes, QStyle.StandardPixmap.SP_DialogYesButton),
            (QMessageBox.StandardButton.No, QStyle.StandardPixmap.SP_DialogNoButton),
        ):
            confirmation.button(standard).setIcon(confirmation.style().standardIcon(icon))
        confirmation.setDefaultButton(QMessageBox.StandardButton.No)
        answer = confirmation.exec()
        confirmation.deleteLater()
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            LibraryStore().remove_recording(entry.source_sha256)
        except LibraryStoreError as error:
            self.show_error(tr("Could not remove recording: {0}", tr(str(error))))
            return
        self._error = None
        self.refresh()
        self.changed.emit(self)

    @Slot()
    def _show_history(self) -> None:
        entry = self.selected_entry
        if entry is not None:
            dialog = LibraryExportsDialog(entry.source_sha256, self.panel)
            dialog.finished.connect(self.refresh)
            dialog.open()

    @Slot()
    def _edit_videos(self) -> None:
        entry = self.selected_entry
        if entry is not None:
            self._open_video_links(entry.source_sha256)

    @Slot(str)
    def _open_video_links(self, source_sha256: str) -> None:
        """Open this recording's links without selecting or loading its source.

        Args:
            source_sha256: Recording addressed by the context action or link icon.
        """
        dialog = LibraryVideosDialog(source_sha256, self.panel)
        dialog.changed.connect(self._video_links_changed)
        dialog.open()

    @Slot()
    def _video_links_changed(self) -> None:
        """Refresh saved-link indicators here and in other open Library panels."""
        self.refresh()
        self.changed.emit(self)

    @Slot(str)
    def _toggle_workflow(self, source_sha256: str) -> None:
        same = self._workflow_digest == source_sha256
        self._close_workflow()
        if same:
            return
        item = self._items[source_sha256]
        icon = self.recordings.itemWidget(item, 1)
        assert isinstance(icon, WorkflowIcon)
        status = self._entries[source_sha256].workflow_status
        selector = WorkflowSelector(icon.button, self.window())
        selector.refresh_labels(status)
        selector.chosen.connect(self._save_workflow)
        selector.dismissed.connect(self._close_workflow)
        selector.show()
        selector.adjustSize()
        layout = selector.layout()
        assert layout is not None
        layout.activate()
        center = icon.button.mapTo(self.window(), icon.button.rect().center())
        checked_center = selector.buttons[status].geometry().center()
        bounds = self.window().rect()
        selector.move(
            max(0, min(center.x() - checked_center.x(), bounds.width() - selector.width())),
            max(0, min(center.y() - checked_center.y(), bounds.height() - selector.height())),
        )
        self._workflow_digest = source_sha256
        self.workflow_selector = selector
        selector.raise_()

    @Slot()
    def _close_workflow(self) -> None:
        selector = self.workflow_selector
        self.workflow_selector = None
        self._workflow_digest = None
        if selector is not None:
            selector.hide()
            application = QApplication.instance()
            assert isinstance(application, QApplication)
            application.removeEventFilter(selector)
            selector.deleteLater()

    @Slot(str)
    def _save_workflow(self, status: str) -> None:
        digest = self._workflow_digest
        if digest is None:
            return
        try:
            LibraryStore().set_workflow_status(digest, status)
        except (ValueError, LibraryStoreError) as error:
            self.show_error(tr("Could not save workflow status: {0}", str(error)))
            return
        self._entries[digest] = replace(self._entries[digest], workflow_status=status)
        self._error = None
        self._close_workflow()
        if self.workflow_filter.currentData() not in (None, status):
            self.refresh()
        else:
            self.refresh_labels()
        self.changed.emit(self)

    @Slot(object)
    def _save_metadata(self, values: dict[str, object]) -> None:
        entry = self.selected_entry
        if entry is None:
            return
        try:
            LibraryStore().update_metadata(entry.source_sha256, values)
        except (ValueError, LibraryStoreError) as error:
            self.editor.show_error(tr("Could not save Library metadata: {0}", str(error)))
            return
        self._error = None
        self.editor.accept()
        self.refresh()
        self.open_requested.emit(entry.source_sha256)

    @Slot()
    def _edit_metadata(self) -> None:
        if self._details_data is not None:
            self.editor.bind_source(self._details_data.source)
            self.editor.show()
            self.editor.raise_()
            self.editor.activateWindow()

    @Slot(bool)
    def _toggle(self, checked: bool) -> None:
        """Show or hide the content and match the folder icon to its visible state."""
        self.panel.setVisible(checked)
        if not checked:
            self._close_workflow()
        if checked:
            self.refresh()
            self._scroll_to_selection()
        self.toggle_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon
                if checked
                else QStyle.StandardPixmap.SP_DirClosedIcon,
            ),
        )
        self.updateGeometry()
