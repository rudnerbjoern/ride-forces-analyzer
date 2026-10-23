# Motion parsing

Motion-only validation of an immutable source tree; no complete file import.
Architecture owns [composition](../architecture/05_building_block_view.md#importer-composition-and-interfaces)
and [source/scientific boundaries](../architecture/08_concepts.md).
The [public service](IMPORT_SERVICE.md) composes decoding, motion and optional data.

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

| Contract      | Requirement                                                                                                                                        |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Entry point   | `parse_motion(source, *, limits=DEFAULT_LIMITS)`                                                                                                   |
| Input         | `SourceEnvelope` for supported schema 2.2.0 or RFDB; `SourceNumber` numbers, unchanged strings, tuple arrays                                       |
| Preconditions | [Strict decoder](STRICT_DECODING.md) establishes bytes/tree correspondence, version and document budgets                                           |
| Success       | `MotionParseSuccess`: same source, `MotionSequence`, `RecordingIndices`, `RecordingVectors`, ordered diagnostics; no complete Recording/GPS status |
| Failure       | `ImportFailure`: no recording, at least one error, retained source and known nonempty version string                                               |
| Execution     | No I/O, decoding, dispatch, network, Qt or scientific transformation; immutable source/outcomes                                                    |

Subset success is neither full-import success nor rider-axis force qualification.
`limits.max_diagnostics` applies during generation; shape/byte guards require decoding.

## Conversion and preservation

| Input               | Conversion                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| Motion component    | Finite `SourceNumber` or ASCII decimal string: optional sign, integer/fraction, optional exponent             |
| String-only grammar | Leading zeros, `.5`, `1.` accepted; JSON numbers retain stricter token grammar                                |
| Rejected            | Whitespace, empty strings, booleans, null, containers, underscores, hex, nonnumeric tokens, infinity overflow |
| Float precision     | Normal Python rounding; tiny magnitudes can underflow to signed zero                                          |
| Present sampleRate  | Same conversion, positive/finite, `ValueOrigin.SOURCE`; non-50 rates take precedence                          |
| Absent sampleRate   | 50, `ValueOrigin.DEFAULT`; null/zero/negative/malformed/overflow/underflow-to-zero fail instead               |

Exact tokens/strings, number/string distinctions, unknown fields and original bytes
remain unchanged. No defaults enter source data; no re-encoding or normalization.
Unknown vector members survive without becoming coordinates.

## Motion, profiles, vectors and indices

| Field/profile                              | Rule                                                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Acceleration                               | Nonempty array; every original slot, including final sample, is an object with valid x/y/z                         |
| Supplied gravity                           | Complete validation and acceleration-matching length, even for Watch or `advancedRecording=false`                  |
| Invalid motion                             | Missing/invalid samples, empty arrays or unequal lengths fail; no partial success, dropping, padding or truncation |
| Absent Watch gravity                       | Normal, retained as `None`                                                                                         |
| Absent iPhone gravity                      | `GRAVITY_UNAVAILABLE` warning                                                                                      |
| Unknown/missing device                     | `UNKNOWN_DEVICE_PROFILE` warning                                                                                   |
| Profile effect                             | Availability expectations only; usable acceleration retained, no invented gravity/changed values                   |
| Six optional direction/calibration vectors | Missing = `None`; defective = targeted warning and whole-vector `None`; valid siblings/extensions retained         |

No rotation, normalization, polarity, units or rider G forces are inferred.

- Supplied indices require integer-valued JSON numbers, excluding booleans/strings.
  Integral fraction/exponent spellings retain tokens; fractional values fail.
- Each index is independently bounded to original acceleration 0…N−1.
  Absent start/end use effective 0/N−1 with `INDEX_DEFAULTED` warnings; invalid
  supplied values fail. Effective start ≤ end.
- Optional gravity/incline indices need no mutual/start-end relationship.
  Taron retains gravityIndex=1513 before startIndex=2284; Iron Gwazi retains
  its gravity marker without a gravity array.
- No slicing/time coordinate is produced. End-index convention and GPS/time
  semantics remain unverified.

## Diagnostics and tests

Errors: `MISSING_REQUIRED_FIELD`, `INVALID_SOURCE_ROOT`, `INVALID_MOTION_SEQUENCE`,
`INVALID_VECTOR`, `MISSING_VECTOR_COMPONENT`, `INVALID_NUMERIC_COMPONENT`,
`MOTION_LENGTH_MISMATCH`, `INVALID_SAMPLE_RATE`, `INVALID_INDEX`,
`INDEX_OUT_OF_RANGE`, `INVALID_INDEX_ORDER`. Optional vector defects use the same
vector/component codes at warning severity; availability/default warnings are above.
Diagnostic-budget exhaustion returns `RESOURCE_LIMIT_EXCEEDED`, without subset success.

Diagnostics use escaped JSON Pointers/original sample indices without source values.
Severity/pointer/code ordering has stable ties. Decoder document limits and
[shared service budgets](IMPORT_SERVICE.md#shared-diagnostic-budget-and-ordering)
remain distinct; standalone calls have independent budgets.
Invalid caller limits raise `ValueError`.

```powershell
uv run --locked pytest tests/importers/test_motion.py
```

Tests cover all components in five originals, bytes/modification-time integrity,
malformed containers/components/rates, independent markers, optional vectors,
profiles, signed zero, final-sample errors and determinism.
Shared Pyright contracts check motion-result union narrowing.
