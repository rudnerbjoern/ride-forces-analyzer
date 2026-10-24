# Choose an export layout

All five layouts show the same ride data in different arrangements. Choose the
one that leaves the important parts of your footage visible and makes the forces
easy to read.

## Compare the layouts

![Five export layouts showing the same Voltron Nevera moment and their positions in a landscape video](../images/voltron-export-themes.png)

| Layout                 | Default position            | Useful when you want to…                                      |
| ---------------------- | --------------------------- | ------------------------------------------------------------- |
| **Flow Ribbon**        | Along the bottom            | Follow all three force curves together in a wide strip.       |
| **Corner Instruments** | Upper right                 | Read separate force cards while keeping the center clear.     |
| **HUD**                | Full screen                 | Follow frameless edge gauges and three force histories.       |
| **G-Orbit**            | Lower left                  | Follow current forces and recent peaks on circular gauges.    |
| **Four-panel column**  | Right side                  | Compare force histories and a separate orientation curve.     |

Flow Ribbon is selected when you first open the export assistant.
The comparison above shows each layout at its own default position; assistant
thumbnails follow your current position choices.
[Open the larger detail views](../EXPORT_THEMES.md) to inspect each layout.

## Try a layout with your recording

1. In the main chart, select a moment with forces you want to show.
2. Click **Export video…** and choose a layout thumbnail or **Layout profile**.
3. Choose landscape or portrait under **Video format**. Every layout supports
   both; the portrait arrangement adapts to the narrower frame.
4. Choose **Position** beside **Layout profile**. Ribbon offers top or
   bottom, Column left or right, and Corners and G-Orbit all four corners.
   HUD uses the whole frame with a fixed **Full screen** position. Its native
   1920×1080 or 1080×1920 output can be scaled to a 4K timeline in your editor.
   The assistant remembers each layout's position while open and keeps a similar
   placement when you switch layouts. Check the preview after switching.
5. Check whether the labels and curves will be readable at your video's viewing
   size, and whether the chosen position leaves the action clear.
6. Choose a light, dark or checkerboard preview background to check visibility.

The preview shows a single moment, rather than playing the video. To inspect
another moment, close the assistant, select another chart sample and reopen it.
No FFmpeg installation is needed to compare layouts.

Layouts provide preset positions and styling. The assistant does not offer dragging,
resizing, custom fonts or custom colors. You can choose the layout, position, video
format and overlay language. For the remaining export steps, follow the
[video export guide](VIDEO_EXPORT.md).

## Read the instruments

- **Vertical:** loading into the seat or lifting away from it. By default,
  positive loads point downward and negative loads upward. The **Vertical**
  checkbox can reverse the display direction; the signed numbers stay the same.
- **Lateral:** sideways forces. Positive values mean right, negative values mean
  left. The diagrams and bars use yellow.
- **Longitudinal:** forward/backward forces. Acceleration is positive and green;
  braking is negative and red.
- **Tilt / orientation:** an angle describing tilt, not a compass heading or GPS
  direction. If the recording lacks usable gravity data, no angle is invented.

Flow Ribbon and Corner Instruments include force histories
and the current vertical context, such as Floater, Airtime or Ejector. The
four-panel column adds a dedicated orientation history. G-Orbit concentrates on
current forces; its quieter peak indicators briefly retain recent extremes while
the numbers continue to show the current values.

HUD leaves the center open and places freely floating instruments around
the screen: vertical G-force and airtime at the left, acceleration/braking at the
right, lateral force below. Fine scale marks, bright pointers, large numbers,
colored glow and black shadows keep the instruments readable over footage.
The vertical scale starts at **−1.5…+5 g** for Seated recordings and **−4…+3 g**
for Flying recordings. Acceleration/braking starts at **±1.5 g** and lateral force
at **±2 g**. Scales expand to fit stronger forces in your chosen interval and stay
fixed throughout the video.

Bright bars briefly hold recent peaks; pointers and numbers show current values.
The outer right edge shows tilt from **0° to 180°** when orientation data is
available. Three force histories at the bottom share a time cursor aligned with
zero on the lateral instrument. Each curve has its own scale, so equal heights
do not necessarily mean equal forces.

Selecting HUD sets **Visible time window** to **30 seconds**, centered on the
cursor. You can change it afterward; loaded presets retain their saved window.
Missing measurements leave gaps. Exact scale and drawing rules are documented in
the [developer layout reference](../development/EXPORT_LAYOUTS.md).

The time plots do not all run in the same direction: the four-panel column reads
left to right, while compact lateral histories show the past below and the future
above. Use the signed readout to identify left/right forces regardless of layout.

**Visible time window** controls how much history surrounds each moment in the
plots. **Smoothing** reduces short fluctuations and can change peaks and airtime
labels. Changing the layout alone does not change your force data.

Airtime labels are provisional interpretations that depend on calibration and
smoothing. They do not measure a rider's sensations. See
[forces and airtime](FORCES_AND_AIRTIME.md) for the categories and their limits.

## Transparency and placement over footage

The checkerboard in the examples represents transparent space. It does not
appear in the exported video. Choose **Transparent overlay · ProRes 4444 MOV**
to place the instruments above your footage in an editor. **Opaque video · H.264
MP4** puts the layout on a black background instead.

The preview background is only a viewing aid; it does not add your footage or
change the exported background. Alignment with footage is done manually in your
video editor.

[Video export guide](VIDEO_EXPORT.md) · [Full-size examples](../EXPORT_THEMES.md) ·
[Developer layout reference](../development/EXPORT_LAYOUTS.md)
