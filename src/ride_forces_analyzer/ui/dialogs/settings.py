"""Application preferences and export defaults, independent of per-export settings.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, LANGUAGES, Language, tr
from ride_forces_analyzer.runtime.cpu_resources import render_job_limit
from ride_forces_analyzer.rendering.model import EXPORT_FRAME_RATES
from ride_forces_analyzer.storage.preferences import Appearance, Preferences
from ride_forces_analyzer.storage.map_tiles import TileCache
from ride_forces_analyzer.ui.presentation.translation import bind, button_text, items
from ride_forces_analyzer.ui.presentation.updates import UpdateController
from .library_labels import LibraryLabelsEditor
from .library_transfer import LibraryTransferControls

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
        render_jobs: Choice of concurrent frame renderers from one to the local CPU limit.
        buttons: Dialog action buttons.
        check_updates: Button starting a manual update check.
        automatic_updates: Checkbox enabling the daily startup check when settings are saved.
        update_status: Label displaying update-check progress and results.
        library_labels: Draft label options saved with the other preferences.
        library_error: Explanation when label preferences cannot be saved.
        library_transfer: Explicit backup/restore actions, separate from Save/Cancel.
        library_restored: Notification after a full Library replacement commits.
    """

    language_selected = Signal(int)
    appearance_selected = Signal(int)
    appearance_previewed = Signal(int)
    library_restored = Signal()

    def __init__(
        self,
        preferences: Preferences,
        parent: QWidget,
        *,
        language: Language,
        updates: UpdateController,
    ) -> None:
        """Initialize settings dialog and its owned state.

        Args:
            preferences: Local application preference access.
            parent: Qt parent that owns this object's lifetime.
            language: Registered language used to translate presentation text and numbers.
            updates: Existing update controller owned by the explorer window.

        Returns:
            None.
        """
        super().__init__(parent)
        self.preferences = preferences
        self.setObjectName("settingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        bind(self, tr("Settings"), "windowTitle")
        self.resize(540, min(760, self.screen().availableGeometry().height() - 80))
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setObjectName("settingsContentScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
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
        self.clear_map_cache.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon),
        )
        self._update_map_cache_count()
        self.clear_map_cache.clicked.connect(self.clear_cached_maps)
        application_form.addRow(self.clear_map_cache)
        layout.addWidget(application)
        group = bind(QGroupBox(), tr("Export"), "title")
        form = QFormLayout(group)
        self.frame_rate = QComboBox()
        items(self.frame_rate, [rate.label for rate in EXPORT_FRAME_RATES])
        self.frame_rate.setCurrentIndex(EXPORT_FRAME_RATES.index(preferences.export_fps()))
        form.addRow(bind(QLabel(), tr("Default video frame rate")), self.frame_rate)
        explanation = bind(
            QLabel(),
            tr("Applies to new exports. Saved presets and batches keep their own frame rates."),
        )
        explanation.setWordWrap(True)
        form.addRow(explanation)
        self.render_jobs = QComboBox()
        items(self.render_jobs, [str(jobs) for jobs in range(1, render_job_limit() + 1)])
        self.render_jobs.setCurrentIndex(
            min(preferences.render_jobs(), self.render_jobs.count()) - 1,
        )
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
        self.library_labels = LibraryLabelsEditor(preferences.library_video_labels(), self)
        layout.addWidget(self.library_labels)
        self.library_error = QLabel()
        self.library_error.setTextFormat(Qt.TextFormat.PlainText)
        self.library_error.setWordWrap(True)
        self.library_error.hide()
        layout.addWidget(self.library_error)
        self.library_transfer = LibraryTransferControls(preferences, self.library_labels)
        library_layout = self.library_labels.layout()
        assert library_layout is not None
        library_layout.addWidget(self.library_transfer)
        self.library_transfer.restored.connect(self._library_restored)
        self.library_transfer.status.connect(self._library_status)
        self.library_transfer.busy_changed.connect(self._library_busy)
        update_group = bind(QGroupBox(), tr("Updates"), "title")
        update_layout = QVBoxLayout(update_group)
        self.automatic_updates = bind(
            QCheckBox(),
            tr("Check for updates at startup (once per day)"),
        )
        self.automatic_updates.setChecked(preferences.automatic_updates())
        update_layout.addWidget(self.automatic_updates)
        self.check_updates = button_text(QPushButton(), tr("Check for updates…"))
        self.check_updates.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        )
        self.check_updates.setEnabled(updates.worker is None)
        self.check_updates.clicked.connect(lambda: updates.check(manual=True))
        updates.busy_changed.connect(self.check_updates.setDisabled)
        update_layout.addWidget(self.check_updates)
        self.update_status = QLabel()
        self.update_status.setTextFormat(Qt.TextFormat.PlainText)
        self.update_status.setWordWrap(True)
        self.update_status.setMinimumHeight(2 * self.update_status.fontMetrics().lineSpacing())
        status_policy = self.update_status.sizePolicy()
        status_policy.setRetainSizeWhenHidden(True)
        self.update_status.setSizePolicy(status_policy)
        self.update_status.hide()
        updates.status_changed.connect(self._update_status)
        update_layout.addWidget(self.update_status)
        privacy = bind(
            QLabel(),
            tr("Optional GitHub connection. No recordings, GPS data or file paths are sent."),
        )
        privacy.setWordWrap(True)
        update_layout.addWidget(privacy)
        layout.addWidget(update_group)
        layout.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        bind(self.buttons.button(QDialogButtonBox.StandardButton.Save), tr("&Save"))
        for standard, name in (
            (QDialogButtonBox.StandardButton.Save, tr("Save settings")),
            (QDialogButtonBox.StandardButton.Cancel, tr("Cancel")),
        ):
            button = self.buttons.button(standard)
            bind(button, name, "accessibleName")
            bind(button, name, "toolTip")
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton),
        )
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    @Slot()
    def _library_restored(self) -> None:
        self.library_labels.set_labels(self.preferences.library_video_labels())
        self.library_restored.emit()

    @Slot(str)
    def _library_status(self, message: str) -> None:
        self.library_error.setText(message)
        self.library_error.setVisible(bool(message))

    @Slot(bool)
    def _library_busy(self, busy: bool) -> None:
        self.buttons.setDisabled(busy)
        self.library_labels.set_busy(busy)

    def reject(self) -> None:
        """Cancel a running transfer before allowing Settings to close."""
        if self.library_transfer.busy:
            self.library_transfer.cancel()
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Keep transfer ownership alive until cancellation or commit completes.

        Args:
            event: Native close request.
        """
        if self.library_transfer.busy:
            self.library_transfer.cancel()
            event.ignore()
            return
        super().closeEvent(event)

    @Slot(object)
    def _update_status(self, message: object) -> None:
        if isinstance(message, str):
            bind(self.update_status, message)
            self.update_status.setVisible(bool(message))

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
            button_text(self.clear_map_cache, tr("Map cache cleared."))
            self.clear_map_cache.setEnabled(False)
        else:
            button_text(self.clear_map_cache, tr("Could not clear map cache. Try again later."))

    def _update_map_cache_count(self) -> None:
        count = TileCache().count()
        self.clear_map_cache.setEnabled(count != 0)
        button_text(
            self.clear_map_cache,
            tr("Clear map cache") if count is None else tr("Clear map cache ({0} tiles)", count),
        )

    @Slot()
    def save(self) -> None:
        """Validate and persist the selected application preferences.

        Returns:
            None.
        """
        try:
            saved = self.preferences.remember_library_video_labels(self.library_labels.labels())
        except ValueError as error:
            self.library_error.setText(tr(str(error)))
            self.library_error.show()
            return
        if not saved:
            bind(self.library_error, tr("Could not save video labels. Try again later."))
            self.library_error.show()
            return
        self.preferences.remember_restore_last_file(self.restore_last_file.isChecked())
        self.preferences.remember_automatic_updates(self.automatic_updates.isChecked())
        self.preferences.remember_export_fps(EXPORT_FRAME_RATES[self.frame_rate.currentIndex()])
        self.preferences.remember_render_jobs(self.render_jobs.currentIndex() + 1)
        self.language_selected.emit(self.language.currentIndex())
        self.appearance_selected.emit(
            APPEARANCE_CHOICES.index(Appearance(self.appearance.currentData())),
        )
        self.accept()
