"""Shared replay-time formatting without explorer, analysis or UI dependencies.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""


def format_sample_time(offset: int, rate: float) -> str:
    """MM:SS.ff uses a sample counter; fractional rates retain explicit seconds.

    Args:
        offset: Signed sample offset from the replay origin.
        rate: Positive source sample rate in samples per second.

    Returns:
        Replay label with sample-counter digits, or seconds for fractional rates.
    """
    if not rate.is_integer():
        return f"{offset / rate:.3f} s"
    whole, frame = divmod(abs(offset), int(rate))
    minutes, seconds = divmod(whole, 60)
    width = max(2, len(str(int(rate) - 1)))
    sign = "-" if offset < 0 else ""
    return f"{sign}{minutes:02}:{seconds:02}.{frame:0{width}}"
