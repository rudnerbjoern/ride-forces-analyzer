# Ride Forces Analyzer {{VERSION}}

Explore Ride Forces recordings and create G-force overlays for your coaster
videos. Processing stays local and preserves original recordings.

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
