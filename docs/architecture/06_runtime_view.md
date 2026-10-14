# 6. Runtime View

[Architecture index](README.md)

## Qt bootstrap

```mermaid
sequenceDiagram
    actor User
    participant Entry as __main__.main
    participant Settings as config.AppSettings
    participant Qt as QApplication / QMainWindow
    User->>Entry: Launch module with optional settings
    Entry->>Settings: Use supplied model or construct defaults
    Settings-->>Entry: Validated immutable settings
    Entry->>Qt: Construct application and minimal window
    Entry->>Qt: Set title, dimensions and placeholder label
    Entry->>Qt: Show window and run event loop
    User->>Qt: Close window
    Qt-->>Entry: Event loop exit code
```

AppSettings rejects unknown settings and invalid title/dimensions outside widgets.
Window dimensions are positive and at most 16,777,215 pixels, the Qt widget limit.
Invalid model construction fails before window creation. The GUI smoke test starts
the real module in a separate Windows process and exits through the Qt event loop;
see [M1 evidence](../validation/M1.md).

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
A call is synchronous; scheduling, background workers and progress UI are not
implemented. Invalid caller argument types/limit configuration raise TypeError or
ValueError; expected source/I/O defects return structured failures.

Optional missing/defective GPS does not invalidate usable core motion. Invalid
supplied gravity remains fatal; gravity is never fabricated. Global resource
failures remain fatal even inside unknown or optional content. Unreadable or
oversized inputs have no complete-source digest; no partial read is represented
as complete provenance. Each call owns independent state, so repeated same
bytes/policy produce equivalent output. See [API contracts](../development/IMPORT_SERVICE.md).

## Future scenarios

Library import through widgets, calibrated scientific analysis, interactive playback, frame
rendering, encoding and POV synchronization remain planned. This view introduces
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
