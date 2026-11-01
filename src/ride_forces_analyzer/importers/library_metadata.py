"""Source metadata and source-evidenced recording dates for the Library.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words timespec

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ride_forces_analyzer.domain import Recording, RecordingFormat, SourceNumber

_APP_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class LibraryMetadata:
    """Immutable Library projection alongside retained source date evidence.

    Attributes:
        source_ride_name: Verbatim source name, or None when unavailable.
        source_park_name: Verbatim source location, or None when unavailable.
        source_date: Exact source date token, without rewriting or normalization.
        source_timezone: Verbatim source time-zone text.
        recorded_at_utc: UTC instant with six fractional digits and Z, or None.
        recorded_day: ISO date at the recording location, or None.
        day_timezone: Source zone used for the recording day, UTC fallback, or None.
    """

    source_ride_name: str | None
    source_park_name: str | None
    source_date: SourceNumber | None
    source_timezone: str | None
    recorded_at_utc: str | None
    recorded_day: str | None
    day_timezone: str | None


def project_library_metadata(recording: Recording) -> LibraryMetadata:
    """Project names and supported recording dates without modifying the source.

    Ride Forces 2.2.0 dates use seconds since 2001-01-01 UTC. RFDB dates
    remain unknown pending independent source evidence. Unrepresentable or missing
    dates stay unknown. The source zone preserves the recording's local day;
    missing or invalid zones use UTC. The computer's time zone is never used.

    Args:
        recording: Successfully imported recording with its admitted source profile.

    Returns:
        Immutable source metadata with supported dates rounded to microseconds.
    """
    metadata = recording.metadata
    instant: str | None = None
    day: str | None = None
    day_timezone: str | None = None
    if recording.source_format is RecordingFormat.RIDE_FORCES and metadata.date is not None:
        value = metadata.date.value
        # Bound before integer conversion, including for extreme source exponents.
        if -63113904000 <= value < 252423993600:
            try:
                seconds = int(value)
                microseconds = int(((value - seconds) * 1_000_000).to_integral_value())
                utc = _APP_EPOCH + timedelta(seconds=seconds, microseconds=microseconds)
            except OverflowError:
                pass
            else:
                instant = utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
                try:
                    zone = ZoneInfo(metadata.timezone) if metadata.timezone else UTC
                except ZoneInfoNotFoundError, ValueError:
                    zone = UTC
                try:
                    day = utc.astimezone(zone).date().isoformat()
                except OverflowError, ValueError:
                    zone = UTC
                    day = utc.date().isoformat()
                day_timezone = zone.key if isinstance(zone, ZoneInfo) else "UTC"

    return LibraryMetadata(
        metadata.name,
        metadata.location,
        metadata.date,
        metadata.timezone,
        instant,
        day,
        day_timezone,
    )
