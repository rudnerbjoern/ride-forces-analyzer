"""Monotonic, sample-based playback without GUI or analysis dependencies.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from math import isfinite
from time import monotonic


class SamplePlayback:
    """Play existing integer samples at their inferred recording rate, without looping."""

    def __init__(
        self,
        sample_count: int,
        sample_rate: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Raise ValueError for empty recordings or rates that are not finite and positive."""
        if sample_count < 1 or not isfinite(sample_rate) or sample_rate <= 0:
            raise ValueError("Playback requires samples and a finite positive sample rate")
        self._count = sample_count
        self._rate = sample_rate
        self._clock = clock
        self._sample = 0
        self._position = 0.0
        self._origin = 0.0
        self._speed = 1.0
        self._anchor = 0.0
        self._playing = False

    @property
    def playing(self) -> bool:
        """Whether playback is active; reaching the last sample stops it."""
        return self._playing

    @property
    def speed(self) -> float:
        """Playback multiplier, defaulting to normal recording speed."""
        return self._speed

    def set_speed(self, speed: float) -> None:
        """Select 0.5×, 1× or 2× without moving the current position or changing pause state.

        Raise ValueError for unsupported multipliers.
        """
        if speed not in (0.5, 1.0, 2.0):
            raise ValueError("Playback speed must be 0.5, 1 or 2")
        if speed != self._speed:
            now = self._clock()
            self._origin = self._advance(now)
            self._anchor = now
            self._speed = speed

    def play(self, index: int) -> int:
        """Start at index, or restart at zero when already at the last sample."""
        self.seek(index)
        if index == self._count - 1:
            self.seek(0)
        self._origin = self._sample
        self._anchor = self._clock()
        self._position = float(self._sample)
        self._playing = self._count > 1
        return self._sample

    def current_sample(self) -> int:
        """Return the elapsed-time sample, skipping missed UI ticks and clamping at end."""
        self.current_position()
        return self._sample

    def current_position(self) -> float:
        """Return continuous sample position for display motion, without interpolating data."""
        return self._advance(self._clock())

    def _advance(self, now: float) -> float:
        if self._playing:
            elapsed = max(0.0, now - self._anchor)
            self._position = min(
                self._count - 1,
                self._origin + elapsed * self._rate * self._speed,
            )
            self._sample = int(self._position)
            if self._sample == self._count - 1:
                self._playing = False
        return self._position

    def pause(self) -> int:
        """Freeze at the current integer sample and return its index."""
        index = self.current_sample()
        self._playing = False
        self._position = float(index)
        return index

    def seek(self, index: int) -> None:
        """Move to a valid sample, retaining play/pause state except at the end.

        Raise ValueError outside the recording. Adopting the current sample does
        not reset the clock, allowing UI feedback without cumulative time drift.
        """
        if not 0 <= index < self._count:
            raise ValueError("Playback sample is outside the recording")
        if index != self._sample:
            self._sample = self._origin = index
            self._position = float(index)
            self._anchor = self._clock()
            if index == self._count - 1:
                self._playing = False
