"""Source-time peak hold envelopes, independent of frame order and video rate.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True, slots=True)
class PeakEnvelope:
    """Hold positive and negative force peaks using deterministic source-time states.

    Attributes:
        first: First included source index or the control selecting that bound.
        rate: Sample or frame rate per second, as declared by this operation.
        states: Prepared peak states aligned with source time.
        release_g_per_second: Rate in g per second at which a held peak returns toward the
            measured value.
    """

    first: int
    rate: float
    states: tuple[tuple[float, float, float, float] | None, ...]
    release_g_per_second: float = 1.0

    @classmethod
    def prepare(
        cls,
        values: Sequence[float | None],
        first: int,
        last: int,
        rate: float,
        *,
        hold_seconds: float = 1.5,
        release_g_per_second: float = 1.0,
    ) -> "PeakEnvelope":
        """Prepare immutable source-time values for repeated presentation queries.

        Args:
            values: Values to format, validate or add in their supplied order.
            first: First included source sample index.
            last: Last included source sample index.
            rate: Sample or frame rate per second, as declared by this operation.
            hold_seconds: Duration in seconds for which a peak is retained.
            release_g_per_second: Rate in g per second at which a held peak returns toward the
                measured value.

        Returns:
            Immutable source-time states prepared for repeated queries over the selected
            interval.

        Raises:
            ValueError: Peak hold duration must be finite and nonnegative. Peak release speed
                must be finite and positive.
        """
        if not isfinite(hold_seconds) or hold_seconds < 0:
            raise ValueError("Peak hold duration must be finite and nonnegative")
        if not isfinite(release_g_per_second) or release_g_per_second <= 0:
            raise ValueError("Peak release speed must be finite and positive")
        states: list[tuple[float, float, float, float] | None] = []
        positive = negative = 0.0
        positive_release = negative_release = float(first)
        for index in range(first, last + 1):
            value = values[index]
            if value is None:
                positive = negative = 0.0
                positive_release = negative_release = float(index)
                states.append(None)
                continue
            positive = max(
                0.0,
                positive
                - max(0.0, index - max(index - 1, positive_release)) / rate * release_g_per_second,
            )
            negative = max(
                0.0,
                negative
                - max(0.0, index - max(index - 1, negative_release)) / rate * release_g_per_second,
            )
            if value > 0 and value >= positive:
                positive, positive_release = value, index + hold_seconds * rate
            if value < 0 and -value >= negative:
                negative, negative_release = -value, index + hold_seconds * rate
            states.append((positive, negative, positive_release, negative_release))
        return cls(first, rate, tuple(states), release_g_per_second)

    def at(self, position: float, current: float | None) -> tuple[float, float]:
        """Read the prepared state at the requested source-sample position.

        Args:
            position: Fractional source-sample position.
            current: Current measured value or operation state.

        Returns:
            Prepared state at the requested source-sample position, adjusted according to the
            query contract.
        """
        if current is None:
            return 0.0, 0.0
        index = floor(position)
        state = self.states[index - self.first]
        if state is None:
            return max(0.0, current), min(0.0, current)
        positive, negative, positive_release, negative_release = state
        positive = max(
            0.0,
            current,
            positive
            - max(0.0, position - max(index, positive_release))
            / self.rate
            * self.release_g_per_second,
        )
        negative = max(
            0.0,
            -current,
            negative
            - max(0.0, position - max(index, negative_release))
            / self.rate
            * self.release_g_per_second,
        )
        return positive, -negative
