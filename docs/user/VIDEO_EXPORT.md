# Export a ride overlay

Turn your `.forces` or `.zforces` recording into a video showing the forces throughout your
ride. Export a transparent overlay to place above your Onride footage, or a video
with a black background to watch on its own.

The steps below use English interface labels. German and French are also available.

## Before you start

- Open your recording with **Open recording**.
- Install FFmpeg for video export. The **Windows Complete ZIP** includes it;
  other downloads use a separately installed FFmpeg. Follow the
  [installation instructions](INSTALLATION.md#enable-video-export).
- Keep enough free disk space, especially for transparent MOV files.

You can try layouts and previews without FFmpeg. Opening and exporting leave
your original recording unchanged, and processing works offline after setup.

## 1. Choose the part of the ride

Click a point in the chart that you want to see in the preview, then click
**Export video…**. The assistant opens with that moment and your current smoothing.

Choose **Range** to decide how much of the ride to export:

- **Start/end markers (default):** the interval marked in the recording.
- **Current selection:** the interval set by **From sample** and **To sample**
  in the main window.
- **Entire recording:** everything in the file.

Zooming the chart does not set the export range. To export a custom section, set
the two sample fields before opening the assistant and choose **Current selection**.

## 2. Choose the look and output

The first page groups export settings, force display and encoding on the left,
with a large preview on the right. Presets and layout thumbnails stay above them.

Click a layout thumbnail and check the large preview.
[Compare all five layouts](EXPORT_LAYOUTS.md) to find a suitable position for
your footage.

![Export assistant with layout choices, settings and a transparent overlay preview](../images/export-preview.png)

Choose these settings:

- **Layout format:** landscape for a normal widescreen video, or portrait for
  vertical videos. This sets the layout arrangement.
- **Export area:** **Full frame** keeps the complete video frame; **Content area**
  exports the smaller layout image for positioning in your video editor.
  HUD always uses Full frame. **Output dimensions** shows the actual video size.
- **Position:** in Full frame, choose one of the selected layout's placements.
  The preview updates immediately. Changing layout or format keeps a supported
  or equivalent position (such as top left → top), otherwise it selects the default.
  Content area hides this choice and keeps it for your return to Full frame.
  HUD exports at 1920×1080 or 1080×1920; other Full-frame layouts export
  at 3840×2160 or 2160×3840. Review export also shows the actual dimensions.
- **Overlay language:** English, German or French, independently of the application language.
- **Output:** **Transparent overlay · ProRes 4444 MOV** to place the graphics
  over footage in an editor; **Opaque video · H.264 MP4** for a black background.
- **Video frame rate:** match your footage and editing timeline. Choices are
  23.976, 24, 25, 30, 50, 59.94 and 60 fps. Choose 23.976 or 59.94 for footage
  recorded at that rate, rather than rounding to 24 or 60.

Transparent MOV files can be much larger than MP4 files. The size estimate is
only a rough guide. To remember a frame rate for future exports, use
**Settings → Export** in the main window.

**Parallel render jobs** in the same settings controls how many video frames are
generated concurrently. Choose from 1 up to this computer's logical processor
count; the default is 1. More jobs use more CPU and memory and are not always
faster. This local preference applies to individual exports and batches; presets
retain their visual settings independently.

HUD retains its native resolution without upscaling. For a 4K project, let your
video editor scale the complete overlay to fill the timeline frame.

## 3. Check the preview

The preview shows the sample 60% of the way through the selected export range,
rounded to the nearest sample. All layout thumbnails and the large preview use
that moment; they do not play the video. Very short ranges can select an endpoint,
and a range containing only one sample uses that sample.

- **Visible time window** controls how many seconds the small history plots
  show around each moment. It does not change the length of the exported video.
- **Smoothing** controls how much the displayed forces are averaged. **1 sample**
  turns smoothing off; larger settings reduce short peaks and can change the
  airtime labels. Original measurements remain unchanged.
- The **Vertical** checkbox changes the direction of the vertical plot, without
  changing the signs of the numbers. The default shows positive loads downward
  and negative loads upward.
- Checkerboard, light and dark backgrounds help you inspect the preview. They
  are not exported. Transparent MOV keeps transparency; opaque MP4 uses black.

Changing the export range recalculates the preview sample without moving the
workspace cursor. Layout, language and display changes retain that sample.
The preview caption identifies the sample actually shown.

Airtime labels are provisional interpretations of the recording. Their meaning
depends on calibration and smoothing; they are not a measurement of what a rider felt.

## 4. Save the video

1. If FFmpeg was not found automatically, click **Browse…** next to **FFmpeg**
   and choose its executable (`ffmpeg.exe` on Windows, `ffmpeg` on Linux/macOS).
2. Click **Review export →**. Check the settings and estimated file size on the left
   and the large preview on the right. Use **Back** to change the layout or settings.
3. Click **Export video…**, choose a destination and file name, then save.
4. Wait for the export to finish. The progress bar counts frames passed to the
   encoder; the remaining time estimates pending frames. **Finalizing video…**
   means the encoder is finishing the file, with no duration estimate. You can
   cancel the export.

On Windows, the taskbar icon also shows export progress while the window is
minimized. For batches it shows overall queue progress. The indicator disappears
after completion, failure or cancellation.

The suggested file name includes the recording name and chosen overlay, for
example `Manta - HUD.mov`.

If the video already exists, confirm replacement in the save dialog. The old video
is replaced only after export succeeds. Cancellation or failure keeps the old video
and removes incomplete output.

The NVIDIA option uses supported hardware when available and falls back to the
CPU otherwise. An NVIDIA graphics card is not required.

## 5. Put the overlay above your footage

In a video editor that supports transparent ProRes 4444, such as DaVinci Resolve:

1. Use a timeline with the same frame rate as your footage and overlay.
2. Place your ride footage on a video track.
3. Place the exported **MOV** on a track above it.
   For **Content area**, position the smaller clip over your footage; its original
   Full-frame placement is not part of the video. Adjust scale in the editor if needed.
   **Full frame** already includes the selected placement on the complete canvas.
4. Move the overlay along the timeline until a recognizable ride moment, such
   as a launch or drop, lines up with the footage. Check another moment later
   in the ride as well.
5. Export the combined video from your editor.

The analyzer does not load your footage or synchronize it automatically.
[Watch the Manta example](https://youtu.be/0sGiE6F8YlI) for all five overlays
shown in turn over Onride footage. An additional
[Manta HUD example](https://youtu.be/JGcNPKoKU1Q) shows only the HUD layout.

## Reuse settings

Use the disk icon with a plus (tooltip: **Save as…**) in the assistant's preset area to save a setup. Choose a saved
preset to load it immediately and use it again.
Presets retain their own frame rate.
For several exports, the new-folder and list icons (tooltips: **Add this export to batch…**
and **Saved batches…**) let
you prepare and run a queue.
Follow [presets and batches](EXPORT_BATCHES.md) for the complete workflow and
how saved jobs retain their recording paths and settings.

## Common questions

- **Export video is disabled:** the recording needs usable calibration directions
  for directional forces. A recording that only supports raw x/y/z display
  cannot be exported as a ride overlay.
- **The preview works, but export cannot find FFmpeg:** install FFmpeg and select
  it with **Browse…**. On macOS, an app opened from Finder may not find a command
  installed through Homebrew automatically.
- **My video has a black background:** check that you exported transparent MOV
  rather than opaque MP4, and that your editor supports transparency in ProRes 4444.
  A normal video player may show transparency against black.
- **The clip covers the wrong part of the ride:** check **Range** on the review
  page. Chart zoom and the preview cursor do not define the exported interval.
- **The MOV is very large:** transparent ProRes is intended for editing. Choose
  MP4 when you want a smaller standalone video with a black background.

[Installation](INSTALLATION.md) ·
[Layout gallery](../EXPORT_LAYOUTS.md) ·
[Technical export reference](../implementation/VIDEO_EXPORT.md)
