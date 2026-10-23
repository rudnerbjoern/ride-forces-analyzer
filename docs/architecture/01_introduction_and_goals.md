# 1. Introduction and Goals

[Architecture index](README.md)

## Requirements overview

Ride Forces Analyzer is an offline Windows desktop project for importing Ride
Forces recordings, analyzing motion and producing charts and video overlays.
The product does not acquire sensor data or recreate the mobile recording app.

M1 implements an executable minimal Qt window, validated bootstrap settings and
separated subsystem packages. M2 implements lossless Path/bytes importing under
schema 2.2.0 and the explicit unversioned RFDB profile, with immutable source/domain
data and deterministic diagnostics.
The raw explorer now invokes that importer through a background adapter and shows
complete source-axis charts, sample navigation and inclusive local selections.
M3 implements immutable analysis contracts and explicit device-unit/norm primitives.
Source-app projection, live configurable smoothing and coarse GPS overview are
implemented in the explorer. Reduced M3 includes selected-range per-axis
extrema and focused Windows acceptance. Extra filters/events and universal physical rider
qualification are deferred; GPS analytics is excluded. Five-profile 4K transparent/opaque
video export with previews and saved batches, CSV and JSON sample exports are implemented.
Interactive sample playback supports pause/resume, seeking and 0.5×/1×/2× speed
selection. Synchronization and remaining release work
remain planned.

The [roadmap](../ROADMAP.md) owns completed and remaining product scope.
These architecture chapters and the linked API/product contracts describe current
behavior; completed requirement plans and acceptance diaries are not maintained.

## Quality goals

1. Preserve every original byte, unknown field and authorized GPS value.
2. Process installed application inputs offline, without cloud dependencies.
3. Keep typed domain/import/analysis logic independent of Qt widgets.
4. Produce reproducible results and explicit failure, absence and provenance states.
5. Make scientific uncertainty visible before interpreting rider-axis forces.

[Chapter 10](10_quality_requirements.md) defines observable quality scenarios.

## Stakeholders

| Role                     | Contact / authority                                      | Expectations                                                                    |
| ------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Project owner            | Repository owner; explicit review and operation approval | Useful offline tooling, preserved recordings and verified milestones            |
| Desktop user             | Desktop explorer user                                    | Import, inspect and export local rides without hidden data loss                 |
| Developer / coding agent | Repository instructions in AGENTS.md                     | Clear boundaries, stable contracts and reproducible Windows checks              |
| Video editor             | Export consumer                                          | Opaque video / transparent overlays; manual alignment until M7                  |
