# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays. Processing stays local;
original recordings remain unchanged.

## Included in {{VERSION}}

- Windows x64, Linux x64 and separate macOS Apple Silicon/Intel downloads,
  with native GUI/import/rendering/encoding checks for each target.
  Development remains on Windows.
- Native user-data folders, platform-aware FFmpeg discovery and update assets;
  export works from a read-only launch directory.
- Interactive force charts, per-sample airtime context, optional airtime events,
  shared immutable analysis snapshots and 4K exports. Original samples, metadata
  and independent GPS remain intact.
- Updated user documentation, reproducible ride-detail screenshots and a
  Midnight-themed GitHub Pages site with platform-specific download links.
- Portable Windows EXE, standard ZIP and complete ZIP with FFmpeg; GitHub also
  supplies source downloads.

## Compatibility and limits

- Linux targets Ubuntu 24.04/glibc 2.39; macOS targets version 15 or newer.
  These packages require a separately installed FFmpeg. macOS apps are ad-hoc
  signed, without Developer ID/notarization, and may require explicit OS approval.
- Integrations use the recording-analysis and service contracts.
- Saved export presets and batch jobs require the current explicit analysis
  recipe. Older or incomplete records are rejected without automatic migration
  or destructive database cleanup; recreate unsupported presets/jobs.
- Airtime event detection is opt-in and distinct from the stable display labels.
  Neither constitutes scientific qualification of arbitrary recordings.
- Windows packages are unsigned. Clean-Windows-VM qualification and the documented
  redistribution source/notice gaps remain open.

## Installation

Native downloads require no Python installation:

| Download                                           | Use                                                                             |
| -------------------------------------------------- | ------------------------------------------------------------------------------- |
| `Ride-Forces-Analyzer-{{VERSION}}-windows-x64.exe` | Portable Windows application                                                    |
| `…-windows-x64-standard.zip`                       | Windows application/notices; select an existing FFmpeg for export               |
| `…-windows-x64-complete.zip`                       | Also includes FFmpeg, detected beside the extracted EXE                         |
| `…-linux-x64.tar.gz`                               | Ubuntu 24.04 x64; extract and run `./Ride-Forces-Analyzer` inside its directory |
| `…-macos-arm64.zip`                                | macOS 15+ Apple Silicon; extract and move the app to Applications               |
| `…-macos-x64.zip`                                  | macOS 15+ Intel; extract and move the app to Applications                       |

- Windows: extract ZIPs and start their EXE. No installer or automatic installation.
- Linux: keep `_internal` beside the executable. Install the desktop libraries in
  the [release guide](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/development/RELEASE.md#linux-and-macos-packages).
- Linux/macOS: install compatible FFmpeg separately, for example with
  `sudo apt install ffmpeg` or `brew install ffmpeg`; select it with Browse if needed.
- macOS: after checking the hash, use **Open Anyway** in Privacy & Security if
  required for the trusted download. Do not disable Gatekeeper globally.
- Verify downloads with `WINDOWS-SHA256SUMS.txt`, `LINUX-X64-SHA256SUMS.txt`,
  `MACOS-ARM64-SHA256SUMS.txt` or `MACOS-X64-SHA256SUMS.txt`.
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
