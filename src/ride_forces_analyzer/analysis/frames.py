"""Explicit passive frame math; source rider mappings remain unqualified.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words linalg

from dataclasses import dataclass, replace
from datetime import datetime
from importlib import import_module
from importlib.metadata import version
import re
from typing import Protocol, cast

import numpy as np
from numpy.typing import NDArray

from ride_forces_analyzer.domain import Vector3
from ride_forces_analyzer.domain._validation import has_type
from ride_forces_analyzer.importers import ImportSuccess, Severity

from .device import MotionUnitContract, analyze_device_vectors
from .models import (
    AnalysisChannel,
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    FrameLabel,
    ProfileName,
    SampleValues,
)

# Numerical admission tolerance, not an empirical source-calibration tolerance.
FRAME_ATOL = 1e-10


@dataclass(frozen=True, slots=True)
class OrthonormalFrame:
    """Rows are target unit axes in DEVICE coordinates; v_target = R @ v_device.

    Right-handed axes only. Inputs are never normalized, completed or repaired.
    For RIDER: x forward, y left, z rider-up is an explicit project convention.
    Construction establishes matrix geometry, not a physical source mapping.

    Attributes:
        rows: Ordered basis vectors forming the frame transformation.
    """

    rows: tuple[Vector3, Vector3, Vector3]

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Frame requires three explicit typed basis vectors. Frame axes must be
                unit length and mutually orthogonal. Frame must be right-handed with
                determinant +1.
        """
        rows = tuple(self.rows)
        if len(rows) != 3 or any(not has_type(row, Vector3) for row in rows):
            raise ValueError("Frame requires three explicit typed basis vectors")
        object.__setattr__(self, "rows", rows)
        matrix = self.matrix
        if not np.allclose(matrix @ matrix.T, np.eye(3), rtol=0, atol=FRAME_ATOL):
            raise ValueError("Frame axes must be unit length and mutually orthogonal")
        if not np.isclose(np.linalg.det(matrix), 1.0, rtol=0, atol=FRAME_ATOL):
            raise ValueError("Frame must be right-handed with determinant +1")

    @property
    def matrix(self) -> NDArray[np.float64]:
        """Return an independent matrix; editing it cannot change this frame.

        Returns:
            An independent matrix; editing it cannot change this frame.
        """
        return np.array([(row.x, row.y, row.z) for row in self.rows], dtype=np.float64)


class _Rotation(Protocol):
    """Typed subset of a validated three-dimensional rotation."""

    def apply(self, vectors: NDArray[np.float64], *, inverse: bool) -> NDArray[np.float64]:
        """Transform vectors using this rotation or its inverse.

        Args:
            vectors: Vectors in the declared coordinate frame.
            inverse: Whether to apply the inverse transformation.

        Returns:
            Transformed vectors in the requested direction.
        """
        ...


class _RotationFactory(Protocol):
    """Construct rotations without repairing already validated frame matrices."""

    def from_matrix(self, matrix: NDArray[np.float64], *, assume_valid: bool) -> _Rotation:
        """Construct a rotation from the supplied matrix.

        Args:
            matrix: Transformation matrix in the declared axis order.
            assume_valid: Whether the caller has already validated the values.

        Returns:
            Rotation represented by the supplied matrix.
        """
        ...


_ROTATION = cast(_RotationFactory, getattr(import_module("scipy.spatial.transform"), "Rotation"))
_SCIPY_VERSION = version("scipy")


