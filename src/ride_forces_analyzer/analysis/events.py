"""Version-1 provisional airtime episodes, independent of presentation labels.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

from dataclasses import dataclass, fields, replace
from math import ceil, floor, isfinite

from ride_forces_analyzer.importers import Severity
from .models import AnalysisDiagnostic, AnalysisProvenance, CapabilityState
from .recording import (
    AirtimeEvent,
    AnalysisQuality,
    EventAnalysis,
    EventEvaluationState,
    ForceInput,
    StageConfiguration,
    VerticalContext,
)


@dataclass(frozen=True, slots=True)
class _Rules:
    floater_bound_g: float = 0.25
    strong_bound_g: float = -0.5
    minimum_duration_seconds: float = 0.20
    maximum_interruption_seconds: float = 0.04
    onset_window_seconds: float = 0.20
    ejector_onset_g_per_second: float = -3.0
    onset_memory_seconds: float = 0.50


def event_rules(configuration: StageConfiguration) -> _Rules:
    """Admit finite version-1 parameters or raise ValueError for unsupported rules."""
    if configuration.algorithm != "airtime-events" or configuration.version != "1":
        raise ValueError("Unsupported event algorithm/version")
    names = {field.name for field in fields(_Rules)}
    parameters: dict[str, float] = {}
    for key, value in configuration.parameters:
        if (
            key not in names
            or key in parameters
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise ValueError("Unsupported event parameters")
        parameters[key] = float(value)
    rules = _Rules(**parameters)
    if not (
        rules.floater_bound_g >= 0
        and rules.strong_bound_g < -rules.floater_bound_g
        and rules.minimum_duration_seconds > 0
        and rules.maximum_interruption_seconds >= 0
        and rules.onset_window_seconds > 0
        and rules.ejector_onset_g_per_second < 0
        and rules.onset_memory_seconds >= 0
    ):
        raise ValueError("Invalid event parameter bounds")
    return rules


@dataclass(slots=True)
class _Episode:
    first: int
    last: int
    minimum: float
    minimum_index: int
    start_incomplete: bool
    count: int = 0
    onset: float | None = None
    ejector: bool = False

    def result(self, rate: float, rules: _Rules, incomplete: bool) -> AirtimeEvent:
        category = (
            VerticalContext.EJECTOR_AIRTIME
            if self.ejector
            else VerticalContext.STRONG_AIRTIME
            if self.minimum < rules.strong_bound_g
            else VerticalContext.AIRTIME
            if self.minimum < -rules.floater_bound_g
            else VerticalContext.FLOATER_AIRTIME
        )
        return AirtimeEvent(
            self.first,
            self.last,
            (self.last - self.first + 1) / rate,
            self.minimum,
            self.minimum_index,
            self.onset,
            category,
            self.start_incomplete,
            incomplete,
        )


def evaluate_events(
    source: ForceInput,
    configuration: StageConfiguration | None,
    rate: float,
    provenance: AnalysisProvenance,
) -> EventAnalysis:
    """Evaluate complete vertical history under the separate event-rule contract.

    Returns:
        EVALUATED events (possibly empty) with provisional quality and gap/onset
        diagnostics, or NOT_EVALUATED with an explicit configuration/input reason.
        Input stages and buffers are never changed or copied.

    Raises:
        ValueError: Rules/rate are unsupported or timing products are not finite.
    """
    rules = event_rules(configuration) if configuration is not None else None
    channels = source.channels
    reason = None
    if rules is None:
        reason = "Event detection is not configured"
    elif channels is None or not any(channels[0].valid_rows):
        reason = "No valid vertical input for event detection"
    if reason is not None:
        diagnostic = AnalysisDiagnostic("EVENTS_NOT_EVALUATED", Severity.INFO, reason)
        return EventAnalysis(
            source,
            configuration,
            EventEvaluationState.NOT_EVALUATED,
            None,
            diagnostic,
            AnalysisQuality(diagnostics=(diagnostic,)),
            None,
        )
    assert rules is not None and configuration is not None and channels is not None
    if isinstance(rate, bool) or not isfinite(rate) or rate <= 0:
        raise ValueError("Event sample rate must be finite and positive")
    products = (
        rules.minimum_duration_seconds * rate,
        rules.maximum_interruption_seconds * rate,
        rules.onset_window_seconds * rate,
    )
    if not all(isfinite(value) for value in products):
        raise ValueError("Event timing products must be finite")
    required, interruption, window = (
        max(1, ceil(products[0])),
        floor(products[1]),
        max(1, round(products[2])),
    )
    window_duration = window / rate
    if not isfinite(window_duration) or not isfinite(len(channels[0].valid_rows) / rate):
        raise ValueError("Event timing products must be finite")
    vertical = channels[0]
    values = vertical.values
    events: list[AirtimeEvent] = []
    diagnostics: list[AnalysisDiagnostic] = []
    episode: _Episode | None = None
    valid_start = 0
    rapid_at: int | None = None

    def finish(incomplete: bool) -> None:
        nonlocal episode
        if episode is not None and episode.count >= required:
            events.append(episode.result(rate, rules, incomplete))
        episode = None

    for index, valid in enumerate(vertical.valid_rows):
        if not valid:
            finish(True)
            valid_start, rapid_at = index + 1, None
            continue
        value = float(values[index])
        onset = None
        if index - window >= valid_start:
            difference = (value - float(values[index - window])) / window_duration
            if isfinite(difference):
                onset = difference
                if onset <= rules.ejector_onset_g_per_second:
                    rapid_at = index
            else:
                rapid_at = None
                diagnostics.append(
                    AnalysisDiagnostic(
                        "EVENT_ONSET_UNAVAILABLE",
                        Severity.WARNING,
                        "Non-finite event onset difference",
                        "events",
                        index,
                    ),
                )
        if value > rules.floater_bound_g:
            rapid_at = None
            if episode is not None and index - episode.last > interruption:
                finish(False)
            continue
        if episode is None:
            episode = _Episode(index, index, value, index, index == valid_start)
        episode.last = index
        episode.count += 1
        if value < episode.minimum:
            episode.minimum, episode.minimum_index = value, index
        if onset is not None:
            episode.onset = onset if episode.onset is None else min(episode.onset, onset)
        if (
            value < rules.strong_bound_g
            and rapid_at is not None
            and (index - rapid_at) / rate <= rules.onset_memory_seconds
        ):
            episode.ejector = True
    finish(True)
    missing = vertical.valid_rows.count(False)
    if missing:
        diagnostics.append(
            AnalysisDiagnostic(
                "EVENT_INPUT_GAPS",
                Severity.WARNING,
                f"{missing} missing vertical samples split event coverage",
                "events",
            ),
        )
    return EventAnalysis(
        source,
        configuration,
        EventEvaluationState.EVALUATED,
        tuple(events),
        None,
        AnalysisQuality(
            capabilities=(("events", CapabilityState.PROVISIONAL),),
            diagnostics=tuple(diagnostics),
        ),
        replace(provenance, algorithm=configuration.algorithm),
    )
