"""Immutable sample buffers and explicit row-validity masks.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ride_forces_analyzer.validation.checks import has_type


@dataclass(frozen=True, slots=True, init=False)
class SampleValues:
    """Own float64 bytes and explicit row validity; expose fresh read-only NumPy views.

    Attributes:
        _data: Owned sample buffer.
        shape: Dimensions of the retained sample buffer.
        valid_rows: Validity mask distinguishing missing rows from numeric zero.
    """

    _data: bytes = field(repr=False)
    shape: tuple[int, ...]
    valid_rows: tuple[bool, ...]

    def __init__(
        self,
        values: NDArray[np.generic],
        *,
        valid_rows: Sequence[bool] | None = None,
    ) -> None:
        """Initialize sample values and its owned state.

        Args:
            values: Values to format, validate or add in their supplied order.
            valid_rows: Mask identifying present, valid sample rows.

        Returns:
            None.

        Raises:
            TypeError: Samples require a real numeric NumPy array, excluding booleans.
            ValueError: Samples require a nonempty scalar or column array. Sample columns
                cannot be empty. Validity must contain one explicit boolean per source row.
                Valid rows must contain only finite numbers. Missing rows require explicit
                NaN, never zero or hidden values.
        """
        if not has_type(values, np.ndarray) or values.dtype.kind not in "iuf":
            raise TypeError("Samples require a real numeric NumPy array, excluding booleans")
        if values.ndim not in (1, 2) or values.shape[0] == 0:
            raise ValueError("Samples require a nonempty scalar or column array")
        if values.ndim == 2 and values.shape[1] == 0:
            raise ValueError("Sample columns cannot be empty")
        owned = np.array(values, dtype="<f8", order="C", copy=True)
        validity = tuple(valid_rows) if valid_rows is not None else (True,) * len(owned)
        if len(validity) != len(owned) or any(type(item) is not bool for item in validity):
            raise ValueError("Validity must contain one explicit boolean per source row")
        for row, valid in zip(owned, validity, strict=True):
            if valid and not bool(np.all(np.isfinite(row))):
                raise ValueError("Valid rows must contain only finite numbers")
            if not valid and not bool(np.all(np.isnan(row))):
                raise ValueError("Missing rows require explicit NaN, never zero or hidden values")
        object.__setattr__(self, "_data", owned.tobytes(order="C"))
        object.__setattr__(self, "shape", tuple(owned.shape))
        object.__setattr__(self, "valid_rows", validity)

    @property
    def values(self) -> NDArray[np.float64]:
        """Metadata edits to this fresh view cannot change the owned model or data.

        Returns:
            A read-only view whose metadata can be changed without modifying the owned buffer.
        """
        return np.frombuffer(self._data, dtype="<f8").reshape(self.shape)
