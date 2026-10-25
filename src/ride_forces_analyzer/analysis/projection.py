"""Source-app direction projection; distinct from qualified physical-frame analysis.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words linalg

from ride_forces_analyzer.domain import Recording, RecordingFormat, Vector3


def source_directions(
    recording: Recording,
) -> tuple[Vector3 | None, Vector3 | None, Vector3 | None]:
    """Select provisional vertical/lateral/longitudinal inputs without changing source fields.

    The observed RFDB profile uses calibration Y/X/Z for the same source-app
    axes. Admission and normalization remain in project_directions.

    Args:
        recording: Validated recording whose original source data remains unchanged.

    Returns:
        The tuple[Vector3 | None, Vector3 | None, Vector3 | None] result of the operation
        described above.
    """
    vectors = recording.vectors
    if recording.source_format is RecordingFormat.RFDB:
        return vectors.y_calibration, vectors.x_calibration, vectors.z_calibration
    return vectors.vertical_direction, vectors.lateral_direction, vectors.longitudinal_direction


def project_directions(
    samples: tuple[Vector3, ...],
    directions: tuple[Vector3, Vector3, Vector3],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Normalize rounded source directions explicitly, then dot-project, without rotation repair.

    Args:
        samples: Sample values in the declared source or analysis representation.
        directions: Projection directions in the source frame.

    Returns:
        The tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]] result of the
        operation described above.

    Raises:
        ValueError: Directions exceed the declared rounded-basis admission bounds.
            Direction projection exceeds finite display range.
    """
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
