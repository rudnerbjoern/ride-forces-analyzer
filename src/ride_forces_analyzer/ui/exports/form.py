"""Video-export input controls and layout-specific placement choices.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import LANGUAGE_CHOICES, LANGUAGES, get_language, tr
from ride_forces_analyzer.ui.presentation.translation import bind, items

# cspell:words pixmap Deutsch

from pathlib import Path
from typing import cast

from PySide6.QtCore import (
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
    PROFILES,
)
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.storage.export_models import SavedPreset


from PySide6.QtCore import Signal
from ride_forces_analyzer.analysis.recording import RecordingAnalysis


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
        fixed_extent: Fixed area label for plugins supporting only Full frame.
        output_dimensions: Read-only resolved output dimensions in pixels.
        overlay_language: Overlay-only language choice.
        mode: Transparent MOV or opaque MP4 choice.
        fps: Standard or preserved custom frame-rate choice.
        interval: Marker, selection or whole-recording range choice.
        seconds: Visible source-time window.
        smoothing: Odd smoothing-window choice.
        flip_vertical: Vertical-axis presentation choice.
        flip_lateral: Fixed documented lateral polarity indicator.
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
        self.positions: dict[ExportLayout, LayoutPosition] = {}
        settings_layout = QVBoxLayout(self)
        form = QFormLayout()
        self._form = form
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        section_font = self.font()
        section_font.setBold(True)

        def section(title: str) -> None:
            label = bind(QLabel(), title)
            label.setFont(section_font)
            form.addRow(label)

        section(tr("Export settings"))
        self.layout_profile = QComboBox()
        items(self.layout_profile, [tr(title) for _, title in PROFILES])
        self.layout_profile.currentIndexChanged.connect(self._layout_changed)
        form.addRow(bind(QLabel(), tr("Layout profile")), self.layout_profile)
        self.aspect = QComboBox()
        items(self.aspect, [tr("Landscape · 16:9"), tr("Portrait · 9:16")])
        form.addRow(bind(QLabel(), tr("Layout format")), self.aspect)
        self.aspect.currentIndexChanged.connect(self._refresh_positions)
        self.extent = QComboBox()
        items(self.extent, [tr("Full frame"), tr("Content area")])
        for index, extent in enumerate(ExportExtent):
            self.extent.setItemData(index, extent.value)
        bind(self.extent, tr("Export area"), "accessibleName")
        self.fixed_extent = bind(QLabel(), tr("Full frame"))
        extent_row = QHBoxLayout()
        extent_row.setContentsMargins(0, 0, 0, 0)
        extent_row.addWidget(self.extent)
        extent_row.addWidget(self.fixed_extent)
        form.addRow(bind(QLabel(), tr("Export area")), extent_row)
        self.position = QComboBox()
        self.position.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        form.addRow(bind(QLabel(), tr("Position")), self.position)
        self.output_dimensions = QLabel()
        form.addRow(bind(QLabel(), tr("Output dimensions")), self.output_dimensions)
        self.overlay_language = QComboBox()
        items(self.overlay_language, [definition.name for definition in LANGUAGES.values()])
        self.overlay_language.setCurrentIndex(LANGUAGE_CHOICES.index(get_language()))
        self.mode = QComboBox()
        items(
            self.mode,
            [tr("Transparent overlay · ProRes 4444 MOV"), tr("Opaque video · H.264 MP4")],
        )
        form.addRow(bind(QLabel(), tr("Output")), self.mode)
        form.addRow(bind(QLabel(), tr("Overlay language")), self.overlay_language)
        self.fps = QComboBox()
        items(self.fps, [rate.label for rate in EXPORT_FRAME_RATES])
        for index, rate in enumerate(EXPORT_FRAME_RATES):
            self.fps.setItemData(index, rate.value)
        self.fps.setCurrentText(self.preferences.export_fps().label)
        form.addRow(bind(QLabel(), tr("Video frame rate")), self.fps)
        self.interval = QComboBox()
        items(
            self.interval,
            [tr("Start/end markers (default)"), tr("Current selection"), tr("Entire recording")],
        )
        form.addRow(bind(QLabel(), tr("Range")), self.interval)
        section(tr("Force display"))
        self.seconds = QDoubleSpinBox()
        self.seconds.setDecimals(3)
        self.seconds.setRange(1, 60)
        self.seconds.setValue(12)
        bind(self.seconds, " s", "suffix")
        form.addRow(bind(QLabel(), tr("Visible time window")), self.seconds)
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
        self.flip_lateral = bind(QCheckBox(), tr("+ Right / − Left"))
        self.flip_lateral.setChecked(False)
        self.flip_lateral.setEnabled(False)
        form.addRow(bind(QLabel(), tr("Lateral")), self.flip_lateral)
        section(tr("Encoding"))
        self.gpu = bind(QCheckBox(), tr("Use NVIDIA GPU"))
        bind(self.gpu, tr("Use NVIDIA GPU when supported; CPU fallback otherwise"), "toolTip")
        self.gpu.setChecked(True)
        form.addRow(bind(QLabel(), tr("Acceleration")), self.gpu)
        self.size_estimate = QLabel()
        self.size_estimate.setWordWrap(True)
        self.size_note = bind(
            QLabel(),
            tr(
                "Rough planning range, not a guarantee. Actual size depends on motion, detail and CPU/GPU encoding.",
            ),
        )
        self.size_note.setWordWrap(True)
        self.encoder = QLineEdit()
        try:
            bind(self.encoder, str(find_ffmpeg()), "text")
        except ValueError:
            self.encoder.setPlaceholderText(tr("Choose installed FFmpeg executable"))
        self.browse = bind(QPushButton(), tr("Browse…"))
        self.browse.clicked.connect(self._browse)
        encoder_row = QHBoxLayout()
        encoder_row.addWidget(self.encoder)
        encoder_row.addWidget(self.browse)
        form.addRow("FFmpeg", encoder_row)
        form.addRow(bind(QLabel(), tr("Estimated file size")), self.size_estimate)
        form.addRow(self.size_note)
        settings_layout.addLayout(form)
        settings_layout.addStretch()
        bind(self.smoothing, data.smoothing_text, "toolTip")
        self._refresh_positions()
        self.extent.currentIndexChanged.connect(self._refresh_geometry)
        self.position.currentIndexChanged.connect(self._refresh_geometry)
        self.controls = (
            self.overlay_language,
            self.aspect,
            self.layout_profile,
            self.position,
            self.extent,
            self.mode,
            self.fps,
            self.interval,
            self.seconds,
            self.flip_vertical,
            self.flip_lateral,
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
            self.mode,
            self.fps,
            self.interval,
        ):
            combo.currentIndexChanged.connect(self.changed)
        self.seconds.valueChanged.connect(self.changed)
        self.flip_vertical.toggled.connect(self.changed)
        self.flip_lateral.toggled.connect(self.changed)
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
        return ExportSettings(
            language=LANGUAGE_CHOICES[self.overlay_language.currentIndex()],
            aspect=aspect,
            fps=StandardFrameRate(rate) if isinstance(rate, str) else cast(int, rate),
            window_seconds=float(self.seconds.value()),
            output=VideoOutput.TRANSPARENT if self.mode.currentIndex() == 0 else VideoOutput.OPAQUE,
            invert_vertical=self.flip_vertical.isChecked(),
            invert_lateral=self.flip_lateral.isChecked(),
            prefer_gpu=self.gpu.isChecked(),
            layout=layout,
            position=LayoutPosition(self.position.currentData()),
            extent=extent
            if extent in registry.PLUGINS[layout].supported_extents(aspect)
            else ExportExtent.FULL_FRAME,
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
        if plugin.preferred_window_seconds is not None:
            self.seconds.setValue(plugin.preferred_window_seconds)
        self.flip_vertical.setChecked(True)
        self.flip_lateral.setChecked(False)
        self.flip_vertical.setEnabled(True)
        self.flip_lateral.setEnabled(False)

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
        self._refresh_geometry()

    @Slot()
    def _refresh_geometry(self) -> None:
        """Show applicable plugin controls and centrally resolved output dimensions."""
        settings = self.settings()
        plugin = registry.PLUGINS[settings.layout]
        selectable = len(plugin.supported_extents(settings.aspect)) > 1
        self.extent.setVisible(selectable)
        self.fixed_extent.setVisible(not selectable)
        self._form.setRowVisible(
            self.position,
            settings.extent is ExportExtent.FULL_FRAME
            and len(plugin.positions(settings.aspect).regions) > 1,
        )
        width, height = registry.resolve_geometry(settings).output_size
        self.output_dimensions.setText(f"{width}×{height}")

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
        self.flip_lateral.setChecked(False)
        self.gpu.setChecked(settings.prefer_gpu)
        self.interval.setCurrentIndex(("markers", "selection", "entire").index(preset.range_mode))
