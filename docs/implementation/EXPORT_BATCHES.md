# Saved export presets and batches

<!-- cspell:words LOCALAPPDATA -->

## Scope

Persist named export presets and reusable batch definitions in local SQLite.
One recording can have multiple presets; a batch can include multiple recordings,
and selected or all saved batches run as one sequential queue. Each recording /
preset combination produces its own video, not a concatenation of different rides.
This implements export configuration storage, not the M4 ride/media library.

## Contracts

- Use Python sqlite3 and existing Pydantic; no new dependencies or database server.
  Default database: `%LOCALAPPDATA%/Ride Forces Analyzer/exports.sqlite3`, with
  version 1 and transactional preset/batch writes. Unsupported or damaged databases
  are reported, never silently replaced. Preset and batch names are unique.
- Presets retain layout, landscape/portrait aspect, overlay language, output mode, fps, time context, axis inversion, GPU
  preference, odd 1–51 sample smoothing and range policy. Save as creates a new
  preset; Update selected replaces only that named preset. Loading refreshes
  production previews without modifying the explorer's recording/settings.
  Older records without an aspect field retain landscape; a single batch can
  mix portrait and landscape jobs. The job table identifies each job's aspect.
  Older records without an overlay language retain English. Replaying a saved
  batch uses its stored video language independently of the current UI language.
- Jobs retain an absolute source path, original SHA-256, title, concrete inclusive
  source range and a complete preset snapshot. Editing/deleting a library preset
  does not change saved jobs. Original recordings remain read-only and external.
- Add this export to batch in the assistant captures the current recording and
  settings, including a custom selection. The batch editor adds every selected
  recording × every selected preset; its marker/entire range choice is explicit
  and resolved separately for each recording. Row removal is saved immediately.
- Batches are accessible without an open recording. Run selected or Run ALL
  snapshots the requested definitions and executes them sequentially in a worker.
  Missing/invalid/changed sources fail their job and leave other jobs runnable.
  Every job imports again and checks the original digest, restores smoothing, then
  uses the existing production renderer/encoder and complete-decode publication.
- Each run creates a unique output directory, numbered batch folders and safe,
  numbered recording/preset filenames. Never overwrite previous outputs. Persist
  per-job completed/failed/cancelled/skipped states in run-report.json.
- Cancellation stops the current encode and remaining queue, removes incomplete
  output and preserves completed videos. Parent close/Escape cannot abandon an
  active export. Progress distinguishes the current job and final result counts.
- Saved definitions survive restart; they do not embed sensor bytes or discover
  relocated files automatically. Moving/changing a source requires a new job.
  Automatic resume and a persistent execution-history UI are outside this scope.

## Acceptance

[Native Windows evidence](../validation/EXPORT_BATCHES.md) must cover SQLite
reopen/version protection, duplicate/invalid-write rollback, preset snapshots,
multiple rides/presets, saved custom ranges, digest mismatch, per-job failures,
cancellation/no overwrite, four real videos from two recordings × two presets,
native save/load/update/queue/run-all UI, close lifecycle and focused strict checks.
