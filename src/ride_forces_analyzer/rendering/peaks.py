"""Source-time peak hold envelopes, independent of frame order and video rate."""

from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True, slots=True)
class PeakEnvelope:
    first: int
    rate: float
    states: tuple[tuple[float, float, float, float] | None, ...]
    release_g_per_second: float = 1.0

    @classmethod
    def prepare(
        cls,
        values: tuple[float | None, ...],
        first: int,
        last: int,
        rate: float,
        *,
        hold_seconds: float = 1.5,
        release_g_per_second: float = 1.0,
    ) -> "PeakEnvelope":
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
