# Provisional airtime event rules

`airtime-events`, version `1`: provisional domain rules, not validated physical
definitions or rider-sensation measurements. [Sample-context](AIRTIME.md)
confirmation/hysteresis are separate and never detector inputs.

## Configuration and input

- Enable with `AnalysisConfiguration.events = StageConfiguration("airtime-events", "1")`.
  Default `None` means `NOT_EVALUATED` with a reason.
- Presets and batch recipes retain explicit rules. Unsupported algorithms,
  versions or parameters fail calculation; no silent disabling.
- Parameters may override these defaults:

| Parameter                      | Default | Constraint                           |
| :----------------------------- | :------ | :----------------------------------- |
| `floater_bound_g`              | 0.25    | Finite, nonnegative                  |
| `strong_bound_g`               | -0.5    | Finite, below negative floater bound |
| `minimum_duration_seconds`     | 0.20    | Finite, positive                     |
| `maximum_interruption_seconds` | 0.04    | Finite, nonnegative                  |
| `onset_window_seconds`         | 0.20    | Finite, positive                     |
| `ejector_onset_g_per_second`   | -3.0    | Finite, negative                     |
| `onset_memory_seconds`         | 0.50    | Finite, nonnegative                  |

- Input: configured projected/smoothed vertical stage, validity mask and inferred
  uniform source rate. No extra smoothing, gravity substitution or GPS alignment.
- Unavailable input or no valid vertical rows: `NOT_EVALUATED`. Otherwise
  `EVALUATED`, possibly empty; missing rows produce incomplete-coverage diagnostics.

## Intervals, minimum duration and interruptions

| Rule               | Contract                                                                                                                                          |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qualifying sample  | Valid vertical load ≤ `floater_bound_g`                                                                                                           |
| Interval           | First through last qualifying sample; inclusive original indices, never renumbered                                                                |
| End trigger        | Above-threshold interruption exceeds allowance, data gap or recording end                                                                         |
| Minimum            | At least `max(1, ceil(minimum_duration_seconds * rate))` qualifying samples; bridged samples do not count                                         |
| Bridging           | At most `floor(maximum_interruption_seconds * rate)` consecutive valid above-threshold samples between qualifying portions; zero forbids bridging |
| Duration           | `(last - first + 1) / rate`, including interior bridges, excluding trailing above-threshold samples                                               |
| Short candidates   | Omitted even when truncated                                                                                                                       |
| Data gap           | Always splits episodes and resets onset; never bridged                                                                                            |
| `start_incomplete` | Episode begins at recording start or immediately after a gap                                                                                      |
| `end_incomplete`   | Episode remains active at recording end/gap, including an unresolved short interruption                                                           |
| Complete end       | Observed above-threshold interruption exceeds allowance                                                                                           |

Incomplete flags describe observation limits, not continued airtime outside them.
Analysis uses complete supplied history before export selection; selection, zoom,
frame rate, seeking and language neither clip nor split nor recalculate events.

## Minimum, onset and category

Minimum: lowest qualifying vertical value; earliest original index breaks ties.
Category describes the strongest observed portion, not the entire duration:

| Category        | Condition                                            |
| --------------- | ---------------------------------------------------- |
| Floater Airtime | Minimum ≥ `-floater_bound_g`                         |
| Airtime         | `strong_bound_g` ≤ minimum < `-floater_bound_g`      |
| Strong Airtime  | Minimum < `strong_bound_g`, without qualifying onset |
| Ejector Airtime | A strong sample has qualifying recent onset          |

- Onset: backward difference over `max(1, round(onset_window_seconds * rate))`
  samples, divided by actual window duration; contiguous valid history only.
  Preceding samples outside the episode may establish onset.
- Difference ≤ `ejector_onset_g_per_second` qualifies for `onset_memory_seconds`.
  Valid loads above `floater_bound_g` clear memory. A qualified strong sample
  marks the episode Ejector.
- `onset_g_per_second`: minimum available signed window difference among qualifying
  samples; `None` without sufficient history. Non-finite differences clear onset
  memory, cannot qualify and produce diagnostics.
- This indicator is not qualified biomechanical jerk.

## Results and reuse

- Immutable `AirtimeEvent` values, source-index ordered without overlap, inside
  `EventAnalysis`: actual force-stage reference, rules, calculation provenance and
  `PROVISIONAL` capability. Input retains its own quality/provenance.
- Rule changes rebuild events only; context-confirmation changes do not. Smoothing
  rebuilds events only if selected as their input. Exports retain bound results.
- No display-label subscription; technical service notifications are distinct.
  Unsupported rules end the request with `AnalysisFailed`, preserving the previous
  result without partial replacement.

Architecture owns [stage responsibilities](../architecture/05_building_block_view.md),
[reuse and snapshot lifetime](../architecture/08_concepts.md#snapshot-lifetime-and-reuse)
and [service delivery/error handling](../architecture/06_runtime_view.md#explorer-analysis-delivery).
