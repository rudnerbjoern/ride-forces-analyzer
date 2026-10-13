# Observed Ride Forces 2.2.0 file variants

**Evidence:** Five original read-only fixtures in the
[recording catalog](../development/RECORDINGS.md). Observations were reproduced
on 2026-10-13 by [the recursive inventory utility](../../tests/fixture_inventory.py)
and pinned in [the complete snapshot](../../tests/fixtures/schema-inventory.json).
This is an exhaustive corpus inventory, not a manufacturer-authored specification.
No scientific axis or time semantics are inferred.

<!-- cspell:words Phantasialand Gwazi -->

## 1. Device profiles and comparison

The original iPhone quartet uses `advancedRecording=true` and supplies paired
acceleration/gravity and GPS. The owner subsequently supplied Iron Gwazi from
Apple Watch and confirmed that `device` marks the data-availability profile.
Its `advancedRecording=false` recording omits gravity, GPS and top-level
coordinates. All five use the same schema version. Missing means the property
is absent, not null, empty or numeric zero. Expected availability is device-aware;
actual fields still need validation and must never be fabricated.

| Field / observation    | Kraken           | Manta  | Taron         | VoltronNevera | IronGwazi           |
| ---------------------- | ---------------- | ------ | ------------- | ------------- | ------------------- |
| `schemaVersion`        | 2.2.0            | 2.2.0  | 2.2.0         | 2.2.0         | 2.2.0               |
| `sampleRate`           | 50               | 50     | absent        | absent        | 50                  |
| `accelerationSequence` | 10084            | 9640   | 9089          | 10504         | 8712                |
| `gravitySequence`      | 10084            | 9640   | 9089          | 10504         | absent              |
| `locationSequence`     | 174              | 193    | 182           | 149           | absent              |
| `startIndex`           | 913              | 1214   | 2284          | 1571          | 1720                |
| `endIndex`             | 9138             | 9639   | 6639          | 10374         | 8179                |
| `gravityIndex`         | 1028             | 2013   | 1513          | 6894          | 7382                |
| `inclineIndex`         | 2928             | 3370   | 2852          | 7368          | 3121                |
| `location`             | SeaWorld Orlando | absent | Phantasialand | Europa-Park   | Busch Gardens Tampa |
| `ridingPosition`       | Seated           | Flying | absent        | absent        | Seated              |
| `attributes`           | 1                | 1      | 2             | 1             | 2                   |
| `advancedRecording`    | true             | true   | true          | true          | false               |
| `device`               | iPhone           | iPhone | iPhone        | iPhone        | Apple Watch         |

Weather fields are present in Kraken, Taron and Voltron Nevera and absent in
Manta and Iron Gwazi. Attributes retain source order: Row=1 for Kraken/Manta/
Voltron Nevera, Row=2 then Seat=1 for Taron, and Row=1 then Seat=1 for Iron Gwazi.
This is observed metadata, not a restricted attribute vocabulary.

## 2. Complete top-level field/type/presence matrix

The union remains **34 fields**. The following table includes every top-level
field, its observed JSON type and availability in each recording. Number token
classes distinguish an integer spelling from a fraction/exponent spelling;
both are JSON numbers. Presence does not prove universal mandatory fields.

