"""Immutable user additions kept separate from original recording metadata.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import replace
from typing import Literal

from pydantic import BaseModel

from .models import Attribute, RecordingMetadata, RidingPosition, ValueOrigin


class RecordingAdditions(BaseModel, frozen=True, strict=True, extra="forbid"):
    """Current Library overrides, with None restoring the imported value.

    Attributes:
        ride_name: Optional ride-name override.
        park_name: Optional park-name override.
        row: Optional row text, independent of the source attribute's scalar type.
        seat: Optional seat text.
        train: Optional train text.
        riding_position: Optional supported riding-position override.
        notes: Current user notes, initially empty.
    """

    ride_name: str | None = None
    park_name: str | None = None
    row: str | None = None
    seat: str | None = None
    train: str | None = None
    riding_position: Literal["Seated", "Flying"] | None = None
    notes: str = ""

    def metadata(self, original: RecordingMetadata) -> RecordingMetadata:
        """Resolve editable metadata without changing original dates or unknown values.

        Args:
            original: Immutable imported metadata.

        Returns:
            Metadata using overrides where set and original values everywhere else.
        """
        return replace(
            original,
            name=self.ride_name if self.ride_name is not None else original.name,
            location=self.park_name if self.park_name is not None else original.location,
            riding_position=(
                RidingPosition(self.riding_position, ValueOrigin.USER)
                if self.riding_position is not None
                else original.riding_position
            ),
        )

    def attributes(self, original: tuple[Attribute, ...]) -> tuple[Attribute, ...]:
        """Resolve row/seat/train labels while retaining unfamiliar attributes.

        Args:
            original: Complete imported attribute records.

        Returns:
            Effective attributes, retaining source identifiers and untouched values.
        """
        values = {"row": self.row, "seat": self.seat, "train": self.train}
        result: list[Attribute] = []
        present: set[str] = set()
        for attribute in original:
            key = attribute.label.casefold()
            present.add(key)
            value = values.get(key)
            result.append(
                Attribute(attribute.id, attribute.label, value) if value is not None else attribute,
            )
        result.extend(
            Attribute(f"library:{key}", key.title(), value)
            for key, value in values.items()
            if key not in present and value is not None
        )
        return tuple(result)
