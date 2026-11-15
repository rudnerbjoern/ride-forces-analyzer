"""Shared translated labels for export choices.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from ride_forces_analyzer.i18n import tr
from ride_forces_analyzer.rendering.model import ExportSafeRegion


def safe_region_label(profile: ExportSafeRegion) -> str:
    """Return the translated label for a captured or effective Safe Region choice.

    Args:
        profile: Validated profile to describe without changing its stored identity.

    Returns:
        The same choice label used by the selector and export summaries.
    """
    return {
        ExportSafeRegion.OFF: tr("Off"),
        ExportSafeRegion.PORTRAIT_SOCIAL_A: tr("A: light"),
        ExportSafeRegion.PORTRAIT_SOCIAL_B: tr("B: medium"),
        ExportSafeRegion.PORTRAIT_SOCIAL_C: tr("C: higher"),
    }[profile]
