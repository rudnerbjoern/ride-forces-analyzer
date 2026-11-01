"""Versioned, immutable definitions for saved export presets and batch snapshots.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import replace
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

from ride_forces_analyzer.analysis.recording import AnalysisConfiguration
from ride_forces_analyzer.analysis.calibration import CalibrationOverrides
from ride_forces_analyzer.domain.metadata import RecordingAdditions
from ride_forces_analyzer.rendering.model import ExportSettings, analysis_configuration_metadata
from ride_forces_analyzer.rendering.layouts import registry

RangeMode = Literal["markers", "selection", "entire"]


class SavedPreset(BaseModel, frozen=True, strict=True, extra="forbid"):
    """Saved preset contract and owned data.

    Attributes:
        schema_version: Version identifying the admitted source or stored document
            contract.
        name: Stable identifier or displayed name for this model or view.
        settings: Validated settings controlling this operation.
        smoothing_window: Odd number of source samples used for smoothing.
        range_mode: Policy selecting the export sample interval.
        analysis_configuration: Analysis settings captured for the operation.
    """

    schema_version: Literal[1]
    name: str = Field(min_length=1, max_length=120)
    settings: ExportSettings
    smoothing_window: int = Field(ge=1, le=51)
    range_mode: RangeMode
    analysis_configuration: AnalysisConfiguration

    @field_validator("settings")
    @classmethod
    def explicit_position(cls, value: ExportSettings) -> ExportSettings:
        """Bind implicit placement to its current named default for saved snapshots.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            Export settings with the selected layout's default placement made explicit.
        """
        if value.position is not None:
            return value
        plugin = registry.PLUGINS[value.layout]
        positions = plugin.positions(value.aspect)
        return replace(value, position=positions.default)

    @field_validator("analysis_configuration", mode="before")
    @classmethod
    def decode_configuration(cls, value: object, info: ValidationInfo) -> object:
        """Decode stored analysis recipes using declared defaults for omitted fields.

        Args:
            value: Candidate value to validate, format or store.
            info: Prepared information for the operation.

        Returns:
            Validated JSON configuration, or unchanged Python input for strict validation.

        Raises:
            ValueError: Required fields are missing or supplied values are invalid.
        """
        if isinstance(value, dict):
            recipe = cast(dict[str, object], value)
            if info.mode == "json":
                return TypeAdapter(AnalysisConfiguration).validate_json(
                    json.dumps(recipe),
                    strict=True,
                )
            return recipe
        return value

    @model_validator(mode="after")
    def matching_window(self) -> Self:
        """Require the saved smoothing window to match the analysis recipe.

        Returns:
            The validated preset itself.

        Raises:
            ValueError: Analysis configuration and smoothing window must match.
        """
        window = dict(self.analysis_configuration.smoothing.parameters).get("window_samples", 11)
        if type(window) is not int or window != self.smoothing_window:
            raise ValueError("Analysis configuration and smoothing window must match")
        return self

    @field_serializer("analysis_configuration")
    def serialize_configuration(
        self,
        value: AnalysisConfiguration,
    ) -> dict[str, object]:
        """Serialize only the recipe; frozen profile mappings need an explicit JSON view.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            JSON-compatible analysis configuration.
        """
        return analysis_configuration_metadata(value)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        """Trim surrounding whitespace from a supplied name.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            Trimmed string, or the original value for subsequent type validation.
        """
        return value.strip() if isinstance(value, str) else value

    @field_validator("smoothing_window")
    @classmethod
    def odd_window(cls, value: int) -> int:
        """Require a positive odd smoothing-window size.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            Validated positive odd window size.

        Raises:
            ValueError: Smoothing must be an odd sample count.
        """
        if value % 2 == 0:
            raise ValueError("Smoothing must be an odd sample count")
        return value


class BatchJob(BaseModel, frozen=True, strict=True, extra="forbid"):
    """Batch job contract and owned data.

    Attributes:
        recording_path: Path of the source recording used by the saved job.
        source_sha256: SHA-256 identity of the original recording bytes.
        ride: Recording name or resolved recording for this export job.
        preset: Validated immutable export preset to store or apply.
        range_mode: Policy selecting the export sample interval.
        first_sample: First included source sample index, when the job uses explicit
            bounds.
        last_sample: Last included source sample index, when the job uses explicit bounds.
        metadata_additions: Captured user additions; legacy jobs retain original metadata.
    """

    recording_path: Path
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ride: str
    preset: SavedPreset
    range_mode: RangeMode
    first_sample: int = Field(ge=0)
    last_sample: int = Field(ge=0)
    metadata_additions: RecordingAdditions | None = None

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        """Require the final source sample to follow the first sample.

        Returns:
            The validated inclusive range itself.

        Raises:
            ValueError: Last sample must not precede first sample. Batch recordings require
                absolute file paths.
        """
        if self.last_sample < self.first_sample:
            raise ValueError("Last sample must not precede first sample")
        if not self.recording_path.is_absolute():
            raise ValueError("Batch recordings require absolute file paths")
        return self


class SavedBatch(BaseModel, frozen=True, strict=True, extra="forbid"):
    """Saved batch contract and owned data.

    Attributes:
        schema_version: Version identifying the admitted source or stored document
            contract.
        name: Stable identifier or displayed name for this model or view.
        jobs: Immutable video jobs in their selected execution order.
    """

    schema_version: Literal[1]
    name: str = Field(min_length=1, max_length=120)
    jobs: tuple[BatchJob, ...]

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: object) -> object:
        """Trim surrounding whitespace from a supplied name.

        Args:
            value: Candidate value to validate, format or store.

        Returns:
            Trimmed string, or the original value for subsequent type validation.
        """
        return value.strip() if isinstance(value, str) else value


def make_preset(
    name: str,
    settings: ExportSettings,
    smoothing_window: int,
    range_mode: RangeMode,
    analysis_configuration: AnalysisConfiguration,
) -> SavedPreset:
    """Capture visual settings and a portable analysis recipe in a named preset.

    Args:
        name: Display name or identifier used to select the requested item.
        settings: Validated settings controlling this operation.
        smoothing_window: Odd number of source samples used for smoothing.
        range_mode: Policy selecting the export sample interval.
        analysis_configuration: Analysis settings captured for the operation.

    Returns:
        Saved preset with recording-specific markers removed from its portable analysis
        recipe.
    """
    return SavedPreset(
        schema_version=1,
        name=name,
        settings=settings,
        smoothing_window=smoothing_window,
        range_mode=range_mode,
        analysis_configuration=replace(
            analysis_configuration,
            ride_bounds=None,
            calibration=CalibrationOverrides(),
        ),
    )
