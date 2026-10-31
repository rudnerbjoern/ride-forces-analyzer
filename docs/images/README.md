# Documentation images

This is the reference for documentation image content, settings and reproduction.

## License reference

The [central owner grant](../../ASSET_LICENSES.md) defines the covered images,
author, attribution, reuse conditions and third-party rights, including the
OpenStreetMap background. The complete [CC BY-SA 4.0 legal text](LICENSE-CC-BY-SA-4.0.txt)
is retained here for redistribution.

Bundled POV photographs are listed in the
[POV inventory](../../src/ride_forces_analyzer/rendering/pov/README.md).

## Image content and reproduction

All images use the actual application or production renderer, in English.
Workspace and appearance screenshots show version 1.2.0.
Checkerboards illustrate transparency and are not part of exported videos.
HUD placement views are enlarged to illustrate a 4K editing timeline; its video
export retains the native 1920×1080 or 1080×1920 resolution.
Source hashes and exact settings are retained in the linked generated manifests.

| Images                                                | Content and fixed settings                                                                                                                                                                                                                               | Manifest                                 |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `workspace-dark.png`, `workspace-light.png`           | Voltron Nevera sample 4960, replay `01:07.39`, selection 4200–5100, 11-sample smoothing; 1600×1100 workspace.                                                                                                                                            | [Application](app-reference.json)        |
| `voltron-gps-overview.png`                            | Voltron Nevera GPS dialog, 850×650, English, full recorded route with first/last markers and an explicitly loaded OpenStreetMap background. Map details may change over time.                                                                            | [GPS](gps-reference.json)                |
| `export-preview.png`                                  | Same Voltron sample and smoothing; 1500×1000 assistant, Flow Ribbon at the bottom, Full frame, 3840×2160 landscape transparent output, 50 fps, 12-second window.                                                                                         | [Application](app-reference.json)        |
| `export-preview-pov.png`                              | Voltron Nevera preview sample 6853, replay `01:45.32` (60% of marker interval 1571–10374), 11-sample smoothing; same export settings as `export-preview.png`, with the bundled Toutatis POV photo.                                                       | [POV](pov-reference.json)                |
| Voltron layout images and `voltron-export-themes.png` | All five layouts at sample 8575, replay `02:20.04` (140.08 s at 50 Hz; recording time 171.50 s), marker interval 1571–10374, 11-sample smoothing; 3840×2160 placement views and detail crops. HUD uses a 30-second window; other layouts use 12 seconds. | [Voltron Nevera](voltron-reference.json) |
| `voltron-airtime-detail.png`                          | Voltron sample 4960, replay `01:07.39`, interval 4500–5250, 11-sample smoothing; force curves, context strip and legend.                                                                                                                                 | [README details](readme-reference.json)  |
| `taron-force-cards.png`                               | Taron sample 3399, replay `00:22.15`, 11-sample smoothing; vertical +0.05 g, lateral +0.35 g, longitudinal +1.08 g.                                                                                                                                      | [README details](readme-reference.json)  |
| `manta-smoothing-comparison.png`                      | Manta samples 4650–4900 (93–98 s); vertical force with smoothing windows 1, 11 and 31 on identical time/force scales, without a cursor.                                                                                                                  | [README details](readme-reference.json)  |
| `appearance-*.png`                                    | Same Voltron scene as the workspace screenshots; one image per theme except System, 800×650 content plus native window frame, inspector hidden, no downscaling.                                                                                          | [Appearance](appearance-reference.json)  |

The Voltron Nevera layout sample has vertical +4.37 g, lateral −0.67 g,
longitudinal −0.42 g and tilt 62.9°. It is the fixed vertical-force maximum with
simultaneous lateral and braking forces; regeneration never selects a new peak.
The layout generator checks the original recording's SHA-256 before drawing.
Airtime labels are provisional interpretations.
Native UI captures use Segoe UI 9 pt and scale factor 1; README detail captures
use a 1280×720 dark workspace. The standard app capture always refreshes both
export screenshots (checkerboard and Toutatis POV) together with both workspace
images in one application session. The separate POV manifest records the actual
preview sample and background SHA-256. Export thumbnails follow the selected position
through each layout's existing placement rules.

Run the required command from the repository root in native Windows PowerShell:

```powershell
# Workspace and both export assistant screenshots
.\.venv\Scripts\python.exe .\scripts\capture_app_reference.py
# GPS overview with OpenStreetMap background (requires internet)
.\.venv\Scripts\python.exe .\scripts\capture_app_reference.py --gps
# README details
.\.venv\Scripts\python.exe .\scripts\capture_app_reference.py --details
# Appearance gallery
.\.venv\Scripts\python.exe .\scripts\capture_app_reference.py --themes
# Five Voltron Nevera layouts, crops and comparison sheet
.\.venv\Scripts\python.exe .\scripts\render_export_reference.py
```

Add `--output .tmp/image-review` to review results before replacing tracked images.
The generators pin recordings and settings, reject source-hash mismatches and leave
original recordings unchanged. UI capture uses isolated temporary preferences and
an export database under `.tmp/`; GUI captures run sequentially, apart from GUI tests.
Windows, Qt and installed font versions can affect pixels.

Inspect changed images for legibility, clipping, transparency and matching captions.
Keep the smoothing comparison's axes identical. Update existing descriptions in place
and run `npm run test:docs` to check Markdown, spelling and local links.
