# Saved export presets and batches

For saving presets, preparing a queue and finding its results, see the
[user presets and batches guide](../user/EXPORT_BATCHES.md).

## Scope

User databases retain their Windows LOCALAPPDATA location. Linux uses absolute
XDG_DATA_HOME or `~/.local/share/ride-forces-analyzer`; macOS uses
`~/Library/Application Support/Ride Forces Analyzer`. Presets and preferences stay
outside the frozen application. Package formats and external FFmpeg requirements
are defined in the [release guide](../development/RELEASE.md#linux-and-macos-packages).

Local SQLite presets and reusable batches; multiple presets per recording and
multiple recordings per batch. Selected/all batches form one sequential queue.
Each recording × preset produces a separate video, never concatenated rides.
The ride/media library remains outside this scope; see the [roadmap](../ROADMAP.md).

Architecture owns [storage/component boundaries](../architecture/05_building_block_view.md#video-export-boundary),
[database location](../architecture/07_deployment_view.md#local-export-configuration)
and [batch runtime](../architecture/06_runtime_view.md#saved-batch-runtime).

## Contracts

| Saved object    | Required contents                                                                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Preset          | Layout, position, landscape/portrait aspect, overlay language, output mode, fps, time context, axis inversion, GPU preference, odd 1–51 sample smoothing and range policy |
| Analysis recipe | Explicit versioned projection, smoothing, independent orientation, context/events, input dependencies and source-app policy; smoothing matches preset window              |
| Job             | Absolute source path, original SHA-256, title, concrete inclusive source range and complete preset snapshot                                                               |
| Storage         | Recipes/definitions only; no source bytes or stage buffers; originals remain external/read-only                                                                           |

- Writes are transactional; preset/batch names are unique. Damaged/unsupported
  databases are reported, never silently replaced.
- Reusable presets omit file-specific ride bounds and Gravity/Incline overrides.
  Each queued job captures its recording's bounds and reference recipe, including
  replay zero and the explicit calibration version/window. Later marker or
  preference edits do not change a saved job. Adding files restores valid local
  bounds and calibration before binding jobs; execution uses the saved recipe only.
  Existing recipes may omit the optional `ride_bounds`
  field, meaning original markers; all numerical stage settings remain explicit.
- Every preset/job requires complete analysis/video settings, including aspect,
  position and language. Missing/unsupported fields are rejected without fallback recipes,
  format migration or destructive cleanup. New-object `ExportSettings` defaults
  do not fill incomplete stored records.
- Preset creation resolves an implicit position to the current layout/format default
  and persists its named enum value. Jobs retain that explicit position; subsequent
  preset/default changes do not move it. Unsupported layout/format/position combinations
  are rejected. Coordinates and sizes remain in layout metadata, never in stored jobs.
- Save as creates a preset; Update selected replaces only that named preset.
  Loading refreshes production previews without changing explorer recording/settings.
- Editing/deleting a preset does not change saved job snapshots.
  Jobs replay their saved overlay language independently of UI language.
- Mixed portrait/landscape jobs are supported; the job table identifies aspect.

| Queue interaction        | Contract                                                                                                         |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Add this export to batch | Capture assistant recording/settings, including custom selection                                                 |
| Batch-editor addition    | Every selected recording × every selected preset; explicit marker/entire range resolved separately per recording |
| Remove rows              | Save immediately                                                                                                 |
| Open/run                 | Available without an open recording; Run selected / Run ALL snapshot definitions for sequential worker execution |

- Each job losslessly imports its source, checks the original digest **before**
  analysis, then prepares its complete saved recipe once. Analyze full recording
  history before applying the stored interval; bind that snapshot to production
  rendering/encoding and exclusive publication, independently of explorer presentation.
- Missing, invalid or changed sources fail their job; remaining jobs can run.
- Each run creates a unique output directory, numbered batch folders and safe,
  numbered recording/preset filenames. Never overwrite earlier outputs.
- Incrementally persist completed/failed/cancelled/skipped job states in `run-report.json`.
  Progress wraps the shared `ExportProgress` with job index/count and label.
  Separate bars show the equally weighted overall queue and the current video's
  submitted frames. A new job resets video progress and its estimate; settled jobs,
  including failures, advance the queue without fabricating frame counts.
- Cancellation stops the active encode and skips remaining jobs; remove incomplete
  output, preserve completed videos. Parent close/Escape cannot abandon an active export.
- Definitions survive restart, without embedded sensor data or automatic relocated-file
  discovery. Moving/changing a source requires a new job. Automatic resume and a
  persistent execution-history UI remain outside scope.
