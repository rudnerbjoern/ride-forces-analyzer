"""Source-app direction projection; distinct from qualified physical-frame analysis.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words linalg

from ride_forces_analyzer.domain import Vector3


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
