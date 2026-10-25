"""Analysis request state and technical service notification payloads.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass
from enum import StrEnum


from ..models import (
    AnalysisDiagnostic,
)

from .configuration import (
    AnalysisConfiguration,
    AnalysisStage,
)
from .snapshot import RecordingAnalysis


class RequestStatus(StrEnum):
    """Request lifecycle: no request, pending work, published result or failure.

    This status describes the service request, not the retained snapshot's age
    or scientific capabilities. A failed request can retain an older snapshot.

    Attributes:
        IDLE: Named value for idle (`idle`).
        PENDING: Named value for pending (`pending`).
        READY: Named value for ready (`ready`).
        FAILED: Named value for failed (`failed`).
    """

    IDLE = "idle"
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AnalysisState:
    """Describe subscription initial state independently of snapshot configuration.

    Attributes:
        source_sha256: Current complete-source identity, or None without a source.
        snapshot: Last completed snapshot, possibly older than the current request,
            or None when no completed result exists.
        requested_configuration: Current requested configuration, or None if idle.
        requested_revision: Revision used to reject stale queued deliveries.
        status: Current request lifecycle status.
        dirty_stages: Stages awaiting recalculation for the requested configuration.
        failure: Current request's failure diagnostic, or None without a failure.
    """

    source_sha256: str | None
    snapshot: RecordingAnalysis | None
    requested_configuration: AnalysisConfiguration | None
    requested_revision: int
    status: RequestStatus
    dirty_stages: frozenset[AnalysisStage] = frozenset()
    failure: AnalysisDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class AnalysisUpdated:
    """Publication payload for a completed consistent snapshot, not an emitter.

    Attributes:
        source_sha256: Full source hash associated with the published result.
        revision: Completed request revision, rechecked at UI delivery time.
        replaced_stages: Stages replaced relative to the preceding snapshot.
        snapshot: New immutable result; subscribers may share its references.
    """

    source_sha256: str
    revision: int
    replaced_stages: frozenset[AnalysisStage]
    snapshot: RecordingAnalysis


@dataclass(frozen=True, slots=True)
class AnalysisInvalidated:
    """Optional pending-work payload, leaving the completed snapshot unchanged.

    Attributes:
        source_sha256: Source identity for the pending request.
        revision: Requested revision, rechecked before updating pending UI state.
        dirty_stages: Invalidated stages, including their affected dependents.
    """

    source_sha256: str
    revision: int
    dirty_stages: frozenset[AnalysisStage]


@dataclass(frozen=True, slots=True)
class AnalysisFailed:
    """Failure payload terminating a matching request without publishing partial data.

    Attributes:
        source_sha256: Source identity of the failed request.
        revision: Failed revision; stale failures must not clear newer pending work.
        affected_stages: Stages affected by the failed recalculation.
        failure: Structured diagnostic; the older snapshot retains its configuration.
    """

    source_sha256: str
    revision: int
    affected_stages: frozenset[AnalysisStage]
    failure: AnalysisDiagnostic


type AnalysisNotification = AnalysisUpdated | AnalysisInvalidated | AnalysisFailed
