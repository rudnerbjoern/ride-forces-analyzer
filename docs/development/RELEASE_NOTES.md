# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays for your coaster
videos. Processing stays local and preserves original recordings.

## Included in version 0.3.0

- Portable Windows EXE, standard ZIP and complete ZIP with FFmpeg, plus source downloads.
- A colored airtime context strip that follows chart zoom, with stable vertical-force
  labels for Floater, Airtime, Strong Airtime and Ejector. These are provisional
  interpretations, not measured rider sensations.
- Consistent export colors: yellow lateral forces, green acceleration and red braking.
  Flow Ribbon, Corner Instruments and Telemetry Capsule also show vertical-force context.
- Click the chart to select a sample; inspect extrema for the visible chart range.
  The From/To interval is highlighted, and holding its arrows accelerates sample stepping.
- A more compact workspace with organized technical details and visible-range extrema.
- Remembered folders, language and appearance, with Windows defaults for new users.
- FFmpeg Browse opens the configured encoder directory; invalid preference inputs
  are rejected before changing saved settings.
- About information and optional GitHub update notifications.
- Export filenames based on the recording, estimated output size and remaining time.

## Installation

For Windows x64, `Ride-Forces-Analyzer-{{VERSION}}-windows-x64.exe` starts without
installing Python. The `…-standard.zip` contains the application and notices;
select an existing FFmpeg for video export. The `…-complete.zip` also includes
FFmpeg, detected automatically after extraction. Start the EXE in the extracted
folder. There is no installer or automatic installation. Required dependency
notices accompany the packages; `corresponding-sources.zip` supplies the available
third-party sources. This collection is incomplete: matching Qt PDF material and
complete source/build material for the static FFmpeg dependencies were not located
in the provider downloads. The included `REDISTRIBUTION.json` records these gaps.
Use `WINDOWS-SHA256SUMS.txt` to verify the download files.

Download `source.zip` and `SHA256SUMS.txt` from this release. Extract the ZIP,
open PowerShell in its directory and run `setup.ps1`, then `start.ps1`.
Video export additionally needs `setup.ps1 -VideoExport` or a compatible existing
FFmpeg executable. Setup downloads dependencies; installed processing works offline.
Source setup is an alternative to the Windows downloads.

See the [README](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/README.md) for features, screenshots and setup help.
Known limits and planned features are in the [roadmap](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/docs/ROADMAP.md).
GPS supplies rough spatial context rather than force or speed measurement.
Video exports need manual alignment with footage.

## Licenses and support

Program code: GPL-3.0-or-later. The five supplied recordings, including GPS and
metadata, and the listed documentation images: CC BY-SA 4.0, with attribution
notices. These grants do not automatically apply to your recordings or exports.
See [licenses and third-party boundaries](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/README.md#license).

Use GitHub Issues for ordinary bugs and feature requests. Report security problems
privately through [SECURITY.md](https://github.com/{{REPOSITORY}}/blob/{{TAG}}/SECURITY.md).
