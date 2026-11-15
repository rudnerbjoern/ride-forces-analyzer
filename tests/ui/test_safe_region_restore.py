"""Loaded preset/repeat choices survive form edits before selector integration."""

# cspell:words qtbot pytestqt

from pathlib import Path
import json

from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from ride_forces_analyzer.explorer import ExplorerData
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    VideoAspect,
    prepare_export,
)
from ride_forces_analyzer.storage.export_models import SavedPreset, make_preset
from ride_forces_analyzer.storage.exports import ExportStore
from ride_forces_analyzer.storage.preferences import Preferences
from ride_forces_analyzer.ui.exports.form import ExportForm


def test_captured_profile_survives_form_edits_save_and_unsupported_formats(
    qtbot: QtBot,
    manta: ExplorerData,
    export_directory: Path,
) -> None:
    assert manta.analysis is not None
    parent = QWidget()
    qtbot.addWidget(parent)
    form = ExportForm(manta, Preferences(export_directory / "preferences.sqlite3"), parent)
    store = ExportStore(export_directory / "exports.sqlite3")
    observed: list[ExportSafeRegion] = []
    form.changed.connect(lambda: observed.append(form.settings().safe_region))
    assert form.settings().safe_region is ExportSafeRegion.OFF
    for mode in ExportSafeRegion:
        settings = ExportSettings(
            layout=ExportLayout.RIBBON,
            aspect=VideoAspect.PORTRAIT,
            safe_region=mode,
        )
        snapshot = prepare_export(manta.analysis, settings, 3600, 3601).snapshot
        restored = SavedPreset(
            schema_version=1,
            name=mode.value,
            settings=snapshot.settings,
            smoothing_window=snapshot.smoothing_window,
            range_mode="selection",
            analysis_configuration=snapshot.analysis_configuration,
        )
        previous = len(observed)
        form.apply_preset(restored)
        assert len(observed) > previous and observed[-1] is mode
        assert form.settings().safe_region is mode
        form.seconds.setValue(30)
        captured = make_preset(
            mode.value,
            form.settings(),
            11,
            "selection",
            manta.analysis.configuration,
        )
        store.save_preset(captured)
        form.aspect.setCurrentIndex(0)
        assert form.settings().safe_region is ExportSafeRegion.OFF
        form.aspect.setCurrentIndex(1)
        assert form.settings().safe_region is mode
        form.extent.setCurrentIndex(form.extent.findData(ExportExtent.CONTENT_AREA.value))
        assert form.settings().safe_region is ExportSafeRegion.OFF
        form.extent.setCurrentIndex(form.extent.findData(ExportExtent.FULL_FRAME.value))
        assert form.settings().safe_region is mode
        assert captured.settings.safe_region is mode
    reloaded = ExportStore(store.path).presets()
    assert {preset.settings.safe_region for preset in reloaded} == set(ExportSafeRegion)
    legacy = json.loads(
        next(
            preset
            for preset in reloaded
            if preset.settings.safe_region is ExportSafeRegion.PORTRAIT_SOCIAL_C
        ).model_dump_json(),
    )
    legacy["settings"].pop("safe_region")
    previous = len(observed)
    form.apply_preset(SavedPreset.model_validate_json(json.dumps(legacy)))
    assert form.settings().safe_region is ExportSafeRegion.OFF
    assert len(observed) > previous and observed[-1] is ExportSafeRegion.OFF
