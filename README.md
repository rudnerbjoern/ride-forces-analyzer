# Ride Forces Analyzer

Explore your coaster rides. See the forces. Bring them into your videos.

Ride Forces Analyzer is a Windows desktop application for ride data recorded
with the [**Ride Forces** app](https://rideforces.com/) on an iPhone or Apple Watch
and exported as `.forces` files. Open a recording, explore how vertical,
lateral and longitudinal G-forces change throughout the ride, and turn the data
into an overlay for your Onride footage.

**Independent project:** Ride Forces Analyzer is developed independently of the
Ride Forces app and its developer. This project is not affiliated with, endorsed
by or sponsored by them.

Your recordings stay on your computer. Processing works offline and never
changes the original files.

![Voltron Nevera recording in the dark workspace, showing three force curves, current values and selected-range extrema](docs/images/workspace-dark.png)

*Explore the complete ride, inspect a moment, or focus on a selected section.*

## What you can do

- **Explore three force channels together.** Follow vertical loads, right/left
  forces, acceleration and braking on a shared time axis. Show or hide individual
  curves and inspect the values at any sample.
- **Focus on the interesting part.** Zoom with the mouse wheel or drag across
  the chart. Start/end markers define the initial view; reset returns to it.
  Select a section to see its minimum and maximum values for every channel.
- **Smooth the display interactively.** Adjust the slider while watching the
  curves update. Right-click to restore the default. Smoothing changes the
  displayed curves, while your original measurements remain intact.
- **Keep the ride context nearby.** View available ride, park, train, row and
  seat information. Open an approximate GPS route overview when positions are
  present in the recording.
- **Prepare several exports at once.** Save your preferred settings, reuse them
  for another ride, and queue multiple recordings and layouts for one batch run.

Directional forces are shown when the recording contains usable calibration
directions. Otherwise, you can still inspect the raw x/y/z channels, with an
explanation of what is unavailable.

## Make overlays for your videos

The export assistant shows the current graph sample before you render.
Compare five layouts, adjust the settings and check the result in the preview.

![Export assistant showing five layout thumbnails, landscape settings and a large transparent Flow Ribbon preview](docs/images/export-preview.png)

*The checkerboard shows transparency; it is not part of the exported video.*

Choose **Flow Ribbon** for a strip along the bottom, **Corner Instruments** for
the upper right, **Telemetry Capsule** for the top, **G-Orbit** for signed force
gauges, or the **four-panel column** for force and orientation plots.

![All five export layouts compared at Manta's strong negative vertical-force peak](docs/images/manta-export-themes.png)

[Compare every layout in detail using the same Manta moment](docs/EXPORT_THEMES.md).

Every layout supports **4K landscape** for classic YouTube videos and **portrait**
for Shorts or TikTok. Export the whole recording, its marker interval or your
selected section. Choose the overlay language independently of the application.

- **Transparent MOV (ProRes 4444):** place it above your footage in a video editor
  such as DaVinci Resolve. These editing files can be large.
- **Opaque MP4 (H.264):** export a video with a solid background.
- **Optional NVIDIA acceleration:** supported hardware speeds up encoding;
  CPU export remains available.
- **Saved presets and batches:** reuse settings or run several ride/preset
  combinations sequentially. Completed videos survive cancellation of the queue.

Align the exported overlay with your footage in the editor. Automatic video
synchronization is not available yet.

## Choose your workspace

Switch between **English and German**, and between **dark and light** appearance.
Language and appearance choices are remembered. Without a saved choice, German
Windows selects German and other languages select English; **System** appearance
follows Windows' current light/dark scheme.
The chart stays central, with display settings, selection and ride details in
the inspector. Smaller windows let you switch between the chart and inspector.

The **About…** dialog shows version/license information and offers **Check for
updates…**. Optional startup checks are off by default and run at most once daily
when enabled. A newer published GitHub release, including a prerelease, offers
**Open release**, **Later** or **Skip this version**. Update checks send no
recordings, GPS data or file paths; downloads and installation remain manual.
Offline use does not require update checks.

![The same Voltron Nevera recording in the light workspace, with force curves and inspector visible](docs/images/workspace-light.png)

*The light scheme shows the same recording, selection and current values.*

## Get started

You need **Windows 10 or 11, 64-bit**, and a recording made with the
[Ride Forces app](https://rideforces.com/) and exported as `.forces`.
Download version **0.2.0** from [GitHub Releases](https://github.com/rudnerbjoern/ride-forces-analyzer/releases/tag/v0.2.0):

- **EXE:** start the application directly, without installing Python.
- **Standard ZIP:** application and license notices; choose an existing FFmpeg for video export.
- **Complete ZIP:** application, notices and FFmpeg; extract it and start the EXE.
- **Source ZIP:** for running from source or development.

There is no installer. To run from source, download or clone this project,
open PowerShell in its folder and run:

```powershell
.\setup.ps1
.\start.ps1
```

Setup requires internet access to download the environment. After installation,
you can open and process recordings offline.

1. Click **Open recording** (Ctrl+O) and select your file.
2. Explore the chart, move the sample slider or select an interval.
3. Click **Export 4K…**, choose a layout and review the preview before exporting.

Video export also needs FFmpeg. Install the supplied version with
`setup.ps1 -VideoExport`, or select an existing `ffmpeg.exe` in the assistant.
See the [setup guide](docs/development/SETUP.md) for detailed installation help.

Release packaging provides a standalone Windows EXE, a standard ZIP without
FFmpeg and a complete ZIP including FFmpeg. No Python installation is needed
for these packages. Available upstream sources and checksums accompany the files;
missing third-party source material is recorded in the included license notices.
Version 0.2.0 is a preview release; clean-VM and code-signing qualification remain open.

## Understanding the display

Replay time uses `MM:SS.ff`, where `ff` counts samples within a second rather
than hundredths. At 50 Hz, `01:31.47` means 91.94 seconds.
Positive lateral values mean right; positive longitudinal values mean acceleration.
Negative values mean left and braking respectively.

Results depend on the recording, calibration and smoothing. The display follows
documented source-app conventions; exact agreement with every recording is not
guaranteed. GPS is a rough location reference, not a force or speed measurement.
Missing sensor data is never invented.

For current limitations and planned features, see the [roadmap](docs/ROADMAP.md).
The [documentation index](docs/README.md) links detailed behavior and source comparisons.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, checks, pull requests and recording
permissions. Report vulnerabilities privately using [SECURITY.md](SECURITY.md).

## License

Copyright © 2026 Björn Rudner.

The program source code is licensed under the **GNU General Public License,
version 3 or (at your option) any later version** (`GPL-3.0-or-later`).
You may use, modify and redistribute it under those terms, including commercially.
The program is provided without any warranty; see [LICENSE](LICENSE) for the full terms.

The five supplied test recordings, including their GPS data and metadata, are
separately licensed under **CC BY-SA 4.0**. Shared adaptations must follow its
ShareAlike terms. See their
[license and attribution](tests/fixtures/real/README.md) and the
[recording catalog](docs/development/RECORDINGS.md).
The 14 supplied documentation images are also licensed under **CC BY-SA 4.0**;
see their [image license and attribution](docs/images/README.md).
These grants do not automatically apply to your own recordings or exports.
Third-party components retain their own licenses. The project license does not
replace the applicable Qt/PySide6, FFmpeg or other dependency obligations.
See [third-party licenses and materials](THIRD_PARTY_NOTICES.md) for the inventory
and remaining redistribution requirements.
