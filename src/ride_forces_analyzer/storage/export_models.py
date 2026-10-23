"""Versioned, immutable definitions for saved export presets and batch snapshots.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import asdict, fields, replace
from pathlib import Path
import json
from typing import Literal, Self, cast

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    TypeAdapter,
    field_serializer,
    field_validator,
    model_validator,
)

from ride_forces_analyzer.analysis.recording import AnalysisConfiguration, StageConfiguration
from ride_forces_analyzer.analysis.models import AnalysisProfile
from ride_forces_analyzer.rendering.model import ExportSettings
from ride_forces_analyzer.rendering.layouts import registry

RangeMode = Literal["markers", "selection", "entire"]


def _require_fields(value: object, required: set[str], label: str) -> None:
    """Reject incomplete stored objects; typed objects may use new-object defaults."""
    if isinstance(value, dict):
        missing = required - cast(dict[str, object], value).keys()
        if missing:
            raise ValueError(f"{label} is incomplete; missing fields: {', '.join(sorted(missing))}")


class SavedPreset(BaseModel, frozen=True, strict=True, extra="forbid"):
    schema_version: Literal[1]
    name: str = Field(min_length=1, max_length=120)
    settings: ExportSettings
    smoothing_window: int = Field(ge=1, le=51)
    range_mode: RangeMode
    analysis_configuration: AnalysisConfiguration

    @field_validator("settings", mode="before")
    @classmethod
    def complete_settings(cls, value: object) -> object:
        _require_fields(value, {item.name for item in fields(ExportSettings)}, "Export settings")
        return value

    @field_validator("settings")
    @classmethod
    def explicit_position(cls, value: ExportSettings) -> ExportSettings:
        """Bind implicit placement to its current named default for saved snapshots."""
        if value.position is not None:
            return value
        plugin = registry.PLUGINS[value.layout]
        positions = plugin.landscape if value.aspect == "landscape" else plugin.portrait
        return replace(value, position=positions.default)

    @field_validator("analysis_configuration", mode="before")
    @classmethod
    def complete_configuration(cls, value: object, info: ValidationInfo) -> object:
        _require_fields(
            value,
            {item.name for item in fields(AnalysisConfiguration)} - {"ride_bounds"},
            "Analysis recipe",
        )
        if isinstance(value, dict):
            recipe = cast(dict[str, object], value)
            _require_fields(
                recipe.get("profile"),
                {item.name for item in fields(AnalysisProfile)},
                "Analysis profile",
            )
            for name in ("projection", "smoothing", "orientation", "context", "events"):
                _require_fields(
                    recipe.get(name),
                    {item.name for item in fields(StageConfiguration)},
                    "Analysis stage",
                )
            if info.mode == "json":
                return TypeAdapter(AnalysisConfiguration).validate_json(
                    json.dumps(recipe),
                    strict=True,
                )
            return recipe
        return value

    @model_validator(mode="after")
    def matching_window(self) -> Self:
        window = dict(self.analysis_configuration.smoothing.parameters).get("window_samples", 11)
        if type(window) is not int or window != self.smoothing_window:
            raise ValueError("Analysis configuration and smoothing window must match")
        return self

    @field_serializer("analysis_configuration")
    def serialize_configuration(
        self,
        value: AnalysisConfiguration,
    ) -> dict[str, object]:
        """Serialize only the recipe; frozen profile mappings need an explicit JSON view."""
        profile = value.profile
        return {
            "profile": {
                "name": profile.name,
                "schema_version": profile.schema_version,
                "configuration": dict(profile.configuration),
                "policy_references": profile.policy_references,
                "assumptions": profile.assumptions,
                "allow_provisional": profile.allow_provisional,
            },
            "projection": asdict(value.projection),
            "smoothing": asdict(value.smoothing),
            "orientation": asdict(value.orientation),
            "context": asdict(value.context),
            "events": asdict(value.events) if value.events is not None else None,
            "context_input": value.context_input,
            "events_input": value.events_input,
            "ride_bounds": value.ride_bounds,
            "calibration": asdict(value.calibration),
        }

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("smoothing_window")
    @classmethod
    def odd_window(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("Smoothing must be an odd sample count")
        return value


class BatchJob(BaseModel, frozen=True, strict=True, extra="forbid"):
    recording_path: Path
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ride: str
    preset: SavedPreset
    range_mode: RangeMode
    first_sample: int = Field(ge=0)
    last_sample: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if self.last_sample < self.first_sample:
            raise ValueError("Last sample must not precede first sample")
        if not self.recording_path.is_absolute():
            raise ValueError("Batch recordings require absolute file paths")
        return self


class SavedBatch(BaseModel, frozen=True, strict=True, extra="forbid"):
    schema_version: Literal[1]
    name: str = Field(min_length=1, max_length=120)
    jobs: tuple[BatchJob, ...]

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def make_preset(
    name: str,
    settings: ExportSettings,
    smoothing_window: int,
    range_mode: RangeMode,
    analysis_configuration: AnalysisConfiguration,
) -> SavedPreset:
    return SavedPreset(
        schema_version=1,
        name=name,
        settings=settings,
        smoothing_window=smoothing_window,
        range_mode=range_mode,
        analysis_configuration=replace(analysis_configuration, ride_bounds=None),
    )
