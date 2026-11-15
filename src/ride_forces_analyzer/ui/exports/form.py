"""Video-export input controls and layout-specific placement choices.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, LANGUAGES, get_language, tr
from ride_forces_analyzer.ui.presentation.translation import bind, button_text, items

# cspell:words pixmap Deutsch

from pathlib import Path
from typing import cast

from PySide6.QtCore import (
    QEvent,
    Qt,
    Slot,
    QSignalBlocker,
)
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QDoubleSpinBox,
)

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.encoding import find_ffmpeg
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.rendering.model import (
    VideoOutput,
    VideoAspect,
    EXPORT_FRAME_RATES,
    StandardFrameRate,
    ExportLayout,
    ExportExtent,
    ExportSettings,
    ExportSafeRegion,
    PROFILES,
)
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.storage.export_models import SavedPreset
from .labels import safe_region_label


from PySide6.QtCore import Signal
from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.runtime.error_logging import record_error


class ExportForm(QWidget):
    """Own export inputs without launching preview, analysis or encoding workers.

    Attributes:
        changed: Signal requesting a preview for changed export inputs.
        smoothing_changed: Signal carrying the newly selected smoothing index.
        positions: Retained placement choices keyed by overlay layout.
        preferences: Existing preferences supplying defaults for new exports.
        layout_profile: Overlay layout choice.
        position: Placement choice supported by the selected layout and aspect.
        aspect: Landscape or portrait choice.
        extent: Requested Full-frame or native Content-area export choice.
        safe_region: Retained Off/A/B/C choice, effective only for Portrait Full frame.
        safe_region_note: Reason for an inactive choice or identical G-Orbit variants.
        fixed_extent: Fixed area label for plugins supporting only Full frame.
        output_dimensions: Read-only resolved output dimensions in pixels.
        overlay_language: Overlay-only language choice.
        mode: Transparent MOV or opaque MP4 choice.
        fps: Standard or preserved custom frame-rate choice.
        interval: Marker, selection or whole-recording range choice.
        seconds: Visible source-time window.
        smoothing: Odd smoothing-window choice.
        flip_vertical: Vertical-axis presentation choice.
        lateral_polarity: Read-only explanation of the fixed lateral signs.
        gpu: Preferred supported GPU encoding choice.
        size_estimate: Prepared approximate output-size text.
        size_note: Explanation of size-estimate limits.
        encoder: Optional FFmpeg executable path.
        browse: Button opening encoder selection.
        controls: Inputs disabled while video export is active.
    """

    changed = Signal()
    smoothing_changed = Signal(int)

    def __init__(self, data: ExplorerData, preferences: Preferences, parent: QWidget) -> None:
        """Build a settings form using the bound source's display defaults.

        Args:
            data: Prepared explorer data supplying initial smoothing.
            preferences: Existing default frame rate and export preferences.
            parent: Dialog owning the form's lifetime.

        Returns:
            None.
        """
        super().__init__(parent)
        self.preferences = preferences
        self._seconds_edited = False
        self._vertical_edited = False
        self.positions: dict[ExportLayout, LayoutPosition] = {}
        settings_layout = QVBoxLayout(self)
        form = QFormLayout()
        self._form = form
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        section_font = self.font()
        section_font.setBold(True)

        def section(title: str) -> None:
            label = bind(QLabel(), title)
            label.setFont(section_font)
            label.setObjectName("exportSection")
            if form.rowCount():
                label.setContentsMargins(0, 12, 0, 0)
            form.addRow(label)

        section(tr("Layout and placement"))
        self.aspect = QComboBox()
        items(self.aspect, [tr("Landscape · 16:9"), tr("Portrait · 9:16")])
        bind(self.aspect, tr("Image format"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Image format")), self.aspect)
        self.aspect.currentIndexChanged.connect(self._refresh_positions)
        self.layout_profile = QComboBox()
        items(self.layout_profile, [tr(title) for _, title in PROFILES])
        self.layout_profile.currentIndexChanged.connect(self._layout_changed)
        form.addRow(bind(QLabel(), tr("Layout profile")), self.layout_profile)
        self.extent = QComboBox()
        items(self.extent, [tr("Full frame"), tr("Content area")])
        for index, extent in enumerate(ExportExtent):
            self.extent.setItemData(index, extent.value)
        bind(self.extent, tr("Image area"), "accessibleName")
        self.fixed_extent = bind(QLabel(), tr("Full frame"))
        extent_row = QHBoxLayout()
        extent_row.setContentsMargins(0, 0, 0, 0)
        extent_row.addWidget(self.extent)
        extent_row.addWidget(self.fixed_extent)
        form.addRow(bind(QLabel(), tr("Image area")), extent_row)
        self.position = QComboBox()
        self.position.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        form.addRow(bind(QLabel(), tr("Position")), self.position)
        self.safe_region = QComboBox()
        items(self.safe_region, [safe_region_label(profile) for profile in ExportSafeRegion])
        for index, profile in enumerate(ExportSafeRegion):
            self.safe_region.setItemData(index, profile.value)
        bind(self.safe_region, tr("Safe Region"), "accessibleName")
        help_text = tr(
            "Portrait and Full frame only; your choice is retained while inactive. A/B/C add equal side clearance and progressively raise force plots. G-Orbit uses the same arrangement. Platform overlap and cropping remain possible.",
        )
        bind(self.safe_region, help_text, "toolTip")
        bind(self.safe_region, help_text, "accessibleDescription")
        safe_region_label_widget = bind(QLabel(), tr("&Safe Region"))
        safe_region_label_widget.setBuddy(self.safe_region)
        form.addRow(safe_region_label_widget, self.safe_region)
        self.safe_region_note = QLabel()
        self.safe_region_note.setWordWrap(True)
        self.safe_region_note.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow("", self.safe_region_note)
        self.output_dimensions = QLabel()
        form.addRow(bind(QLabel(), tr("Resolution")), self.output_dimensions)
        section(tr("Content and presentation"))
        self.interval = QComboBox()
        items(
            self.interval,
            [tr("Start/end markers (default)"), tr("Current selection"), tr("Entire recording")],
        )
        bind(self.interval, tr("Recording section"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Recording section")), self.interval)
        self.overlay_language = QComboBox()
        items(self.overlay_language, [definition.name for definition in LANGUAGES.values()])
        self.overlay_language.setCurrentIndex(LANGUAGE_CHOICES.index(get_language()))
        form.addRow(bind(QLabel(), tr("Overlay language")), self.overlay_language)
        self.seconds = QDoubleSpinBox()
        self.seconds.setDecimals(3)
        self.seconds.setRange(1, 60)
        self.seconds.setValue(12)
        bind(self.seconds, " s", "suffix")
        bind(self.seconds, tr("Plot time window"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Plot time window")), self.seconds)
        self.smoothing = QComboBox()
        items(self.smoothing, [tr("{0} samples", count) for count in range(1, 52, 2)])
        self.smoothing.setCurrentIndex(
            data.smoothing_window // 2,
        )
        form.addRow(bind(QLabel(), tr("Smoothing")), self.smoothing)
        self.flip_vertical = bind(
            QCheckBox(),
            tr("Positive values downward"),
        )
        bind(self.flip_vertical, tr("Positive values below zero, as in the reference"), "toolTip")
        self.flip_vertical.setChecked(True)
        form.addRow(bind(QLabel(), tr("Vertical")), self.flip_vertical)
        self.lateral_polarity = bind(QLabel(), tr("Positive right, negative left"))
        self.lateral_polarity.setWordWrap(True)
        form.addRow(bind(QLabel(), tr("Lateral")), self.lateral_polarity)
        section(tr("Video file"))
        self.mode = QComboBox()
        self.mode.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        items(
            self.mode,
            [tr("Transparent overlay · ProRes 4444 MOV"), tr("Opaque video · H.264 MP4")],
        )
        bind(self.mode, tr("Video format"), "accessibleName")
        form.addRow(bind(QLabel(), tr("Video format")), self.mode)
        self.fps = QComboBox()
        items(self.fps, [rate.label for rate in EXPORT_FRAME_RATES])
        for index, rate in enumerate(EXPORT_FRAME_RATES):
            self.fps.setItemData(index, rate.value)
        self.fps.setCurrentText(self.preferences.export_fps().label)
        form.addRow(bind(QLabel(), tr("Video frame rate")), self.fps)
        self.size_estimate = QLabel()
        self.size_estimate.setWordWrap(True)
        self.size_note = bind(
            QLabel(),
            tr(
                "Rough planning range, not a guarantee. Actual size depends on motion, detail and CPU/GPU encoding.",
            ),
        )
        self.size_note.setWordWrap(True)
        form.addRow(bind(QLabel(), tr("Estimated file size")), self.size_estimate)
        form.addRow(self.size_note)
        section(tr("Encoding"))
        self.gpu = bind(QCheckBox(), tr("Prefer NVIDIA GPU"))
        bind(self.gpu, tr("Use NVIDIA GPU when supported; CPU fallback otherwise"), "toolTip")
        self.gpu.setChecked(True)
        form.addRow(bind(QLabel(), tr("GPU encoding")), self.gpu)
        self.encoder = QLineEdit()
        try:
            bind(self.encoder, str(find_ffmpeg()), "text")
        except ValueError as error:
            record_error("ui.exports.form.__init__", error)
            self.encoder.setPlaceholderText(tr("Choose installed FFmpeg executable"))
        self.browse = button_text(
            QPushButton(),
            tr("Browse…"),
            tooltip=tr("Choose FFmpeg executable"),
            caption=tr("&Browse…"),
        )
        self.browse.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
        )
        self.browse.clicked.connect(self._browse)
        encoder_row = QHBoxLayout()
        encoder_row.addWidget(self.encoder)
        encoder_row.addWidget(self.browse)
        form.addRow("FFmpeg", encoder_row)
        settings_layout.addLayout(form)
        settings_layout.addStretch()
        bind(self.smoothing, data.smoothing_text, "toolTip")
        self._refresh_positions()
        self.extent.currentIndexChanged.connect(self.refresh_geometry)
        self.position.currentIndexChanged.connect(self.refresh_geometry)
        self.controls = (
            self.overlay_language,
            self.aspect,
            self.layout_profile,
            self.position,
            self.extent,
            self.safe_region,
            self.mode,
            self.fps,
            self.interval,
            self.seconds,
            self.flip_vertical,
            self.encoder,
            self.gpu,
            self.browse,
            self.smoothing,
        )
        for combo in (
            self.overlay_language,
            self.layout_profile,
            self.aspect,
            self.position,
            self.extent,
            self.safe_region,
            self.mode,
            self.fps,
            self.interval,
        ):
            combo.currentIndexChanged.connect(self.changed)
        self.seconds.valueChanged.connect(self._seconds_changed)
        self.flip_vertical.toggled.connect(self._vertical_changed)
        self.gpu.toggled.connect(self.changed)
        self.smoothing.currentIndexChanged.connect(self.smoothing_changed)

    def settings(self) -> ExportSettings:
        """Read the current inputs through the existing typed settings contract.

        Returns:
            Validated render/encoding settings reflecting the form inputs.

        Raises:
            ValueError: A selected input is unsupported by the settings contract.
        """
        rate = self.fps.currentData()
        layout = PROFILES[self.layout_profile.currentIndex()][0]
        aspect = VideoAspect.LANDSCAPE if self.aspect.currentIndex() == 0 else VideoAspect.PORTRAIT
        extent = ExportExtent(self.extent.currentData())
        if extent not in registry.PLUGINS[layout].supported_extents(aspect):
            extent = ExportExtent.FULL_FRAME
        return ExportSettings(
            language=LANGUAGE_CHOICES[self.overlay_language.currentIndex()],
            aspect=aspect,
            fps=StandardFrameRate(rate) if isinstance(rate, str) else cast(int, rate),
            window_seconds=float(self.seconds.value()),
            output=VideoOutput.TRANSPARENT if self.mode.currentIndex() == 0 else VideoOutput.OPAQUE,
            invert_vertical=self.flip_vertical.isChecked(),
            invert_lateral=False,
            prefer_gpu=self.gpu.isChecked(),
            layout=layout,
            position=LayoutPosition(self.position.currentData()),
            extent=extent,
            safe_region=registry.effective_safe_region(
                ExportSafeRegion(self.safe_region.currentData()),
                aspect,
                extent,
            ),
        )

    def bounds(self, analysis: RecordingAnalysis, selection: tuple[int, int]) -> tuple[int, int]:
        """Resolve the selected range against the supplied snapshot and selection.

        Args:
            analysis: Current prepared analysis carrying effective marker bounds.
            selection: Inclusive source selection captured when opening the assistant.

        Returns:
            Marker, selected or whole-recording inclusive sample bounds.
        """
        return (analysis.ride_bounds, selection, (0, len(analysis.time.source_indices) - 1))[
            self.interval.currentIndex()
        ]

    def remember_positions(self) -> None:
        """Retain each layout's placement using the existing layout registry.

        Returns:
            None.
        """
        settings = self.settings()
        for key, plugin in registry.PLUGINS.items():
            if settings.aspect not in plugin.supported_aspects:
                continue
            positions = plugin.positions(settings.aspect)
            self.positions[key] = positions.select(
                settings.position,
                self.positions.get(key),
            )

    @Slot(int)
    def _layout_changed(self, index: int) -> None:
        self._refresh_positions()
        plugin = registry.PLUGINS[PROFILES[index][0]]
        if not self._seconds_edited and plugin.preferred_window_seconds is not None:
            with QSignalBlocker(self.seconds):
                self.seconds.setValue(plugin.preferred_window_seconds)
        if not self._vertical_edited:
            with QSignalBlocker(self.flip_vertical):
                self.flip_vertical.setChecked(True)

    @Slot(float)
    def _seconds_changed(self, _value: float) -> None:
        """Retain an explicitly edited time window across later layout choices."""
        self._seconds_edited = True
        self.changed.emit()

    @Slot(bool)
    def _vertical_changed(self, _checked: bool) -> None:
        """Retain an explicitly edited vertical direction across layout choices."""
        self._vertical_edited = True
        self.changed.emit()

    @Slot()
    def _refresh_positions(self) -> None:
        previous = self.position.currentData()
        aspect = VideoAspect.LANDSCAPE if self.aspect.currentIndex() == 0 else VideoAspect.PORTRAIT
        model = self.layout_profile.model()
        assert isinstance(model, QStandardItemModel)
        for index, (key, _) in enumerate(PROFILES):
            item = model.item(index)
            assert item is not None
            item.setEnabled(aspect in registry.PLUGINS[key].supported_aspects)
            item.setToolTip(
                "" if item.isEnabled() else str(tr("Landscape only")),
            )
        plugin = registry.PLUGINS[PROFILES[self.layout_profile.currentIndex()][0]]
        if aspect not in plugin.supported_aspects:
            self.layout_profile.setCurrentIndex(
                next(
                    index
                    for index, (key, _) in enumerate(PROFILES)
                    if aspect in registry.PLUGINS[key].supported_aspects
                ),
            )
            return
        positions = plugin.positions(aspect)
        labels = {
            LayoutPosition.FULL_SCREEN: tr("Full screen"),
            LayoutPosition.TOP: tr("Top"),
            LayoutPosition.BOTTOM: tr("Bottom"),
            LayoutPosition.LEFT: tr("Left"),
            LayoutPosition.RIGHT: tr("Right"),
            LayoutPosition.TOP_LEFT: tr("Top left"),
            LayoutPosition.TOP_RIGHT: tr("Top right"),
            LayoutPosition.BOTTOM_LEFT: tr("Bottom left"),
            LayoutPosition.BOTTOM_RIGHT: tr("Bottom right"),
        }
        with QSignalBlocker(self.position):
            self.position.clear()
            items(self.position, [labels[position] for position in positions.regions])
            for index, position in enumerate(positions.regions):
                self.position.setItemData(index, position.value)
            selected = positions.select(
                LayoutPosition(previous) if previous is not None else None,
                self.positions.get(plugin.key),
            )
            self.position.setCurrentIndex(self.position.findData(selected.value))
        self.refresh_geometry()

    @Slot()
    def refresh_geometry(self) -> None:
        """Restore applicable controls and centrally resolved output dimensions.

        Returns:
            None; unsupported format choices remain retained but inactive.
        """
        settings = self.settings()
        plugin = registry.PLUGINS[settings.layout]
        self.mode.setMinimumWidth(self.mode.sizeHint().width())
        selectable = len(plugin.supported_extents(settings.aspect)) > 1
        self.extent.setVisible(selectable)
        self.fixed_extent.setVisible(not selectable)
        eligible = (
            settings.aspect is VideoAspect.PORTRAIT and settings.extent is ExportExtent.FULL_FRAME
        )
        self.safe_region.setEnabled(eligible)
        bind(
            self.safe_region_note,
            tr("For G-Orbit, A/B/C use the same arrangement.")
            if eligible
            else tr("Inactive — Portrait and Full frame only. Effective: Off."),
        )
        self._form.setRowVisible(
            self.safe_region_note,
            not eligible or settings.layout is ExportLayout.ORBIT,
        )
        self._form.setRowVisible(
            self.position,
            settings.extent is ExportExtent.FULL_FRAME
            and len(plugin.positions(settings.aspect).regions) > 1,
        )
        width, height = registry.resolve_geometry(settings).output_size
        self.output_dimensions.setText(f"{width}×{height}")

    def changeEvent(self, event: QEvent) -> None:
        """Refresh capability explanations after the interface language changes.

        Args:
            event: Qt event delivered to the form.

        Returns:
            None; retained choices and explicit display edits stay unchanged.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.LocaleChange and hasattr(self, "controls"):
            self._refresh_positions()

    @Slot()
    def _browse(self) -> None:
        configured = self.encoder.text().strip()
        directory = ""
        if configured:
            candidate = Path(configured).expanduser()
            directory = str((candidate if candidate.is_dir() else candidate.parent).resolve())
        path, _ = QFileDialog.getOpenFileName(
            self.window(),
            tr("Choose FFmpeg"),
            directory,
            tr("All files (*)"),
        )
        if path:
            bind(self.encoder, path, "text")

    def apply_preset(self, preset: SavedPreset) -> None:
        """Apply a saved preset's input values without preparing analysis.

        Args:
            preset: Existing validated preset whose input choices are restored.

        Returns:
            None; changed controls emit the same input notifications as user edits.
        """
        settings = preset.settings
        self._seconds_edited = True
        self._vertical_edited = True
        self.safe_region.setCurrentIndex(self.safe_region.findData(settings.safe_region.value))
        self.overlay_language.setCurrentIndex(LANGUAGE_CHOICES.index(settings.language))
        self.aspect.setCurrentIndex(0 if settings.aspect is VideoAspect.LANDSCAPE else 1)
        self.layout_profile.setCurrentIndex(
            next(i for i, (key, _) in enumerate(PROFILES) if key == settings.layout),
        )
        self.extent.setCurrentIndex(self.extent.findData(settings.extent.value))
        plugin = registry.PLUGINS[settings.layout]
        positions = plugin.positions(settings.aspect)
        self.position.setCurrentIndex(
            self.position.findData((settings.position or positions.default).value),
        )
        self.mode.setCurrentIndex(0 if settings.output == VideoOutput.TRANSPARENT else 1)
        if self.fps.findText(settings.fps_label) < 0:
            self.fps.addItem(settings.fps_label, settings.fps)
        self.fps.setCurrentText(settings.fps_label)
        self.seconds.setValue(settings.window_seconds)
        self.smoothing.setCurrentIndex(preset.smoothing_window // 2)
        self.flip_vertical.setChecked(settings.invert_vertical)
        self.gpu.setChecked(settings.prefer_gpu)
        self.interval.setCurrentIndex(("markers", "selection", "entire").index(preset.range_mode))
        self.changed.emit()
