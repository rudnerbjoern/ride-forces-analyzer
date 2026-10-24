# Provisional airtime context

For an explanation of the displayed forces, colors and labels, see the
[user forces and airtime guide](../user/FORCES_AND_AIRTIME.md).

<!-- cspell:words Pendrill RFDB -->

- **Input:** smoothed calibrated vertical channel and effective source sample rate;
  `AnalysisConfiguration.context_input` can select projection instead. The prepared
  stage retains its actual input/configuration.
- **Version 1:** documented constants may be omitted or explicitly unchanged.
  Unsupported algorithms, versions or threshold overrides fail the request.
- **Categories:** language-independent `VerticalContext` identifiers; presentation
  translates labels/colors without reclassification. Excluded stages carry a coded
  reason and no labels; invalid rows within an available series use `UNAVAILABLE`.
- **Raw display:** no context claims; prepared-stage availability is unaffected.
- **Consumers:** Flow Ribbon, Corner Instruments and HUD vertical hints, both
  aspects/languages. Column and G-Orbit retain their existing labels. The explorer
  uses prepared categories in its vertical card and 10-pixel strip inside the plot's
  bottom edge; the strip clips to the visible range and follows zoom/resize.
- **Boundaries:** measurements, filters, axis signs, recordings, graph values and
  numeric readouts are unchanged. Display confirmation/hysteresis do not define
  the separate opt-in [airtime events](AIRTIME_EVENTS.md).

Architecture owns [component responsibilities](../architecture/05_building_block_view.md#video-export-boundary)
and [stage reuse/lifetime](../architecture/08_concepts.md#snapshot-lifetime-and-reuse).

## Presentation heuristic

Provisional product thresholds; not scientific definitions or validated detection
of rider sensations. The Floater interval follows [RFDB](https://rideforcesdb.com/airtime);
the other categories, onset and stabilization remain project-defined:

| Condition                             | Label           |
| ------------------------------------- | --------------- |
| Above 1.05 g                          | Heavy Gs        |
| 0.95 through 1.05 g                   | Normal Gs       |
| Above 0.25 and below 0.95 g           | Light Gs        |
| −0.25 through +0.25 g                 | Floater Airtime |
| −0.5 through below −0.25 g            | Airtime         |
| Below −0.5 g without qualifying onset | Strong Airtime  |
| Below −0.5 g with qualifying onset    | Ejector Airtime |

Onset and lookup rules:

- Backward difference over `max(1, round(0.2 * sample_rate))` samples, divided by
  actual window duration; a decline of at least 3 g/s qualifies for 0.5 seconds.
- Strong loading while qualified starts Ejector, retained throughout the phase
  below −0.5 g. Light Gs clears onset memory.
- Missing/non-finite values clear history and show Unavailable; differentiation
  never crosses gaps. A recording starting in negative loading supplies no earlier onset.
- Preparation is causal over the complete supplied channel, including history
  before an export interval. Fractional positions use the preceding sample's label;
  numeric readouts retain interpolation. Seeking/frame rate do not affect categories.

Display stabilization uses source-sample timing, without another force filter:

| Rule                        | Behavior                                                                                                                         |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Detailed-label confirmation | `max(1, ceil(0.12 * sample_rate))` consecutive samples; not a physical event minimum                                             |
| Enter airtime family        | Generic Airtime immediately while subtype is pending; Heavy Gs cannot persist                                                    |
| Leave airtime family        | Non-airtime candidate immediately, subject to Floater hysteresis below                                                           |
| Confirmed Floater           | Retained within ±0.31 g; entry boundary remains ±0.25 g                                                                          |
| Confirmed Strong/Ejector    | Retained below −0.4 g unless another strong subtype is confirmed; at −0.4 g or above, generic Airtime while a subtype is pending |
| Missing value               | Unavailable immediately; pending confirmation cleared                                                                            |

The first available non-airtime candidate appears immediately. Brief broad
transitions and generic fallback labels preserve responsiveness. Confirmation and
hysteresis can make the label differ from the instantaneous number.

## Context text colors

Compact-theme hints use the stabilized category, identically in both languages
and aspects. The explorer's dark palette matches export; light appearance uses
darker equivalents for contrast.

| Context         | Color      | Hex       |
| --------------- | ---------- | --------- |
| Heavy Gs        | Violet     | `#c6a0ff` |
| Normal Gs       | Light gray | `#dddddd` |
| Light Gs        | Light blue | `#9ac8ff` |
| Floater Airtime | Cyan       | `#6edceb` |
| Airtime         | Yellow     | `#ebd36a` |
| Strong Airtime  | Orange     | `#ffa044` |
| Ejector Airtime | Red        | `#ff6375` |

Unavailable uses the theme's neutral hint color. Labels identify categories without
color. Colors describe load categories, not safety limits; graph traces and numeric
readout colors are independent.

## Evidence and limits

- [Pendrill and Eager (2020)](https://doi.org/10.1088/1361-6552/aba732): supports
  considering acceleration changes/jerk in coaster experience, not these thresholds.
- [Ejector glossary](https://park.fan/en/glossary/ejector-airtime): qualitative
  strong, sudden airtime; neither source validates this implementation.
- The backward difference is an onset indicator, not qualified biomechanical jerk.
  Calibration, sensor motion, filtering, posture and restraints limit sensation
  inference. [Source-contract limits](../architecture/08_concepts.md#scientific-provenance-and-gates)
  still apply; owner review of thresholds against recordings remains open.
- Behavior tests and [reference images](../images/README.md#image-content-and-reproduction)
  support implementation/visual review, not scientific qualification.
