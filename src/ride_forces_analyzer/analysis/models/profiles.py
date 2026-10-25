"""Analysis profiles, scalar parameters and explicit scientific-policy assumptions.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from types import MappingProxyType


from ride_forces_analyzer.validation.checks import has_type

from ride_forces_analyzer.validation.checks import (
    validate_text as _text,
    text_values as _texts,
    validate_enum as _enum,
)


type ParameterValue = None | bool | str | int | float


class ProfileName(StrEnum):
    """Profile name contract and owned data.

    Attributes:
        RAW_DEVICE_ONLY: Named value for raw device only (`raw_device_only`).
        DEVICE_VECTORS: Named value for device vectors (`device_vectors`).
        RIDER_CALIBRATED: Named value for rider calibrated (`rider_calibrated`).
        GPS_EXPLORATORY: Named value for gps exploratory (`gps_exploratory`).
        GPS_STRICT: Named value for gps strict (`gps_strict`).
    """

    RAW_DEVICE_ONLY = "raw_device_only"
    DEVICE_VECTORS = "device_vectors"
    RIDER_CALIBRATED = "rider_calibrated"
    GPS_EXPLORATORY = "gps_exploratory"
    GPS_STRICT = "gps_strict"


@dataclass(frozen=True, slots=True)
class AnalysisProfile:
    """Analysis profile contract and owned data.

    Attributes:
        name: Stable identifier or displayed name for this model or view.
        schema_version: Version identifying the admitted source or stored document
            contract.
        configuration: Requested immutable analysis or export configuration.
        policy_references: References supporting the selected scientific policy.
        assumptions: Explicit assumptions admitted by this analysis profile.
        allow_provisional: Whether the profile permits explicitly provisional results.
    """

    name: ProfileName = ProfileName.RAW_DEVICE_ONLY
    schema_version: str = "1"
    configuration: Mapping[str, ParameterValue] = field(default_factory=dict[str, ParameterValue])
    policy_references: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    allow_provisional: bool = False

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            TypeError: Provisional permission must be explicit boolean. Profile configuration
                must be a scalar-valued mapping. Configuration values must be immutable
                scalars.
            ValueError: Configuration numbers must be finite. The raw default cannot enable
                assumptions or processing settings. Non-default profiles require explicit
                reviewed-policy references. Provisional profiles require named assumptions.
        """
        _enum(self.name, ProfileName)
        _text(self.schema_version, "Profile schema")
        if type(self.allow_provisional) is not bool:
            raise TypeError("Provisional permission must be explicit boolean")
        if not has_type(self.configuration, Mapping):
            raise TypeError("Profile configuration must be a scalar-valued mapping")
        copied: dict[str, ParameterValue] = {}
        for key, value in self.configuration.items():
            _text(key, "Configuration key")
            if value is not None and type(value) not in (bool, str, int, float):
                raise TypeError("Configuration values must be immutable scalars")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError("Configuration numbers must be finite")
            copied[key] = value
        object.__setattr__(self, "configuration", MappingProxyType(dict(sorted(copied.items()))))
        for name in ("policy_references", "assumptions"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        if self.name is ProfileName.RAW_DEVICE_ONLY:
            if self.allow_provisional or self.assumptions or self.configuration:
                raise ValueError("The raw default cannot enable assumptions or processing settings")
        elif not self.policy_references:
            raise ValueError("Non-default profiles require explicit reviewed-policy references")
        if self.allow_provisional and not self.assumptions:
            raise ValueError("Provisional profiles require named assumptions")
