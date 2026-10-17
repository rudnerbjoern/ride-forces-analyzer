# Strict source decoding

The decoder provides bounded read-only inputs, strict JSON and schema dispatch.
It does not construct a Recording, call the motion parser, apply metadata/rate
defaults, interpret GPS/time or perform analysis. See
[ADR 0002](../decisions/0002-forces-source-contract.md) and
[M2 validation](../validation/M2.md).

## Public API

```python
from pathlib import Path

from ride_forces_analyzer.importers import DecodeResult, ImportLimits, decode_forces


def inspect_source(path: Path) -> int | None:
    result: DecodeResult = decode_forces(path, limits=ImportLimits())
    if result.success is True:
        return result.byte_count
    return None
```

`decode_forces(path: Path, *, limits=DEFAULT_LIMITS)` reads local regular files
only. `decode_forces_bytes(data: bytes, *, limits=DEFAULT_LIMITS)` performs no
file access. Both return DecodeSuccess | ImportFailure. These stage-specific
names distinguish decoded sources from the separately implemented
[complete import_forces API](IMPORT_SERVICE.md).

DecodeSuccess exposes success=True, schema_version="2.2.0", retained SourceEnvelope,
original byte_count, source_sha256 and an empty diagnostic tuple. It exposes no
Recording or inferred capability/GPS status. ImportFailure exposes success=False,
recording=None and one fatal structured diagnostic. Invalid Python argument types
raise TypeError; invalid limit configuration raises ValueError before I/O.

The file adapter rejects directories, non-regular handles and Windows network/device
paths. It opens binary/unbuffered/read-only, checks the opened handle and joins
short reads until EOF or the total max_bytes+1 budget. Reads use at most 65,536 bytes
per call. Never trust stat size alone or report a partial read as full provenance.

## Grammar, version and source ownership

Decode strict UTF-8 only; one leading UTF-8 BOM may be a decoding marker and stays
in original bytes. UTF-16/32 are not guessed. Empty/whitespace/BOM-only input,
invalid UTF-8, JSON comments, trailing content/commas, malformed tokens, duplicate
members at every depth and non-JSON NaN/Infinity constants fail deterministically.
Duplicate detection compares decoded keys, including equivalent escape spellings.
The root must be an object; schemaVersion must be a nonempty string and exactly
2.2.0. New versions require an explicit adapter and authorized source evidence.

The 2.2.0 adapter checks required acceleration and supplied start/end fields, nonempty
acceleration array, sample objects with x/y/z string/number shapes, and integer-valued
JSON start/end numbers. It does not convert components, validate measured finiteness,
check marker bounds/paired lengths or require gravity/GPS/optional metadata.
Those remain the separate motion and optional-data stages. Structurally valid
JSON containing a nonnumeric component string can decode; this is not a valid
motion-import claim. The decoder never silently repairs a required shape.

The source tree is built from the retained bytes using exact SourceNumber hooks
for every JSON number. Numeric strings remain strings; booleans/null/absence
remain distinct. Decimal-finite numbers such as 1e9999 remain exact source tokens;
whether they fit into a finite float is checked only when later accessors interpret
them. Numbers outside Decimal's representable range fail structurally.
Unknown fields, all GPS content, source order and original whitespace/BOM/spelling
survive. SourceEnvelope privately owns recursively immutable mappings/tuples.
Python JSON string semantics, including escaped surrogate pairs, are retained.

On bounded decoding errors, original bytes/count/hash remain available; an invalid
document has root=None. Supported/unsupported schema errors may retain a valid
tree and a known version. Unreadable/oversized input retains no source, byte count
or digest. No hash of a prefix is presented as an original-file hash.

## Resource policy

All limits are immutable per-call positive non-boolean integers below sys.maxsize.
max_depth additionally supports 1–128, a conservative ceiling for the recursive
standard-library decoder and source copying; Python globals are never changed.
Defaults follow ADR 0002:

- max_bytes: 16,777,216.
- max_depth: 32 (root container = 1).
- max_sequence_length: 100,000 elements in every array, including extensions/GPS.
- max_nodes: 1,000,000 values, excluding object key strings.
- max_object_members: 1,024 per object.
- max_string_length: 65,536 decoded characters per string/key.
- max_number_length: 128 characters per exact numeric token.
- max_diagnostics: 1,000; Stage 2 stops at its first fatal error and always uses one.

A JSON-aware iterative preflight checks grammar, nesting, array/member/node budgets,
keys, number tokens and decoded string lengths before complete tree allocation.
Escaped quotes/brackets and UTF-16 surrogate pairs do not distort counts. Keys
are decoded individually only after their lexical budget passes. Complete decoding
then uses strict constant/duplicate hooks as defense in depth.
Exactly at a supported budget passes; excess emits RESOURCE_LIMIT_EXCEEDED with
the limit name and escaped JSON Pointer. Output diagnostic count is inherently
bounded here; the Stage 5 combined pipeline now enforces its aggregate budget.
Shape/byte budgets do not promise exact peak RAM or throughput. A runtime recursion
failure is also a structured resource error rather than an uncaught exception.

## Diagnostics, offline checks and tests

Codes: EMPTY_INPUT, INVALID_UTF8, INVALID_JSON, NON_JSON_NUMBER, INVALID_JSON_NUMBER,
DUPLICATE_JSON_KEY, INVALID_ROOT, INVALID_SCHEMA_VERSION, UNSUPPORTED_SCHEMA_VERSION,
MISSING_REQUIRED_FIELD, INVALID_REQUIRED_FIELD, RESOURCE_LIMIT_EXCEEDED,
SOURCE_NOT_FOUND, SOURCE_UNREADABLE, INVALID_SOURCE_PATH. Stage 2 returns the first
fatal error in deterministic traversal/adapter order; never includes source values,
paths or decoder exception excerpts in messages. JSON Pointers identify fields.
No URLs are fetched, positions looked up, telemetry sent or Qt imported.

```powershell
uv run pytest tests/test_decoder.py tests/test_project.py
```

Tests cover every decoder failure category and resource threshold, preflight
before full allocation, exact byte/token retention, all five recordings, duplicate
escaped keys, Unicode/depth attacks, short/bounded reads, safe I/O failures and
bytes-only offline behavior. Permission/race/read failures use deterministic mocks;
these do not establish Windows ACL or hostile-filesystem integration behavior.
The shared Pyright suite verifies narrowing of the decoder-specific union.

Context7 was consulted for the standard-library JSON hooks and permissive defaults;
see the [CPython JSON documentation](https://github.com/python/cpython/blob/main/Doc/library/json.rst).