def rotate_vectors(
    samples: SampleValues,
    frame: OrthonormalFrame,
    *,
    inverse: bool = False,
) -> SampleValues:
    """Passive target components, or inverse target-to-device; no unit assignment.

    Args:
        samples: Sample values in the declared source or analysis representation.
        frame: Validated orthonormal target frame.
        inverse: Whether to apply the inverse transformation.

    Returns:
        Owned transformed vectors with source validity preserved.

    Raises:
        TypeError: Rotation requires owned samples and a validated frame. Inverse
            selection must be boolean.
        ValueError: Rotation requires three component columns. Frame conversion exceeded
            finite float64 range.
    """
    if not has_type(samples, SampleValues) or not has_type(frame, OrthonormalFrame):
        raise TypeError("Rotation requires owned samples and a validated frame")
    if type(inverse) is not bool:
        raise TypeError("Inverse selection must be boolean")
    if len(samples.shape) != 2 or samples.shape[1] != 3:
        raise ValueError("Rotation requires three component columns")
    # SciPy otherwise repairs non-orthogonal matrices. Validate first and disable repair.
    rotation = _ROTATION.from_matrix(frame.matrix, assume_valid=True)
    values = samples.values
    valid = np.asarray(samples.valid_rows)
    output = np.full(values.shape, np.nan, dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        output[valid] = rotation.apply(values[valid], inverse=inverse)
    if not np.isfinite(output[valid]).all():
        raise ValueError("Frame conversion exceeded finite float64 range")
    return SampleValues(output, valid_rows=samples.valid_rows)


@dataclass(frozen=True, slots=True)
class RiderCalibration:
    """Source-bound exploratory mapping, never a certificate of rider calibration.

    Attributes:
        source_sha256: SHA-256 identity of the original recording bytes.
        basis: Reference basis used by this model.
        references: Resolved calibration references and their evidence.
    """

    source_sha256: str
    basis: OrthonormalFrame
    references: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate constructor fields and establish the documented model invariants.

        Returns:
            None.

        Raises:
            ValueError: Calibration requires a lowercase source SHA-256. Calibration requires
                nonempty independent references.
            TypeError: Calibration requires an explicit validated basis. Calibration
                references must be a collection.
        """
        if not has_type(self.source_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}",
            self.source_sha256,
        ):
            raise ValueError("Calibration requires a lowercase source SHA-256")
        if not has_type(self.basis, OrthonormalFrame):
            raise TypeError("Calibration requires an explicit validated basis")
        if isinstance(self.references, (str, bytes)):
            raise TypeError("Calibration references must be a collection")
        refs = tuple(self.references)
        if not refs or any(not has_type(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("Calibration requires nonempty independent references")
        object.__setattr__(self, "references", refs)


def analyze_rider_frame(
    source: ImportSuccess,
    *,
    calculation_time: datetime,
    calibration: RiderCalibration | None = None,
    profile: AnalysisProfile | None = None,
    acceleration_contract: MotionUnitContract | None = None,
    gravity_contract: MotionUnitContract | None = None,
) -> AnalysisResult:
    """Return exploratory RIDER vectors or explicit exclusions, never VERIFIED rider G.

    No source vector, marker, pose, gravity direction or default implies a mapping.
    Quantity/unit gates are inherited independently from device analysis.

    Args:
        source: Input recording, retained source representation or source path to read.
        calculation_time: Aware timestamp recorded in calculation provenance.
        calibration: Selected calibration basis and reference evidence.
        profile: Explicit processing or export profile.
        acceleration_contract: Unit and quantity evidence for source acceleration.
        gravity_contract: Unit and quantity evidence for source gravity.

    Returns:
        Exploratory rider vectors or explicit exclusions, never verified rider g.

    Raises:
        TypeError: Frame analysis requires full M2 import success. Calibration must be
            typed or absent.
        ValueError: Frame analysis requires the rider_calibrated profile. Calibration does
            not match this source. Exploratory frame projection requires explicit
            provisional permission.
        AssertionError: If a required internal invariant does not hold.
    """
    if not has_type(source, ImportSuccess):
        raise TypeError("Frame analysis requires full M2 import success")
    selected = (
        profile
        if profile is not None
        else AnalysisProfile(
            ProfileName.RIDER_CALIBRATED,
            policy_references=("ADR-0005: explicit exploratory frame gate",),
        )
    )
    if not has_type(selected, AnalysisProfile) or selected.name is not ProfileName.RIDER_CALIBRATED:
        raise ValueError("Frame analysis requires the rider_calibrated profile")
    if calibration is not None:
        if not has_type(calibration, RiderCalibration):
            raise TypeError("Calibration must be typed or absent")
        if calibration.source_sha256 != source.source_sha256:
            raise ValueError("Calibration does not match this source")
        if not selected.allow_provisional:
            raise ValueError(
                "Exploratory frame projection requires explicit provisional permission",
            )
    device = analyze_device_vectors(
        source,
        calculation_time=calculation_time,
        acceleration_contract=acceleration_contract,
        gravity_contract=gravity_contract,
    )
    configuration = {**selected.configuration, **device.profile.configuration}
    configuration.update({"scipy_version": _SCIPY_VERSION, "frame_atol": FRAME_ATOL})
    if calibration is not None:
        for index, row in enumerate(calibration.basis.rows):
            configuration[f"rider_basis.row_{index}"] = repr((row.x, row.y, row.z))
    selected = replace(selected, configuration=configuration)
    channels: list[AnalysisChannel] = []
    diagnostics: list[AnalysisDiagnostic] = []
    for channel in device.channels[::2]:
        identifier = channel.identifier.replace("-device", "-rider")
        available = channel.state is CapabilityState.VERIFIED and calibration is not None
        if not available:
            state = (
                channel.state
                if channel.state is CapabilityState.INVALID
                else CapabilityState.UNAVAILABLE
            )
            reason = channel.reason or "No independently qualified rider-frame mapping"
            projected = AnalysisChannel(
                identifier,
                channel.quantity,
                state,
                channel.source_sequence,
                reason=reason,
            )
            codes = [
                item.code for item in device.diagnostics if item.channel_id == channel.identifier
            ]
            code = codes[0] if codes else "RIDER_FRAME_UNQUALIFIED"
            diagnostics.append(
                AnalysisDiagnostic(
                    code,
                    Severity.ERROR if state is CapabilityState.INVALID else Severity.WARNING,
                    reason,
                    identifier,
                ),
            )
        else:
            assert calibration is not None and channel.samples is not None
            try:
                samples = rotate_vectors(channel.samples, calibration.basis)
                projected = replace(
                    channel,
                    identifier=identifier,
                    state=CapabilityState.PROVISIONAL,
                    frame=FrameLabel.RIDER,
                    frame_evidence=calibration.references,
                    samples=samples,
                    columns=("longitudinal", "lateral", "vertical"),
                )
                diagnostics.append(
                    AnalysisDiagnostic(
                        "RIDER_FRAME_PROVISIONAL",
                        Severity.WARNING,
                        "Exploratory mapping has no verified source-app calibration",
                        identifier,
                    ),
                )
            except ValueError as error:
                projected = AnalysisChannel(
                    identifier,
                    channel.quantity,
                    CapabilityState.INVALID,
                    channel.source_sequence,
                    reason=str(error),
                )
                diagnostics.append(
                    AnalysisDiagnostic(
                        "FRAME_TRANSFORM_RANGE",
                        Severity.ERROR,
                        str(error),
                        identifier,
                    ),
                )
        channels.append(projected)
    return AnalysisResult(
        source,
        selected,
        AnalysisProvenance(
            source.recording.source.provenance,
            "0.1.0",
            "passive-rider-v1",
            calculation_time,
        ),
        tuple(channels),
        tuple(diagnostics),
    )