| Field                         | Observed type                | Kraken  | Manta   | Taron   | VoltronNevera | IronGwazi |
| ----------------------------- | ---------------------------- | ------- | ------- | ------- | ------------- | --------- |
| `accelerationSequence`        | array                        | present | present | present | present       | present   |
| `advancedRecording`           | boolean                      | present | present | present | present       | present   |
| `attributes`                  | array                        | present | present | present | present       | present   |
| `date`                        | number (decimal_or_exponent) | present | present | present | present       | present   |
| `device`                      | string                       | present | present | present | present       | present   |
| `endIndex`                    | number (integer)             | present | present | present | present       | present   |
| `gravityIndex`                | number (integer)             | present | present | present | present       | present   |
| `gravitySequence`             | array                        | present | present | present | present       | absent    |
| `inclineIndex`                | number (integer)             | present | present | present | present       | present   |
| `lateralDirectionVector`      | object                       | present | present | present | present       | present   |
| `latitude`                    | number (decimal_or_exponent) | present | present | present | present       | absent    |
| `location`                    | string                       | present | absent  | present | present       | present   |
| `locationSequence`            | array                        | present | present | present | present       | absent    |
| `longitude`                   | number (decimal_or_exponent) | present | present | present | present       | absent    |
| `longitudinalDirectionVector` | object                       | present | present | present | present       | present   |
| `maxForce`                    | number (decimal_or_exponent) | present | present | present | present       | present   |
| `minForce`                    | number (decimal_or_exponent) | present | present | present | present       | present   |
| `name`                        | string                       | present | present | present | present       | present   |
| `ridingPosition`              | string                       | present | present | absent  | absent        | present   |
| `sampleRate`                  | number (integer)             | present | present | absent  | absent        | present   |
| `schemaVersion`               | string                       | present | present | present | present       | present   |
| `smoothingFactor`             | number (integer)             | present | present | present | present       | present   |
| `startIndex`                  | number (integer)             | present | present | present | present       | present   |
| `temperature`                 | number (decimal_or_exponent) | present | absent  | present | present       | absent    |
| `timezone`                    | string                       | present | present | present | present       | present   |
| `uuid`                        | string                       | present | present | present | present       | present   |
| `verticalDirectionVector`     | object                       | present | present | present | present       | present   |
| `weatherConditions`           | string                       | present | absent  | present | present       | absent    |
| `windDirection`               | number (integer)             | present | absent  | present | present       | absent    |
| `windGust`                    | number (decimal_or_exponent) | present | absent  | present | present       | absent    |
| `windSpeed`                   | number (decimal_or_exponent) | present | absent  | present | present       | absent    |
| `xCalibrationVector`          | object                       | present | present | present | present       | present   |
| `yCalibrationVector`          | object                       | present | present | present | present       | present   |
| `zCalibrationVector`          | object                       | present | present | present | present       | present   |

## 3. Exhaustive nested inventory

Every value and array element was visited, including the final motion samples.
The normalized path union has **76 paths**. No duplicate object keys, non-finite
JSON numbers, null values or mixed element types occur in this corpus. Files
decode as UTF-8 without a BOM. All have maximum container depth 3 (root object = 1).
The longest JSON number token has 22 characters; the longest string/key has 36.

| Recording     | Original bytes | JSON value nodes | Normalized paths | Root fields |
| ------------- | -------------- | ---------------- | ---------------- | ----------- |
| Kraken        | 837779         | 82643            | 76               | 34          |
| Manta         | 801293         | 79294            | 70               | 28          |
| Taron         | 782329         | 74773            | 74               | 32          |
| VoltronNevera | 862820         | 85726            | 74               | 32          |
| IronGwazi     | 346781         | 34900            | 52               | 25          |

The snapshot records each path's type histogram, object-member presence counts,
array-length histogram, number-token classes and negative-number counts, plus
string length bounds and finite-decimal-string counts. It also lists each root
field's present/absent files. A child member's count divided by its parent's
object count measures observed within-array presence; a missing parent is
reported separately rather than counted as a malformed child. Paths use `$`,
JSON-quoted object keys and `[*]` for every array element. Literal `"*"` keys
remain distinct from wildcards. Node totals exclude object key strings.

### Motion and six direction/calibration vectors

Every acceleration and present gravity element is exactly an object with x/y/z;
**every component in every sample** is a finite decimal string. This covers
48,029 acceleration vectors and 39,317 gravity vectors, not merely the first
1,000 elements. The six named direction/calibration objects also contain exactly
x/y/z, all finite decimal strings, in all five files. Member order varies.
Do not infer normalization, axes, handedness, polarity or physical units.

Present paired motion lengths match in all four iPhone files. Iron Gwazi has
8,712 acceleration samples and no gravity property. This is an observed missing
capability, not a mismatched array that may be padded or truncated. No current
motion object has a per-sample timestamp or any additional nested field.

### GPS fixes

All **698** fixes in the original quartet contain exactly `timestamp`,
`longitude`, `latitude`, `altitude`, `speed`, `course`, `horizontalAccuracy`,
`verticalAccuracy`, `speedAccuracy`, `courseAccuracy`. Every member is a finite
JSON number. No member is missing within those fixes. Iron Gwazi has no GPS
property; its GPS length is therefore absent, not zero.
GPS arrays are independent of motion arrays and must not be indexed 1:1.
Negative-value counts below cover every fix and do not establish sentinel units
or meaning. All negative values counted in these six fields are exactly -1.

