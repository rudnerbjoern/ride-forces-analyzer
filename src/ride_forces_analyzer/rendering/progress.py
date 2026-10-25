"""Frame-based remaining-time estimate, independent of widgets and wall clocks.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import ceil


def remaining_seconds(elapsed: float, completed: int, total: int) -> int | None:
    """Estimate pending frames using the average elapsed time per completed frame.

    Args:
        elapsed: Elapsed processing time in seconds.
        completed: Number of completed frames.
        total: Total number of frames or items to process.

    Returns:
        Estimated remaining seconds, or None before a useful estimate is available.
    """
    if completed <= 0 or elapsed <= 0 or total <= 0:
        return None
    return ceil(elapsed / completed * max(0, total - completed))
