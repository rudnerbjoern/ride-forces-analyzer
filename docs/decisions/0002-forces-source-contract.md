# ADR 0002 — Ride Forces source ownership and import boundaries

Status: Accepted and implemented for M2, 2026-10-13.
Requirements: [DEV-REQ-002](../requirements/DEV-REQ-002-forces-importer.md),
primarily FR-001, FR-004, FR-007, FR-024 and FR-030; also FR-003, FR-008,
FR-013, FR-018–027. The original Stage 0 decision was documentation-only.
Stage 1 now implements [canonical models and result types](../development/CANONICAL_MODELS.md);
Stage 5 now implements [complete read-only integration](../development/IMPORT_SERVICE.md)
with verified M2 acceptance; see [M2 validation](../validation/M2.md).
Stage 3 now implements [motion validation](../development/MOTION_PARSING.md)
over a supplied source envelope. Stage 2 now implements
[strict source decoding](../development/STRICT_DECODING.md); its scope is documented below.
Stage 4 now implements [optional-data parsing](../development/OPTIONAL_PARSING.md)
as an independent subset, including the GPS error policies below.

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

Stage 5 implements these contracts within the existing `importers` and
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
Implementation and acceptance evidence are consolidated in
[M2 validation](../validation/M2.md). Each implementation stage and Git
publication still require separate owner authorization.

## Stage 1 implementation choices — 2026-10-13

