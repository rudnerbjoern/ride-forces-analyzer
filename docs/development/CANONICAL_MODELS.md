# Canonical models and diagnostics

The domain and result layers provide immutable representations. Construction
performs no decoding, schema dispatch, raw-field diagnostics, force calculation,
time inference or Qt integration.
[ADR 0002](../decisions/0002-forces-source-contract.md) defines the larger contract;
[M2 validation](../validation/M2.md) records actual verification.

## Public boundaries

Import data concepts from `ride_forces_analyzer.domain` and diagnostics/outcomes
from `ride_forces_analyzer.importers`. Domain modules have no importer/UI dependency.
Both packages use standard-library dataclasses with `frozen=True, slots=True`.
Pydantic continues to validate bootstrap settings; no new dependency is needed.

| Concept              | Implemented representation                                             |
| -------------------- | ---------------------------------------------------------------------- |
| Source ownership     | SourceEnvelope, SourceProvenance, SourceNumber, recursive SourceValue  |
| Motion               | Vector3, MotionSequence, SampleRate                                    |
| Indices and vectors  | RecordingIndices, RecordingVectors                                     |
| Optional metadata    | RecordingMetadata, RidingPosition, ValueOrigin                         |
| Ordered attributes   | Attribute; Recording.attributes is a tuple                             |
| Independent GPS      | GpsFix, GpsEntry, GpsSequence, GpsStatus                               |
| Complete domain view | Recording                                                              |
| Structured outcome   | ImportDiagnostic, Severity, ImportSuccess, ImportFailure, ImportResult |

## Original bytes and the source tree

`SourceEnvelope(original_bytes, root=None, *, source_path=None)` owns immutable bytes.
Passing a bytearray makes a copy before hashing; count and SHA-256 always describe
the retained bytes. The optional Path is provenance only: construction never
reads, checks or writes that path. `original_bytes` is the exact round-trip API,
including whitespace, BOM if supplied, key order and numeric spelling. A failed
later decode may retain bytes with `root=None`.

Supply a preconstructed object mapping for `root`. Every dictionary is copied
into an owned read-only mapping; every list/tuple becomes an owned tuple, including
unknown nested fields. Null, booleans, strings and explicit `SourceNumber` values
remain distinct. A missing property stays missing. Mutable input changes cannot
affect the envelope. Cycles, non-string object keys, native int/float scalars and
unsupported objects are rejected to prevent lossy/mutable source representations.

Construct `SourceNumber("1.00")` for a JSON number, and ordinary `"1.00"` for a
JSON string. Number tokens retain exact spelling plus a Decimal value, including
precision, exponent and signed zero. Equality distinguishes `1` from `1.0`.
The [decoder](STRICT_DECODING.md) captures tokens before float conversion and
enforces document/resource policies.

The model intentionally does not verify that supplied bytes and supplied tree
correspond. The decoder constructs both from the same retained input; see
[strict decoding](STRICT_DECODING.md). SourceEnvelope/Recording
equality is supported; objects containing mappings are not promised to be hashable
or serializable with `dataclasses.asdict`. Ordinary mutation is blocked; Python's
reflective `object.__setattr__` is not a security boundary.

## Canonical values and absence

Vector3/GpsFix accessors hold finite floats. Boolean, string and non-finite numeric
inputs cannot masquerade as measured numbers. No normalization, unit conversion,
projection, geographical rejection or epoch conversion occurs. Exact source values
remain separately available through the source envelope.

MotionSequence copies caller sequences into tuples. Acceleration is nonempty;
provided gravity must have equal length and valid Vector3 values. Absent gravity
is `None` and `paired_motion_available=False`, never zero vectors. Indices are
nonnegative, bounded by acceleration length, and start does not exceed end.
Start/end are effective bounds: missing source fields default to 0/N-1 with
INDEX_DEFAULTED warnings; source absence remains visible in the source envelope.
Gravity/incline markers may precede start or each other; no slicing occurs.
Constructors protect canonical consistency; the motion parser validates raw fields
and produces structured diagnostics.

