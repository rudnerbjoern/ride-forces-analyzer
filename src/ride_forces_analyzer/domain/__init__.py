"""Immutable source and canonical recording models, independent of importer/UI logic.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from .models import (
    Attribute,
    GpsEntry,
    GpsFix,
    GpsSequence,
    GpsStatus,
    MotionSequence,
    Recording,
    RecordingIndices,
    RecordingMetadata,
    RecordingVectors,
    RidingPosition,
    SampleRate,
    ValueOrigin,
    Vector3,
)
from .source import SourceEnvelope, SourceNumber, SourceProvenance, SourceValue

__all__ = [
    "Attribute",
    "GpsEntry",
    "GpsFix",
    "GpsSequence",
    "GpsStatus",
    "MotionSequence",
    "Recording",
    "RecordingIndices",
    "RecordingMetadata",
    "RecordingVectors",
    "RidingPosition",
    "SampleRate",
    "SourceEnvelope",
    "SourceNumber",
    "SourceProvenance",
    "SourceValue",
    "ValueOrigin",
    "Vector3",
]
