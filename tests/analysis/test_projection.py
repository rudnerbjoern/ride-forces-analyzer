"""Source-app projection polarity and rounded-basis admission contracts."""

import pytest

from ride_forces_analyzer.analysis.projection import project_directions
from ride_forces_analyzer.domain import Vector3


def test_projection_and_explicit_rounded_direction_normalization() -> None:
    directions = (Vector3(0, 0.999, 0), Vector3(0, 0, 1), Vector3(1, 0, 0))
    values = project_directions((Vector3(2, -3, 4),), directions)
    assert values == ((-3.0,), (4.0,), (2.0,))
    with pytest.raises(ValueError):
        project_directions((Vector3(1, 2, 3),), (directions[0], directions[0], directions[2]))
    with pytest.raises(ValueError):
        project_directions((Vector3(1, 2, 3),), (Vector3(0, -1, 0), directions[1], directions[2]))
