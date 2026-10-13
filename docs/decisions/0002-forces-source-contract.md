# ADR 0002 — Ride Forces source ownership and import boundaries

Status: Proposed implementation contract, Stage 0 review, 2026-10-13.
Requirements: [DEV-REQ-002](../requirements/DEV-REQ-002-forces-importer.md),
primarily FR-001, FR-004, FR-007, FR-024 and FR-030; also FR-003, FR-008,
FR-013, FR-018–027. No production importer or canonical model is implemented.

## Evidence and context

The [complete recursive inventory](../../tests/fixtures/schema-inventory.json)
covers the four original iPhone recordings and the owner-supplied Iron Gwazi
Apple Watch recording. See [format observations](../requirements/FORMAT-ANALYSIS.md).
All five use schema `2.2.0`; the union has 34 top-level fields and 76 normalized
paths. Individual recordings have 25–34 top-level fields, 52–76 paths, depth 3,
34,900–85,726 JSON values and 346,781–862,820 original bytes. Every array element
was visited; this is not a prefix sample or a manufacturer specification.

The owner confirmed that `device` identifies the data-availability profile:
Apple Watch provides fewer fields than iPhone. Iron Gwazi has
`device="Apple Watch"`, `advancedRecording=false` and 8,712 acceleration samples,
with no gravity sequence, GPS sequence or top-level coordinates. The original
quartet has `device="iPhone"`, `advancedRecording=true`, paired motion and GPS.
The previous unconditional gravity requirement would reject a genuine recording.

## Public API and capabilities — FR-001, FR-030

Implement these contracts in later stages, within the existing `importers` and
`domain` packages, independently of Qt:

```python
import_forces(path: Path, *, limits: ImportLimits = DEFAULT_LIMITS) -> ImportResult
import_forces_bytes(data: bytes, *, limits: ImportLimits = DEFAULT_LIMITS) -> ImportResult
```

The path adapter performs bounded, binary, read-only local I/O and delegates to
pure decoding/validation. The bytes API accepts immutable bytes. Neither mutates
input, accesses the network or changes process-wide decoder settings. Invalid
caller limit configuration raises `ValueError` before I/O; expected source/I/O
defects produce an `ImportResult`, not uncaught decoder exceptions.

`ImportResult` is an immutable success/failure union. Success has a complete,
validated `Recording` for its available capabilities and no error diagnostics.
Failure has no recording and at least one error diagnostic. Warnings and info
are allowed on success. On unreadable/oversized input, schema, retained source,
exact byte count and hash may be unavailable (`None`); never fabricate a hash or
report partial-read counts as the complete source length. Successful results
always include exact original bytes, byte count, SHA-256 and recognized version.

The core requires schema version, nonempty acceleration, start/end indices and
every acceleration x/y/z component, with a positive finite effective sample rate. Gravity is an
optional capability. When supplied it must be valid, nonempty and the same
length as acceleration; invalid supplied gravity is fatal, never omitted,
truncated or padded. Missing gravity is normal for the Apple Watch profile.
For iPhone it emits `GRAVITY_UNAVAILABLE` warning; an unknown/missing device emits
`UNKNOWN_DEVICE_PROFILE` warning and never implies a capability. `advancedRecording`
is preserved separately and does not fabricate data or override present arrays.

Expose `paired_motion_available` and GPS availability explicitly. A successful
acceleration-only recording is not a claim of eligibility for M3 rider-axis
analysis. The device profile controls expected availability, not axis polarity,
units, timestamp epoch, calibration validity or universal mandatory-field rules.
Future fields on either device survive unchanged and are validated when used.

## Explicit owner defaults — FR-030, FR-009, FR-012

The owner specified two defaults on 2026-10-13. When the source property is
**absent**, the domain view exposes effective `ridingPosition="Seated"` and
`sampleRate=50` Hz. The source envelope keeps those properties absent. Record
explicit provenance for each accessor (`source` versus `default`) so callers
can distinguish stored data from policy. A valid present value always wins,
including `"Flying"` or a non-50 sample rate.

A present invalid rate (including null, boolean, non-finite, zero or negative value)
is a core error; do not apply the absence default. A present defective riding
position is an optional-field warning and unavailable accessor, not silently
`"Seated"`. Taron/Voltron Nevera lack both properties; three other recordings
store rate 50 explicitly. Defaults are owner policy, not empirical proof of
manufacturer conventions. Any index/rate time coordinate remains inferred;
M2 does not generate per-sample timestamps or decide an epoch.

## Source envelope ownership — FR-004

Choose in-memory immutable original bytes, not a reference to a mutable path.
The source path is optional provenance only. Retain bytes before interpreting
them and hash those bytes. Round-trip means retrieving identical bytes, not
re-encoding a decoded tree. Whitespace, key order, numeric spelling and every GPS
value therefore survive, even if the original file later moves or changes.

Additionally expose a recursively immutable source tree: fresh owned read-only
object mappings, ordered tuples for arrays and immutable scalar values. Keep
JSON number tokens and exact numeric values in a distinct number representation;
never confuse numbers with numeric strings or booleans. Unknown nested fields,
missing versus null properties and array order remain distinguishable. Decoded
mutable dictionaries must not escape through an accessor. A failed supported
parse may retain bounded original bytes but must not expose an invalid tree as
a valid recording. Oversized input is not retained in full.

Do not intentionally change source bytes, names or timestamps. OS-managed access
time may change on a read; tests verify bytes, SHA-256, size and modification time,
not an impossible filesystem-wide promise about access time.

