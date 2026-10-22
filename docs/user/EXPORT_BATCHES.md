# Save presets and export several videos

A **preset** remembers an export setup. A **batch** groups export jobs so they can
run one after another. Each recording/preset combination produces a separate
video; batches do not join rides into one clip.

For your first export, start with the [video export guide](VIDEO_EXPORT.md).
The steps below use the English interface labels.

## Save and reuse a preset

1. Open a recording and click **Export 4K…**.
2. Choose your layout, position, video format, language, output type, frame rate, visible
   time window, smoothing and range.
3. Click **Save as…** in the preset area and give the setup a unique name.
4. For another export, select that preset and click **Load**.

To change a saved preset, load it, adjust the settings and click **Update selected**.
Presets remember their own position, frame rate and overlay language, independently of
the application's defaults.

## Queue the current export

In the export assistant, click **Add this export to batch…** and choose or create
a batch. This saves the current recording, settings and interval as a job.
Use this route when you want to retain a custom **Current selection** interval.

An existing job keeps the settings saved when it was added. Updating or deleting
the original preset does not change that job. To use changed settings, remove
the old job and add it again.

## Add several recordings and presets

1. Click **Batches…** in the main window or **Saved batches…** in the export assistant.
2. Select a batch, or click **New batch…** and enter a unique name.
3. Select one or more saved presets.
4. Choose **Start/end markers for each recording** or **Entire recording**.
5. Click **Add recordings × presets…** and select your `.forces` or `.zforces` files.
6. Check the job table, including the recording, range, smoothing and video format.

Every selected recording is paired with every selected preset. For example,
three recordings and two presets create six videos. Portrait and landscape jobs
can share a batch. **Remove selected jobs** saves the removal immediately.
You can manage saved batches without opening a recording first.

## Run the queue and find the results

1. Check the **FFmpeg** field; use **Browse…** if the executable was not found.
2. Select the batches you want and click **Run selected batches…**, or choose
   **Run ALL saved batches…**.
3. Choose an output folder and follow the current-job progress and result counts.

Each run creates a new directory below the chosen folder, with numbered batch
folders and video filenames. Earlier outputs are not overwritten. The run's
`run-report.json` records completed, failed, cancelled and skipped jobs; there
is no persistent execution-history screen.

**Cancel remaining exports** stops the active export and skips pending jobs.
Incomplete output is removed, while already completed videos remain saved.
There is no automatic resume; review the results before starting another run.

## Keep source recordings available

Saved jobs refer to the original file at its saved location. They do not contain
a copy of the recording. Moving, renaming or changing a source file can make its
job fail. Add a new job using the correct file; the application does not search
for relocated recordings automatically.

One failed job does not prevent the remaining jobs from running. Check the
reported error, correct the file or FFmpeg setup, and retry the affected exports.
Older or incomplete saved presets/jobs may be unsupported and need recreating.
The application reports unsupported storage rather than silently resetting it.

## Privacy

Presets and batch definitions are saved locally and survive application restarts.
Definitions and run reports can contain recording names and paths; review them
before sharing. Processing and encoding work offline after setup, and original
recordings remain unchanged.

[Video export](VIDEO_EXPORT.md) · [Installation and FFmpeg](INSTALLATION.md) ·
[Technical batch reference](../implementation/EXPORT_BATCHES.md)
