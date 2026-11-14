"""Typed Safe Region compatibility and saved-settings serialization contracts."""

from dataclasses import FrozenInstanceError, replace
import json
from typing import cast

from pydantic import TypeAdapter, ValidationError
import pytest

from ride_forces_analyzer.analysis.preparation import source_app_configuration
from ride_forces_analyzer.rendering.layouts import resolve_geometry
from ride_forces_analyzer.rendering.model import (
    ExportExtent,
    ExportLayout,
    ExportSafeRegion,
    ExportSettings,
    VideoAspect,
)
from ride_forces_analyzer.storage.export_models import SavedPreset


@pytest.mark.parametrize("layout", list(ExportLayout))
@pytest.mark.parametrize("aspect", list(VideoAspect))
@pytest.mark.parametrize("extent", list(ExportExtent))
def test_legacy_settings_default_to_off_without_changing_existing_geometry(
    layout: ExportLayout,
    aspect: VideoAspect,
    extent: ExportExtent,
) -> None:
    if (layout is ExportLayout.COLUMN and aspect is VideoAspect.PORTRAIT) or (
        layout is ExportLayout.HUD and extent is ExportExtent.CONTENT_AREA
    ):
        pytest.skip("Unsupported existing layout combination")
    original = ExportSettings(layout=layout, aspect=aspect, extent=extent)
    adapter = TypeAdapter(ExportSettings)
    payload = json.loads(adapter.dump_json(original))
    del payload["safe_region"]
    restored = adapter.validate_json(json.dumps(payload), strict=True)
    assert restored.safe_region is ExportSafeRegion.OFF
    assert restored == original
    assert restored.dimensions == original.dimensions
    assert resolve_geometry(restored) == resolve_geometry(original)


@pytest.mark.parametrize(
    "layout",
    [ExportLayout.HUD, ExportLayout.RIBBON, ExportLayout.CORNERS, ExportLayout.ORBIT],
)
@pytest.mark.parametrize(
    "mode,stored",
    [
        (ExportSafeRegion.OFF, "off"),
        (ExportSafeRegion.PORTRAIT_SOCIAL_A, "portrait_social_a"),
        (ExportSafeRegion.PORTRAIT_SOCIAL_B, "portrait_social_b"),
        (ExportSafeRegion.PORTRAIT_SOCIAL_C, "portrait_social_c"),
    ],
)
def test_safe_region_round_trips_through_saved_settings(
    layout: ExportLayout,
    mode: ExportSafeRegion,
    stored: str,
) -> None:
    settings = ExportSettings(layout=layout, aspect=VideoAspect.PORTRAIT, safe_region=mode)
    preset = SavedPreset(
        schema_version=1,
        name="Portrait",
        settings=settings,
        smoothing_window=11,
        range_mode="markers",
        analysis_configuration=source_app_configuration(),
    )
    payload = preset.model_dump_json()
    assert json.loads(payload)["settings"]["safe_region"] == stored
    restored = SavedPreset.model_validate_json(payload)
    assert restored == preset
    assert restored.settings.safe_region is mode
    with pytest.raises(FrozenInstanceError):
        setattr(restored.settings, "safe_region", ExportSafeRegion.OFF)


@pytest.mark.parametrize(
    "value",
    [
        "off",
        "portrait_social_a",
        "portrait_social_b",
        "portrait_social_c",
        "unknown",
        True,
        False,
        0,
        1,
        None,
        {},
        [],
    ],
)
def test_constructor_requires_a_typed_safe_region_member(value: object) -> None:
    with pytest.raises(ValueError, match="Unknown export Safe Region mode"):
        ExportSettings(safe_region=cast(ExportSafeRegion, value))


@pytest.mark.parametrize(
    "value",
    [
        "unknown",
        "portrait_social",
        "portrait_social_d",
        "PORTRAIT_SOCIAL_A",
        "",
        True,
        False,
        0,
        1,
        1.0,
        None,
        {},
        [],
    ],
)
def test_stored_settings_reject_unknown_profiles_and_wrong_types(value: object) -> None:
    payload = {"layout": "hud", "aspect": "portrait", "safe_region": value}
    with pytest.raises(ValidationError, match="safe_region"):
        TypeAdapter(ExportSettings).validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize(
    "mode",
    [
        ExportSafeRegion.PORTRAIT_SOCIAL_A,
        ExportSafeRegion.PORTRAIT_SOCIAL_B,
        ExportSafeRegion.PORTRAIT_SOCIAL_C,
    ],
)
@pytest.mark.parametrize(
    "aspect,extent",
    [
        (VideoAspect.LANDSCAPE, ExportExtent.FULL_FRAME),
        (VideoAspect.LANDSCAPE, ExportExtent.CONTENT_AREA),
        (VideoAspect.PORTRAIT, ExportExtent.CONTENT_AREA),
    ],
)
def test_profile_rejects_ineligible_combinations_in_python_and_json(
    mode: ExportSafeRegion,
    aspect: VideoAspect,
    extent: ExportExtent,
) -> None:
    off = ExportSettings(layout=ExportLayout.RIBBON, aspect=aspect, extent=extent)
    with pytest.raises(ValueError, match="Safe Region requires Portrait Full frame"):
        replace(off, safe_region=mode)
    adapter = TypeAdapter(ExportSettings)
    payload = json.loads(adapter.dump_json(off))
    payload["safe_region"] = mode.value
    with pytest.raises(ValidationError, match="Safe Region requires Portrait Full frame"):
        adapter.validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize(
    "mode",
    [
        ExportSafeRegion.PORTRAIT_SOCIAL_A,
        ExportSafeRegion.PORTRAIT_SOCIAL_B,
        ExportSafeRegion.PORTRAIT_SOCIAL_C,
    ],
)
def test_profile_does_not_enable_a_landscape_only_layout_in_portrait(
    mode: ExportSafeRegion,
) -> None:
    with pytest.raises(ValueError, match="Unsupported export format"):
        ExportSettings(
            layout=ExportLayout.COLUMN,
            aspect=VideoAspect.PORTRAIT,
            safe_region=mode,
        )
