# 6. Runtime View

[Architecture index](README.md)

## Qt bootstrap

```mermaid
sequenceDiagram
    actor User
    participant Entry as __main__.main
    participant Settings as config.AppSettings
    participant Qt as QApplication / ExplorerWindow
    User->>Entry: Launch module with optional settings
    Entry->>Settings: Use supplied model or construct defaults
    Settings-->>Entry: Validated immutable settings
    Entry->>Qt: Construct application and raw explorer
    Entry->>Qt: Set title, dimensions and raw chart controls
    Entry->>Qt: Show window and run event loop
    User->>Qt: Close window
    Qt-->>Entry: Event loop exit code
```

AppSettings rejects unknown settings and invalid title/dimensions outside widgets.
Window dimensions are positive and at most 16,777,215 pixels, the Qt widget limit.
Invalid model construction fails before window creation. The GUI smoke test starts
the real module in a separate Windows process and exits through the Qt event loop;
its tests exercise the real bootstrap contract above.

## Optional update discovery

Before normal interaction, the explorer schedules an optional update check after
the event loop starts. A controller applies the saved opt-in, daily attempt limit
and skipped version. A worker calls the Qt-independent release service; only the
GUI thread updates status or opens a release notice. Closing the main window
suppresses late results. Network operations have bounded reads/timeouts and never
block the GUI or recording processing. Manual checks in About bypass the daily
interval and show errors; automatic errors are silent. No installer is invoked.

## Read-only import and failures

```mermaid
sequenceDiagram
    participant Caller
    participant Service as Public import service
    participant Decoder as Strict decoder
    participant File as Local original
    participant Motion as Motion validation
    participant Optional as Optional validation
    participant Domain as Immutable domain models
    Caller->>Service: import_forces(Path, limits)
    Service->>Decoder: decode_forces(Path, limits)
    Decoder->>File: Bounded binary read only
    File-->>Decoder: Original bytes
    Decoder->>Decoder: Resource preflight, strict JSON and version dispatch
    Decoder-->>Service: DecodeSuccess or ImportFailure
    alt Decode / schema / I/O failure
        Service-->>Caller: ImportFailure with ordered diagnostic
    else Decoding succeeds
        Service->>Service: Create per-call diagnostic budget
        Service->>Motion: Validate motion using shared budget
        Motion-->>Service: Motion subset or ImportFailure
        alt Invalid core motion or exhausted budget
            Service-->>Caller: ImportFailure, optional validation is skipped
        else Motion succeeds
            Service->>Optional: Validate metadata, attributes and independent GPS
            Optional-->>Service: Optional data with warnings or budget failure
            alt Diagnostic budget exhausted
                Service-->>Caller: ImportFailure, no Recording
            else Complete available data
                Service->>Domain: Construct Recording with owned source
                Domain-->>Service: Immutable Recording
                Service-->>Caller: ImportSuccess with ordered warnings/info
            end
        end
    end
```

The bytes variant bypasses the file read and otherwise uses the same composition.
The public service remains synchronous; the raw explorer runs it on a Qt worker
thread with an indeterminate progress indicator. Other callers choose scheduling. Invalid caller argument types/limit configuration raise TypeError or
ValueError; expected source/I/O defects return structured failures.

Optional missing/defective GPS does not invalidate usable core motion. Invalid
supplied gravity remains fatal; gravity is never fabricated. Global resource
failures remain fatal even inside unknown or optional content. Unreadable or
oversized inputs have no complete-source digest; no partial read is represented
as complete provenance. Each call owns independent state, so repeated same
bytes/policy produce equivalent output. See [API contracts](../development/IMPORT_SERVICE.md).

## Product boundaries

Selected-range extrema update on source/selection/mode/smoothing changes.
Persistent ride library, interactive playback and POV synchronization remain
planned. Frame rendering and encoding are implemented for the 4K overlay slice. Universal physical
rider qualification and analytical GPS are outside current M3 acceptance. This view introduces
no invented runtime interactions for those services.

## Implemented device-only analysis

```mermaid
sequenceDiagram
    participant Caller
    participant Device as analysis.device
    participant Pint as Private Pint registry
    participant NumPy
    Caller->>Device: Full M2 success, explicit UTC time, per-sequence contracts
    loop Acceleration and gravity independently
        Device->>Device: Check source hash, sequence, unit and quantity references
        alt Absent sequence or absent contract
            Device->>Device: UNAVAILABLE channels with ordered warnings, no samples
        else Qualified DEVICE components
            Device->>Pint: Convert one supported component-unit factor to SI
            Pint-->>Device: Explicit SI scale
            Device->>NumPy: Convert owned array, then stable Euclidean norm
            NumPy-->>Device: Owned vectors and magnitude, or finite-range defect
            Device->>Device: Retain usable vectors and report invalid products independently
        end
    end
    Device-->>Caller: Immutable AnalysisResult retaining complete M2 source
```

