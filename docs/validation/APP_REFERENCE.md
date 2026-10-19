# Source-app comparison evidence

<!-- cspell:words Flojector -->

Calibrated forces is available by default for every import with usable directions.
Availability does not imply scientific qualification. [source-app projection decision](../architecture/09_architecture_decisions.md#source-app-projection)
defines the owner-adopted source-app policy; [explorer contracts](../implementation/RAW_EXPLORER.md)
define live smoothing and presentation.

## Computation and qualification

Normalize each stored vertical/lateral/longitudinal direction row independently,
project acceleration directly as source-app g, and apply a centered arithmetic
mean (odd windows 1–51, default 11). Do not add/subtract gravity, replace rounded directions with orthogonal axes,
or apply two successive calibration rotations. Retain
unfiltered projections. Recording-edge windows shorten/renormalize; source-app
edge handling and endIndex inclusion remain unverified. Compare inclusive marker
intervals without claiming the source app's exact selection convention.

The exact pinned Manta source at window 11 has owner-confirmed projection, units,
signs, filtering, replay, Combined and Orientation evidence. Other sources/windows
remain PROVISIONAL. Generic frame APIs retain their stricter independent gates.
Missing/invalid directions or unavailable numerical support preserve raw operation
with a calibration diagnostic. Hashes identify provenance, not feature eligibility.

| Quantity     | Source-app evidence / implementation limit                                                                              |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| Lateral      | Positive right, negative left                                                                                           |
| Longitudinal | Positive acceleration, negative braking                                                                                 |
| Combined     | Norm of filtered directional components; evidence tests only, no production Combined chart                              |
| Orientation  | Angle of normalized current source gravity to stored vertical, clipped cosine before acos; implemented for video export |
| Time         | Start-relative `MM:SS.ff`, ff is sample counter at integer rate; internal recording seconds remain index/rate           |

At 50 Hz default 11 samples has nominal N/rate 0.22 s, endpoint span 0.20 s and
±0.10 s support. Means are not cascaded. Manta unfiltered vertical extrema are
approximately -5.03988/+3.66707, distinct from its smoothed display.

## Corpus extrema regression

| Recording      | Source minimum | Reconstructed minimum | Source maximum | Reconstructed maximum |
| -------------- | -------------- | --------------------- | -------------- | --------------------- |
| Manta          | -3.720832109   | -3.720831193          | 2.614470243    | 2.614460771           |
| Iron Gwazi     | -1.333528161   | -1.333624797          | 3.784377098    | 3.784489785           |
| Kraken         | -0.220217317   | -0.220226569          | 4.076864719    | 4.076822294           |
| Taron          | -0.626344442   | -0.626451405          | 4.345596790    | 4.345766817           |
| Voltron Nevera | -1.598199964   | -1.598163271          | 4.365312576    | 4.365497903           |

These are vertical extrema at the compared 11-sample policy. The 0.0002 ceiling
is a corpus regression bound, not physical accuracy or private-algorithm identity.
Fixture identity/digests are in the [catalog](../development/RECORDINGS.md).

## Manta replay reference

Source rate 50 Hz, startIndex 1214 (recording 24.28 s). The following supplied
snapshots are independent comparison points; no parameters were fitted to them.

| Replay   | Sample | Recording seconds | Vertical g | Lateral g | Longitudinal g | Combined g | Orientation |
| -------- | ------ | ----------------- | ---------- | --------- | -------------- | ---------- | ----------- |
| 00:00.00 | 1214   | 24.28             | -0.04      | -0.01     | 0.99           | 0.99       | 92 degrees  |
| 00:10.00 | 1714   | 34.28             | 1.00       | 0.01      | -0.01          | 1.00       | 0 degrees   |
| 01:07.00 | 4564   | 91.28             | 0.52       | -0.02     | -0.08          | 0.52       | 47 degrees  |
| 01:12.00 | 4814   | 96.28             | -3.44      | 0.07      | 0.35           | 3.46       | 120 degrees |
| 01:26.00 | 5514   | 110.28            | 1.96       | -0.21     | 0.41           | 2.02       | 77 degrees  |

All 15 directional readouts and five Combined/Orientation readouts match at the
shown precision. At 01:26, directional values are 1.960580571/-0.214940883/
0.412735885; their norm is 2.015050041 (2.02 displayed). Averaging raw magnitudes
would give 2.115184090 and fails that reference. Orientation 77.397274 degrees
matches 77; averaging angles first gives 77.743270 and does not match.

Vertical minimum sample 4782 (recording 95.64 s; replay 71.36 s), maximum sample
5047 (100.94 s; replay 76.66 s). At gravityIndex 2013 vertical is approximately
0.9989; at inclineIndex 3370 vertical/longitudinal/lateral is 0.7414/0.6736/-0.0060.
The overview's initial longitudinal load, lift plateau and final vertical baseline
are visually consistent. This does not qualify arbitrary mounting or every file.

## Kraken replay reference and known discrepancy

Source rate 50 Hz, start/end 913/9138; selected span 164.5 s, recording offset
18.26 s. At `01:31.47`, index is `913 + 91*50 + 47 = 5510`; interpreting .47 as
hundredths selects a different sample and does not match.

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

Seven nonzero-time rows match all five readouts at shown precision. All eight
Orientation values match. At replay zero the computation instead rounds to
1.00/0.00/-0.10 g, Combined 1.00 g. This start mismatch remains open; neither raw
projection nor shortened selection-edge averaging establishes an equivalent rule.
Regression tests preserve the discrepancy without broad tolerances or fitted offsets.

Selected lateral extrema -0.711935869/+0.422388300 and longitudinal
-1.092671545/+0.447732913 agree visually with the overview patterns. At gravityIndex
1028, vertical/lateral/longitudinal is about 1.002325/-0.002091/0.002562;
at inclineIndex 2928, 0.932704/-0.006582/0.352202.

## Voltron Nevera reference and known discrepancy

Effective 50 Hz is an absence-only project default, not a measured acquisition
rate. Source start/end 1571/10374 gives recording offset 31.42 s and selected span
176.06 s. The two peak groups and near-1 g middle interval agree visually.

| Quantity     | Reconstructed minimum / maximum g | Screenshot comparison                                                  |
| ------------ | --------------------------------- | ---------------------------------------------------------------------- |
| Vertical     | -1.598163271 / 4.365497903        | -1.60 matches; shown maximum 4.36 differs from normal rounding to 4.37 |
| Lateral      | -1.262322395 / 0.920521857        | -1.26 / +0.92 match                                                    |
| Longitudinal | -1.208233927 / 1.072801471        | -1.21 / +1.07 match                                                    |
| Combined     | 0.094203046 / 4.436456817         | 0.09 / 4.44 match                                                      |

Stored vertical maximum 4.365312576 also normally rounds to 4.37. The displayed
4.36 difference remains unresolved; no truncation or retuning is applied.

Duration readouts are reference material for planned statistics, not implemented
algorithms. Threshold inclusion/crossing interpolation is unverified; independently
rounded bins may not sum exactly to totals:

| Statistic          | Screenshot seconds / bins                                   |
| ------------------ | ----------------------------------------------------------- |
| Vertical positives | 28.79 total; 2–3 g 11.31, 3–4 g 14.50, 4–5 g 2.98           |
| Vertical negatives | 21.02 total; Floater 10.89, Flojector 6.61, Ejector 3.53    |
| Acceleration       | 3.37 total; 0.5–1 g 2.96, 1–1.5 g 0.41                      |
| Braking            | 7.43 total; 0.5–1 g 6.90, 1–1.5 g 0.52                      |
| Combined positives | 29.26 total; 2–3 g 11.54; obscured bins are not transcribed |

## Weather metadata

Evidence is the owner-provided Voltron Nevera weather screenshot from 2026-10-17,
compared with the original authorized fixture.
Voltron's screenshot corroborates Mostly Clear, temperature 17.786710739135742
(17.8 °C), wind direction 195 degrees (SSW), speed 0.9936420124626161 m/s
(4 km/h rounded) and gust 3.874126195764542 m/s (14 km/h rounded).
Multiplying the source wind values by 3.6 matches the displayed integer km/h;
195 degrees lies in the 16-point SSW sector [191.25, 213.75). Temperature matches
the one-decimal Celsius display. This is a source-specific comparison, not a
guaranteed unit schema for every recording.
The importer retains all five optional fields; absent/invalid values retain
existing diagnostics. [Parser contract](../development/OPTIONAL_PARSING.md#weather-fields-and-source-app-evidence)
and the full-import regression cover exact accessors, rounding and original bytes.
Weather metadata is not currently a dedicated explorer panel.

## GPS comparison across all originals

GPS is coarse spatial context only. It must not control force calibration,
sensor timing, ride segmentation or force values. North-up local WGS84 plots
preserve source order; geographic distances below are approximations assuming
degrees. They are not measured track length, ride speed or ride elevation.

| Recording      | GPS points | GPS span s | Largest gap s | Approximate extent m E/W × N/S | Horizontal accuracy median / max | Negative speed entries |
| -------------- | ---------- | ---------- | ------------- | ------------------------------ | -------------------------------- | ---------------------- |
| Manta          | 193        | 192.00     | 1.00          | 118 × 170                      | 11.52 / 46.12                    | 36                     |
| Kraken         | 174        | 196.06     | 12.00         | 206 × 396                      | 22.09 / 199.99                   | 11                     |
| Taron          | 182        | 180.74     | 1.00          | 125 × 109                      | 42.11 / 380.26                   | 0                      |
| Voltron Nevera | 149        | 225.78     | 11.71         | 298 × 156                      | 25.03 / 199.99                   | 18                     |
| Iron Gwazi     | absent     | —          | —             | —                              | —                                | —                      |

All four sequences have increasing timestamps, approximately one-second median
intervals and all ten fields. Kraken has three gaps >2 s, Voltron 15, others none.
Accuracy units are not independently proved; Taron's maximum exceeds its full
plotted extent if interpreted as meters. Negative speed/course values remain
unqualified sentinels, never reverse travel or invented fixes.

Voltron's northeast cluster, southwest excursion and long crossing connections
visually match the supplied map. Exact point registration, track elements and
station/launch positions are unverified. Extent is 297.97×156.18 m, endpoint
separation 36.40 m, connected-point length 1,155.20 m, longest step 68.59 m.
Its GPS span 225.780630 s exceeds complete sensor span 210.06 s by 15.72 s;
GPS relative-to-source-date offsets +0.378860…+226.159490 do not establish shared
acquisition timing. GPS intervals range 0.005958–11.707501 s; nine exceed 5 s.
Horizontal accuracy source range 6.62–199.99 includes 27 entries >50 and 18 >100;
altitude 159.12–165.52 is not a qualified elevation profile. Speed/course have
18/46 negative entries respectively.

Connected-point lengths / endpoint separations (m): Manta 533.40/59.05,
Kraken 1,790.73/6.27, Taron 883.66/19.42. Crossings, jumps and endpoint clusters
do not identify ride elements. Iron Gwazi has no GPS and borrows no other route.
The implemented neutral-blue offline overview disconnects invalid/missing fixes
and missing/zero or negative/>2 s intervals; it provides no background map or speed colors.

### Source-speed color hypothesis

Nonnegative speed maxima are Manta 6.404428, Kraken 14.761415, Taron 13.328056,
Voltron 14.216463 (23.06/53.14/47.98/51.18 km/h if m/s). A common linear 0–15
source-unit green-to-red inspection scale gives qualitative Voltron agreement:
slow northeast points green, faster central return orange/red. Palette, thresholds,
normalization, interpolation and processed-vs-source speed are unverified. No maps
for the other three GPS originals are supplied, so cross-recording confirmation
is unavailable. Course availability does not imply speed availability.

Correlations between nonnegative ending-fix speed and adjacent distance/time are
Manta 0.318, Kraken 0.099, Taron 0.266, Voltron 0.346, without fitted lag, quality
selection or smoothing. The weak relationship means geometric step speed cannot
replace source speed. Speed coloring remains plausible, not a confirmed app contract.

## Verification boundary

Source-specific regressions cover these comparisons, weather accessors, smoothing,
force levels and GPS presentation using the pinned original recordings. Run the
maintained checks on native Windows from the repository root:

```text
uv run --locked pytest tests/analysis/test_reference.py tests/explorer/test_data.py tests/importers/test_optional.py
```

Independent screenshots and rounded numeric comparisons establish the scoped
contracts above, not pixel identity or private source-algorithm equivalence.
[explorer contract](../implementation/RAW_EXPLORER.md) and [analysis contract](../architecture/08_concepts.md#scientific-provenance-and-gates) own their
separate product acceptance. GPS units/epochs/sentinels and general physical
rider calibration remain unqualified.
