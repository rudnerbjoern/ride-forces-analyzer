"""Saved export presets and the assistant connection to persistent batches.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.runtime.error_reporting import record_error
from ride_forces_analyzer.ui.presentation.translation import bind, items

# cspell:words pixmap Deutsch


from PySide6.QtCore import (
    Qt,
    Slot,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from ride_forces_analyzer.exports.batches import make_job
from ride_forces_analyzer.storage.export_models import SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import (
    ExportStore,
    ExportStoreError,
)


from PySide6.QtCore import Signal
from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from .form import ExportForm


class ExportPresets(QWidget):
    """Own preset selection, persistence and the assistant's batch dialog.

    Attributes:
        selected: Signal delivering the preset requested for application.
        message: Signal delivering translated operation feedback.
        store: Existing persistent export-definition repository.
        form: Current export inputs captured for saves and queued jobs.
        analysis: Current bound analysis snapshot, updated by the dialog.
        first: Selection start captured when the assistant opened.
        last: Selection end captured when the assistant opened.
        saved: Saved presets currently offered by the selector.
        batch_window: Open batch editor, when present.
        preset_selector: Choice of stored preset names.
        save_preset: Button saving a new named preset.
        update_preset: Button updating the selected saved preset.
        delete_preset: Button deleting the selected saved preset.
        queue: Button adding the current source and recipe to a batch.
        manage_batches: Button opening the batch editor.
        controls: Preset and batch controls disabled during video export.
        _dialog: Parent dialog owning prompts and the auxiliary batch window.
    """

    selected = Signal(object)
    message = Signal(object)

    def __init__(
        self,
        store: ExportStore,
        form: ExportForm,
        analysis: RecordingAnalysis,
        first: int,
        last: int,
        parent: QWidget,
    ) -> None:
        """Create preset controls bound to one assistant and source selection.

        Args:
            store: Existing export-definition storage.
            form: Form supplying current input choices.
            analysis: Prepared source snapshot used by captures.
            first: Inclusive selection start captured on opening.
            last: Inclusive selection end captured on opening.
            parent: Dialog owning this component and auxiliary batch window.

        Returns:
            None.
        """
        super().__init__(parent)
        self.store, self.form, self.analysis = store, form, analysis
        self._dialog = parent
        self.first, self.last = first, last
        self.saved: tuple[SavedPreset, ...] = ()
        self.batch_window: QDialog | None = None
        presets_layout = QVBoxLayout(self)
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_row = QHBoxLayout()
        presets_row.setContentsMargins(0, 0, 0, 0)
        presets_row.addWidget(bind(QLabel(), tr("Saved preset")))
        self.preset_selector = QComboBox()
        self.preset_selector.activated.connect(self._load_preset)
        presets_row.addWidget(self.preset_selector, 1)
        divider = QFrame()
        divider.setObjectName("presetActionsDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        presets_row.addWidget(divider)
        self.save_preset = QPushButton()
        save_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        save_pixmap = QPixmap(40, 40)
        save_pixmap.setDevicePixelRatio(2)
        save_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(save_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        save_icon.paint(painter, 0, 0, 20, 20)
        for color, width in ((QColor("#203020"), 5), (QColor("#70d43b"), 3)):
            painter.setPen(QPen(color, width))
            painter.drawLine(12, 15, 17, 15)
            painter.drawLine(15, 12, 15, 17)
        painter.end()
        self.save_preset.setIcon(QIcon(save_pixmap))
        bind(self.save_preset, tr("Save as…"), "toolTip")
        bind(self.save_preset, tr("Save as…"), "accessibleName")
        self.save_preset.clicked.connect(self._save_preset)
        self.update_preset = QPushButton()
        self.update_preset.setIcon(save_icon)
        bind(self.update_preset, tr("Update selected"), "toolTip")
        bind(self.update_preset, tr("Update selected"), "accessibleName")
        self.update_preset.clicked.connect(self._update_preset)
        self.delete_preset = QPushButton()
        self.delete_preset.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton),
        )
        bind(self.delete_preset, tr("Delete preset"), "toolTip")
        bind(self.delete_preset, tr("Delete preset"), "accessibleName")
        self.delete_preset.clicked.connect(self._delete_preset)
        self.queue = QPushButton()
        self.queue.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder),
        )
        bind(self.queue, tr("Add this export to batch…"), "toolTip")
        bind(self.queue, tr("Add this export to batch…"), "accessibleName")
        self.queue.clicked.connect(self._queue)
        self.manage_batches = QPushButton()
        self.manage_batches.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        )
        bind(self.manage_batches, tr("Saved batches…"), "toolTip")
        bind(self.manage_batches, tr("Saved batches…"), "accessibleName")
        self.manage_batches.clicked.connect(self._manage_batches)
        presets_row.addWidget(self.save_preset)
        presets_row.addWidget(self.update_preset)
        presets_row.addWidget(self.delete_preset)
        batch_divider = QFrame()
        batch_divider.setObjectName("presetBatchDivider")
        batch_divider.setFrameShape(QFrame.Shape.VLine)
        batch_divider.setFrameShadow(QFrame.Shadow.Sunken)
        presets_row.addWidget(batch_divider)
        presets_row.addWidget(self.queue)
        presets_row.addWidget(self.manage_batches)
        presets_layout.addLayout(presets_row)
        self.controls = (
            self.preset_selector,
            self.delete_preset,
            self.save_preset,
            self.update_preset,
            self.queue,
            self.manage_batches,
        )

    def set_analysis(self, analysis: RecordingAnalysis) -> None:
        """Retain the dialog's latest prepared snapshot for subsequent captures.

        Args:
            analysis: Snapshot used by the current export configuration.

        Returns:
            None without changing saved recipes or existing batch snapshots.
        """
        self.analysis = analysis

    def refresh(self, select: str | None = None) -> None:
        """Reload saved names and optionally select one by its retained spelling.

        Args:
            select: Name to select after refreshing, or None for the placeholder.

        Returns:
            None; report storage failures through the message signal.
        """
        try:
            self.saved = self.store.presets()
            self.preset_selector.clear()
            items(self.preset_selector, [tr("Choose a saved preset…")])
            items(self.preset_selector, [preset.name for preset in self.saved])
            if select is not None:
                self.preset_selector.setCurrentText(select)
        except ExportStoreError as error:
            record_error("Export configuration", error)
            self.message.emit(tr(str(error)))

    def _preset(self, name: str) -> SavedPreset:
        mode = ("markers", "selection", "entire")[self.form.interval.currentIndex()]
        return make_preset(
            name,
            self.form.settings(),
            self.form.smoothing.currentIndex() * 2 + 1,
            "selection" if mode == "selection" else "entire" if mode == "entire" else "markers",
            self.analysis.configuration,
        )

    @Slot()
    def _save_preset(self) -> None:
        name, accepted = QInputDialog.getText(
            self._dialog,
            tr("Save export preset"),
            tr("Preset name"),
        )
        if not accepted:
            return
        try:
            preset = self._preset(name)
            self.store.save_preset(preset)
            self.refresh(preset.name)
            self.message.emit(tr("Saved preset: {0}", preset.name))
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            self.message.emit(tr(str(error)))

    @Slot()
    def _update_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            self.message.emit(tr("Choose a saved preset to update"))
            return
        try:
            preset = self._preset(self.saved[index].name)
            self.store.save_preset(preset, overwrite=True)
            self.refresh(preset.name)
            self.message.emit(tr("Preset updated. Existing saved batch snapshots are unchanged."))
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            self.message.emit(tr(str(error)))

    @Slot()
    def _delete_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            self.message.emit(tr("Choose a saved preset first"))
            return
        name = self.saved[index].name
        try:
            self.store.delete_preset(name)
            self.refresh()
            self.message.emit(tr("Preset deleted: {0}", name))
        except ExportStoreError as error:
            record_error("Export configuration", error)
            self.message.emit(tr(str(error)))

    @Slot()
    def _queue(self) -> None:
        try:
            names = tuple(batch.name for batch in self.store.batches())
            name, accepted = QInputDialog.getItem(
                self._dialog,
                tr("Add to saved batch"),
                tr("Choose an existing batch or enter a new name"),
                names,
                0,
                True,
            )
            if not accepted:
                return
            preset_name = (
                self.preset_selector.currentText()
                if self.preset_selector.currentIndex() > 0
                else self.form.layout_profile.currentText()
            )
            first, last = self.form.bounds(self.analysis, (self.first, self.last))
            job = make_job(self.analysis, self._preset(preset_name), first=first, last=last)
            if name.strip() not in names:
                name = self.store.create_batch(name).name
            self.store.append_jobs(name, (job,))
            self.message.emit(
                tr("Saved this recording/preset in batch: {0}. No video was rendered.", name),
            )
        except (ValueError, ExportStoreError) as error:
            record_error("Export configuration", error)
            self.message.emit(tr(str(error)))

    @Slot()
    def _manage_batches(self) -> None:
        from ride_forces_analyzer.ui.exports.batches import BatchDialog

        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.raise_()
            return
        self.batch_window = BatchDialog(self.store, self._dialog)
        self.batch_window.show()

    def close_batches(self) -> bool:
        """Close the batch editor through its existing cancellation lifecycle.

        Returns:
            True when the editor is closed or absent; False while it must remain open.
        """
        if self.batch_window is not None and self.batch_window.isVisible():
            self.batch_window.close()
            return not self.batch_window.isVisible()
        return True

    @Slot()
    def _load_preset(self) -> None:
        index = self.preset_selector.currentIndex() - 1
        if not 0 <= index < len(self.saved):
            self.message.emit(tr("Choose a saved preset first"))
            return
        self.selected.emit(self.saved[index])
