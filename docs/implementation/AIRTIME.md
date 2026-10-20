# Provisional airtime context

<!-- cspell:words Pendrill -->

Airtime context defaults to the smoothed, calibrated vertical channel and effective
source sample rate. `AnalysisConfiguration.context_input` may explicitly select
projection instead; the prepared context retains that actual input/configuration.
Version 1 accepts the documented constants, omitted or explicitly unchanged;
unsupported algorithms, versions or threshold overrides fail the request.
Context does not change measurements, filters, axis signs or recordings. Flow Ribbon, Corner
Instruments and Capsule use these labels in their vertical hint, in both aspects
and languages. Column and G-Orbit retain their existing labels.
The explorer shows the same prepared labels and shared palette in a 10-pixel
context strip at the bottom inside the calibrated plot. The strip clips to the
visible time range and follows zoom/resize. Dark appearance matches the
export palette; light appearance uses darker equivalents for readable contrast.
The graph values, smoothing and numeric readouts remain unchanged. Component
responsibilities belong to the [building block view](../architecture/05_building_block_view.md#video-export-boundary).

Prepared categories are language-independent `VerticalContext` identifiers.
Presentation translates their labels/colors without reclassification. An excluded
context stage has a coded reason and no labels; within an available series, invalid
rows use `UNAVAILABLE`. Raw display makes no context claims and does not change
the prepared stage's availability.

Domain [airtime events](AIRTIME_EVENTS.md) use separate opt-in rules. Display
confirmation and hysteresis do not establish their intervals or minimum duration.

## Presentation heuristic

These thresholds are provisional product choices, not a scientific definition or
validated detection of rider sensations:

| Condition                             | Label           |
| ------------------------------------- | --------------- |
| Above 1.05 g                          | Heavy Gs        |
| 0.95 through 1.05 g                   | Normal Gs       |
| Above 0.1 and below 0.95 g            | Light Gs        |
| −0.1 through +0.1 g                   | Floater Airtime |
| −0.5 through below −0.1 g             | Airtime         |
| Below −0.5 g without qualifying onset | Strong Airtime  |
| Below −0.5 g with qualifying onset    | Ejector Airtime |

Onset is the backward difference over a rounded 0.2-second source window (at
least one sample), expressed in g/s using the actual window duration. A decline
of at least 3 g/s qualifies for 0.5 seconds. Entering the strong range while
qualified starts Ejector; it persists only while the load remains below −0.5 g.
Light Gs clears onset memory. Missing/non-finite values clear all history
and show Unavailable; differentiation never crosses a gap.

Preparation uses the complete supplied channel, including available history
before the export interval, without looking ahead. Fractional preview positions
use the preceding sample's label; numeric readouts retain interpolation. Seeking
and export frame rate do not change classifications. Starting a recording within
negative loading cannot establish an earlier onset. Context text is stabilized separately from graph samples and numeric readouts:

- Detailed labels require `ceil(0.12 * sample_rate)` consecutive samples. This is
  a presentation confirmation time, not a scientific minimum event duration.
- Entering the airtime family immediately displays generic Airtime while its
  subtype is pending. Return to positive loading clears airtime immediately.
  Heavy Gs therefore cannot remain displayed during an airtime candidate.
- Once confirmed, Floater persists within ±0.16 g instead of repeatedly crossing
  its ±0.1 g entry boundary. Strong/Ejector labels persist below −0.4 g, unless
  another strong subtype is confirmed. At −0.4 g or above they clear immediately
  to generic Airtime while the next subtype is pending.
- Missing values clear the label and all pending confirmation immediately.

Only text is stabilized; no extra force-signal filter is applied. Broad transitions
and generic fallback text can remain brief, intentionally preserving responsiveness.
Confirmed text can differ from the instantaneous number within the documented
hysteresis bands or during confirmation. All timing uses source samples.

## Context text colors

Flow Ribbon, Corner Instruments and Capsule color the vertical hint using the
stabilized context label, identically for both languages and aspects:

| Context         | Color      | Hex       |
| --------------- | ---------- | --------- |
| Heavy Gs        | Violet     | `#c6a0ff` |
| Normal Gs       | Light gray | `#dddddd` |
| Light Gs        | Light blue | `#9ac8ff` |
| Floater Airtime | Cyan       | `#6edceb` |
| Airtime         | Yellow     | `#ebd36a` |
| Strong Airtime  | Orange     | `#ffa044` |
| Ejector Airtime | Red        | `#ff6375` |

Unavailable retains the theme's neutral hint color. Text identifies the context
independently of color. This palette describes load categories, not safety limits.
Graph traces and numeric readout colors are independent of this context palette.

## Evidence and limits

[Pendrill and Eager (2020)](https://doi.org/10.1088/1361-6552/aba732)
support considering acceleration changes and jerk in coaster experience, but do
not establish these classification thresholds. The
[ejector glossary](https://park.fan/en/glossary/ejector-airtime) describes strong,
sudden airtime qualitatively. Neither source validates this implementation.

The backward difference of a smoothed, projected channel is an onset indicator,
not a fully qualified biomechanical jerk measurement. Calibration, sensor motion,
filter settings, rider posture and restraints limit sensation inference. Existing
source-contract limits still apply. Thresholds need owner review against recordings.

Automated behavior checks and reference images do not establish scientific
qualification. The [image reference scripts](../images/README.md#image-content-and-reproduction)
provide visual review artifacts; scientific qualification remains open.
