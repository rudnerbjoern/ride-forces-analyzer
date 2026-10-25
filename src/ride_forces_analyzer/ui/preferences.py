"""Application preferences and export defaults, independent of per-export settings.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, LANGUAGES, Language, tr
from ride_forces_analyzer.cpu_resources import render_job_limit
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES, ExportSettings
from ride_forces_analyzer.storage.preferences import Appearance, Preferences
from ride_forces_analyzer.storage.map_tiles import TileCache
from .translation import bind, items

APPEARANCE_CHOICES = tuple(Appearance)


class SettingsDialog(QDialog):
    """Settings dialog contract and owned data.

    Attributes:
        language_selected: Qt signal for language selected notifications.
        appearance_selected: Qt signal for appearance selected notifications.
        appearance_previewed: Qt signal for appearance previewed notifications.
        preferences: Local application preference access for this window or controller.
        language: Choice control for language.
        appearance: Choice control for appearance.
        restore_last_file: Checkbox controlling restore last file.
        clear_map_cache: Button for clear map cache.
        frame_rate: Choice control for frame rate.
        render_jobs: Requested concurrent frame-renderer count, bounded by local CPU
            availability.
        buttons: Dialog action buttons.
    """

    language_selected = Signal(int)
    appearance_selected = Signal(int)
    appearance_previewed = Signal(int)

    def __init__(self, preferences: Preferences, parent: QWidget, *, language: Language) -> None:
        """Initialize settings dialog and its owned state.

        Args:
            preferences: Local application preference access.
            parent: Qt parent that owns this object's lifetime.
            language: Registered language used to translate presentation text and numbers.

        Returns:
            None.
        """
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
        items(self.language, [definition.name for definition in LANGUAGES.values()])
        self.language.setCurrentIndex(LANGUAGE_CHOICES.index(language))
        application_form.addRow(bind(QLabel(), tr("Language")), self.language)
        self.appearance = QComboBox()
        bind(self.appearance, tr("Appearance"), "accessibleName")
        self._populate_appearances()
        self.appearance.currentIndexChanged.connect(self.preview_appearance)
        bind(
            self.appearance,
            tr("Application appearance · does not change exported videos"),
            "toolTip",
        )
        application_form.addRow(bind(QLabel(), tr("Appearance")), self.appearance)
        self.restore_last_file = bind(QCheckBox(), tr("Restore last file"))
        self.restore_last_file.setChecked(preferences.restore_last_file())
        application_form.addRow(self.restore_last_file)
        self.clear_map_cache = QPushButton()
        self._update_map_cache_count()
        self.clear_map_cache.clicked.connect(self.clear_cached_maps)
        application_form.addRow(self.clear_map_cache)
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
        self.render_jobs = QSpinBox()
        self.render_jobs.setRange(1, render_job_limit())
        self.render_jobs.setValue(preferences.render_jobs())
        bind(self.render_jobs, tr("Parallel render jobs"), "accessibleName")
        bind(
            self.render_jobs,
            tr(
                "Applies to exports and batches on this computer. More jobs use more CPU and memory.",
            ),
            "toolTip",
        )
        form.addRow(bind(QLabel(), tr("Parallel render jobs")), self.render_jobs)
        layout.addWidget(group)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def changeEvent(self, event: QEvent) -> None:
        """Refresh translated or themed controls after a Qt change event.

        Args:
            event: Qt event delivered to this handler.

        Returns:
            None.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "appearance"):
            self._populate_appearances()

    def _populate_appearances(self) -> None:
        selected = (
            Appearance(self.appearance.currentData())
            if self.appearance.count()
            else self.preferences.appearance()
        )
        labels = {
            Appearance.SYSTEM: tr("System"),
            Appearance.LIGHT: tr("Light"),
            Appearance.DARK: tr("Dark"),
            Appearance.VERBOLTEN: tr("Verbolten"),
            Appearance.MANTA: tr("Manta"),
            Appearance.FALCONS_FLIGHT: tr("Falcons Flight"),
            Appearance.TARON: tr("Taron"),
            Appearance.RED_FORCE: tr("Red Force"),
            Appearance.LOCH_NESS: tr("Loch Ness"),
            Appearance.SLINKY_DOG_DASH: tr("Slinky Dog Dash"),
            Appearance.TOP_THRILL_2: tr("Top Thrill 2"),
        }
        pinned = (Appearance.SYSTEM, Appearance.LIGHT, Appearance.DARK)
        remaining = sorted(
            (appearance for appearance in Appearance if appearance not in pinned),
            key=lambda appearance: str(labels[appearance]).casefold(),
        )
        with QSignalBlocker(self.appearance):
            self.appearance.clear()
            self.appearance.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            for appearance in (*pinned, *remaining):
                self.appearance.addItem(str(labels[appearance]), appearance.value)
            self.appearance.setCurrentIndex(self.appearance.findData(selected.value))

    @Slot()
    def preview_appearance(self) -> None:
        """Preview an appearance choice without committing the settings dialog.

        Returns:
            None.
        """
        self.appearance_previewed.emit(
            APPEARANCE_CHOICES.index(Appearance(self.appearance.currentData())),
        )

    @Slot()
    def clear_cached_maps(self) -> None:
        """Clear the local map tile cache and report the outcome.

        Returns:
            None.
        """
        if TileCache().clear():
            bind(self.clear_map_cache, tr("Map cache cleared."))
            self.clear_map_cache.setEnabled(False)
        else:
            bind(self.clear_map_cache, tr("Could not clear map cache. Try again later."))

    def _update_map_cache_count(self) -> None:
        count = TileCache().count()
        self.clear_map_cache.setEnabled(count != 0)
        bind(
            self.clear_map_cache,
            tr("Clear map cache") if count is None else tr("Clear map cache ({0} tiles)", count),
        )

    @Slot()
    def save(self) -> None:
        """Validate and persist the selected application preferences.

        Returns:
            None.
        """
        self.preferences.remember_restore_last_file(self.restore_last_file.isChecked())
        self.preferences.remember_export_fps(EXPORT_FRAME_RATES[self.frame_rate.currentIndex()])
        self.preferences.remember_render_jobs(self.render_jobs.value())
        self.language_selected.emit(self.language.currentIndex())
        self.appearance_selected.emit(
            APPEARANCE_CHOICES.index(Appearance(self.appearance.currentData())),
        )
        self.accept()
