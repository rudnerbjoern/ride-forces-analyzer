# Ride Forces Analyzer

Explore your coaster rides. See the forces. Bring them into your videos.

Ride Forces Analyzer is a Windows desktop application for recordings exported
from the **Ride Forces** mobile app. Open a `.forces` file, explore how vertical,
lateral and longitudinal G-forces change throughout the ride, and turn the data
into an overlay for your Onride footage.

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
The chart stays central, with display settings, selection and ride details in
the inspector. Smaller windows let you switch between the chart and inspector.

![The same Voltron Nevera recording in the light workspace, with force curves and inspector visible](docs/images/workspace-light.png)

*The light scheme shows the same recording, selection and current values.*

## Get started

You need **Windows 10 or 11, 64-bit**, and a recording exported as `.forces`.
A standalone installer is not available yet. Download or clone this project,
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
