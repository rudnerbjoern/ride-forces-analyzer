# Source-app comparison evidence

Source-specific observations and independent comparison values for the pinned
[recordings](../development/RECORDINGS.md). Architecture remains authoritative for
the [source-app policy](../architecture/09_architecture_decisions.md#source-app-projection),
[scientific gates](../architecture/08_concepts.md#scientific-provenance-and-gates)
and [open qualification limits](../architecture/11_technical_risks.md).
Live display behavior belongs to the [explorer contract](../implementation/RAW_EXPLORER.md).

## RFDB axis interpretation

- The five authorized schema 2.2.0 recordings retain both representations:
  calibration Y/X/Z equals vertical/lateral/longitudinal direction components
  exactly. The unversioned [Typhoon RFDB recording](../development/RECORDINGS.md#typhoon)
  supplies only the calibration representation.
- RFDB analysis therefore uses Y/X/Z with the same rounded-basis admission and
  normalized direction projection. This is a provisional source-app
  interpretation, not a qualified physical frame or a general RFDB specification.
- Typhoon's stored extrema (-1.0298018181818185, 4.981484909090909) match direct
  projection onto its unnormalized Y vector and a centered 11-sample mean.
  Normalizing that rounded vector changes these values slightly (approximately
  -1.029864 and 4.981784). Stored extrema remain untouched metadata; they do not
  override the shared normalized display policy.

## Computation and qualification

- Compared calculation: independent direction-row normalization, direct projection
  and one centered mean. No gravity addition/subtraction, orthogonal replacement or
  successive calibration rotations. Numerical/edge rules: [adopted policy](../architecture/09_architecture_decisions.md#source-app-projection).
- Comparisons use inclusive marker intervals. Source-app edge handling and
  `endIndex` inclusion remain unverified; no exact selection equivalence is claimed.
- Pinned Manta at window 11: selected original CSV rows cross-check source-app
  projection, signs, filtering, replay, Combined and Orientation. The first exported
  force differs; other samples/windows and physical g units remain provisional.
- All unified derived stages retain PROVISIONAL capability and assumed units,
  including confirmed comparisons. No qualified physical forces are established;
  [generic frame gates](../architecture/09_architecture_decisions.md#passive-frame-transforms)
  remain independent. Hashes identify provenance, not feature eligibility.

| Quantity     | Source-app evidence / implementation limit                                                                              |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Lateral      | Positive right, negative left                                                                                           |
| Longitudinal | Positive acceleration, negative braking                                                                                 |
| Combined     | Manta CSV: norm of smoothed device axes; prepared sample/CSV value, no production Combined chart                        |
| Orientation  | Angle of normalized current source gravity to stored vertical, clipped cosine before acos; implemented for video export |
| Time         | Start-relative `MM:SS.ff`, ff is sample counter at integer rate; internal recording seconds remain index/rate           |

- At 50 Hz, 11 samples: nominal N/rate 0.22 s, endpoint span 0.20 s, ±0.10 s support.
- Manta unfiltered vertical extrema: approximately -4.43665/+3.13443, distinct from
  the smoothed display.

## Reference-calibration evidence

- Original Gravity/Incline indices from all five pinned `.forces` recordings:
  centered 5-sample acceleration means (index -2 through index +2), normalized
  vertical, longitudinal projection perpendicular to vertical with original sign,
  lateral from longitudinal cross vertical.
- All 45 direction components match the stored original axes after rounding to
  three decimals. Unrounded axis-angle differences are below 0.04 degrees;
  maximum force difference with full-history 11-sample display smoothing is below
  0.0029 on the existing provisional g scale over the original ride intervals.
- Centered odd windows 1–51 and 101 were compared; five samples give the smallest
  maximum axis-angle error for every fixture. With 11 samples, longitudinal errors
  reach 17.36 degrees for Taron and 8.37 degrees for Voltron Nevera.
- Replacing the Incline acceleration mean with the gravity mean at window 5
  gives longitudinal errors of 32.70 degrees for Taron and 62.47 degrees for Voltron.
  Acceleration minus gravity also fails to reproduce the original axes. Iron Gwazi
  has no gravity data and reproduces its axes from acceleration alone.
- This supports a fixed calibration window independent of display smoothing.
  It does not establish the app's general algorithm, unrounded internal precision,
  boundary handling or physical calibration validity. The supported
  [reference-calibration API](../development/ANALYSIS_MODELS.md#reference-calibration)
  explicitly clips and renormalizes new-reference windows at recording edges.
- The [calibration regressions](../../tests/analysis/test_calibration.py) enforce
  the stated source-precision, angle and force limits across all five recordings.

## Corpus extrema regression

| Recording      | Source minimum | Reconstructed minimum | Source maximum | Reconstructed maximum |
| -------------- | -------------- | --------------------- | -------------- | --------------------- |
| Manta          | -3.557118177   | -3.557139183          | 2.638292313    | 2.638281318           |
| Iron Gwazi     | -1.333528161   | -1.333624797          | 3.784377098    | 3.784489785           |
| Kraken         | -0.220217317   | -0.220226569          | 4.076864719    | 4.076822294           |
| Taron          | -0.626344442   | -0.626451405          | 4.345596790    | 4.345766817           |
| Voltron Nevera | -1.598199964   | -1.598163271          | 4.365312576    | 4.365497903           |

- Compared vertical extrema use 11-sample smoothing.
- Regression ceiling: 0.0002; no physical accuracy/private-algorithm identity claim.
- Source identities/digests: [catalog](../development/RECORDINGS.md).

## Manta replay reference

- Source rate: 50 Hz; startIndex 2750, recording offset 55.00 s.
- The original [CSV export](../../tests/fixtures/real/Manta-BE687591-84BB-4469-AAC0-E5A16B0744F9.csv)
  contains 6888 rows, matching the inclusive marker count. Selected rows below are
  independent rounded references; no parameter fitting or general sample mapping
  from filenames alone.

| Replay   | Sample | Recording seconds | Vertical g | Lateral g | Longitudinal g | Combined g | Orientation    |
| -------- | ------ | ----------------- | ---------- | --------- | -------------- | ---------- | -------------- |
| 00:10.00 | 3250   | 65.00             | 0.74       | 0.01      | 0.68           | 1.00       | 42.16 degrees  |
| 00:40.00 | 4750   | 95.00             | -3.08      | 0.00      | 0.13           | 3.08       | 145.85 degrees |
| 00:40.32 | 4782   | 95.64             | -3.55      | 0.11      | 0.09           | 3.55       | 177.92 degrees |
| 01:12.00 | 6350   | 127.00            | 2.23       | 0.18      | 0.32           | 2.26       | 48.06 degrees  |
| 02:17.37 | 9637   | 192.74            | 1.00       | 0.01      | 0.06           | 1.00       | 3.68 degrees   |

- Selected rows match all directional forces, device-axis Combined and
  independent Orientation at two decimal places. No claim covers every CSV row.
- First CSV vertical value: 1.00 g versus full-history 11-sample mean 1.01 g.
  Source-app selection-edge behavior remains unverified; no fitted edge rule.
- gravityIndex 2238 and inclineIndex 3416 remain source markers; they do not
  qualify arbitrary mounting or physical rider forces.

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
| Manta          | 145        | 177.68     | 15.01         | 96 × 118                       | 14.25 / 56.17                    | 46                     |
| Kraken         | 174        | 196.06     | 12.00         | 206 × 396                      | 22.09 / 199.99                   | 11                     |
| Taron          | 182        | 180.74     | 1.00          | 125 × 109                      | 42.11 / 380.26                   | 0                      |
| Voltron Nevera | 149        | 225.78     | 11.71         | 298 × 156                      | 25.03 / 199.99                   | 18                     |
| Iron Gwazi     | absent     | —          | —             | —                              | —                                | —                      |

- All four sequences: increasing timestamps, approximately one-second median
  intervals, all ten fields. Gaps >2 s: Manta 6, Kraken 3, Voltron 15, Taron 0.
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
- Other connected-point lengths / endpoint separations (m): Manta 769.59/24.54,
  Kraken 1,790.73/6.27, Taron 883.66/19.42. Crossings/jumps/clusters identify no ride elements.
- Iron Gwazi: no GPS; no borrowed route. Current offline overview: neutral-blue
  connections, breaks at unavailable fixes and missing/zero/negative/>2 s intervals,
  no default background map or speed colors. The optional requested map adds no
  scientific qualification. Product behavior: [GPS contract](../implementation/RAW_EXPLORER.md).

### Source-speed color hypothesis

- Nonnegative speed maxima: Manta 11.275048, Kraken 14.761415, Taron 13.328056,
  Voltron 14.216463; 40.59/53.14/47.98/51.18 km/h **if** source units are m/s.
- Linear 0–15 source-unit green/red inspection scale qualitatively matches Voltron:
  slow northeast points green, faster central return orange/red. Palette, thresholds,
  normalization, interpolation and processed-versus-source speed remain unverified.
- No maps supplied for the other three GPS recordings; no cross-recording confirmation.
  Available course does not establish available speed.
- Nonnegative ending-fix speed versus adjacent distance/time correlation:
  Manta 0.161, Kraken 0.099, Taron 0.266, Voltron 0.346. No fitted lag, quality selection
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
