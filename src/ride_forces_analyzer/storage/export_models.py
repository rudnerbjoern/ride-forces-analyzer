"""Versioned, immutable definitions for saved export presets and batch snapshots."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ride_forces_analyzer.rendering.model import ExportSettings

RangeMode = Literal["markers", "selection", "entire"]


class SavedPreset(BaseModel, frozen=True, strict=True, extra="forbid"):
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    settings: ExportSettings
    smoothing_window: int = Field(default=11, ge=1, le=51)
    range_mode: RangeMode = "markers"

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
) -> SavedPreset:
    return SavedPreset(
        name=name,
        settings=settings,
        smoothing_window=smoothing_window,
        range_mode=range_mode,
    )
