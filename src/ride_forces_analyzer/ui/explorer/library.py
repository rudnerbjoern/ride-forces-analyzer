"""Collapsible Library surface, toolbar toggle and explicit archive-import transport.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words Demi

from pathlib import Path
from dataclasses import replace
from html import escape

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSizePolicy,
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
    ArchiveImportResult,
    LibraryArchive,
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


class ParkFilter(QComboBox):
    """Open the Library park popup without the transient Qt scroll-animation window."""

    def showPopup(self) -> None:
        """Show this popup immediately, restoring the shared animation preference afterward."""
        effect = Qt.UIEffect.UI_AnimateCombo
        enabled = QApplication.isEffectEnabled(effect)
        QApplication.setEffectEnabled(effect, False)
        try:
            super().showPopup()
        finally:
            QApplication.setEffectEnabled(effect, enabled)


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
        panel: Initially hidden Library content and explicit archive-import controls.
        toggle_button: Localized toolbar control with open/closed folder icons.
        import_button: Explicit multi-file archive import action.
        import_results: Read-only per-file outcomes from the latest import.
        recordings: Newest-first recording rows under day headers that cannot be selected.
        details: Read-only source/date/import details for the selected recording.
        empty_label: Empty-Library explanation.
        park_filter: Effective park selection, including all and unknown parks.
        search: Combined ride/park name search.
        clear_filters: Action restoring all recordings.
        editor: Dialog for the selected recording's additions.
        edit_button: Action opening the metadata dialog.
        videos_button: Icon opening the selected recording's separate video-link dialog.
        history_button: Action opening its export attempts and saved-settings review.
        workflow_selector: Foreground status selection layer, or None while closed.
        open_requested: Signal carrying the selected archived source digest.
    """

    open_requested = Signal(str)

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
        self.import_button = button_text(QPushButton(), tr("Import recordings…"))
        self.import_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
        )
        self.import_button.clicked.connect(self._choose_import)
        layout.addWidget(self.import_button)
        self.import_results = QPlainTextEdit()
        self.import_results.setReadOnly(True)
        self.import_results.setMinimumWidth(0)
        self.import_results.setMaximumHeight(160)
        bind(self.import_results, tr("Library import results"), "accessibleName")
        self.import_results.hide()
        layout.addWidget(self.import_results)
        self.park_filter = ParkFilter()
        self.park_filter.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.park_filter.setMinimumContentsLength(10)
        self.park_filter.setMinimumWidth(0)
        bind(self.park_filter, tr("Park"), "accessibleName")
        bind(self.park_filter, tr("Park"), "toolTip")
        layout.addWidget(self.park_filter)
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
        self.recordings = QTreeWidget()
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
        self.edit_button = button_text(
            QPushButton(),
            tr("Edit metadata…"),
            caption=tr("Metadata…"),
        )
        self.editor = LibraryMetadataDialog(self.panel)
        self.edit_button.clicked.connect(self._edit_metadata)
        self.editor.save_requested.connect(self._save_metadata)
        self.editor.reset_requested.connect(lambda: self._save_metadata({}))
        entry_actions = QHBoxLayout()
        entry_actions.addWidget(self.edit_button, 1)
        self.videos_button = button_text(QPushButton(), tr("Video links…"))
        bind(self.videos_button, tr("Video links…"), "toolTip")
        bind(self.videos_button, tr("Video links…"), "accessibleName")
        self.videos_button.clicked.connect(self._edit_videos)
        self.videos_button.hide()
        entry_actions.addWidget(self.videos_button, 1)
        for button in (self.edit_button, self.videos_button):
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(0)
        layout.addLayout(entry_actions)
        self.history_button = button_text(QPushButton(), tr("Export history…"))
        self.history_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        self.history_button.clicked.connect(self._show_history)
        self.history_button.hide()
        layout.addWidget(self.history_button)
        self.editor.hide()
        self.edit_button.hide()
        self.addWidget(self.panel)
        self.panel.hide()
        self.toggle_button = button_text(QPushButton(), tr("Library"))
        self.toggle_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirClosedIcon),
        )
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self._toggle)
        self._import_worker: ArchiveImportWorker | None = None
        self._entries: dict[str, LibraryEntry] = {}
        self._items: dict[str, QTreeWidgetItem] = {}
        self.workflow_selector: WorkflowSelector | None = None
        self._workflow_digest: str | None = None
        self._details_data: ExplorerData | None = None
        self._error: str | None = None
        self.refresh_labels()
        self.park_filter.currentIndexChanged.connect(self.refresh)
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
            entries = store.entries(
                park=park if isinstance(park, str) else None,
                search=self.search.text(),
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

    def refresh_labels(self) -> None:
        """Refresh translated headings and details while keeping selection and chart state."""
        self._heading.ensurePolished()
        self.empty_label.ensurePolished()
        if self.park_filter.count():
            self.park_filter.setItemText(0, tr("All parks"))
            self.park_filter.setItemText(1, tr("Unknown park"))
        filtered = self.park_filter.currentIndex() > 0 or bool(self.search.text().strip())
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
        self.edit_button.setVisible(editable)
        self.edit_button.setIcon(
            metadata_icon(self.edit_button.palette().color(QPalette.ColorRole.ButtonText)),
        )
        self.videos_button.setIcon(
            link_icon(self.videos_button.palette().color(QPalette.ColorRole.ButtonText)),
        )
        self.videos_button.setVisible(selected is not None)
        self.history_button.setVisible(selected is not None)
        self.editor.refresh_labels()
        if self.workflow_selector is not None and self._workflow_digest is not None:
            self.workflow_selector.refresh_labels(
                self._entries[self._workflow_digest].workflow_status,
            )

    def show_recording(self, data: ExplorerData) -> None:
        """Display original metadata only when the loaded source matches the selection.

        Args:
            data: Successfully loaded explorer data from the existing load lifecycle.
        """
        entry = self.selected_entry
        if entry is not None and entry.source_sha256 == data.source.source_sha256:
            self._details_data = data
            self.editor.bind_source(data.source)
            self._error = None
            self.refresh_labels()

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
        blocked_search = self.search.blockSignals(True)
        self.park_filter.setCurrentIndex(0)
        self.search.clear()
        self.park_filter.blockSignals(blocked_park)
        self.search.blockSignals(blocked_search)
        self.refresh()

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
            dialog = LibraryVideosDialog(entry.source_sha256, self.panel)
            dialog.open()

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
        self.refresh_labels()

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

    @Slot()
    def _choose_import(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Import recordings into Library"),
            "",
            tr("Ride Forces (*.forces *.zforces);;All files (*)"),
        )
        if not filenames:
            return
        self.import_button.setEnabled(False)
        worker = ArchiveImportWorker(tuple(Path(filename) for filename in filenames))
        worker.signals.completed.connect(self._import_finished)
        worker.signals.failed.connect(self._import_failed)
        self._import_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _import_finished(self, results: tuple[ArchiveImportResult, ...]) -> None:
        lines: list[str] = []
        for result in results:
            message = (
                tr("Imported")
                if result.status == "imported"
                else tr("Updated in Library")
                if result.status == "updated"
                else tr("Already in Library")
                if result.status == "duplicate"
                else tr("Import failed: {0}", result.error or "")
            )
            lines.append(f"{result.path.name}: {message}")
        self.import_results.setPlainText("\n".join(lines))
        self.import_results.show()
        self.import_button.setEnabled(True)
        self._import_worker = None
        self.refresh()
        selected = self.selected_entry
        if selected is not None and any(
            result.status == "updated" and result.source_sha256 == selected.source_sha256
            for result in results
        ):
            self.open_requested.emit(selected.source_sha256)

    @Slot(str)
    def _import_failed(self, message: str) -> None:
        self.import_results.setPlainText(tr("Import failed: {0}", message))
        self.import_results.show()
        self.import_button.setEnabled(True)
        self._import_worker = None

    @Slot(bool)
    def _toggle(self, checked: bool) -> None:
        """Show or hide the content and match the folder icon to its visible state."""
        self.panel.setVisible(checked)
        if not checked:
            self._close_workflow()
        if checked:
            self.refresh()
        self.toggle_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirOpenIcon
                if checked
                else QStyle.StandardPixmap.SP_DirClosedIcon,
            ),
        )
        self.updateGeometry()


class ArchiveImportSignals(QObject):
    """Transport background archive outcomes without accessing widgets.

    Attributes:
        completed: Ordered per-file import results.
        failed: Explanation of an unexpected worker failure.
    """

    completed = Signal(object)
    failed = Signal(str)


class ArchiveImportWorker(QRunnable):
    """Run explicit archive imports off the GUI thread.

    Attributes:
        paths: Selected local recording paths.
        signals: Completion/error transport to the Library component.
    """

    def __init__(self, paths: tuple[Path, ...]) -> None:
        """Retain selected paths for processing by the archive service.

        Args:
            paths: Supported recordings selected through the file dialog.
        """
        super().__init__()
        self.paths = paths
        self.signals = ArchiveImportSignals()

    @Slot()
    def run(self) -> None:
        """Import files independently and report results through queued Qt signals."""
        try:
            results = LibraryArchive().import_paths(self.paths)
        except Exception as error:
            record_error("Library import worker", error)
            self.signals.failed.emit(str(error))
        else:
            self.signals.completed.emit(results)