| GPS member with negative values | Kraken | Manta | Taron | VoltronNevera | IronGwazi |
| ------------------------------- | ------ | ----- | ----- | ------------- | --------- |
| `speed`                         | 11     | 36    | 0     | 18            | absent    |
| `course`                        | 33     | 36    | 46    | 46            | absent    |
| `speedAccuracy`                 | 13     | 36    | 0     | 18            | absent    |
| `courseAccuracy`                | 35     | 36    | 46    | 52            | absent    |
| `horizontalAccuracy`            | 0      | 0     | 0     | 0             | absent    |
| `verticalAccuracy`              | 0      | 0     | 0     | 0             | absent    |

The first speed is -1 for Kraken, Manta and Voltron Nevera and 0 for Taron.
No negative horizontal/vertical accuracy occurs in this corpus. Neither this
absence nor a negative count proves future validity or a universal sentinel rule.

### Attributes and other nesting

Every attribute is an object with exactly `id`, `label`, `value`, all strings.
Each iPhone file has four arrays (acceleration, gravity, GPS, attributes);
Iron Gwazi has two arrays. There are no further nested arrays or object shapes.
Empty arrays/objects and null are absent in these originals; synthetic inventory
tests distinguish them from missing properties.

## 4. Index, timing and semantic boundaries

Taron has gravityIndex=1513 before startIndex=2284. Iron Gwazi has
inclineIndex=3121 before gravityIndex=7382, even though no gravity sequence is
stored. Therefore no cross-marker order, marker removal or gravity reconstruction
may be inferred. All supplied indices are bounded by acceleration length.
The inclusive/exclusive interpretation of endIndex remains unverified.

Three sample rates are explicitly 50; Taron and Voltron Nevera omit the field.
All smoothing factors are 1. Index/rate may support
an explicitly inferred relative coordinate later, not a measured timestamp.
The source date/GPS timestamp epoch, agreement of their origins, GPS units and
negative sentinel meanings remain unverified. Source extrema are preserved,
not recomputed. Device and riding position do not prove calibration correctness.

### Owner-specified defaults, separate from observations

The owner instructed on 2026-10-13 that absent ridingPosition uses effective
`"Seated"` and absent sampleRate uses effective 50 Hz. Taron and Voltron Nevera
therefore receive these defaults in the typed domain view: Stage 3 implements
sample rate and [Stage 4](../development/OPTIONAL_PARSING.md) implements riding position.
Raw source fields
stay absent; provenance distinguishes default from source. Invalid present
values do not trigger an absence default. This is an explicit importer policy,
not a rewritten fixture or verified manufacturer rule.

## 5. Reproduction and reconciliation

From the repository root with native Windows Python 3.14.6 / uv:

```powershell
uv run python tests/fixture_inventory.py --output .tmp/schema-inventory.json
uv run pytest tests/test_fixture_inventory.py tests/test_project.py
```

The CLI writes only under `.tmp/` and never updates the expected snapshot or an
original recording. Tests compare deterministic UTF-8/LF snapshot bytes, cover
late-element extensions, mixed types, optional nesting, escaped keys, empty/null
values and object-order independence. Duplicate members/non-JSON constants are
rejected to prevent misleading inventory. This test helper is not the production
importer, resource guard or canonical model.

Reconciliation: the prior 34-field union and motion/GPS quartet counts remain
correct. The prior assertion of sampleRate presence in every file was incorrect:
Taron and Voltron Nevera omit it, now covered by the explicit owner default.
Earlier prefix-only claims for motion types are now verified over every sample;
GPS type evidence covers all ten fields in all fixes. Iron Gwazi adds no new
field but disproves universally present gravity/GPS/coordinates and universal
iPhone/advanced-recording assumptions. FR-008/FR-013 and acceptance wording now
reflect a usable acceleration-only Apple Watch profile.
See [ADR 0002](../decisions/0002-forces-source-contract.md) for FR-001, FR-004,
FR-007, FR-024 and FR-030 decisions and explicit future implementation boundaries.