SampleRate defaults to `(50.0, ValueOrigin.DEFAULT)` and RidingPosition to
`("Seated", ValueOrigin.DEFAULT)`, implementing the owner's absence policies.
Explicitly supplied valid source values use `ValueOrigin.SOURCE`; equal numeric
values with different origins remain distinguishable. Invalid source rate cannot
become a default; invalid optional riding position is represented by `None` and
a later parser warning. Constructors do not insert either default into source data
or infer presence by inspecting a source mapping.

Optional metadata uses `None`, not zero or false. Date, extrema and smoothing use
SourceNumber without scientific reinterpretation. Attributes preserve arbitrary
labels and order, and copy their source-valued nested payloads. All six optional
direction/calibration vectors have independent typed accessors.

GpsSequence preserves every original indexed slot as GpsEntry, including
`fix=None` for an unavailable fix. GPS count is independent of acceleration count.
Recording distinguishes ABSENT, PRESENT (including an empty sequence), and INVALID
(no usable container). Negative speed/course/accuracy and finite suspicious
coordinates remain represented. [Optional parsing](OPTIONAL_PARSING.md)
generates GPS/metadata warnings and accessors independently of full import.
The [motion parser](MOTION_PARSING.md) handles device-based gravity availability;
model constructors perform no profile inference.

## Diagnostics and results

ImportDiagnostic carries uppercase code, Severity, RFC 6901 JSON Pointer, nonempty
message and optional nonnegative source sample index. The empty pointer denotes
the root; `json_pointer` escapes arbitrary keys and indices. `ordered_diagnostics`
copies input and orders error/warning/info, then escaped pointer lexicographically,
then code. Exact ties retain emission order. Index 10 therefore sorts before index
2 in pointer text; this is the explicit ADR policy, not sample reordering.

ImportResult is the union of frozen ImportSuccess and ImportFailure. Success
requires a complete Recording and excludes error diagnostics. Failure requires at
least one error, always exposes `recording=None`, and can retain original bytes.
Unknown failure version, byte count and digest remain `None`. Known empty retained
bytes have count zero and a real digest, distinct from unreadable input.
Successful count/hash/version accessors expose the Recording's source provenance.

Use the literal tag or the result class for typed control flow:

```python
from ride_forces_analyzer.importers import ImportResult


def inspect_result(result: ImportResult) -> int | None:
    if result.success is True:
        return len(result.recording.motion.acceleration)
    return None
```

Both result constructors copy and order diagnostic lists. Standard representations
omit source bytes/tree, GPS coordinates, sequences and recording metadata to avoid
accidental trace dumps. Caller-supplied diagnostic messages still require safe,
field-oriented text; no automatic sensitive-content classifier is implemented.
Constructors perform no parsing; the [service](IMPORT_SERVICE.md) returns these
outcomes for full file/bytes imports.

## Validation

```powershell
uv run pytest tests/test_source_models.py tests/test_recording_models.py tests/test_import_results.py
uv run mypy src
npm run typecheck
npm run test:types
```

Pyright contracts exercise literal-tag narrowing, invalid typed
construction, frozen-field assignment and source-mapping mutation. Existing
Pydantic contracts remain in the same npm suite. Synthetic runtime tests cover
owned byte/tree/sequence inputs, exact source tokens, defaults and absence,
diagnostic ordering, consistent outcomes and a fresh Qt-free package import.
The five real recording integrity tests remain unchanged.

Frozen dataclasses alone do not freeze nested inputs, and MappingProxyType is a
dynamic view unless its backing dictionary is privately owned. These choices were
checked through Context7 against the official
[dataclasses](https://docs.python.org/3.14/library/dataclasses.html) and
[mapping proxy](https://docs.python.org/3.14/library/types.html#types.MappingProxyType)
documentation. The decoder enforces [resource limits](STRICT_DECODING.md).
Native Windows checks and measurements are recorded in
[M2 validation](../validation/M2.md).
Total process/native peak RAM remains unverified. Full M2 acceptance and its
hosted evidence are recorded in that report.