Use standard-library frozen dataclasses with slots for compact typed values;
copy sequences to tuples and recursively copy source mappings before exposing
readonly views. Frozen alone is insufficient for nested input ownership. Pydantic
remains the bootstrap validator; no new library is required. Context7 and the
[dataclass](https://docs.python.org/3.14/library/dataclasses.html)/
[mapping proxy](https://docs.python.org/3.14/library/types.html#types.MappingProxyType)
documentation informed these choices.

SourceNumber stores original token plus exact Decimal value. SourceEnvelope
owns bytes and computes provenance, optionally retaining a preconstructed frozen
root. Stage 1 cannot prove that supplied tree and bytes correspond without a
decoder; Stage 2 must create them from the same retained input. Source copying is
for normal Python inputs, not a replacement for document resource guards.

ImportResult is the ImportSuccess/ImportFailure union with immutable Literal
success fields. Use `success is True` or class checks for type narrowing. Model
constructors enforce consistent canonical values and outcomes; parser-specific
error/warning generation, device-profile interpretation and version dispatch
remain subsequent-stage responsibilities. This records implemented model choices,
not completion of the full proposed import contract.

## Stage 3 motion policy — FR-011–016

The separately authorized scope implements pure parse_motion(SourceEnvelope),
returning MotionParseSuccess | ImportFailure. Success represents only validated
motion/indices/vectors; it is not ImportSuccess or a complete Recording. Stage 2
supplies decoder dispatch/budgets, Stage 4 optional GPS and Stage 5 full composition.

Convert finite ASCII decimal strings and exact SourceNumber JSON numbers to
finite float accessors, retaining original strings/tokens/bytes. Decimal strings
allow sign, leading zeros, fractions and exponents, but no whitespace, underscores,
hexadecimal, boolean or null. Normal float rounding and underflow do not rewrite
the source. Unknown nested vector extensions remain preserved under FR-010;
only x/y/z are interpreted. Defective motion components are fatal; defective
optional structural vectors warn and become unavailable without normalization.

Only absent sampleRate uses the owner default 50 with DEFAULT provenance.
Present valid values retain SOURCE provenance, including non-50 values; invalid
present values never default. No relative time utility is authorized in this stage.

Apple Watch gravity absence remains normal and explicit. Missing iPhone gravity
warns; unknown/missing devices warn without inventing capabilities. Supplied
gravity must always be valid and pair exactly, regardless of device or
advancedRecording. Never synthesize, drop, pad or truncate measured arrays.

Indices are mathematically integral JSON numbers, not strings/booleans; finite
fraction/exponent spellings with integral values are accepted and retained.
Bound every supplied marker independently against acceleration, require only
start <= end, and perform no slicing. Taron's 1513 gravity marker before its 2284
start is explicitly valid. Iron Gwazi retains its gravity marker without gravity.
GPS/time/axis/end-index semantics remain unverified. See
[M2 validation](../validation/M2.md) for tests and remaining exit criteria.

## Stage 2 implementation decisions — FR-001, FR-003–010, FR-024, FR-026

The separately authorized Stage 2 implements decode_forces(Path) and
decode_forces_bytes(bytes), returning DecodeSuccess | ImportFailure. Keep the
import_forces API for complete Recording integration: decoded
JSON success must never masquerade as measured-data/import success.

Preflight checks all lexical/shape budgets iteratively before full tree allocation,
including extensions. It also detects duplicate decoded keys and invalid grammar;
standard-library constant/number/object-pair hooks provide a second strict boundary.
SourceNumber retains exact finite Decimal numbers, including values outside float
range; later motion accessors still check float finiteness. Required field and
component/index JSON shapes are checked without motion conversion or defaults.
Optional metadata/GPS and unknown fields remain losslessly available.

Defaults are the table above. All limit values must be positive non-boolean
integers below sys.maxsize. max_depth is configurable from 1 through 128, a
conservative ceiling for the recursive decoder/source ownership implementation;
do not mutate Python's recursion or integer-conversion settings. Stage 2 returns
one deterministic fatal error, so every supported diagnostic budget is honored.
Stage 5 now enforces the last-slot aggregate policy during validation.

Use unbuffered binary local reads, regular-file checks before and after opening,
short-read joining, individual chunks <=65,536 bytes and total reads <=max_bytes+1.
Reject Windows UNC/device paths before I/O. Do not retain oversized/partial input
or invent hashes/counts. Retain bounded original bytes on decoding errors; retain
the valid tree on schema errors. Permission/race tests use controlled mocks;
OS access times, mapped-drive locality and hostile filesystem behavior remain outside
verified evidence. See [M2 validation](../validation/M2.md).

## Stage 4 implementation decisions — FR-009–010, FR-017–022, FR-025

The separately authorized Stage 4 implements parse_optional_data(SourceEnvelope),
returning OptionalParseSuccess | ImportFailure. It uses existing canonical models
and preserves the same source envelope. Success covers only optional accessors;
it neither validates core motion nor constructs a complete Recording. Stage 5
now supplies integration and aggregate diagnostic-budget enforcement.

Absent ridingPosition alone uses Seated with DEFAULT provenance. Valid source
strings containing non-whitespace characters are not trimmed or restricted to a known posture vocabulary;
defective presence warns and becomes unavailable. Optional metadata types follow
the observed JSON representation: strings, booleans and finite-number accessors.
Date/extrema/smoothing expose exact SourceNumber tokens without float/epoch/force
interpretation. Unknown properties and missing/null distinctions survive.

Attributes accept arbitrary source-valued payloads, string IDs/labels and source
order, without a fixed count or label vocabulary. Invalid entries warn at their
original index and are unavailable in the typed tuple; valid sibling order and
the complete original array remain. Absent/invalid containers yield None, while
valid empty arrays yield an empty tuple. Source presence distinguishes absence
from defective presence; typed attribute offsets are not original source indices.

GPS follows the fix/member/container policy above. PRESENT means an array exists,
including empty or all-unavailable arrays; slots are never removed. Missing iPhone
GPS emits GPS_UNAVAILABLE info; Apple Watch absence needs no warning. Supplied
GPS is validated on either device. Conventional ±90/±180 coordinate bounds are
nonfatal heuristics only, without verified source-unit claims. Non-increasing
timestamps warn relative to the previous usable fix with a valid timestamp,
across missing/invalid gaps. Comparisons use exact Decimals; no sorting or elapsed
time is inferred. Negative warnings use exact source signs, including float
underflow. Finite positive accuracy/course values have no invented rejection bounds.

The optional subset enforces its local max_diagnostics budget: accept exactly at
the limit; on the next diagnostic replace the last slot with a fatal resource
record and stop without a successful subset. Default 1,000 and immutable per-call
limit configuration are unchanged. Shape/byte guards belong to prior decoding;
manual source trees are not proven bounded documents. The complete-pipeline budget
is now enforced by Stage 5. See [optional contracts](../development/OPTIONAL_PARSING.md)
and [M2 validation](../validation/M2.md) for verified acceptance evidence.

## Stage 5 integration decisions — FR-028–030

Expose import_forces(Path) and import_forces_bytes(bytes) through the importer
facade with the original ImportResult union. Compose strict decoding first,
motion validation second, optional validation last; stop at decoder/core failure.
Successful calls construct the existing complete Recording and retain the same
original source envelope, provenance, available data and ordered diagnostics.
There is no Qt/network/write integration, analysis, library or export behavior.

Use a shared per-call DiagnosticBudget for motion and optional validation workers.
The standalone parser facades each allocate their own budget; their default
behavior is preserved. Check during emission, including core errors, warnings
and info; accept exactly at the limit if no next diagnostic is emitted. On overflow,
replace the last slot with a fatal resource record at the triggering pointer and
stop without a Recording. Preserve the existing severity/pointer/code ordering;
an earlier core error can sort before the resource error. Decoder failures already
fit every positive budget with a single fail-fast diagnostic. No mutable recording
or collector is shared across calls, including concurrent bytes imports.

Absent/invalid attribute containers become an empty Recording.attributes tuple
because that is the existing model contract. Source presence and diagnostics keep
absence, defective presence and valid empty arrays distinguishable. Every GPS slot
and GPS status remain explicit. Complete refers to available source capabilities,
never validated M3 calibration, axes, units, epochs or GPS sentinel semantics.

Measure Windows Path and preloaded bytes APIs separately: one warmup, five timed
calls with GC outside timings, then one separate tracemalloc import. Report actual
Python allocation peaks, not total/native process RAM; disclose warm filesystem
cache and tracing overhead. Do not create throughput guarantees, a performance
threshold test or a new dependency. The development utility never rewrites a
fixture. See [public contracts](../development/IMPORT_SERVICE.md) and
[M2 validation](../validation/M2.md) for final Stage 6 acceptance and hosted CI evidence.

## Owner amendment — absent start/end boundaries, 2026-10-17

For the explorer's default view/reset, the owner specified independent fallbacks:
absent startIndex uses zero; absent endIndex uses N-1. Supported import therefore
allows these fields to be absent. Canonical indices retain effective bounded
values; INDEX_DEFAULTED warnings and unchanged source-envelope absence distinguish
fallbacks from stored markers. Present malformed, out-of-bounds or reversed indices
still fail. No source marker is fabricated and no end-index slicing is inferred.
