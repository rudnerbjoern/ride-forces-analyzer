# Observed Ride Forces 2.2.0 file variants

**Evidence:** Four original read-only fixtures in
[the recording catalog](../development/RECORDINGS.md). This document records
**observations**, not a manufacturer-authored file-format specification.
Observation date: 2026-10-13. No scientific axis or time semantics are inferred.

## 1. Baseline comparison

| Field / observation | Kraken | Manta | Taron | Voltron Nevera |
| --- | --- | --- | --- | --- |
| `schemaVersion` | 2.2.0 | 2.2.0 | 2.2.0 | 2.2.0 |
| `sampleRate` | 50 | 50 | 50 | 50 |
| Acceleration samples | 10084 | 9640 | 9089 | 10504 |
| Gravity samples | 10084 | 9640 | 9089 | 10504 |
| GPS fixes | 174 | 193 | 182 | 149 |
| `startIndex` | 913 | 1214 | 2284 | 1571 |
| `endIndex` | 9138 | 9639 | 6639 | 10374 |
| `gravityIndex` | 1028 | 2013 | 1513 | 6894 |
| `inclineIndex` | 2928 | 3370 | 2852 | 7368 |
| `location` | SeaWorld Orlando | absent | Phantasialand | Europa-Park |
| `ridingPosition` | Seated | Flying | absent | absent |
| `attributes` count | 1 | 1 | 2 | 1 |
| Weather fields | all five | none | all five | all five |
| `advancedRecording` | true | true | true | true |
| `device` | iPhone | iPhone | iPhone | iPhone |

### Complete observed top-level field union (34 fields)

`accelerationSequence`, `advancedRecording`, `attributes`, `date`, `device`,
`endIndex`, `gravityIndex`, `gravitySequence`, `inclineIndex`,
`lateralDirectionVector`, `latitude`, `location`, `locationSequence`,
`longitude`, `longitudinalDirectionVector`, `maxForce`, `minForce`,
`name`, `ridingPosition`, `sampleRate`, `schemaVersion`,
`smoothingFactor`, `startIndex`, `temperature`, `timezone`, `uuid`,
`verticalDirectionVector`, `weatherConditions`, `windDirection`,
`windGust`, `windSpeed`, `xCalibrationVector`, `yCalibrationVector`,
`zCalibrationVector`.

Observed top-level **presence variations**:
- `location` is absent only for Manta.
- `ridingPosition` occurs only for Kraken and Manta.
- `temperature`, `weatherConditions`, `windDirection`, `windGust`,
  `windSpeed` occur for Kraken, Taron and Voltron Nevera, not Manta.
- All other listed union fields are present in all four observed files.
  This does **not** prove that they are universally mandatory.

## 2. Nested data and type evidence

### `accelerationSequence` and `gravitySequence`

Each is a JSON array of objects containing `x`, `y`, `z`.
Each of the four recorded first 1,000 acceleration samples has component types
`string`, `string`, `string`. Numeric strings such as `"0.973"`
must therefore be supported. The observed arrays have matching lengths per file;
this does not justify silently repairing a future mismatch. The key order differs
(e.g. Manta's first acceleration object orders `z,y,x`; Kraken orders `x,y,z`).

### Direction and calibration vectors

Top-level objects `verticalDirectionVector`, `lateralDirectionVector`,
`longitudinalDirectionVector`, `xCalibrationVector`, `yCalibrationVector`,
`zCalibrationVector` have `x`, `y`, `z` members. Member order varies by
file. Do not infer direction, units, length or handedness. Preserve full values.

### `locationSequence`

GPS fix objects were observed to contain the following members:
`timestamp`, `longitude`, `latitude`, `altitude`, `speed`,
`course`, `horizontalAccuracy`, `verticalAccuracy`,
`speedAccuracy`, `courseAccuracy`.
Observed `timestamp`, `speed` and `latitude` in each file's first 1,000
available fixes are JSON numbers. The GPS arrays have substantially fewer
entries than motion arrays and must not be indexed 1:1.

The first GPS fix in Kraken, Manta and Voltron Nevera has `speed: -1`;
Taron's first has `speed: 0`. Values of `-1` also occur in `course`,
`speedAccuracy` and `courseAccuracy`. These may be unavailable-value
sentinels but the upstream meaning is **not verified**; retain and warn rather
than replacing with numeric zero or declaring genuine negative motion.

### `attributes`

Each entry has `id`, `label`, `value`.
- Kraken: `Row=1`.
- Manta: `Row=1`.
- Taron: `Row=2`, `Seat=1` (two entries, in that order).
- Voltron Nevera: `Row=1`.

There is no basis for restricting attributes to `Row`/`Seat`; retain
arbitrary labels and unknown extra members.

## 3. Index and time anomalies

Taron has `gravityIndex=1513` before `startIndex=2284`.
Kraken's `gravityIndex=1028` is after start, and Manta's
`gravityIndex=2013` is after start. Consequently, a fixed rule requiring
`start <= gravity <= incline <= end` would incorrectly reject Taron.
Validate bounds but do not prescribe cross-marker order.

A sample-index divided by `sampleRate` produces a useful provisional
relative time, **not** a verified original device timestamp. The source
`date` field is a numeric value around hundreds of millions, as are
GPS fix timestamps; their epoch remains unverified. Also avoid assuming
source `date` and GPS `timestamp` necessarily have identical origin.

## 4. Semantics deliberately not asserted

- No manufacturer specification establishes `maxForce`/`minForce`
  calculation, sign, smoothing, axis or interpretation.
- `smoothingFactor=1` in these four examples is an observed value only.
- GPS speed/altitude units, sentinel rules and accuracy semantics require validation.
- The displayed `ridingPosition` values are metadata, not automatic proof of
  calibration correctness.
- The `endIndex` boundary convention is unverified.
- No raw per-motion-sample timestamp is visible in these four current
  `accelerationSequence` objects.
- Observed JSON object key order is not significant; raw source bytes must
  nevertheless be kept for exact source preservation.

## 5. Requirements consequences

The M2 importer must tolerate optional metadata, an arbitrary number of
attributes, numeric strings in sensor vectors, differing vector key order,
different lengths of independently timestamped GPS sequences and unconstrained
cross-marker ordering. It must fail meaningfully for invalid core data and
retain all original bytes and unknown fields for future reinterpretation.

See [DEV-REQ-002](DEV-REQ-002-forces-importer.md) and
[implementation plan](../implementation/DEV-REQ-002/PLAN.md).
