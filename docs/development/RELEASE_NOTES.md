# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays. Processing stays local;
original recordings remain unchanged.

## Included in {{VERSION}}

- Portable Windows EXE, standard ZIP, complete ZIP with FFmpeg and source downloads.
- Zoom-aware airtime strip with stable Floater, Airtime, Strong Airtime and Ejector
  labels: provisional interpretations, not measured rider sensations.
- Yellow lateral forces; green acceleration/red braking. Flow Ribbon, Corner
  Instruments and Telemetry Capsule also show vertical-force context.
- Click-to-select samples, visible-range extrema, highlighted From/To selection
  and accelerating sample-arrow steps.
- Compact workspace with organized technical details/extrema.
- Remembered folders, language/appearance and Windows defaults for new users.
- FFmpeg Browse starts in the configured directory; invalid preferences are rejected before saving.
- About information and optional GitHub update notifications.
- Recording-based export filenames, approximate size and remaining-time estimates.

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
