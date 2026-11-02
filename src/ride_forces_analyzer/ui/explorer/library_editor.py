"""Library metadata dialog; validation and persistence stay in services.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.importers import ImportSuccess
from ride_forces_analyzer.domain import SourceNumber
from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.ui.presentation.translation import bind


class LibraryMetadataDialog(QDialog):
    """Present optional additions alongside inherited source-value placeholders.

    Attributes:
        fields: Optional ride, park, row, seat and train text overrides.
        position: Imported posture or explicit Seated/Flying override.
        notes: Current user notes.
        error: Visible storage/validation failure while keeping unsaved input.
        buttons: Standard Save, Reset and Cancel actions matching other app dialogs.
        save_requested: Signal carrying the current editable values.
        reset_requested: Signal requesting removal of all additions.
    """

    save_requested = Signal(object)
    reset_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build the form without reading or writing a recording.

        Args:
            parent: Library panel owning these controls.
        """
        super().__init__(parent)
        bind(self, tr("Edit metadata…"), "windowTitle")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(540, 440)
        layout = QVBoxLayout(self)
        details = bind(QGroupBox(), tr("Recording details"), "title")
        form = QFormLayout(details)
        self.fields: dict[str, QLineEdit] = {}
        for key, label in (
            ("ride_name", "Ride"),
            ("park_name", "Park"),
            ("row", "Row"),
            ("seat", "Seat"),
            ("train", "Train"),
        ):
            field = QLineEdit()
            field.setMinimumWidth(0)
            bind(field, tr(label), "accessibleName")
            form.addRow(bind(QLabel(), tr(label)), field)
            self.fields[key] = field
        self.position = QComboBox()
        bind(self.position, tr("Riding position"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Riding position")), self.position)
        layout.addWidget(details)
        notes_group = bind(QGroupBox(), tr("Notes"), "title")
        notes_layout = QVBoxLayout(notes_group)
        self.notes = QPlainTextEdit()
        self.notes.setMinimumHeight(100)
        bind(self.notes, tr("Notes"), "accessibleName")
        notes_layout.addWidget(self.notes)
        layout.addWidget(notes_group, 1)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Reset
            | QDialogButtonBox.StandardButton.Cancel,
        )
        bind(self.buttons.button(QDialogButtonBox.StandardButton.Save), tr("&Save"))
        bind(self.buttons.button(QDialogButtonBox.StandardButton.Cancel), tr("Cancel"))
        bind(
            self.buttons.button(QDialogButtonBox.StandardButton.Reset),
            tr("Reset to source values"),
        )
        for standard, label, icon in (
            (
                QDialogButtonBox.StandardButton.Save,
                "Save additions",
                QStyle.StandardPixmap.SP_DialogSaveButton,
            ),
            (
                QDialogButtonBox.StandardButton.Reset,
                "Reset to source values",
                QStyle.StandardPixmap.SP_DialogResetButton,
            ),
            (
                QDialogButtonBox.StandardButton.Cancel,
                "Cancel",
                QStyle.StandardPixmap.SP_DialogCancelButton,
            ),
        ):
            button = self.buttons.button(standard)
            button.setIcon(self.style().standardIcon(icon))
            bind(button, tr(label), "toolTip")
            bind(button, tr(label), "accessibleName")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset)
        layout.addWidget(self.buttons)
        self._source: ImportSuccess | None = None

    def bind_source(self, source: ImportSuccess) -> None:
        """Display stored additions and placeholders without editing the source.

        Args:
            source: Loaded recording owning immutable original values and additions.
        """
        self._source = source
        self.error.hide()
        original: dict[str, str | None] = {
            "ride_name": source.recording.metadata.name,
            "park_name": source.recording.metadata.location,
        }
        for attribute in source.recording.attributes:
            if attribute.label.casefold() in {"row", "seat", "train"}:
                value = attribute.value
                original[attribute.label.casefold()] = (
                    value.token
                    if isinstance(value, SourceNumber)
                    else value
                    if isinstance(value, str)
                    else None
                )
        values = source.additions.model_dump()
        for key, field in self.fields.items():
            field.setText(values[key] or "")
            field.setPlaceholderText(original.get(key) or "—")
        self.notes.setPlainText(source.additions.notes)
        self.position.clear()
        self.refresh_labels()

    def refresh_labels(self) -> None:
        """Translate posture choices while retaining the current unsaved selection."""
        posture = self.position.currentData()
        if not self.position.count() and self._source is not None:
            posture = self._source.additions.riding_position
        original = self._source.recording.metadata.riding_position if self._source else None
        blocked = self.position.blockSignals(True)
        self.position.clear()
        self.position.addItem(
            tr("Use imported value: {0}", original.value if original else "—"),
            None,
        )
        self.position.addItem(tr("Seated"), "Seated")
        self.position.addItem(tr("Flying"), "Flying")
        self.position.setCurrentIndex(max(0, self.position.findData(posture)))
        self.position.blockSignals(blocked)

    def _save(self) -> None:
        values: dict[str, object] = {
            key: field.text() or None for key, field in self.fields.items()
        }
        values["riding_position"] = self.position.currentData()
        values["notes"] = self.notes.toPlainText()
        self.save_requested.emit(values)

    def _reset(self) -> None:
        self.reset_requested.emit()

    def show_error(self, message: str) -> None:
        """Keep unsaved input visible alongside a service failure explanation.

        Args:
            message: Localized explanation supplied by the persistence boundary.
        """
        self.error.setText(message)
        self.error.show()
