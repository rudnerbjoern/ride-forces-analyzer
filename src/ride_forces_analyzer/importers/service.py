"""FR-028–030: offline, read-only import of supported recordings into domain models.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

from ride_forces_analyzer.domain import Recording

from ._diagnostic_budget import DiagnosticBudget, DiagnosticBudgetExceeded
from .decoder import DecodeResult, decode_forces, decode_forces_bytes
from .limits import DEFAULT_LIMITS, ImportLimits
from .motion import validate_motion
from .optional import validate_optional_data
from .result import ImportFailure, ImportResult, ImportSuccess


def _complete(decoded: DecodeResult, limits: ImportLimits) -> ImportResult:
    if isinstance(decoded, ImportFailure):
        return decoded
    source = decoded.source
    diagnostics = DiagnosticBudget(limits.max_diagnostics)
    try:
        motion = validate_motion(source, diagnostics)
        if isinstance(motion, ImportFailure):
            return motion
        optional = validate_optional_data(source, diagnostics)
        if isinstance(optional, ImportFailure):
            return optional
    except DiagnosticBudgetExceeded:
        return diagnostics.failure(source)
    recording = Recording(
        decoded.schema_version,
        source,
        motion.motion,
        motion.indices,
        source_format=decoded.source_format,
        metadata=optional.metadata,
        attributes=optional.attributes if optional.attributes is not None else (),
        vectors=motion.vectors,
        gps=optional.gps,
        gps_status=optional.gps_status,
        smoothing_factor=optional.smoothing_factor,
        max_force=optional.max_force,
        min_force=optional.min_force,
    )
    return ImportSuccess(recording, diagnostics.records)


def import_forces(path: Path, *, limits: ImportLimits = DEFAULT_LIMITS) -> ImportResult:
    """Read a bounded local original without writes and import its available capabilities.

    Args:
        path: Filesystem path read or written by this operation.
        limits: Resource limits applied to the operation.

    Returns:
        Imported recording and capability diagnostics, or a structured import failure.
    """
    return _complete(decode_forces(path, limits=limits), limits)


def import_forces_bytes(
    data: bytes,
    *,
    compressed: bool = False,
    limits: ImportLimits = DEFAULT_LIMITS,
) -> ImportResult:
    """Import exact immutable bytes without filesystem or network access.

    Args:
        data: Input data in the representation declared by the parameter type.
        compressed: Decode zforces bytes with the existing bounded Raw-DEFLATE decoder.
        limits: Resource limits applied to the operation.

    Returns:
        Imported recording and capability diagnostics, or a structured import failure.

    Raises:
        TypeError: Data is not immutable bytes or compressed is not a bool.
        ValueError: Limits is not an ImportLimits instance.
    """
    return _complete(decode_forces_bytes(data, compressed=compressed, limits=limits), limits)
