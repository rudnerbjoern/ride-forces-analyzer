"""Calibration from supplied source directions for any successfully imported recording.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words linalg orthogonalized

from dataclasses import dataclass, replace
from datetime import datetime
from importlib.util import find_spec
from importlib.metadata import version


from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.importers import ImportSuccess

MANTA_SHA256 = "30cf81c360cb28f45ee97234779689bdcdd7ec3aa8fa148645a4b015771be6c6"
REFERENCE_ALGORITHM = "source-direction-unit-projection-centered-mean-11-v1"


def project_directions(
    samples: tuple[Vector3, ...],
    directions: tuple[Vector3, Vector3, Vector3],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Normalize rounded source directions explicitly, then dot-project, without rotation repair."""
    import numpy as np

    rows = np.array([(v.x, v.y, v.z) for v in directions], dtype=np.float64)
    # Three-decimal rounding admits <= sqrt(3)*0.0005 vector error.
    # This gate admits that storage precision, not arbitrary calibration defects.
    if np.max(np.abs(rows @ rows.T - np.eye(3))) > 0.003 or np.linalg.det(rows) <= 0:
        raise ValueError("Directions exceed the declared rounded-basis admission bounds")
    rows /= np.linalg.norm(rows, axis=1)[:, None]
    values = np.array([(v.x, v.y, v.z) for v in samples], dtype=np.float64) @ rows.T
    if not np.isfinite(values).all():
        raise ValueError("Direction projection exceeds finite display range")
    return (
        tuple(float(v) for v in values[:, 0]),
        tuple(float(v) for v in values[:, 1]),
        tuple(float(v) for v in values[:, 2]),
    )


def centered_mean(values: tuple[float, ...], window: int) -> tuple[float, ...]:
    """Centered odd-window mean; truncate and renormalize at recording edges."""
    if type(window) is not int or window < 1 or window > 51 or window % 2 == 0:
        raise ValueError("Smoothing window must be an odd integer from 1 through 51")
    if not values:
        raise ValueError("Reference smoothing requires samples")
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    weights = np.ones(window, dtype=np.float64)
    half = window // 2
    result = (
        np.convolve(array, weights, mode="full")[half : half + len(values)]
        / np.convolve(
            np.ones(len(values)),
            weights,
            mode="full",
        )[half : half + len(values)]
    )
    if not np.isfinite(result).all():
        raise ValueError("Reference smoothing exceeds finite display range")
    return tuple(float(v) for v in result)


def centered_mean_11(values: tuple[float, ...]) -> tuple[float, ...]:
    """Compatibility entry point for the independently compared default window."""
    return centered_mean(values, 11)


@dataclass(frozen=True, slots=True)
class AppReference:
    source_sha256: str
    calculation_time: datetime
    raw_projection: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    channels: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
    source_directions: tuple[Vector3, Vector3, Vector3]
    sample_rate: float
    numpy_version: str
    smoothing_window: int = 11
    algorithm: str = REFERENCE_ALGORITHM
    time_basis: str = "INFERRED_UNIFORM"
    confirmed_contracts: tuple[str, ...] = (
        "Source acceleration scale is interpreted as g under the owner-adopted import policy",
        "Three-decimal direction rows explicitly normalized individually; not orthogonalized",
        "Centered 11-sample mean; truncated renormalized recording edges are owner-adopted policy",
        "Source direction signs follow the supplied vertical/lateral/longitudinal vectors",
    )
    capability: str = "VERIFIED"
    unit: str = "g"
    references: tuple[str, ...] = (
        "Owner enabled calibrated forces for all importable recordings, 2026-10-17",
        "ADR-0006: unit source-direction projection and centered 11-sample mean",
    )


def reconstruct_app_reference(
    source: ImportSuccess,
    *,
    calculation_time: datetime,
) -> AppReference | None:
    """Apply the owner-selected processing policy without filename or source-hash gates."""
    if find_spec("numpy") is None:
        return None
    if calculation_time.utcoffset() is None:
        raise ValueError("Calculation time must have a timezone")
    vectors = source.recording.vectors
    vertical, lateral, longitudinal = (
        vectors.vertical_direction,
        vectors.lateral_direction,
        vectors.longitudinal_direction,
    )
    if vertical is None or lateral is None or longitudinal is None:
        raise ValueError("Reference source directions are incomplete")
    raw = project_directions(
        source.recording.motion.acceleration,
        (vertical, lateral, longitudinal),
    )
    channels = centered_mean_11(raw[0]), centered_mean_11(raw[1]), centered_mean_11(raw[2])
    return AppReference(
        source.source_sha256,
        calculation_time,
        raw,
        channels,
        (vertical, lateral, longitudinal),
        source.recording.motion.sample_rate.value,
        version("numpy"),
        capability="VERIFIED" if source.source_sha256 == MANTA_SHA256 else "PROVISIONAL",
    )


def smooth_reference(
    reference: AppReference,
    window: int,
    *,
    calculation_time: datetime,
) -> AppReference:
    """Always smooth the unchanged projection, never previously filtered channels."""
    if calculation_time.utcoffset() is None:
        raise ValueError("Calculation time must have a timezone")
    raw = reference.raw_projection
    channels = (
        centered_mean(raw[0], window),
        centered_mean(raw[1], window),
        centered_mean(raw[2], window),
    )
    return replace(
        reference,
        channels=channels,
        smoothing_window=window,
        calculation_time=calculation_time,
        algorithm=f"source-direction-unit-projection-centered-mean-{window}-v1",
        capability="VERIFIED"
        if reference.source_sha256 == MANTA_SHA256 and window == 11
        else "PROVISIONAL",
        confirmed_contracts=tuple(
            contract
            for contract in reference.confirmed_contracts
            if not contract.startswith("Centered")
        )
        + (f"Centered {window}-sample mean; truncated renormalized recording edges",),
    )
