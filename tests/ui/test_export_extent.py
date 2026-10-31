"""Assistant capabilities, output geometry and estimate updates in one session."""

# cspell:words qapp

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QWidget
import pytest

from ride_forces_analyzer.explorer import ExplorerData, load_recording
from ride_forces_analyzer.i18n import Language, get_language, tr
from ride_forces_analyzer.rendering.layouts import registry
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    PROFILES,
)
from ride_forces_analyzer.rendering.size_estimate import estimate_size_bytes
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.ui.presentation.translation import set_ui_language
from tests.support.recordings import REAL_FIXTURE_DIRECTORY
from tests.ui.helpers import wait_until


def test_assistant_extent_geometry_visibility_estimates_and_localization(
    qapp: QApplication,
    small_preview_frames: None,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = load_recording(next(REAL_FIXTURE_DIRECTORY.glob("Manta-*.forces")))
    assert isinstance(data, ExplorerData)
    original_language = get_language()
    set_ui_language(qapp, Language.ENGLISH)
    parent = QWidget()
    dialog = ExportDialog(
        data,
        3600,
        4099,
        parent,
        current_sample=3600,
        store=ExportStore(export_directory / "extent.sqlite3"),
    )
    form = dialog.form

    def choose_layout(key: ExportLayout) -> None:
        form.layout_profile.setCurrentIndex(
            next(i for i, (name, _) in enumerate(PROFILES) if name == key),
        )

    def check_output(
        dimensions: str,
        extent: ExportExtent,
        *,
        position_visible: bool = True,
        selectable: bool = True,
    ) -> None:
        settings = form.settings()
        assert settings.extent is extent
        assert form.output_dimensions.text() == dimensions
        assert dialog.review_fields["resolution"].text() == dimensions
        assert form.position.isHidden() is not position_visible
        assert dialog.review_fields["position"].isHidden() is not position_visible
        assert form.extent.isHidden() is not selectable
        assert form.fixed_extent.isHidden() is selectable
        assert dialog.review_fields["extent"].text() == tr(
            "Content area" if extent is ExportExtent.CONTENT_AREA else "Full frame",
        )
        first, last = form.bounds(dialog.analysis, (dialog.first, dialog.last))
        low, high = estimate_size_bytes(settings, last - first + 1, data.sample_rate)
        expected = tr("{0:.0f}–{1:.0f} MiB", low / 2**20, high / 2**20)
        assert form.size_estimate.text() == expected
        assert dialog.review_size_estimate.text() == expected
        wait_until(lambda: dialog.previews.result is not None)
        assert dialog.next.isEnabled()

    try:
        dialog.show()
        wait_until(dialog.isVisible)
        layout = form.findChild(QFormLayout)
        assert layout is not None
        for row, expected in enumerate(
            (
                "Layout profile",
                "Layout format",
                "Export area",
                "Position",
                "Output dimensions",
                "Output",
                "Overlay language",
                "Video frame rate",
                "Range",
            ),
            start=1,
        ):
            item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            assert item is not None
            label = item.widget()
            assert isinstance(label, QLabel) and label.text() == expected
        check_output("3840×2160", ExportExtent.FULL_FRAME)
        assert form.extent in dialog.controls
        choose_layout(ExportLayout.ORBIT)
        form.position.setCurrentIndex(form.position.findData("top_right"))
        full_estimate = form.size_estimate.text()
        revision = dialog.previews.revision
        form.extent.setCurrentIndex(form.extent.findData(ExportExtent.CONTENT_AREA.value))
        assert dialog.previews.revision > revision and dialog.previews.result is None
        check_output("800×800", ExportExtent.CONTENT_AREA, position_visible=False)
        content_estimate = form.size_estimate.text()
        assert content_estimate != full_estimate
        form.mode.setCurrentIndex(1)
        gpu_estimate = form.size_estimate.text()
        assert dialog.review_size_estimate.text() == gpu_estimate
        form.gpu.setChecked(False)
        cpu_estimate = form.size_estimate.text()
        assert cpu_estimate != gpu_estimate
        assert dialog.review_size_estimate.text() == cpu_estimate
        form.gpu.setChecked(True)
        assert form.size_estimate.text() == gpu_estimate
        assert dialog.review_size_estimate.text() == gpu_estimate
        form.mode.setCurrentIndex(0)
        check_output("800×800", ExportExtent.CONTENT_AREA, position_visible=False)
        assert form.position.currentData() == "top_right"
        dialog.next.click()
        assert dialog.pages.currentIndex() == 1
        assert dialog.review_fields["extent"].isVisible()
        assert not dialog.review_fields["position"].isVisible()
        dialog.back.click()
        form.extent.setCurrentIndex(form.extent.findData(ExportExtent.FULL_FRAME.value))
        check_output("3840×2160", ExportExtent.FULL_FRAME)
        assert form.position.currentData() == "top_right"
        assert form.size_estimate.text() == full_estimate
        form.extent.setCurrentIndex(form.extent.findData(ExportExtent.CONTENT_AREA.value))
        check_output("800×800", ExportExtent.CONTENT_AREA, position_visible=False)
        for language in Language:
            set_ui_language(qapp, language)
            QApplication.processEvents()
            check_output("800×800", ExportExtent.CONTENT_AREA, position_visible=False)
            assert form.extent.currentText() == tr("Content area")
            assert form.extent.accessibleName() == tr("Export area")
        choose_layout(ExportLayout.HUD)
        check_output("1920×1080", ExportExtent.FULL_FRAME, position_visible=False, selectable=False)
        assert form.fixed_extent.text() == tr("Full frame")
        form.aspect.setCurrentIndex(1)
        check_output("1080×1920", ExportExtent.FULL_FRAME, position_visible=False, selectable=False)
        choose_layout(ExportLayout.RIBBON)
        check_output("840×1120", ExportExtent.CONTENT_AREA, position_visible=False)
        portrait_estimate = form.size_estimate.text()
        form.aspect.setCurrentIndex(0)
        check_output("3072×360", ExportExtent.CONTENT_AREA, position_visible=False)
        assert form.size_estimate.text() != portrait_estimate
        form.mode.setCurrentIndex(1)
        check_output("3072×360", ExportExtent.CONTENT_AREA, position_visible=False)
        choose_layout(ExportLayout.COLUMN)
        check_output("960×2160", ExportExtent.CONTENT_AREA, position_visible=False)
        form.aspect.setCurrentIndex(1)
        assert form.settings().layout is not ExportLayout.COLUMN
        check_output("840×1120", ExportExtent.CONTENT_AREA, position_visible=False)
        form.aspect.setCurrentIndex(0)
        choose_layout(ExportLayout.ORBIT)
        # Capabilities, rather than layout names, determine the fixed-area display.
        monkeypatch.setattr(
            registry,
            "PLUGINS",
            {
                **registry.PLUGINS,
                ExportLayout.ORBIT: replace(
                    registry.PLUGINS[ExportLayout.ORBIT],
                    landscape_content=None,
                ),
            },
        )
        form.aspect.setCurrentIndex(1)
        form.aspect.setCurrentIndex(0)
        check_output("3840×2160", ExportExtent.FULL_FRAME, selectable=False)
    finally:
        dialog.close()
        QThreadPool.globalInstance().waitForDone()
        parent.deleteLater()
        set_ui_language(qapp, original_language)
        QApplication.processEvents()
