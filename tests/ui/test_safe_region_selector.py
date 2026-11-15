"""Safe Region controls, production previews and summaries in one native session."""

# cspell:words qapp qtbot pytestqt pixmap

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QScrollArea, QWidget
from pytestqt.qtbot import QtBot

from ride_forces_analyzer.analysis.recording import RecordingAnalysis
from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.exports.batches import make_job
from ride_forces_analyzer.i18n import Language, get_language, tr
from ride_forces_analyzer.rendering.layouts.contracts import LayoutPosition
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    PROFILES,
)
from ride_forces_analyzer.rendering.preview import (
    ExportPreview,
    PreviewBackground,
    build_previews,
)
from ride_forces_analyzer.storage.export_models import SavedBatch, SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.ui.exports.batches import BatchDialog
from ride_forces_analyzer.ui.exports.labels import safe_region_label
from ride_forces_analyzer.ui.exports.preview import preview_pixmap
from ride_forces_analyzer.ui.exports.video import ExportDialog
from ride_forces_analyzer.ui.presentation.translation import set_ui_language
from tests.ui.helpers import wait_until


def test_selector_production_previews_summaries_and_stale_results(
    qapp: QApplication,
    qtbot: QtBot,
    manta: ExplorerData,
    export_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert manta.analysis is not None
    original_language = get_language()
    set_ui_language(qapp, Language.ENGLISH)
    parent = QWidget()
    qtbot.addWidget(parent)
    store = ExportStore(export_directory / "selector.sqlite3")
    dialog = ExportDialog(manta, 3600, 4099, parent, store=store)
    qtbot.addWidget(dialog)
    form = dialog.form
    modes = tuple(ExportSafeRegion)
    inactive_note = tr("Inactive — Portrait and Full frame only. Effective: Off.")
    accepted: list[ExportPreview] = []
    dialog.previews.ready.connect(accepted.append)
    started, release = Event(), Event()
    captured: list[ExportSettings] = []

    def delayed_previews(
        analysis: RecordingAnalysis,
        settings: ExportSettings,
        first: int,
        last: int,
        sample: int,
        background: PreviewBackground,
        positions: Mapping[ExportLayout, LayoutPosition],
    ) -> ExportPreview:
        captured.append(settings)
        if len(captured) == 1:
            started.set()
            assert release.wait(30)
        return build_previews(analysis, settings, first, last, sample, background, positions)

    def choose_layout(layout: ExportLayout) -> None:
        form.layout_profile.setCurrentIndex(
            next(index for index, (key, _) in enumerate(PROFILES) if key is layout),
        )

    def choose(mode: ExportSafeRegion) -> None:
        form.safe_region.setCurrentIndex(form.safe_region.findData(mode.value))
        assert form.settings().safe_region is mode
        assert dialog.review_fields["safe_region"].text() == safe_region_label(mode)

    def preview() -> ExportPreview:
        wait_until(lambda: dialog.previews.result is not None, timeout=40)
        result = dialog.previews.result
        assert result is not None and dialog.next.isEnabled()
        selected = next(p for p in result.profiles if p.layout is form.settings().layout)
        assert dialog.preview_view.source.toImage() == preview_pixmap(selected.image).toImage()
        for profile in result.profiles:
            button = dialog.profile_buttons[
                next(index for index, (key, _) in enumerate(PROFILES) if key is profile.layout)
            ]
            expected = QIcon(preview_pixmap(profile.image)).pixmap(button.iconSize()).toImage()
            assert button.icon().pixmap(button.iconSize()).toImage() == expected
        return result

    try:
        dialog.show()
        form.aspect.setCurrentIndex(1)
        choose_layout(ExportLayout.HUD)
        dialog.background.setCurrentIndex(
            dialog.background.findData(PreviewBackground.POV_TOUTATIS.value),
        )
        assert form.safe_region.count() == 4
        assert form.safe_region in dialog.controls
        assert form.safe_region.accessibleName() == "Safe Region"
        assert "cropping" in form.safe_region.accessibleDescription()
        assert form.safe_region.focusPolicy() & Qt.FocusPolicy.TabFocus
        assert isinstance(form.lateral_polarity, QLabel)
        assert form.lateral_polarity.text() == tr("Positive right, negative left")
        form_layout = form.findChild(QFormLayout)
        assert form_layout is not None
        label = form_layout.labelForField(form.safe_region)
        assert isinstance(label, QLabel) and label.buddy() is form.safe_region
        form.safe_region.setFocus()
        QTest.keyClick(form.safe_region, Qt.Key.Key_Down)
        assert form.settings().safe_region is modes[1]
        QTest.keyClick(form.safe_region, Qt.Key.Key_Up)
        assert form.settings().safe_region is modes[0]

        # Production frames feed both the main view and every gallery icon.
        images: dict[ExportLayout, list[str]] = {}
        presets: list[SavedPreset] = []
        for mode in modes:
            choose(mode)
            result = preview()
            for profile in result.profiles:
                images.setdefault(profile.layout, []).append(
                    sha256(profile.image.tobytes()).hexdigest(),
                )
            preset = make_preset(
                mode.value,
                form.settings(),
                11,
                "selection",
                manta.analysis.configuration,
            )
            presets.append(preset)
            store.save_preset(preset)
            assert dialog.safe_region_guidance.isHidden() is (mode is ExportSafeRegion.OFF)
        for layout, hashes in images.items():
            assert len(set(hashes)) == (2 if layout is ExportLayout.ORBIT else 4)
        store.save_batch(
            SavedBatch(
                schema_version=1,
                name="Four choices",
                jobs=tuple(
                    make_job(manta.analysis, preset, first=3600, last=4099) for preset in presets
                ),
            ),
        )
        dialog.presets.refresh()
        for preset in presets:
            dialog.presets.preset_selector.setCurrentText(preset.name)
            dialog.presets.preset_selector.activated.emit(
                dialog.presets.preset_selector.currentIndex(),
            )
            assert form.settings().safe_region is preset.settings.safe_region
            assert dialog.presets.preset_selector.toolTip() == tr(
                "Safe Region: {0}",
                safe_region_label(preset.settings.safe_region),
            )
        dialog.presets.manage_batches.click()
        batch = dialog.presets.batch_window
        assert isinstance(batch, BatchDialog)
        for row, mode in enumerate(modes):
            item = batch.table.item(row, 1)
            assert item is not None
            assert tr("Safe Region: {0}", safe_region_label(mode)) in item.text()
        batch.close()
        preview()

        # All directed transitions invalidate the accepted image immediately.
        for source in modes:
            choose(source)
            for target in modes:
                choose(source)
                revision = dialog.previews.revision
                choose(target)
                if source is not target:
                    assert dialog.previews.revision > revision
                    assert dialog.previews.result is None and not dialog.next.isEnabled()
        choose(modes[2])
        for layout, _title in PROFILES:
            if layout is ExportLayout.COLUMN:
                continue
            choose_layout(layout)
            assert form.settings().safe_region is modes[2]
            assert form.safe_region_note.isHidden() is (layout is not ExportLayout.ORBIT)
            if layout is ExportLayout.ORBIT:
                assert form.safe_region_note.text() == tr(
                    "For G-Orbit, A/B/C use the same arrangement.",
                )
            form.extent.setCurrentIndex(form.extent.findData(ExportExtent.CONTENT_AREA.value))
            if layout is not ExportLayout.HUD:
                assert form.settings().safe_region is ExportSafeRegion.OFF
                assert not form.safe_region.isEnabled()
                assert form.safe_region_note.text() == str(inactive_note)
                assert form.safe_region_note.isVisible()
                assert dialog.review_fields["safe_region"].text() == safe_region_label(modes[0])
            form.extent.setCurrentIndex(form.extent.findData(ExportExtent.FULL_FRAME.value))
            assert form.settings().safe_region is modes[2] and form.safe_region.isEnabled()
            form.aspect.setCurrentIndex(0)
            assert form.settings().safe_region is ExportSafeRegion.OFF
            assert not form.safe_region.isEnabled()
            assert form.safe_region_note.text() == str(inactive_note)
            form.aspect.setCurrentIndex(1)
            assert form.settings().safe_region is modes[2]
        choose_layout(ExportLayout.HUD)
        preview()

        # A real in-flight result must not replace a newer selector intent.
        monkeypatch.setattr(
            "ride_forces_analyzer.ui.exports.workers.build_previews",
            delayed_previews,
        )
        before = len(accepted)
        choose(modes[1])
        wait_until(started.is_set)
        for mode in (modes[3], modes[0], modes[2], modes[3]):
            choose(mode)
        release.set()
        preview()
        assert len(accepted) == before + 1
        assert [settings.safe_region for settings in captured] == [modes[1], modes[3]]

        # One native window covers translations, compact sizing and text scaling.
        directory = Path(".tmp/export-form-grouping")
        directory.mkdir(exist_ok=True)
        for language in Language:
            set_ui_language(qapp, language)
            QTest.qWait(30)
            assert form.safe_region.currentText() == safe_region_label(modes[3])
            assert form.safe_region.accessibleName() == tr("Safe Region")
            assert form.aspect.accessibleName() == tr("Image format")
            assert form.interval.accessibleName() == tr("Recording section")
            assert form.seconds.accessibleName() == tr("Plot time window")
            assert form.lateral_polarity.text() == tr("Positive right, negative left")
            assert form.gpu.text() == tr("Prefer NVIDIA GPU")
            column = next(
                index for index, (key, _) in enumerate(PROFILES) if key is ExportLayout.COLUMN
            )
            assert dialog.profile_buttons[column].toolTip() == tr("Landscape only")
            form.aspect.setCurrentIndex(0)
            assert form.safe_region_note.text() == str(inactive_note)
            QTest.qWait(30)
            assert form.grab().save(str(directory / f"{language}-inactive-form.png"))
            form.aspect.setCurrentIndex(1)
            preview()
            assert dialog.review_fields["safe_region"].text() == safe_region_label(modes[3])
            assert dialog.presets.preset_selector.toolTip() == tr(
                "Safe Region: {0}",
                safe_region_label(modes[3]),
            )
            for width, height in ((1240, 820), (1060, 720)):
                dialog.resize(width, height)
                QTest.qWait(30)
                assert (
                    form.safe_region.height()
                    == form.aspect.height()
                    == form.layout_profile.height()
                )
                assert form.safe_region.width() == form.aspect.width()
                assert form.safe_region.geometry().left() == form.aspect.geometry().left()
                assert (
                    form.safe_region.fontMetrics().horizontalAdvance(form.safe_region.currentText())
                    + 30
                    <= form.safe_region.width()
                )
                assert form.mode.width() >= form.mode.sizeHint().width()
                content_scroll = dialog.findChild(QScrollArea, "exportContentScroll")
                assert content_scroll is not None
                guidance_bottom = dialog.safe_region_guidance.mapTo(
                    content_scroll.viewport(),
                    dialog.safe_region_guidance.rect().bottomLeft(),
                ).y()
                assert guidance_bottom <= content_scroll.viewport().height()
                assert dialog.grab().save(str(directory / f"{language}-{width}.png"))
                form_scroll = dialog.pages.widget(0)
                assert isinstance(form_scroll, QScrollArea)
                form_scroll.ensureWidgetVisible(form.encoder)
                QTest.qWait(30)
                assert dialog.grab().save(str(directory / f"{language}-{width}-encoding.png"))
                form_scroll.verticalScrollBar().setValue(0)
                QTest.qWait(30)
            dialog.next.click()
            qapp.processEvents()
            assert dialog.review_fields["safe_region"].isVisible()
            assert dialog.safe_region_guidance.isVisible()
            assert dialog.grab().save(str(directory / f"{language}-review.png"))
            dialog.back.click()
        print(
            f"Native Windows selector session: DPR={dialog.devicePixelRatioF():g}; screenshots={directory}",
        )
    finally:
        release.set()
        dialog.close()
        QThreadPool.globalInstance().waitForDone()
        set_ui_language(qapp, original_language)
        qapp.processEvents()
