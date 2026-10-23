# Understand forces and airtime

The calibrated display follows the recording's directional information. Its
values and labels depend on calibration and smoothing; they do not measure a
rider's sensations or establish safety limits.

## Read the three force channels

- **Vertical:** loading into the seat or lifting away from it. Positive values
  indicate loading into the seat; negative values indicate lifting. Around zero
  is the region used for Floater context.
- **Lateral:** sideways forces. Positive means right; negative means left.
- **Longitudinal:** forward/backward forces. Positive means acceleration;
  negative means braking.

Calibrated values are displayed in **g**. In raw mode, x/y/z units and rider
directions are unknown. Raw mode therefore has no airtime context.
Changing an export axis direction does not change the signs of the numbers.

## Read the airtime strip

The strip below the chart uses the vertical channel to describe each moment.
It follows your time zoom. The vertical value card shows the context at the
selected sample. Labels accompany the colors:

- **Heavy Gs — violet:** stronger loading into the seat.
- **Normal Gs — neutral:** loading around 1 g.
- **Light Gs — light blue:** reduced loading before the near-zero region.
- **Floater Airtime — cyan:** vertical loading from −0.25 to +0.25 g.
- **Airtime — yellow:** negative vertical loading.
- **Strong Airtime — orange:** stronger negative loading without the rapid onset
  required by the Ejector label.
- **Ejector Airtime — red:** strong negative loading with a recent rapid drop
  in vertical loading.

Light appearance uses darker shades for readability. These context colors are
separate from force-channel colors: for example, lateral plots in export layouts
are yellow even when the airtime context is different.

![Voltron airtime detail with force curves, the colored context strip and current context](../images/voltron-airtime-detail.png)

These are provisional product categories, not universal definitions of Floater
or Ejector. Ejector considers how the force changed, rather than only its lowest
value. No label confirms what every rider experienced.

## Why can the label differ from the number?

Detailed labels need a short, consistent sequence before changing. Slight changes
near a category boundary do not immediately switch an established label back and
forth. The display can briefly show the general **Airtime** label while deciding
on a more specific category.

This stabilization affects context labels only. It does not add another smoothing
filter to the curve or numeric value. Missing values show unavailable context
instead of continuing the previous interpretation.

## How smoothing changes the result

Smoothing averages nearby measurements. Increasing it makes curves calmer but
can reduce short peaks and change both the context and the displayed extrema.
Use **1 sample** to inspect unfiltered directional values, or compare with the
default **11 samples**. When comparing rides, note the smoothing setting.

Sensor movement, mounting, calibration and the recording itself limit the
interpretation. Values can differ from the original Ride Forces app. GPS does
not improve or validate the force measurement.

The colored strip describes individual moments. It is not a count or duration
summary of airtime episodes, and the interface has no separate event-analysis
dialog. The underlying optional event analysis has its own technical rules.

[Explore a recording](EXPLORER.md) · [Export layouts](EXPORT_LAYOUTS.md) ·
[Technical thresholds and evidence](../implementation/AIRTIME.md)
