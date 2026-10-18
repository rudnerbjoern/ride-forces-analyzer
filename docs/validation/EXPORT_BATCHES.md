# Preset and batch verification

[Contracts](../implementation/EXPORT_BATCHES.md) define SQLite persistence,
immutable job snapshots and sequential export execution.

Verified scope covers reopen/save/load/update, duplicate-name handling,
transaction rollback, corrupt/foreign/future database protection, concrete ranges,
source path/hash validation, per-job failure continuation, cancellation and unique
output directories. Completed videos survive cancellation; preset changes do not
alter existing jobs.

Native integration reopens SQLite and exports four actual short 4K videos:
Manta/Kraken × transparent Flow Ribbon/opaque G-Orbit. Each is completely decoded
before publication and both originals remain byte-identical.
GUI checks cover several presets/recordings, assistant reopen, restored settings,
run-all selection and parent-close cancellation. GUI transport stubs are distinct
from the real service/encoder integration.

## Scoped evidence

Native Windows x64, Python 3.14.6 / Qt 6.12.0 / FFmpeg 9.0.2;
`feat/4k-force-exports`, base `d88304e25dc67b9c0cec6ffe9c55f03d4d74e66b`,
plus storage/batch/assistant changes, with unchanged locked dependencies.

Recorded commands passed:

```text
python -m pytest tests/test_export_batches.py -v
python -m pytest tests/test_export_gui.py -v
```

Changed storage/rendering/UI modules passed Ruff, mypy and strict Pyright.
Native preset/preview/batch captures were inspected; later aspect/language
coverage is in [video](VIDEO_EXPORT.md) and [localization](LOCALIZATION.md)
verification. No full M4/M6, ride-library, full-suite or hosted-CI claim is implied.