Caller contract/type/hash defects raise TypeError/ValueError. Expected finite-range
calculation defects produce INVALID products with structured errors. Source
absence and unknown units produce UNAVAILABLE products with different warning
codes. A declaration cannot create absent gravity. The caller supplies calculation
time; sample indices remain indices, with no generated timeline or epoch.
There is no addition/subtraction of the two source channels, no normalization
into rider G, and no calibration, filtering or GPS processing. The registry reads
installed definitions at module initialization; subsequent calculations perform
no file or network access. Caller evidence references are explicit attestations,
not an empirical verification service.

## Explicit provisional frame projection

A separate `analysis.frames.analyze_rider_frame` call checks M2 success, source-bound
calibration, profile/assumption permission and independent device-unit contracts.
Missing mapping/data/units returns excluded channels. An explicit admitted basis
passes through SciPy passive rotation; resulting rider vectors are PROVISIONAL.
Range failures yield INVALID, while other usable sequences remain independent.
It never guesses source axes, normalizes input bases or labels real rider forces verified.
The caller supplies UTC time; no clock alignment, gravity combination or filtering occurs.
See [passive frame decision](09_architecture_decisions.md#passive-frame-transforms).

## Raw explorer interaction

```mermaid
sequenceDiagram
    actor User
    participant Window as Raw explorer
    participant Worker as Qt worker
    participant View as Qt-independent presentation
    participant Importer as M2 import service
    User->>Window: Choose a local recording
    Window->>Worker: Start background load and show progress
    Worker->>View: Load and prepare raw view
    View->>Importer: Read-only import
    Importer-->>View: Full success or structured failure
    View-->>Worker: Immutable axes and source or failure
    Worker-->>Window: Queued completion
    Window->>Window: Show complete x/y/z or retain previous view on failure
    User->>Window: Navigate, zoom and choose an inclusive interval
    Window->>View: Validate local sample selection
```

Cancelling the picker changes nothing. The previous view survives load errors.
Application shutdown drains outstanding worker tasks after the window closes;
it does not kill parsing mid-call. Axis labels use source values/inferred elapsed seconds,
not rider G or a fabricated clock. Qt Charts handles interactive chart drawing;
export frame generation and encoding are separate implemented services.

Background presentation attempts source-direction projection and a configurable centered mean
(default 11) for every successful import. Loading selects calibrated curves by
default; the checkbox switches arrays/value bounds while preserving time/selection.
Expected calibration errors or absent optional NumPy retain raw data and a visible
explanation. Source hashes do not gate availability.

The focus workspace presents loaded curves with current-value cards and a right
inspector. A width breakpoint switches compact windows between chart and inspector;
scroll areas preserve reachable controls without changing chart coordinates.
Global import-note access opens the inspector/details and scrolls to diagnostics
after layout. Card values and clock text refresh from explorer presentation when
sample, calibration or smoothing changes. Technical expansion is independent of
analysis state. All raw/calibrated, failure and worker shutdown paths above remain.

## 4K export runtime

Export snapshots the loaded immutable recording, current smoothing and selected
range/profile/aspect/language. A Qt worker prepares/streams frames to FFmpeg; NVIDIA Vulkan
or NVENC is selected only after an actual encode probe, otherwise CPU is used.
Signals report backend/progress, completion and failure without blocking widgets.
Cancellation or window close sets a thread event; incomplete files are discarded.
The service publishes the completed encoder output exclusively.
No existing file is replaced. The user aligns the
single exported overlay with an Onride clip externally in Resolve.

## Saved batch runtime

```mermaid
sequenceDiagram
    actor User
    participant UI as Batch window
    participant Store as SQLite export store
    participant Queue as Batch worker/service
    participant Encoder as Existing export service
    User->>UI: Run selected or all saved batches
    UI->>Store: Read immutable batch definitions
    Store-->>UI: Source paths, hashes, ranges and preset snapshots
    UI->>Queue: Queue snapshot and unique output root
    loop Each recording/preset job
        Queue->>Queue: Reimport, check hash, restore smoothing/range
        Queue->>Encoder: Render and encode one video
        Encoder-->>Queue: Complete output or failure/cancellation
        Queue-->>UI: Progress and per-job result
        Queue->>Queue: Persist incremental run report
    end
```

Expected job failures are recorded and processing continues; cancellation discards
the active incomplete encode and skips remaining jobs. Completed files stay intact.
Close/Escape requests cancellation and never abandons an active encoder. Presets
and definitions survive restart; resume/history services remain outside scope.
