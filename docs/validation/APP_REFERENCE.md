# Source-app comparison evidence

<!-- cspell:words Flojector -->

Source-specific observations and independent comparison values for the pinned
[recordings](../development/RECORDINGS.md). Architecture remains authoritative for
the [source-app policy](../architecture/09_architecture_decisions.md#source-app-projection),
[scientific gates](../architecture/08_concepts.md#scientific-provenance-and-gates)
and [open qualification limits](../architecture/11_technical_risks.md).
Live display behavior belongs to the [explorer contract](../implementation/RAW_EXPLORER.md).

## Computation and qualification

- Compared calculation: independent direction-row normalization, direct projection
  and one centered mean. No gravity addition/subtraction, orthogonal replacement or
  successive calibration rotations. Numerical/edge rules: [adopted policy](../architecture/09_architecture_decisions.md#source-app-projection).
- Comparisons use inclusive marker intervals. Source-app edge handling and
  `endIndex` inclusion remain unverified; no exact selection equivalence is claimed.
- Pinned Manta at window 11: owner-confirmed source-app projection, g scale, signs,
  filtering, replay, Combined and Orientation. Other sources/windows remain provisional.
- All unified derived stages retain PROVISIONAL capability and assumed units,
  including confirmed comparisons. No qualified physical forces are established;
  [generic frame gates](../architecture/09_architecture_decisions.md#passive-frame-transforms)
  remain independent. Hashes identify provenance, not feature eligibility.

| Quantity     | Source-app evidence / implementation limit                                                                              |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Lateral      | Positive right, negative left                                                                                           |
| Longitudinal | Positive acceleration, negative braking                                                                                 |
| Combined     | Norm of filtered directional components; evidence tests only, no production Combined chart                              |
| Orientation  | Angle of normalized current source gravity to stored vertical, clipped cosine before acos; implemented for video export |
| Time         | Start-relative `MM:SS.ff`, ff is sample counter at integer rate; internal recording seconds remain index/rate           |

- At 50 Hz, 11 samples: nominal N/rate 0.22 s, endpoint span 0.20 s, ±0.10 s support.
- Manta unfiltered vertical extrema: approximately -5.03988/+3.66707, distinct from
  the smoothed display.

## Corpus extrema regression

| Recording      | Source minimum | Reconstructed minimum | Source maximum | Reconstructed maximum |
| -------------- | -------------- | --------------------- | -------------- | --------------------- |
| Manta          | -3.720832109   | -3.720831193          | 2.614470243    | 2.614460771           |
| Iron Gwazi     | -1.333528161   | -1.333624797          | 3.784377098    | 3.784489785           |
| Kraken         | -0.220217317   | -0.220226569          | 4.076864719    | 4.076822294           |
| Taron          | -0.626344442   | -0.626451405          | 4.345596790    | 4.345766817           |
| Voltron Nevera | -1.598199964   | -1.598163271          | 4.365312576    | 4.365497903           |

- Compared vertical extrema use 11-sample smoothing.
- Regression ceiling: 0.0002; no physical accuracy/private-algorithm identity claim.
- Source identities/digests: [catalog](../development/RECORDINGS.md).

## Manta replay reference

- Source rate: 50 Hz; startIndex 1214, recording offset 24.28 s.
- Supplied replay snapshots are independent reference points; no parameter fitting.

| Replay   | Sample | Recording seconds | Vertical g | Lateral g | Longitudinal g | Combined g | Orientation |
| -------- | ------ | ----------------- | ---------- | --------- | -------------- | ---------- | ----------- |
| 00:00.00 | 1214   | 24.28             | -0.04      | -0.01     | 0.99           | 0.99       | 92 degrees  |
| 00:10.00 | 1714   | 34.28             | 1.00       | 0.01      | -0.01          | 1.00       | 0 degrees   |
| 01:07.00 | 4564   | 91.28             | 0.52       | -0.02     | -0.08          | 0.52       | 47 degrees  |
| 01:12.00 | 4814   | 96.28             | -3.44      | 0.07      | 0.35           | 3.46       | 120 degrees |
| 01:26.00 | 5514   | 110.28            | 1.96       | -0.21     | 0.41           | 2.02       | 77 degrees  |

- Match: all 15 directional values and all five Combined/Orientation values at shown precision.
- At 01:26: 1.960580571/-0.214940883/0.412735885; component norm 2.015050041 → 2.02.
  Averaging raw magnitudes gives 2.115184090 and fails the reference.
- Orientation: 77.397274 degrees → 77; averaging angles first gives 77.743270 and fails.
- Vertical min: sample 4782, recording 95.64 s, replay 71.36 s. Max: sample 5047,
  recording 100.94 s, replay 76.66 s.
- gravityIndex 2013: vertical ≈0.9989. inclineIndex 3370:
  vertical/longitudinal/lateral ≈0.7414/0.6736/-0.0060.
- Initial longitudinal load, lift plateau and final vertical baseline match visually;
  no qualification of arbitrary mounting or every file.

## Kraken replay reference and known discrepancy

- Source rate: 50 Hz; start/end 913/9138; selected span 164.5 s; offset 18.26 s.
- `01:31.47` → index `913 + 91*50 + 47 = 5510`. Reading .47 as hundredths fails.

| App time | Source index | Vertical g | Lateral g | Longitudinal g | Combined g | Orientation | Result             |
| -------- | ------------ | ---------- | --------- | -------------- | ---------- | ----------- | ------------------ |
| 00:00.00 | 913          | 0.98       | -0.01     | -0.10          | 0.99       | 6 degrees   | Start discrepancy  |
| 00:54.25 | 3638         | 0.93       | 0.00      | 0.35           | 0.99       | 20 degrees  | All readouts match |
| 01:16.28 | 4741         | 2.21       | -0.08     | -0.36          | 2.24       | 72 degrees  | All readouts match |
| 01:31.47 | 5510         | 4.02       | 0.09      | -0.15          | 4.02       | 29 degrees  | All readouts match |
| 01:48.13 | 6326         | 3.59       | 0.04      | -0.02          | 3.59       | 34 degrees  | All readouts match |
| 01:52.04 | 6517         | 3.43       | 0.05      | -0.05          | 3.43       | 0 degrees   | All readouts match |
| 02:02.03 | 7016         | 1.24       | 0.34      | -0.96          | 1.61       | 136 degrees | All readouts match |
| 02:08.16 | 7329         | 1.00       | -0.08     | -0.90          | 1.35       | 2 degrees   | All readouts match |

- Match: seven nonzero-time rows, all five readouts; all eight Orientation values.
- Open start discrepancy: computation 1.00/0.00/-0.10 g, Combined 1.00 g. Raw projection
  and shortened selection-edge averaging establish no equivalent rule. Tests retain
  the mismatch without broad tolerances or fitted offsets.
- Selected extrema: lateral -0.711935869/+0.422388300; longitudinal
  -1.092671545/+0.447732913; visually consistent with overview patterns.
- gravityIndex 1028: vertical/lateral/longitudinal ≈1.002325/-0.002091/0.002562;
  inclineIndex 2928: ≈0.932704/-0.006582/0.352202.

## Voltron Nevera reference and known discrepancy

- Effective 50 Hz: absence-only project default, not measured acquisition rate.
- Source start/end 1571/10374; offset 31.42 s; selected span 176.06 s.
- Two peak groups and near-1 g middle interval agree visually.

| Quantity     | Reconstructed minimum / maximum g | Screenshot comparison                                                  |
| ------------ | --------------------------------- | ---------------------------------------------------------------------- |
| Vertical     | -1.598163271 / 4.365497903        | -1.60 matches; shown maximum 4.36 differs from normal rounding to 4.37 |
| Lateral      | -1.262322395 / 0.920521857        | -1.26 / +0.92 match                                                    |
| Longitudinal | -1.208233927 / 1.072801471        | -1.21 / +1.07 match                                                    |
| Combined     | 0.094203046 / 4.436456817         | 0.09 / 4.44 match                                                      |

- Stored maximum 4.365312576 also normally rounds to 4.37. Displayed 4.36 remains
  unresolved; no truncation or retuning.

Source-app duration statistics below are not reproduced by an implemented algorithm.
The [provisional event rules](../implementation/AIRTIME_EVENTS.md) are a separate
contract. Threshold inclusion/crossing interpolation is unverified; independently
rounded bins may not sum exactly to totals.

| Statistic          | Screenshot seconds / bins                                   |
| ------------------ | ----------------------------------------------------------- |
| Vertical positives | 28.79 total; 2–3 g 11.31, 3–4 g 14.50, 4–5 g 2.98           |
| Vertical negatives | 21.02 total; Floater 10.89, Flojector 6.61, Ejector 3.53    |
| Acceleration       | 3.37 total; 0.5–1 g 2.96, 1–1.5 g 0.41                      |
| Braking            | 7.43 total; 0.5–1 g 6.90, 1–1.5 g 0.52                      |
| Combined positives | 29.26 total; 2–3 g 11.54; obscured bins are not transcribed |

## Weather metadata

- Evidence: owner-provided Voltron screenshot, 2026-10-17, compared with the authorized fixture.
- Conditions: Mostly Clear. Temperature 17.786710739135742 → 17.8 °C.
- Wind: 195 degrees, SSW; 0.9936420124626161 m/s → 4 km/h rounded;
  gust 3.874126195764542 m/s → 14 km/h rounded.
- Wind values ×3.6 match integer km/h; 195 degrees lies in 16-point SSW sector
  [191.25, 213.75). Temperature matches one-decimal Celsius.
- Scope: this source only, not a guaranteed unit schema for every recording.
  [Parser contract](../development/OPTIONAL_PARSING.md#weather-fields-and-source-app-evidence)
  owns five-field retention and absence/invalid diagnostics; full-import regression
  checks exact accessors, rounding and original bytes. No dedicated explorer weather panel.

## GPS comparison across all originals

- Scope: coarse spatial context; no force calibration, timing, segmentation or force input.
- Geometry: north-up local WGS84 approximation in source order, assuming degrees.
  Distances below are not measured track length, speed or elevation.

| Recording      | GPS points | GPS span s | Largest gap s | Approximate extent m E/W × N/S | Horizontal accuracy median / max | Negative speed entries |
| -------------- | ---------- | ---------- | ------------- | ------------------------------ | -------------------------------- | ---------------------- |
| Manta          | 193        | 192.00     | 1.00          | 118 × 170                      | 11.52 / 46.12                    | 36                     |
| Kraken         | 174        | 196.06     | 12.00         | 206 × 396                      | 22.09 / 199.99                   | 11                     |
| Taron          | 182        | 180.74     | 1.00          | 125 × 109                      | 42.11 / 380.26                   | 0                      |
| Voltron Nevera | 149        | 225.78     | 11.71         | 298 × 156                      | 25.03 / 199.99                   | 18                     |
| Iron Gwazi     | absent     | —          | —             | —                              | —                                | —                      |

- All four sequences: increasing timestamps, approximately one-second median
  intervals, all ten fields. Gaps >2 s: Kraken 3, Voltron 15, others 0.
- Accuracy units unproved; Taron's maximum exceeds its full extent if treated as
  meters. Negative speed/course remain unqualified sentinels, not reverse travel or fixes.
- Voltron northeast cluster, southwest excursion and long crossings match the supplied
  map visually. Exact registration, track elements and station/launch positions unverified.
- Voltron approximate geometry: extent 297.97×156.18 m; endpoint separation 36.40 m;
  connected-point length 1,155.20 m; longest step 68.59 m.
- Voltron timing: GPS span 225.780630 s versus complete sensor span 210.06 s
  (difference 15.72 s); source-date offsets +0.378860…+226.159490 establish no shared
  acquisition clock. Intervals 0.005958–11.707501 s; nine >5 s.
- Voltron source accuracy 6.62–199.99: 27 entries >50, 18 >100. Altitude
  159.12–165.52 is not a qualified elevation profile. Negative speed/course: 18/46 entries.
- Other connected-point lengths / endpoint separations (m): Manta 533.40/59.05,
  Kraken 1,790.73/6.27, Taron 883.66/19.42. Crossings/jumps/clusters identify no ride elements.
- Iron Gwazi: no GPS; no borrowed route. Current offline overview: neutral-blue
  connections, breaks at unavailable fixes and missing/zero/negative/>2 s intervals,
  no background map or speed colors. Product behavior: [GPS contract](../implementation/RAW_EXPLORER.md).

### Source-speed color hypothesis

- Nonnegative speed maxima: Manta 6.404428, Kraken 14.761415, Taron 13.328056,
  Voltron 14.216463; 23.06/53.14/47.98/51.18 km/h **if** source units are m/s.
- Linear 0–15 source-unit green/red inspection scale qualitatively matches Voltron:
  slow northeast points green, faster central return orange/red. Palette, thresholds,
  normalization, interpolation and processed-versus-source speed remain unverified.
- No maps supplied for the other three GPS recordings; no cross-recording confirmation.
  Available course does not establish available speed.
- Nonnegative ending-fix speed versus adjacent distance/time correlation:
  Manta 0.318, Kraken 0.099, Taron 0.266, Voltron 0.346. No fitted lag, quality selection
  or smoothing. This does not justify replacing source speed with geometric step speed;
  speed coloring remains a hypothesis, not a confirmed app contract.

## Verification boundary

Relevant regression scope: comparisons, weather accessors, smoothing, force levels
and GPS presentation against pinned originals. Run from the repository root on native Windows:

```text
uv run --locked pytest tests/analysis/test_source_app_evidence.py tests/explorer/test_data.py tests/explorer/test_gps.py tests/importers/test_optional.py
```

- Comparisons establish scoped agreement, not pixel identity or private-algorithm equivalence.
- GPS units/epochs/sentinels and general physical rider calibration remain unqualified.
- Product acceptance: [explorer contract](../implementation/RAW_EXPLORER.md) and
  [analysis concepts](../architecture/08_concepts.md#scientific-provenance-and-gates).
