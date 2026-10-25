"""Owned original bytes and recursively immutable, unnormalized source values.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
from types import MappingProxyType
from typing import cast

from ._validation import has_type

NUMBER_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


@dataclass(frozen=True, slots=True)
class SourceNumber:
    """A JSON number's exact token and decimal value, distinct from a string.

    Attributes:
        token: Original numeric token retained for lossless export.
        value: Candidate value to validate, format or store.
    """

    token: str
    value: Decimal = field(init=False)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: SourceNumber requires a JSON number token. SourceNumber requires a
                finite decimal value.
        """
        if not has_type(self.token, str) or not NUMBER_TOKEN.fullmatch(self.token):
            raise ValueError("SourceNumber requires a JSON number token")
        value = Decimal(self.token)
        if not value.is_finite():
            raise ValueError("SourceNumber requires a finite decimal value")
        object.__setattr__(self, "value", value)


type SourceValue = (
    None | bool | str | SourceNumber | tuple[SourceValue, ...] | Mapping[str, SourceValue]
)


def _freeze(value: object, active: set[int]) -> SourceValue:
    if value is None or isinstance(value, (bool, str, SourceNumber)):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(cast(object, value))
        if identity in active:
            raise ValueError("Source values must be an acyclic JSON tree")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                copied: dict[str, SourceValue] = {}
                for key, child in cast(Mapping[object, object], value).items():
                    if not isinstance(key, str):
                        raise TypeError("Source object members require string keys")
                    copied[key] = _freeze(child, active)
                return MappingProxyType(copied)
            return tuple(_freeze(child, active) for child in cast(Sequence[object], value))
        finally:
            active.remove(identity)
    raise TypeError("Source scalars require null, bool, str or explicit SourceNumber tokens")


def freeze_source_value(value: object) -> SourceValue:
    """Own a source value without inferring types or decoding a document.

    Args:
        value: Candidate value to validate, format or store.

    Returns:
        Owned immutable representation of the supplied source value.
    """
    return _freeze(value, set())


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Source provenance contract and owned data.

    Attributes:
        byte_count: Length of the original supplied source bytes.
        sha256: SHA-256 digest identifying the original supplied source bytes.
        path: Filesystem path read or written by this operation.
    """

    byte_count: int
    sha256: str
    path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Source byte count must be a nonnegative integer. Source digest must be
                a lowercase SHA-256 hex string.
            TypeError: Source path must be a Path or None.
        """
        if type(self.byte_count) is not int or self.byte_count < 0:
            raise ValueError("Source byte count must be a nonnegative integer")
        if not has_type(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Source digest must be a lowercase SHA-256 hex string")
        if self.path is not None and not has_type(self.path, Path):
            raise TypeError("Source path must be a Path or None")


@dataclass(frozen=True, slots=True, init=False)
class SourceEnvelope:
    """Snapshot caller-owned data without decoding bytes or touching a file.

    Attributes:
        original_bytes: Owned original input bytes, preserved without rewriting.
        root: Checkout or data root used to resolve the operation's paths.
        provenance: Source identity, processing configuration and calculation evidence.
    """

    original_bytes: bytes = field(repr=False)
    root: Mapping[str, SourceValue] | None = field(repr=False)
    provenance: SourceProvenance

    def __init__(
        self,
        original_bytes: bytes | bytearray,
        root: Mapping[str, object] | None = None,
        *,
        source_path: Path | None = None,
    ) -> None:
        """Initialize source envelope and its owned state.

        Args:
            original_bytes: Unmodified original recording bytes.
            root: Checkout or data root used to resolve the operation's paths.
            source_path: Original input path, when available.

        Returns:
            None.

        Raises:
            TypeError: Source bytes must be bytes or bytearray. Source root must be an object
                mapping or None.
            AssertionError: If a required internal invariant does not hold.
        """
        if not has_type(original_bytes, (bytes, bytearray)):
            raise TypeError("Source bytes must be bytes or bytearray")
        owned = bytes(original_bytes)
        frozen: Mapping[str, SourceValue] | None = None
        if root is not None:
            if not has_type(root, Mapping):
                raise TypeError("Source root must be an object mapping or None")
            frozen_value = _freeze(root, set())
            assert isinstance(frozen_value, Mapping)
            frozen = frozen_value
        object.__setattr__(self, "original_bytes", owned)
        object.__setattr__(self, "root", frozen)
        object.__setattr__(
            self,
            "provenance",
            SourceProvenance(len(owned), sha256(owned).hexdigest(), source_path),
        )
