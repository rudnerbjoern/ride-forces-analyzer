"""Validated bootstrap configuration, separate from recording/domain models."""

from pydantic import BaseModel, Field

# Qt's documented maximum widget size; reject unsupported sizes before startup.
MAX_WINDOW_DIMENSION = 16_777_215


class AppSettings(BaseModel, frozen=True, strict=True, extra="forbid", validate_default=True):
    """Immutable window settings with strict runtime and static typing."""

    window_title: str = Field(default="Ride Forces Analyzer", min_length=1)
    window_width: int = Field(default=1280, gt=0, le=MAX_WINDOW_DIMENSION)
    window_height: int = Field(default=820, gt=0, le=MAX_WINDOW_DIMENSION)
