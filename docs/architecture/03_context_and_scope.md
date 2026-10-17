# 3. Context and Scope

[Architecture index](README.md)

## Business context

The owner supplies exported recordings from the external Ride Forces app on
an iPhone or Apple Watch. The analyzer consumes local files; it does not connect
to the mobile app, acquire sensors or upload ride data.

```mermaid
flowchart LR
    Capture["External Ride Forces app: iPhone / Apple Watch"]
    Original["Owner-supplied local .forces file"]
    Caller["Developer / local API caller"]
    Analyzer["Ride Forces Analyzer: implemented import boundary"]
    Result["Immutable recording and diagnostics"]
    Desktop["Desktop user"]
    Window["Raw recording explorer: implemented"]
    Video["Local POV video: planned input"]
    Editor["Video editor: planned consumer"]
    Capture --> Original
    Original --> Analyzer
    Caller --> Analyzer
    Analyzer --> Result
    Desktop --> Window
    Window --> Analyzer
    Video -.-> Analyzer
    Analyzer -.-> Editor
```

Solid edges represent existing interactions; dashed edges are planned product
interfaces. The explorer calls the importer asynchronously; raw curves and
sample controls make no universal physical calibration claim. Source-app
projection/mean is implemented; selected-range extrema are implemented within reduced
M3. GPS supplies coarse spatial context only. Playback and video/export remain planned.

## Technical context

| Interface                           | Channel and ownership                                         | Current status                                                       |
| ----------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------- |
| Recording input                     | Local regular Path, bounded binary read, owned original bytes | Implemented; Windows network/device paths are rejected               |
| Bytes input                         | Immutable Python bytes, no filesystem access                  | Implemented                                                          |
| Import output                       | Typed ImportSuccess or ImportFailure in the caller process    | Implemented; no Qt dependency                                        |
| Desktop bootstrap                   | Local PySide6 process and native Qt event loop                | Implemented raw explorer and background file opening                 |
| POV input and video/image outputs   | Future local files; formats and sync follow later milestones  | Planned                                                              |
| Dependency distribution / GitHub CI | Developer network access and Windows PR runners               | Development infrastructure; not an application processing dependency |

[Chapter 05](05_building_block_view.md) documents callable interfaces;
[chapter 07](07_deployment_view.md) separates runtime and development infrastructure.
