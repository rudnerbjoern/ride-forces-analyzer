# Motion parsing — DEV-REQ-002 Stage 3

Scope: FR-011–016 over an existing immutable source tree. This is a pure motion
validation boundary, not a complete file importer. Stage 2 decoding, dispatch and
resource guards are now implemented separately; GPS/metadata parsing and integration remain
planned. See [ADR 0002](../decisions/0002-forces-source-contract.md) and
[Stage 3 evidence](../validation/M2_STAGE3.md).

## API and caller obligations

```python
from ride_forces_analyzer.domain import SourceEnvelope
from ride_forces_analyzer.importers import MotionParseResult, parse_motion


def inspect_motion(source: SourceEnvelope) -> int | None:
    result: MotionParseResult = parse_motion(source)
    if result.success is True:
        return len(result.motion.acceleration)
    return None
```

Supply a SourceEnvelope whose root represents supported schema 2.2.0. Source
numbers must be SourceNumber values; source strings remain strings and arrays
are immutable tuples. The [strict decoder](STRICT_DECODING.md) establishes bytes/tree
correspondence, version support and document limits. Automatic integration with
this parser remains planned. There is no
file I/O, version dispatch, decoding, network, Qt or scientific transformation here.

MotionParseResult is MotionParseSuccess | ImportFailure. Success carries the
same source envelope, MotionSequence, RecordingIndices, RecordingVectors and
ordered diagnostics. It deliberately exposes no complete Recording or GPS status.
Failure carries no recording, at least one error, retained source and any known
nonempty version string. A success of this subset is not full M2 import acceptance
or permission to calculate rider-axis forces. Outcomes and source data are immutable.

## Conversion and preservation

Accept finite SourceNumber values and ASCII decimal strings: optional sign,
integer or decimal fraction, optional exponent. Leading zeros, `.5` and `1.`
are accepted for strings; JSON number tokens retain their stricter SourceNumber
grammar. Reject whitespace, empty strings, booleans, null, containers, underscores,
hexadecimal, nonnumeric tokens and results overflowing to infinity.

Typed accessors use normal Python float rounding; tiny magnitudes can underflow
to signed zero. Exact tokens, original strings, number/string distinctions and
all unknown fields remain in the unchanged source envelope and original bytes.
The parser never inserts defaults into source data, re-encodes bytes or normalizes
vectors. Unknown vector members survive without becoming extra coordinates.

A present sampleRate uses the same numeric conversion and must be positive and
finite. Valid non-50 rates win, with ValueOrigin.SOURCE. Only a missing property
uses 50 with ValueOrigin.DEFAULT. Null, zero, negative, malformed, overflowed or
rates that underflow to zero fail; they never receive the absence default.

## Motion, profiles, vectors and indices

Acceleration must be a nonempty array. Every original slot must contain an
object with valid x/y/z components; validation visits the final sample too.
Supplied gravity must validate completely and match acceleration length.
Missing/invalid samples, empty arrays and unequal lengths fail the subset;
no partial success, silent dropping, padding or truncation occurs.

Absent Apple Watch gravity is normal and remains None. Absent iPhone gravity
emits GRAVITY_UNAVAILABLE; unknown/missing device emits UNKNOWN_DEVICE_PROFILE.
Both warnings permit usable acceleration without inventing gravity. Actual
supplied gravity is always validated, including Apple Watch or advancedRecording=false.
The profile changes availability expectations only, not measured values.

All six direction/calibration vectors are optional. Missing vectors expose None.
Defective supplied vectors emit targeted warnings and expose None for that whole
vector, while valid sibling vectors remain usable. Extension fields are retained.
No rotation, normalization, polarity, units or rider G forces are inferred.

All supplied indices must be integer-valued JSON numbers, excluding booleans
and numeric strings. Integral fraction/exponent spellings are accepted without
rewriting source tokens; fractional values fail. Each is independently bounded
by the original acceleration array length, from zero through N-1.
startIndex/endIndex are required and start must not exceed end. Optional gravityIndex
and inclineIndex need no relation to each other or the start/end interval.
Taron retains gravityIndex=1513 before startIndex=2284. Iron Gwazi retains its
gravity marker even though no gravity array exists. No slicing or time coordinate
is produced; the end-index convention and GPS/time semantics remain unverified.

## Diagnostics and tests

Errors: MISSING_REQUIRED_FIELD, INVALID_SOURCE_ROOT, INVALID_MOTION_SEQUENCE,
INVALID_VECTOR, MISSING_VECTOR_COMPONENT, INVALID_NUMERIC_COMPONENT,
MOTION_LENGTH_MISMATCH, INVALID_SAMPLE_RATE, INVALID_INDEX, INDEX_OUT_OF_RANGE,
INVALID_INDEX_ORDER. Invalid optional vectors use warning severity for the same
vector/component codes. Device/gravity availability warnings are named above.

Each diagnostic uses an escaped JSON Pointer and, for a motion sample, its
original index. Messages identify defects without reproducing source values.
Ordering follows existing severity/pointer/code rules, including stable ties.
Document resource limits are now enforced by the Stage 2 decoder. Aggregate
diagnostic count enforcement for a combined pipeline remains integration work.

```powershell
uv run pytest tests/test_motion_parser.py
```

Parametric tests examine every component of all five recordings, retain their
bytes and modification times, and cover synthetic malformed containers, components,
rates, independent markers, optional vectors, device profiles, signed zero,
late-sample errors and deterministic outcomes. The shared Pyright contract suite
also checks narrowing of the motion-specific result union.
