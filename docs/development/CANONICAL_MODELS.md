# Canonical models and diagnostics

API reference for immutable domain values and import outcomes. Architecture remains
authoritative for [subsystem boundaries](../architecture/05_building_block_view.md#importer-composition-and-interfaces),
[source ownership/defaults/diagnostics](../architecture/08_concepts.md#source-ownership-and-validation),
[import decisions](../architecture/09_architecture_decisions.md#source-ownership-and-import)
and [scientific/resource limits](../architecture/11_technical_risks.md).

## Public boundaries

- Domain imports: `ride_forces_analyzer.domain`; diagnostics/results:
  `ride_forces_analyzer.importers`.
- Models use standard-library `dataclasses` with `frozen=True, slots=True`.
- Constructors validate supplied canonical values; no decoding, schema dispatch,
  raw-field diagnostics, time inference, force calculation or Qt integration.
- Settings use a [separate runtime contract](CODE_QUALITY.md#runtime-and-static-contracts).

| Concept                     | Types                                                                            |
| :-------------------------- | :------------------------------------------------------------------------------- |
| Original source             | `SourceEnvelope`, `SourceProvenance`, `SourceNumber`, recursive `SourceValue`    |
| Motion                      | `Vector3`, `MotionSequence`, `SampleRate`                                        |
| Markers and vectors         | `RecordingIndices`, `RecordingVectors`                                           |
| Metadata/default provenance | `RecordingMetadata`, `RidingPosition`, `ValueOrigin`                             |
| Ordered attributes          | `Attribute`; `Recording.attributes` is a tuple                                   |
| Independent GPS             | `GpsFix`, `GpsEntry`, `GpsSequence`, `GpsStatus`                                 |
| Complete recording          | `Recording`                                                                      |
| Diagnostics/outcomes        | `ImportDiagnostic`, `Severity`, `ImportSuccess`, `ImportFailure`, `ImportResult` |

## Original bytes and the source tree

- `SourceEnvelope(original_bytes, root=None, *, source_path=None)` accepts bytes or
  bytearray; copies mutable bytes and calculates count/SHA-256 from retained input.
  The optional `Path` is provenance only: no file read, check or write.
- `original_bytes` is the exact round-trip API, retaining whitespace, supplied BOM,
  key order and number spelling. `root=None` permits retained bytes without a decoded tree.
- `root` accepts a preconstructed object mapping. Each mapping owns a copied,
  read-only dictionary; lists/tuples become owned tuples, including unknown fields.
  Null, bool, str, `SourceNumber` and missing properties remain distinct.
- Cycles, non-string keys, native int/float scalars and unsupported objects are
  rejected. Changes to caller-owned input cannot change the envelope.
- `SourceNumber("1.00")` represents a JSON number; `"1.00"` remains a string.
  Tokens retain spelling and Decimal value, including exponent, precision and
  signed zero. Equality distinguishes number tokens `1` and `1.0`.
- Bytes/tree correspondence is not checked by model construction. The
  [decoder](STRICT_DECODING.md) builds both from the same bytes, captures tokens
  before float conversion and enforces document/resource policies.
- Envelope/recording equality is supported. Mapping-containing objects have no
  promised hashability or `dataclasses.asdict` serialization. Ordinary mutation is
  blocked; reflective `object.__setattr__` is not a security boundary.

## Canonical values and absence

| API                              | Value/absence contract                                                                                                                                                                                 |
| :------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Vector3` / `GpsFix`             | Finite float accessors; bool, strings and non-finite numbers rejected. No normalization, unit conversion, projection, geographical rejection or epoch conversion; exact tokens remain in the envelope  |
| `MotionSequence`                 | Owns tuple sequences; acceleration nonempty; provided gravity contains typed `Vector3` values and has equal length. Absent gravity is `None`, with `paired_motion_available=False`, never zero vectors |
| `RecordingIndices` / `Recording` | Nonnegative indices; `start <= end`; `Recording` checks every marker against acceleration length. Gravity/incline may precede start or each other; no slicing                                          |
| `SampleRate`                     | Default `(50.0, ValueOrigin.DEFAULT)`; valid explicit source rate uses SOURCE; invalid rate is not a default                                                                                           |
| `RidingPosition`                 | Default `("Seated", ValueOrigin.DEFAULT)`; valid explicit source value uses SOURCE; invalid optional source position becomes `None` with parser warning                                                |
| `RecordingMetadata`              | Optional values use `None`, not fabricated zero/false; date is `SourceNumber`                                                                                                                          |
| Source extrema/smoothing         | `Recording.min_force`, `max_force`, `smoothing_factor` retain `SourceNumber`, without reinterpretation                                                                                                 |
| `Attribute`                      | Arbitrary labels/order retained; nested source-valued payloads copied and frozen                                                                                                                       |
| `RecordingVectors`               | Independent optional `vertical_direction`, `lateral_direction`, `longitudinal_direction`, `x_calibration`, `y_calibration`, `z_calibration` accessors                                                  |
| `GpsSequence`                    | Every original sequential slot retained as `GpsEntry`; unavailable fix is `fix=None`; count independent of motion                                                                                      |
| `GpsStatus`                      | ABSENT, PRESENT (including empty sequence), INVALID (no usable container) remain distinct; PRESENT requires a sequence                                                                                 |

- Start/end are effective bounds. The [motion parser](MOTION_PARSING.md) supplies
  absent boundaries as 0/N−1 with `INDEX_DEFAULTED`; source absence remains visible.
  It also handles device-dependent gravity availability; constructors infer no profile.
- Origins distinguish equal effective values. Constructors neither insert defaults
  into source data nor infer field presence from the source mapping.
- Negative GPS speed/course/accuracy and suspicious finite coordinates remain
  represented. Models assign no verified physical meaning, units, epoch or shared
  motion/GPS clock. [Optional parsing](OPTIONAL_PARSING.md) owns metadata/GPS warnings
  and subset accessors; [scientific gates](../architecture/08_concepts.md#scientific-provenance-and-gates)
  remain authoritative for interpretation.

## Diagnostics and results

- `ImportDiagnostic`: uppercase code, `Severity`, RFC 6901 JSON Pointer, nonempty
  message and optional nonnegative sample index. Empty pointer means root;
  `json_pointer` escapes arbitrary keys/indices.
- `ordered_diagnostics` owns a tuple and sorts ERROR/WARNING/INFO, escaped pointer
  lexicographically, then code; exact ties retain emission order. Pointer index 10
  sorts before 2; samples are not reordered.
- `ImportResult = ImportSuccess | ImportFailure`; both constructors copy and order diagnostics.

| Result             | Invariants/accessors                                                                                                           |
| :----------------- | :----------------------------------------------------------------------------------------------------------------------------- |
| `ImportSuccess`    | `success=True`; complete `Recording`; no error diagnostics; count/hash/version from recording/source provenance                |
| `ImportFailure`    | `success=False`; at least one error; `recording=None`; may retain original source bytes; unknown version/count/hash are `None` |
| Known empty source | Byte count 0 and actual digest; distinct from unreadable input                                                                 |

Typed control flow supports the literal tag or result class:

```python
from ride_forces_analyzer.importers import ImportResult


def inspect_result(result: ImportResult) -> int | None:
    if result.success is True:
        return len(result.recording.motion.acceleration)
    return None
```

- Standard representations omit bytes/tree, GPS coordinates, sequences and metadata.
  Caller messages still require safe field-oriented text; no sensitive-content classifier.
- Constructors perform no parsing. The [import service](IMPORT_SERVICE.md) produces
  these outcomes for full Path/bytes imports.

## Validation

```powershell
uv run --locked pytest tests/domain/test_source.py tests/domain/test_recording.py tests/importers/test_results.py
npm run test:types
```

- Runtime coverage: owned bytes/tree/sequences, exact tokens, defaults/absence,
  diagnostics, result invariants and fresh Qt-free package import.
- Static coverage: literal-tag narrowing, invalid construction, frozen assignment
  and source-mapping mutation. Shared suite details: [code quality](CODE_QUALITY.md).
- Ownership detail: frozen dataclasses do not freeze nested inputs;
  `MappingProxyType` is a dynamic view unless its backing dictionary is privately owned.
  References: [dataclasses](https://docs.python.org/3.14/library/dataclasses.html),
  [mapping proxy](https://docs.python.org/3.14/library/types.html#types.MappingProxyType).
- Decoder [resource budgets](STRICT_DECODING.md) do not establish total process/native
  peak RAM. This remains an [architectural limit](../architecture/11_technical_risks.md).
  Original fixture identities/authorization: [recording catalog](RECORDINGS.md).