## Strict decoding and dispatch — FR-007, FR-024

Use strict UTF-8, accepting a single leading UTF-8 BOM only as a decoding marker
while retaining it in source bytes. Do not guess UTF-16/32 or legacy encodings.
Require one JSON root object and reject duplicate members at every depth, invalid
syntax, non-JSON constants and non-finite domain values. Preserve exact finite
JSON numbers in the source tree; check finiteness again when building float
accessors. Unsupported versions return `UNSUPPORTED_SCHEMA_VERSION`; missing or
non-string version is `INVALID_SCHEMA_VERSION`. Dispatch only literal `2.2.0`,
without treating a device profile as a different schema version.

Unknown fields within `2.2.0` are preserved, subject to the same resource limits.
No automatic best-effort success for another version. Safe unsupported-version
inspection may retain bounded raw bytes/version/provenance but no `Recording`.
Before supporting a later version, add authorized evidence, an inventory, an
explicit adapter/dispatch entry, fixtures and version-specific contract tests;
review this ADR and retain the old adapter's regression suite.

Python's JSON defaults accept duplicate names and non-JSON numeric constants;
explicit hooks/policies are required. Context7 and the
[Python 3.14 JSON documentation](https://docs.python.org/3.14/library/json.html)
were consulted for these decoder boundaries and resource concerns.

## Configurable resource policy — FR-024

These are proposed conservative application defaults, not source-schema limits
or measured throughput guarantees. Counts include unknown extension fields.

| Limit                         | Default    | Corpus maximum |
| ----------------------------- | ---------- | -------------- |
| Original input bytes          | 16,777,216 | 862,820        |
| Container depth, root = 1     | 32         | 3              |
| Elements in each array        | 100,000    | 10,504         |
| Total JSON value nodes        | 1,000,000  | 85,726         |
| Members in each object        | 1,024      | 34             |
| Decoded string/key characters | 65,536     | 36             |
| JSON number-token characters  | 128        | 22             |
| Diagnostic records            | 1,000      | not measured   |

Each limit is a positive non-boolean integer, configurable per call. Exactly at
a limit is accepted; exceeding it fails with `RESOURCE_LIMIT_EXCEEDED` and a
specific limit name/path. Invalid non-regular input paths fail structurally.
Do not rely on a file stat alone: read at most byte limit + 1 to detect growth.
A JSON-aware iterative lexical preflight must enforce nesting, token lengths,
node/member/array budgets before full-tree allocation; handle escaped quotes,
Unicode escapes and brackets inside strings correctly. Strict decoding still
checks grammar and duplicate keys afterward. Cap diagnostics, reserving the
last slot for a fatal limit diagnostic rather than silently dropping warnings.

These input budgets bound accepted shape, not exact peak RAM or CPU. Stage 2
must test every threshold, adversarial nesting/escaping, unknown fields and
bounded reads. Stage 5 measures actual Windows memory/time. The test-only
inventory utility is for pinned trusted fixtures and is not this resource guard.

## Optional GPS errors and diagnostic policy — FR-030

- Missing GPS is normal for Apple Watch. Preserve absence distinctly from a
  present empty array. A missing iPhone GPS sequence is informational, not fatal.
- An invalid GPS container yields `INVALID_OPTIONAL_GPS` warning, unavailable
  typed GPS and retained original content. Syntax/duplicate-key/resource errors
  anywhere, including GPS, remain fatal whole-document errors.
- Preserve source sequence length/order via immutable indexed `GpsEntry` slots.
  Latitude and longitude must be finite JSON numbers to expose a `GpsFix`;
  booleans, numeric strings, null or missing required coordinates make only that
  fix unavailable and emit `INVALID_GPS_FIX`. Do not silently drop its slot.
- Other GPS members, including timestamp, are optional finite-number accessors.
  Defective members produce `INVALID_OPTIONAL_GPS_FIELD` warning and `None` for
  that member while valid coordinates remain usable. Never substitute zero,
  borrow coordinates from metadata or align fixes to acceleration indices.
- Negative speed/course/accuracy values remain available as unverified source
  numbers with `GPS_NEGATIVE_VALUE` warnings. Finite suspicious coordinates and
  non-increasing timestamps produce contextual `GPS_SUSPICIOUS_VALUE` warnings,
  not rejection. No unit conversion or epoch assumption occurs in M2.
- All invalid fixes may coexist with a usable core recording: GPS status is
  explicit and each original slot/content survives. Hitting a global resource
  budget, including diagnostic count, fails the complete import.

Diagnostics use stable codes, severity, RFC 6901 JSON Pointer, message and optional
source sequence index. Order is error/warning/info, then escaped pointer
lexicographically, then code; preserve emission order for exact ties. Messages
name fields and defects, never whole recordings or coordinate values. Missing
optional metadata is absent; defective optional metadata warns. Core motion,
index or paired-length errors fail. These codes and policies are API decisions
for subsequent implementation, not behavior established by Stage 0 tests.

## Consequences and readiness

FR-008/FR-013 and AC-01 are revised to retain the genuine Apple Watch profile
without fabricating missing gravity/GPS. FR-001/FR-004/FR-007/FR-024/FR-030 now
have explicit proposed contracts. Snapshot and integrity tests establish the
source evidence and AC-02 for this inspection, not full M2 import acceptance.
Source-app epochs, axes, end-index convention and GPS sentinels remain open.
Stage 1 may implement models only after a separate owner instruction; no later
stage is started by this ADR. Publication and merge remain separately authorized.
