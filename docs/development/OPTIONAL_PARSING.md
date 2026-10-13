# Optional data parsing — DEV-REQ-002 Stage 4

`importers.parse_optional_data(source: SourceEnvelope, *, limits: ImportLimits = DEFAULT_LIMITS)`
returns `OptionalParseSuccess | ImportFailure`. Supply a supported 2.2.0 envelope
from the [strict decoder](STRICT_DECODING.md). The function performs no I/O,
network access, motion validation, resampling, unit conversion or epoch conversion.
Its success describes only optional accessors, never a complete `Recording`.
The [motion parser](MOTION_PARSING.md) remains independently callable; the
separately authorized [Stage 5 service](IMPORT_SERVICE.md) now composes a complete import.

## Metadata and source ownership — FR-009–010, FR-022, FR-025

All bytes and the complete immutable source tree remain owned by the same envelope.
Unknown root/nested members, original strings, numeric tokens, nulls and absence
are preserved. No fields are inserted, normalized, trimmed or inferred from GPS.

- Text accessors: name, UUID, device, timezone, location and weather conditions
  accept JSON strings verbatim, including empty strings. No UUID/timezone vocabulary
  is imposed. Missing fields are `None`; wrong types warn and become unavailable.
- `advancedRecording` accepts JSON booleans only; absent and false remain distinct.
- Top-level latitude/longitude, temperature and wind direction/speed/gust accept
  finite JSON numbers only. Numeric strings, booleans, null and float overflow warn
  and become `None`. Zero, signed zero and finite negative values remain available.
- `date`, `smoothingFactor`, `maxForce` and `minForce` expose exact `SourceNumber`
  values. They are not interpreted as timestamps or recalculated physical extrema.
  The exact Decimal representation may exceed float range; no float is needed.
- Only **absent** `ridingPosition` produces `RidingPosition("Seated", DEFAULT)`.
  Any present string containing non-whitespace characters wins unchanged with SOURCE provenance. Invalid or
  blank presence warns and yields `None`; it never receives the absence default.

Typed numeric floats are approximate accessors. Exact tokens/Decimal values stay
in the envelope, including underflow and source precision beyond float precision.
These contracts use the existing [canonical models](CANONICAL_MODELS.md).

## Ordered arbitrary attributes — FR-017

Absent or defective attribute containers yield `attributes=None`; source presence
distinguishes the two. A present valid empty array yields `()`. Objects require
string `id` and `label` plus a present `value`. Empty/duplicate IDs and arbitrary
labels are preserved; values may be any immutable JSON source value, including
null, booleans, exact numbers, strings, arrays and objects. There is no fixed count.

Malformed entries warn at their original index and have no typed Attribute. Valid
siblings remain in original order; the complete original array and extensions
stay in the envelope. Typed attribute offsets after a defect are not source indices.
Taron's Row=2 then Seat=1 and Iron Gwazi's two entries are verified explicitly.

## Independent GPS — FR-018–021

`gps_status` distinguishes ABSENT, PRESENT and INVALID. PRESENT describes a valid
array container, including empty arrays and arrays whose fixes are all unavailable.
Each original element has a `GpsEntry(index, fix)`; invalid fixes keep `fix=None`
without dropping or shifting slots. The GPS count is independent of motion count.

Both latitude and longitude must be present finite JSON numbers for a usable fix.
Missing/null/boolean/string/object/array coordinates or float overflow make only
that fix unavailable. Other known fields (timestamp, altitude, speed, course and
all four accuracies) are independent optional finite-number accessors. A defective
member warns and becomes `None`; valid coordinates and siblings remain available.
An absent optional member needs no warning. No metadata coordinate is borrowed.

Every finite negative speed, course or accuracy remains available with a warning;
the policy is not restricted to the observed -1. Exact source signs determine
negativity, including a tiny negative value subject to float underflow to signed zero.
Signed zero itself is not negative. Finite large positive accuracies are not rejected
by an invented threshold. A negative source number beyond float range retains its
exact token with both negative-value and unavailable-member warnings. Values are
unverified source readings, not validated physical speeds or interpreted sentinels.

Two nonfatal heuristics produce contextual warnings: latitude outside ±90 or
longitude outside ±180 (conventional GPS bounds, not verified source units), and
a timestamp not greater than the previous usable timestamp. Timestamp comparisons
use exact source Decimals across unavailable/missing-timestamp gaps, considering
only usable fixes with valid timestamps. They do not sort entries, fill gaps,
derive elapsed time, convert epochs or align to motion. Suspicious finite fixes
remain available. Source-app units, precision claims and sentinel meanings remain open.

Missing Apple Watch GPS is normal. Missing iPhone GPS yields info only. Unknown
device-profile diagnostics belong to the motion parser; optional parsing does not
invent device capabilities or repeat that warning. Supplied Apple Watch GPS is
validated normally rather than discarded because the current fixture lacks it.

## Diagnostics and limits — FR-025

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

Messages identify fields/defects without source values or GPS traces. Ordering uses
the existing severity/JSON Pointer/code policy and original sample indices.
Document syntax, schema and shape budgets remain the decoder's responsibility;
constructing an arbitrary SourceEnvelope manually does not establish those guards.

Stage 4 enforces `limits.max_diagnostics` locally (default 1,000). Exactly at the
budget is accepted. The next diagnostic replaces the last slot with a fatal limit
record and stops parsing; no successful truncated warning set is returned.
The [full service](IMPORT_SERVICE.md) now shares this guard with motion validation;
decoder failures remain fail-fast single-diagnostic results.
Invalid caller limit configuration raises `ValueError` as in the decoder API.

## Verification and boundaries

```powershell
uv run pytest tests/test_optional_parser.py tests/test_project.py
uv run mypy src
npm run typecheck
npm run test:types
```

Tests compare all optional fields, attributes and all ten fields in all 698 GPS
fixes across the five recordings. Pinned byte count/SHA-256 and before/after bytes
and modification times verify integrity. Synthetic cases cover malformed fields,
independent counts, sparse/unavailable slots, arbitrary ordered attributes,
ownership, exact precision, negative values, deterministic warnings and budgets.
See [M2 validation](../validation/M2.md) for actual results.

This subset performs no full import, M3 scientific interpretation or Qt integration.
The separately authorized Stage 5 now supplies full-recording integration; M2
acceptance remains open; results are consolidated in the M2 validation report.
