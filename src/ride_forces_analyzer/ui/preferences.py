"""Application preferences and export defaults, independent of per-export settings.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import Language, tr
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES, ExportSettings
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.storage.map_tiles import TileCache
from .translation import bind, items


class SettingsDialog(QDialog):
    language_selected = Signal(int)
    appearance_selected = Signal(int)

    def __init__(self, preferences: Preferences, parent: QWidget, *, language: Language) -> None:
        super().__init__(parent)
        self.preferences = preferences
        self.setObjectName("settingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        bind(self, tr("Settings"), "windowTitle")
        self.resize(540, 320)
        layout = QVBoxLayout(self)
        application = bind(QGroupBox(), tr("Application"), "title")
        application_form = QFormLayout(application)
        self.language = QComboBox()
        bind(self.language, tr("Language"), "accessibleName")
        items(self.language, ["English", "Deutsch"])
        self.language.setCurrentIndex(1 if language == "de" else 0)
        application_form.addRow(bind(QLabel(), tr("Language")), self.language)
        self.appearance = QComboBox()
        bind(self.appearance, tr("Appearance"), "accessibleName")
        items(self.appearance, [tr("Dark"), tr("Light"), tr("System")])
        self.appearance.setCurrentIndex(
            {"dark": 0, "light": 1, "system": 2}[preferences.appearance()],
        )
        bind(
            self.appearance,
            tr("Application appearance · does not change exported videos"),
            "toolTip",
        )
        application_form.addRow(bind(QLabel(), tr("Appearance")), self.appearance)
        self.restore_last_file = bind(QCheckBox(), tr("Restore last file"))
        self.restore_last_file.setChecked(preferences.restore_last_file())
        application_form.addRow(self.restore_last_file)
        self.clear_map_cache = bind(QPushButton(), tr("Clear map cache"))
        self.clear_map_cache.clicked.connect(self.clear_cached_maps)
        application_form.addRow(self.clear_map_cache)
        self.map_cache_status = QLabel()
        self.map_cache_status.setWordWrap(True)
        application_form.addRow(self.map_cache_status)
        layout.addWidget(application)
        group = bind(QGroupBox(), tr("Export"), "title")
        form = QFormLayout(group)
        self.frame_rate = QComboBox()
        items(self.frame_rate, [ExportSettings(fps=rate).fps_label for rate in EXPORT_FRAME_RATES])
        self.frame_rate.setCurrentIndex(EXPORT_FRAME_RATES.index(preferences.export_fps()))
        form.addRow(bind(QLabel(), tr("Default video frame rate")), self.frame_rate)
        explanation = bind(
            QLabel(),
            tr("Applies to new exports. Saved presets and batches keep their own frame rates."),
        )
        explanation.setWordWrap(True)
        form.addRow(explanation)
        layout.addWidget(group)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @Slot()
    def clear_cached_maps(self) -> None:
        if TileCache().clear():
            bind(self.map_cache_status, tr("Map cache cleared."))
        else:
            bind(self.map_cache_status, tr("Could not clear map cache. Try again later."))

    @Slot()
    def save(self) -> None:
        self.preferences.remember_restore_last_file(self.restore_last_file.isChecked())
        self.preferences.remember_export_fps(EXPORT_FRAME_RATES[self.frame_rate.currentIndex()])
        self.language_selected.emit(self.language.currentIndex())
        self.appearance_selected.emit(self.appearance.currentIndex())
        self.accept()
