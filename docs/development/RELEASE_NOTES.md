# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays. Processing stays local;
original recordings remain unchanged.

## Included in {{VERSION}}

- Shared immutable analysis snapshots for the explorer, previews, exports and
  batches, with source metadata, force values and per-sample airtime context.
- Partial recalculation reuses unchanged stages when smoothing or analysis
  settings change. Orientation remains independent of force smoothing.
- Revision-aware analysis subscriptions deliver initial state, updates and
  failures without publishing stale worker results to the UI.
- Optional, separately configured airtime event detection. Events and display
  context remain provisional interpretations, not validated rider sensations.
- One supported numerical implementation, with explicit availability, quality
  and provenance. Original samples, metadata and independent GPS remain intact.
- Updated user documentation, reproducible ride-detail screenshots and a
  Midnight-themed GitHub Pages site with Windows download links.
- Portable Windows EXE, standard ZIP and complete ZIP with FFmpeg; GitHub also
  supplies source downloads. Dependency maintenance includes the nested
  `markdown-it` security override used by documentation tooling.

## Compatibility and limits

- The former analysis APIs have been removed without compatibility facades.
  Integrations must use the current recording-analysis and service contracts.
- Saved export presets and batch jobs require the current explicit analysis
  recipe. Older or incomplete records are rejected without automatic migration
  or destructive database cleanup; recreate unsupported presets/jobs.
- Airtime event detection is opt-in and distinct from the stable display labels.
  Neither constitutes scientific qualification of arbitrary recordings.
- Windows packages are unsigned. Clean-Windows-VM qualification and the documented
  redistribution source/notice gaps remain open.

## Installation

Windows x64 downloads require no Python installation:

| Download                                           | Use                                                                   |
| -------------------------------------------------- | --------------------------------------------------------------------- |
| `Ride-Forces-Analyzer-{{VERSION}}-windows-x64.exe` | Portable application                                                  |
| `…-standard.zip`                                   | Application/notices; select an existing FFmpeg for export             |
| `…-complete.zip`                                   | Also includes FFmpeg, automatically detected beside the extracted EXE |

- Extract ZIPs and start their EXE. No installer or automatic installation.
- Verify downloads with `WINDOWS-SHA256SUMS.txt`.
- Packages include collected dependency notices. Shipped `REDISTRIBUTION.json`
  records outstanding redistribution source/notice gaps.
- Source alternative: GitHub's **Source code (zip)** / **Source code (tar.gz)**.
  Extract, open PowerShell there, run `setup.ps1`, then `start.ps1`.
  Export additionally needs `setup.ps1 -VideoExport` or compatible installed FFmpeg.
  Setup downloads dependencies; installed processing works offline.

[README](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/README.md):
features, screenshots/setup.
[Roadmap](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/ROADMAP.md):
limits/planned scope. GPS is rough spatial context, not force/speed measurement;
video alignment remains manual.

## Licenses and support

- Code: GPL-3.0-or-later. Five supplied recordings, including GPS/metadata, and
  explicitly listed documentation images: CC BY-SA 4.0 with attribution notices.
  These grants do not automatically cover your recordings/exports.
  See [licenses/third-party boundaries](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/README.md#license).
- Ordinary bugs/features: GitHub Issues. Security reports:
  private channels in [SECURITY.md](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/SECURITY.md).
