"""Versioned, immutable definitions for saved export presets and batch snapshots.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import asdict, replace
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ride_forces_analyzer.analysis.recording import AnalysisConfiguration, source_app_configuration
from ride_forces_analyzer.rendering.model import ExportSettings

RangeMode = Literal["markers", "selection", "entire"]


class SavedPreset(BaseModel, frozen=True, strict=True, extra="forbid"):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    settings: ExportSettings
    smoothing_window: int = Field(default=11, ge=1, le=51)
    range_mode: RangeMode = "markers"
    analysis_configuration: AnalysisConfiguration | None = None

    @property
    def configuration(self) -> AnalysisConfiguration:
        """Resolve legacy presets using the version-1 source-app policy and stored window."""
        if self.analysis_configuration is not None:
            return self.analysis_configuration
        configuration = source_app_configuration()
        return replace(
            configuration,
            smoothing=replace(
                configuration.smoothing,
                parameters=(("window_samples", self.smoothing_window),),
            ),
        )

    @model_validator(mode="after")
    def matching_window(self) -> Self:
        if self.analysis_configuration is not None:
            window = dict(self.analysis_configuration.smoothing.parameters).get(
                "window_samples",
                11,
            )
            if type(window) is not int or window != self.smoothing_window:
                raise ValueError("Analysis configuration and smoothing window must match")
        return self

    @field_serializer("analysis_configuration")
    def serialize_configuration(
        self,
        value: AnalysisConfiguration | None,
    ) -> dict[str, object] | None:
        """Serialize only the recipe; frozen profile mappings need an explicit JSON view."""
        if value is None:
            return None
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
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    jobs: tuple[BatchJob, ...] = ()

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def make_preset(
    name: str,
    settings: ExportSettings,
    smoothing_window: int,
    range_mode: RangeMode,
    analysis_configuration: AnalysisConfiguration | None = None,
) -> SavedPreset:
    return SavedPreset(
        name=name,
        settings=settings,
        smoothing_window=smoothing_window,
        range_mode=range_mode,
        analysis_configuration=analysis_configuration,
    )
