# Ride Forces Analyzer

[![CI](https://github.com/rudnerbjoern/ride-forces-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/rudnerbjoern/ride-forces-analyzer/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/rudnerbjoern/ride-forces-analyzer?include_prereleases)](https://github.com/rudnerbjoern/ride-forces-analyzer/releases)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)](docs/development/SETUP.md)
[![GitHub issues](https://img.shields.io/github/issues/rudnerbjoern/ride-forces-analyzer)](https://github.com/rudnerbjoern/ride-forces-analyzer/issues)

**Relive the ride. Explore the forces. Add them to your videos.**

Find the strongest airtime moment, inspect a launch or bring your ride data into
an Onride video. Ride Forces Analyzer turns `.forces` recordings from the
[Ride Forces app](https://rideforces.com/) on iPhone or Apple Watch into
interactive charts and 4K video overlays on Windows.

**[Download for Windows](https://github.com/rudnerbjoern/ride-forces-analyzer/releases)**
· **[Watch the Manta demo](https://youtu.be/tsRzD416voU)**
· **[Compare overlay layouts](docs/EXPORT_THEMES.md)**

Free and open source · Offline processing · English and German · Light and dark themes

![Voltron Nevera in the dark workspace, showing three force curves, a colored airtime context strip, current Ejector Airtime and visible-range extrema](docs/images/workspace-dark.png)

*Follow the curves, zoom into a favorite element and inspect the forces at that moment.*

## Get started

You need **Windows 10 or 11, 64-bit**, and a recording exported as a `.forces`
file from the Ride Forces app.

### 1. Download and launch

Open [GitHub Releases](https://github.com/rudnerbjoern/ride-forces-analyzer/releases)
and choose a Windows download:

| Download           | Best for                                                                                        |
| :----------------- | :---------------------------------------------------------------------------------------------- |
| **Complete ZIP**   | Exploring rides and exporting videos, with FFmpeg included. Extract the ZIP and launch the EXE. |
| **Standard ZIP**   | Using your own FFmpeg installation. Includes the application and license notices.               |
| **Standalone EXE** | Launching the application directly. Select an existing FFmpeg when you want to export video.    |

These downloads need no Python installation and have no installer.
The **0.4.0 preview** is unsigned; code signing and clean-Windows-VM
qualification remain open. Checksums and third-party notices accompany the release;
see the [release guide](docs/development/RELEASE.md) for packaging limits.

### 2. Open your ride

Click **Open recording** or press **Ctrl+O** and choose your `.forces` file.
Click a point in the chart to inspect that sample, move through the ride with the
slider, or zoom into a section with the mouse wheel or by dragging across the plot.

### 3. Create an overlay

Click **Export 4K…**, choose a layout and check the preview. Export a transparent
MOV for your video editor or an MP4 with a solid background. Align the overlay
with your footage in the editor; automatic video synchronization is not available yet.

Your recordings stay on your computer. Opening, analyzing and exporting work
offline after setup and leave the original files unchanged.

## Explore what happened on the ride

- **Explore three force channels together.** Follow vertical loads, right/left
  forces, acceleration and braking on a shared time axis. Show or hide individual
  curves and inspect the values at any sample.
- **Focus on the interesting part.** Zoom with the mouse wheel or drag across
  the chart. Start/end markers define the initial view; reset returns to it.
  The inspector shows minimum and maximum values for the visible section of
  every channel.
- **Smooth the display interactively.** Adjust the slider while watching the
  curves update. Right-click to restore the default. Smoothing changes the
  displayed curves, while your original measurements remain intact.
- **Follow the airtime context.** A colored strip below the curves distinguishes
  normal loads, Floater, Airtime, Strong Airtime and Ejector. The vertical value
  card shows the current context, with stable labels that avoid rapid flicker.
  These are provisional interpretations of the recording, not measured sensations.
- **Keep the ride context nearby.** View available ride, park, train, row and
  seat information. Open an approximate GPS route overview when positions are
  present in the recording.
- **Prepare several exports at once.** Save your preferred settings, reuse them
  for another ride, and queue multiple recordings and layouts for one batch run.

Directional forces are shown when the recording contains usable calibration
directions. Otherwise, you can still inspect the raw x/y/z channels, with an
explanation of what is unavailable.

### Airtime up close · [Voltron Nevera](https://rcdb.com/7121.htm)

![Zoomed Voltron Nevera force curves and airtime strip showing Floater, Strong Airtime and Ejector around replay 01:07.39](docs/images/voltron-airtime-detail.png)

*Follow the colored strip through the airtime moments. The cursor marks Voltron's
−1.60 g sample at replay 01:07.39, with 11-sample smoothing. Labels are provisional
interpretations of the recording.*

### Forces at a glance · [Taron](https://rcdb.com/12723.htm)

![Taron value cards at replay 00:22.15: vertical +0.05 g with Airtime context, lateral +0.35 g right and longitudinal +1.08 g acceleration](docs/images/taron-force-cards.png)

*One moment, three force channels: Taron at replay 00:22.15. Read each value
alongside its direction or current vertical context.*

### Find your smoothing level · [Manta](https://rcdb.com/4190.htm)

![The same five-second Manta vertical-force interval with no smoothing, the default 11-sample mean and a stronger 31-sample mean, all on identical axes](docs/images/manta-smoothing-comparison.png)

*The same Manta interval with **1 sample (off)**, **11 samples (default)** and
**31 samples (stronger)**. Time and force scales are fixed for this comparison.
Stronger smoothing reduces short peaks and can change the airtime context;
the original samples remain unchanged.*

## Bring the ride into your videos

**[Watch G-Orbit over Manta Onride footage](https://youtu.be/tsRzD416voU)**
to see an exported overlay in use.

![All five export layouts compared at Manta's strong negative vertical-force peak](docs/images/manta-export-themes.png)

| Layout                 | Look and placement                                      |
| :--------------------- | :------------------------------------------------------ |
| **Flow Ribbon**        | A strip along the bottom with force histories.          |
| **Corner Instruments** | Compact instruments in the upper right.                 |
| **Telemetry Capsule**  | A compact panel across the top.                         |
| **G-Orbit**            | Circular gauges with signed forces and peak indicators. |
| **Four-panel column**  | Stacked force and orientation plots.                    |

[Compare larger previews of every layout](docs/EXPORT_THEMES.md).

Export themes use yellow for lateral data, green for acceleration and red for
braking. Flow Ribbon, Corner Instruments and Telemetry Capsule also show the
current vertical context with the same colors and labels as the workspace.

Every layout supports **4K landscape** for classic YouTube videos and **portrait**
for Shorts or TikTok. Export the whole recording, its marker interval or your
selected section. Choose the overlay language independently of the application.

![Export assistant showing five layout thumbnails and a Flow Ribbon preview with Ejector Airtime, yellow lateral history and green/red longitudinal history](docs/images/export-preview.png)

*Preview the selected chart moment before rendering. The checkerboard indicates transparency and is not part of the video.*

- **Transparent MOV (ProRes 4444):** place it above your footage in a video editor
  such as DaVinci Resolve. These editing files can be large.
- **Opaque MP4 (H.264):** export a video with a solid background.
- **Optional NVIDIA acceleration:** supported hardware speeds up encoding;
  CPU export remains available.
- **Saved presets and batches:** reuse settings or run several ride/preset
  combinations sequentially. Completed videos survive cancellation of the queue.

For footage recorded at **59.94 fps**, select the matching export rate
(`60000/1001`) and use the same frame rate in your editing timeline.
Use **Settings → Export** to save your preferred frame rate for new exports.
Saved presets and batches keep their own settings.

Video export needs FFmpeg. The Complete ZIP includes it; other downloads let you
select an existing `ffmpeg.exe` in the export assistant.
See the [export guide](docs/implementation/VIDEO_EXPORT.md) for details.

## Make the workspace yours

Choose **English or German** and **Dark, Light or System** appearance in
**Settings → Application**. Your saved choices are remembered. The chart adapts
to the available window space; smaller windows let you switch between the chart
and inspector.

![The same Voltron Nevera sample in the light workspace, with the airtime context strip, Ejector Airtime value card and selection inspector](docs/images/workspace-light.png)

*The same ride and selected moment, in the light theme.*

The **About…** dialog offers **Check for updates…**. Optional startup checks are
off by default. Checks contact GitHub without sending recordings, GPS data or
file paths; downloads and installation remain manual. Offline processing does
not require update checks.

## Understanding the display

Replay time uses `MM:SS.ff`, where `ff` counts samples within a second rather
than hundredths. At 50 Hz, `01:31.47` means 91.94 seconds.
Positive lateral values mean right; positive longitudinal values mean acceleration.
Negative values mean left and braking respectively.

The airtime strip follows the chart's time zoom. Its context uses vertical load
and recent changes, with short confirmation times and separate entry/exit bounds
to stabilize the labels. Curve values and numeric readouts keep their existing
smoothing. Floater/Ejector boundaries are provisional and depend on calibration
and filtering; see the [airtime context and limits](docs/implementation/AIRTIME.md).

Results depend on the recording, calibration and smoothing. The display follows
documented source-app conventions; exact agreement with every recording is not
guaranteed. GPS is a rough location reference, not a force or speed measurement.
Missing sensor data is never invented.

For current limitations and planned features, see the [roadmap](docs/ROADMAP.md).
The [documentation index](docs/README.md) links detailed behavior and source comparisons.

## Run from source

Prefer running the project directly? Clone it or download GitHub's source archive,
open PowerShell in the project folder, then run:

```powershell
.\setup.ps1
.\start.ps1
```

Setup needs internet access to download the environment. To include the supplied
FFmpeg version, run `.\setup.ps1 -VideoExport` before starting the application.
The [Windows setup guide](docs/development/SETUP.md) covers requirements,
development tools and checks.

## Help and contribute

Have a problem or an idea? [Open an issue](https://github.com/rudnerbjoern/ride-forces-analyzer/issues).
For development, checks, pull requests and recording permissions, see
[CONTRIBUTING.md](CONTRIBUTING.md). Report security vulnerabilities privately
using [SECURITY.md](SECURITY.md).

**Independent project:** Ride Forces Analyzer is not affiliated with, endorsed
by or sponsored by the Ride Forces app or its developer.

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
