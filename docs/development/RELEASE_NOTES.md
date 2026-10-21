# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays. Processing stays local;
original recordings remain unchanged.

## Included in {{VERSION}}

- Downloads for Windows x64, Linux x64 and macOS Apple Silicon/Intel.
- Interactive force charts with zoom, selection, smoothing and colored airtime
  context, plus available ride information and an offline GPS overview.
- Five 4K overlay layouts in landscape or portrait, with English/German labels,
  transparent MOV or black-background MP4, saved presets and export batches.
- Remembered preferences and update checks for your platform. Your original
  recordings remain unchanged, and processing works offline after setup.
- User guides, ride-detail screenshots and a project website with download links.
- Windows Complete ZIP includes FFmpeg; Linux/macOS use an external installation.

## Compatibility and limits

- Linux targets Ubuntu 24.04/glibc 2.39; macOS targets version 15 or newer.
  These packages require a separately installed FFmpeg. macOS apps are ad-hoc
  signed, without Developer ID/notarization, and may require explicit OS approval.
- Older or incomplete saved presets and batch jobs may need recreating. They are
  not automatically converted or silently deleted.
- Airtime labels are provisional interpretations, not measurements of rider
  sensations or safety limits. GPS is approximate; video alignment remains manual.
- Windows packages are unsigned. Clean-machine testing and dependency
  redistribution material remain incomplete; see the
  [release limits](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/development/RELEASE.md).

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
  the [installation guide](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/user/INSTALLATION.md#ubuntu-2404-x64).
- Linux/macOS: install compatible FFmpeg separately, for example with
  `sudo apt install ffmpeg` or `brew install ffmpeg`; select it with Browse if needed.
- macOS: after checking the hash, use **Open Anyway** in Privacy & Security if
  required for the trusted download. Do not disable Gatekeeper globally.
- Verify downloads with `WINDOWS-SHA256SUMS.txt`, `LINUX-X64-SHA256SUMS.txt`,
  `MACOS-ARM64-SHA256SUMS.txt` or `MACOS-X64-SHA256SUMS.txt`.
- Packages include collected dependency notices. Shipped `REDISTRIBUTION.json`
  records outstanding redistribution source/notice gaps.
- To run from source, follow the
  [Windows developer setup](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/development/SETUP.md).

[README](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/README.md):
features and screenshots.
[User guides](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/README.md#for-users):
installation, chart navigation, forces, layouts and exporting videos.
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
