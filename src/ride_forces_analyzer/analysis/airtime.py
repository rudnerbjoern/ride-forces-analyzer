"""Provisional coaster-context labels from signed, smoothed vertical source g.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from math import ceil, floor, isfinite

FLOATER_BOUND_G = 0.25
STRONG_BOUND_G = -0.5
ONSET_WINDOW_SECONDS = 0.2
EJECTOR_ONSET_G_PER_SECOND = -3.0
ONSET_MEMORY_SECONDS = 0.5
CONTEXT_CONFIRM_SECONDS = 0.12
FLOATER_EXIT_BOUND_G = 0.31
STRONG_EXIT_BOUND_G = -0.4


def _stabilize_context(
    values: tuple[float | None, ...],
    labels: list[str],
    rate: float,
) -> tuple[str, ...]:
    """Confirm detailed labels without delaying entry into the airtime family."""
    required = max(1, ceil(CONTEXT_CONFIRM_SECONDS * rate))
    result: list[str] = []
    current = "Unavailable"
    pending: str | None = None
    count = 0
    for value, candidate in zip(values, labels):
        if value is None or not isfinite(value):
            current, pending, count = "Unavailable", None, 0
            result.append(current)
            continue
        if current == "Floater Airtime" and abs(value) <= FLOATER_EXIT_BOUND_G:
            candidate = current
        elif (
            current in ("Ejector Airtime", "Strong Airtime")
            and value < STRONG_EXIT_BOUND_G
            and candidate not in ("Ejector Airtime", "Strong Airtime")
        ):
            candidate = current

        # Broad load changes must never leave Heavy Gs visible during airtime,
        # or leave an airtime label visible after return to positive loading.
        if "Airtime" in candidate and "Airtime" not in current:
            current, pending, count = "Airtime", None, 0
        elif "Airtime" not in candidate and "Airtime" in current:
            current, pending, count = candidate, None, 0
        elif current == "Unavailable":
            current = candidate
        elif current in ("Ejector Airtime", "Strong Airtime") and value >= STRONG_EXIT_BOUND_G:
            current, pending, count = "Airtime", None, 0

        if candidate == current:
            pending, count = None, 0
        else:
            if candidate != pending:
                pending, count = candidate, 0
            count += 1
            if count >= required:
                current, pending, count = candidate, None, 0
        result.append(current)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class AirtimeContext:
    """Presentation heuristic, not a validated measurement of rider sensation.

    Only past/current samples contribute. Gaps reset event history. A rapid
    onset can qualify strong loading within 0.5 seconds; once qualified, the
    ejector label persists through the same strong-loading phase.

    Attributes:
        labels: Classification labels aligned with source samples.
    """

    labels: tuple[str, ...]

    @classmethod
    def prepare(cls, values: tuple[float | None, ...], rate: float) -> "AirtimeContext":
        """Prepare immutable source-time values for repeated presentation queries.

        Args:
            values: Values to format, validate or add in their supplied order.
            rate: Sample or frame rate per second, as declared by this operation.

        Returns:
            Immutable source-time states prepared for repeated queries over the selected
            interval.

        Raises:
            ValueError: Sample rate must be finite and positive.
            AssertionError: If a required internal invariant does not hold.
        """
        if not isfinite(rate) or rate <= 0:
            raise ValueError("Sample rate must be finite and positive")
        window = max(1, round(ONSET_WINDOW_SECONDS * rate))
        labels: list[str] = []
        valid_start = 0
        rapid_at: int | None = None
        ejector = False
        for index, value in enumerate(values):
            if value is None or not isfinite(value):
                labels.append("Unavailable")
                valid_start = index + 1
                rapid_at = None
                ejector = False
                continue
            if index - window >= valid_start:
                previous = values[index - window]
                assert previous is not None
                onset = (value - previous) / (window / rate)
                if onset <= EJECTOR_ONSET_G_PER_SECOND:
                    rapid_at = index
            if value < STRONG_BOUND_G:
                ejector = ejector or (
                    rapid_at is not None and (index - rapid_at) / rate <= ONSET_MEMORY_SECONDS
                )
                label = "Ejector Airtime" if ejector else "Strong Airtime"
            else:
                ejector = False
                if value > 1.05:
                    label = "Heavy Gs"
                elif value >= 0.95:
                    label = "Normal Gs"
                elif value > FLOATER_BOUND_G:
                    label = "Light Gs"
                    rapid_at = None
                elif value >= -FLOATER_BOUND_G:
                    label = "Floater Airtime"
                else:
                    label = "Airtime"
            labels.append(label)
        return cls(_stabilize_context(values, labels, rate))

    def at(self, position: float) -> str:
        """Read the prepared state at the requested source-sample position.

        Args:
            position: Fractional source-sample position.

        Returns:
            Prepared state at the requested source-sample position, adjusted according to the
            query contract.

        Raises:
            ValueError: Position outside airtime context.
        """
        if not isfinite(position) or not 0 <= position < len(self.labels):
            raise ValueError("Position outside airtime context")
        return self.labels[floor(position)]
