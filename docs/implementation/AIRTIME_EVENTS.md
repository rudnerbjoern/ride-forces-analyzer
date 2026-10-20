# Provisional airtime event rules

This is the separate domain contract for `airtime-events`, version `1`.
These are provisional product rules, not validated physical definitions or rider
sensation measurements. [Sample context](AIRTIME.md) has separate presentation
confirmation and hysteresis; neither is an event detector input.

## Configuration and input

Enable detection with `AnalysisConfiguration.events = StageConfiguration("airtime-events", "1")`.
None leaves events NOT_EVALUATED with a reason. Existing default configurations
remain disabled. Explicit recipes retain their rules in presets and batch jobs.
Unknown algorithms, versions or parameters fail the calculation, not silently fall
back to disabled evaluation. Parameters may override the following defaults:

| Parameter                      | Default | Constraint                           |
| :----------------------------- | :------ | :----------------------------------- |
| `floater_bound_g`              | 0.1     | Finite, nonnegative                  |
| `strong_bound_g`               | -0.5    | Finite, below negative floater bound |
| `minimum_duration_seconds`     | 0.20    | Finite, positive                     |
| `maximum_interruption_seconds` | 0.04    | Finite, nonnegative                  |
| `onset_window_seconds`         | 0.20    | Finite, positive                     |
| `ejector_onset_g_per_second`   | -3.0    | Finite, negative                     |
| `onset_memory_seconds`         | 0.50    | Finite, nonnegative                  |

Read the configured projected or smoothed vertical stage, its validity mask and
inferred uniform source rate. No additional smoothing, gravity substitution or GPS
alignment is introduced. Whole-stage unavailability or no valid vertical samples
means NOT_EVALUATED. Otherwise EVALUATED may legitimately contain zero events;
missing rows are explicitly reported as incomplete input coverage.

## Intervals, minimum duration and interruptions

A qualifying sample is valid vertical load at or below `floater_bound_g`.
An episode begins at its first qualifying sample. It ends at its last qualifying
sample when a valid positive interruption exceeds the allowed length, a gap occurs
or the recording ends. Original source indices are inclusive and never renumbered.

Require at least `ceil(minimum_duration_seconds * rate)` qualifying samples.
Short positive interruptions do not contribute to that minimum. Up to
`floor(maximum_interruption_seconds * rate)` consecutive valid samples above the threshold may bridge two qualifying portions. Interior bridged samples contribute
to the reported interval duration `(last - first + 1) / rate`; trailing positive
samples do not. Zero interruption permits no bridging. Brief candidates failing
the minimum are omitted, including truncated candidates.

Missing/invalid rows always split episodes and reset onset history; never bridge
a data gap. An episode beginning at the recording start or immediately after a
gap has `start_incomplete=True`. An episode still active at recording end or a
gap has `end_incomplete=True`, including an unresolved short positive interruption.
A sufficiently long observed positive interruption establishes a complete end.
Flags describe observation limits, not proof that airtime continued beyond them.

Analyze complete supplied history before any export selection. Selection, zoom,
frame rate, seeking and language do not clip, split or recalculate domain events.

## Minimum, onset and category

Report the lowest qualifying vertical value, with the earliest original index
for ties. Category summarizes the strongest observed portion of the episode,
not a claim that its entire duration had that category:

- Floater Airtime when the minimum is at least `-floater_bound_g`.
- Airtime below that bound, through `strong_bound_g` inclusive.
- Strong Airtime strictly below `strong_bound_g` without qualifying onset.
- Ejector Airtime when a strong sample has qualifying recent onset.

Onset is the backward difference over `max(1, round(onset_window_seconds * rate))`
samples divided by that actual window duration. Only contiguous valid history
contributes; preceding samples outside the event can establish onset. A decline
at or below `ejector_onset_g_per_second` qualifies for `onset_memory_seconds`.
Valid loads above the threshold clear that memory. A strong sample while qualified marks
the episode Ejector. Report the minimum available signed window difference among
qualifying samples as `onset_g_per_second`, or None without sufficient history.
Non-finite differences cannot establish onset and are diagnosed explicitly.
This indicator is not a qualified biomechanical jerk measurement.

## Results and reuse

Events are immutable `AirtimeEvent` values ordered by source index without overlap,
inside `EventAnalysis`, carrying the actual force-stage reference, rule configuration,
calculation provenance and PROVISIONAL capability. The input reference retains
its own quality and provenance. No display-label subscription is involved.
Changing rules rebuilds only events; changing context confirmation does not.
Smoothing rebuilds events only when they consume smoothing. Snapshots retained by
exports preserve their original event results. Service change notifications remain
technical payloads, separate from these domain events.
