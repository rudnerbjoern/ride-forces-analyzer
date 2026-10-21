# Optional data parsing

`importers.parse_optional_data(source: SourceEnvelope, *, limits: ImportLimits = DEFAULT_LIMITS)`
returns `OptionalParseSuccess` or `ImportFailure`. Input: supported 2.2.0 envelope
from the [strict decoder](STRICT_DECODING.md). No I/O, network, Qt, motion validation,
resampling, unit/epoch conversion or scientific interpretation.
Success provides optional accessors, never a complete Recording.

Architecture owns [composition](../architecture/05_building_block_view.md#importer-composition-and-interfaces)
and [source/scientific boundaries](../architecture/08_concepts.md).
The [motion parser](MOTION_PARSING.md) is independent;
the [public service](IMPORT_SERVICE.md) composes complete imports.

## Metadata and source ownership

The same envelope retains bytes/tree, unknown members, original strings/numbers,
null/absence and precision. No insertion, normalization, trimming or GPS inference.
Typed floats are approximate; exact tokens/Decimals preserve underflow and precision
beyond float range. See [canonical models](CANONICAL_MODELS.md).

| Accessor                                                        | Rule                                                                                                                                          |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| name, UUID, device, timezone, location, weather conditions      | Verbatim JSON strings, including empty; no UUID/timezone vocabulary; missing = `None`, wrong type = warning/unavailable                       |
| advancedRecording                                               | JSON boolean only; absent differs from false                                                                                                  |
| Root latitude/longitude, temperature, wind direction/speed/gust | Finite JSON numbers only; strings/booleans/null/float overflow warn and yield `None`; zero/signed zero/finite negatives retained              |
| date, smoothingFactor, maxForce, minForce                       | Exact `SourceNumber`, possibly beyond float range; no epoch interpretation or extrema recalculation                                           |
| Absent ridingPosition                                           | `RidingPosition("Seated", DEFAULT)`                                                                                                           |
| Present ridingPosition                                          | Any string with non-whitespace content retained verbatim with SOURCE provenance; invalid/blank warns and yields `None`, never absence default |

## Ordered arbitrary attributes

| Container/entry            | Result                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------------------ |
| Absent/defective container | `attributes=None`; source presence distinguishes them                                            |
| Valid empty array          | `()`                                                                                             |
| Valid object               | String id/label and present value; empty/duplicate IDs/arbitrary labels retained; no fixed count |
| Value                      | Any immutable JSON source value: null, boolean, exact number, string, array or object            |
| Malformed entry            | Warning at original index; no typed Attribute; valid siblings retain order                       |

Original array/extensions remain in the envelope; typed offsets after defects are
not source indices. Tests explicitly retain Taron Row=2 then Seat=1 and Iron Gwazi's two entries.

## Independent GPS

| Contract              | Rule                                                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Status                | `ABSENT`, `PRESENT`, `INVALID`; PRESENT means array container, including empty/all-unavailable arrays                                 |
| Slots                 | Every original element retains `GpsEntry(index, fix)`; invalid fixes use `None`, never dropped/shifted                                |
| Count                 | Independent of motion count                                                                                                           |
| Coordinates           | Both latitude/longitude must be present finite JSON numbers; missing/null/boolean/string/object/array/overflow disables only that fix |
| Other members         | Timestamp, altitude, speed, course, horizontal/vertical/speed/course accuracies: independent optional finite-number accessors         |
| Member defect         | Warning and `None`; valid coordinates/siblings survive; absent optional members need no warning                                       |
| Coordinate provenance | Never borrow metadata coordinates                                                                                                     |

- Every finite negative speed/course/accuracy remains available with a warning,
  not just observed −1. Exact source signs determine negativity, including
  underflow to signed zero; signed zero itself is not negative.
- No invented upper accuracy threshold. Negative values beyond float range retain
  exact tokens with both negative-value/unavailable-member warnings.
- Context warnings: latitude outside ±90/longitude outside ±180, or timestamp not
  greater than previous usable timestamp. Bounds are conventional, not verified units.
- Timestamp comparisons use exact Decimals across unavailable/missing-timestamp
  gaps, considering only usable fixes with valid timestamps.
- Suspicious finite fixes remain available. No sorting, gap filling, elapsed-time
  derivation, epoch conversion or motion alignment. Speeds, units, precision claims
  and sentinel meanings remain unverified.
- Absent Watch GPS is normal; absent iPhone GPS gives info only. Motion owns unknown
  device-profile warnings; optional parsing neither repeats them nor invents capabilities.
  Supplied Watch GPS is validated even though the current fixture lacks it.

## Diagnostics and limits

| Code                        | Severity | Typed effect                                                  |
| --------------------------- | -------- | ------------------------------------------------------------- |
| INVALID_OPTIONAL_METADATA   | warning  | Defective metadata accessor unavailable                       |
| INVALID_OPTIONAL_ATTRIBUTES | warning  | Attribute container unavailable                               |
| INVALID_ATTRIBUTE           | warning  | Entry unavailable; valid siblings retain order                |
| INVALID_OPTIONAL_GPS        | warning  | GPS status INVALID; original container retained               |
| INVALID_GPS_FIX             | warning  | Original indexed slot has no usable fix                       |
| INVALID_OPTIONAL_GPS_FIELD  | warning  | Defective member unavailable; valid coordinates remain usable |
| GPS_NEGATIVE_VALUE          | warning  | Negative source reading retained with unverified meaning      |
| GPS_SUSPICIOUS_VALUE        | warning  | Suspicious finite reading retained                            |
| GPS_UNAVAILABLE             | info     | iPhone GPS absent, no fabricated sequence                     |
| INVALID_SOURCE_ROOT         | error    | Source object unavailable, no subset result                   |
| RESOURCE_LIMIT_EXCEEDED     | error    | Diagnostic budget exceeded, no subset result                  |

- Messages omit source values/GPS traces; ordering follows severity/escaped JSON
  Pointer/code with original sample indices.
- Decoder owns syntax/schema/document-shape guards; a manually constructed
  SourceEnvelope does not establish them.
- Local `limits.max_diagnostics` defaults to 1,000; exact budget accepted.
  Next diagnostic replaces last slot with a fatal limit record and stops parsing;
  no successful truncated warnings.
- [Full service](IMPORT_SERVICE.md#shared-diagnostic-budget-and-ordering) shares the
  guard with motion; decoder failures remain fail-fast single diagnostics.
  Invalid caller limits raise `ValueError`.

## Verification and boundaries

```powershell
uv run --locked pytest tests/importers/test_optional.py tests/recordings/test_integrity.py
```

Tests compare optional fields/attributes and all ten fields in 650 GPS fixes across
five originals; pinned byte counts/SHA-256, bytes/modification times protect integrity.
Synthetic coverage: malformed fields, independent counts, sparse slots, arbitrary
attributes, ownership/precision, negative values, deterministic warnings and budgets.
[Source observations/limits](../architecture/08_concepts.md#source-ownership-and-validation)
remain distinct from complete-import or scientific qualification.

## Weather fields and source-app evidence

Full imports expose weather in `Recording.metadata`:

| Source key        | Metadata accessor  |
| ----------------- | ------------------ |
| weatherConditions | weather_conditions |
| temperature       | temperature        |
| windDirection     | wind_direction     |
| windSpeed         | wind_speed         |
| windGust          | wind_gust          |

[Voltron weather evidence](../validation/APP_REFERENCE.md#weather-metadata) retains
screenshots, exact values and observed conversions, without guaranteeing units for
every recording. Preserve source units/precision/text and exact envelope tokens;
no conversion, compass labels or network lookup. Absent = `None`; invalid optional
values warn without blocking otherwise usable import, subject to resource limits.
Explorer weather display is separate from metadata import.
