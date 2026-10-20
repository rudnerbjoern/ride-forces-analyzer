# Saved export presets and batches

<!-- cspell:words LOCALAPPDATA -->

## Scope

Persist named export presets and reusable batch definitions in local SQLite.
One recording can have multiple presets; a batch can include multiple recordings,
and selected or all saved batches run as one sequential queue. Each recording /
preset combination produces its own video, not a concatenation of different rides.
Saved export configuration does not manage a ride/media library; planned product
scope belongs in the [roadmap](../ROADMAP.md).

## Contracts

- Saved configuration is local, with transactional preset/batch writes. The
  [deployment view](../architecture/07_deployment_view.md#local-export-configuration)
  owns the database path and storage boundary. Unsupported or damaged databases
  are reported, never silently replaced. Preset and batch names are unique.
- Presets retain layout, landscape/portrait aspect, overlay language, output mode, fps, time context, axis inversion, GPU
  preference, odd 1–51 sample smoothing and range policy. Save as creates a new
  preset; Update selected replaces only that named preset. Loading refreshes
  production previews without modifying the explorer's recording/settings.
  Older records without an aspect field retain landscape; a single batch can
  mix portrait and landscape jobs. The job table identifies each job's aspect.
  Analysis configuration includes the versioned projection, smoothing, independent
  orientation, context, event settings, input dependencies and source-app policy.
  Older records without an analysis configuration use the version-1 source-app
  policy and stored smoothing window. A supplied configuration must agree with
  that window. SQLite stores only this recipe, never source bytes or stage buffers.
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
  Every job imports again and checks the original digest, restores its complete
  analysis recipe while reusing compatible prepared stages, then binds that
  snapshot to the production renderer/encoder and exclusive publication. Analysis
  uses the complete recording history before the stored interval is applied.
- Each run creates a unique output directory, numbered batch folders and safe,
  numbered recording/preset filenames. Never overwrite previous outputs. Persist
  per-job completed/failed/cancelled/skipped states in run-report.json.
- Cancellation stops the current encode and remaining queue, removes incomplete
  output and preserves completed videos. Parent close/Escape cannot abandon an
  active export. Progress distinguishes the current job and final result counts.
- Saved definitions survive restart; they do not embed sensor bytes or discover
  relocated files automatically. Moving/changing a source requires a new job.
  Automatic resume and a persistent execution-history UI are outside this scope.
