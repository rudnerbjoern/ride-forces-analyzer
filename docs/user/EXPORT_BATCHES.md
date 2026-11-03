# Save presets and export several videos

A **preset** remembers an export setup. A **batch** groups export jobs so they can
run one after another. Each recording/preset combination produces a separate
video; batches do not join rides into one clip.

For your first export, start with the [video export guide](VIDEO_EXPORT.md).
The steps below use the English interface labels.

## Save and reuse a preset

1. Open a recording and click **Export video…**.
2. Choose your layout, layout format, export area, position, language, output type, frame rate, visible
   time window, smoothing and range.
3. Click the disk icon with a plus (tooltip: **Save as…**) in the preset area and give the setup a unique name.
4. For another export, select that preset to load it immediately.

To change a saved preset, load it, adjust the settings and click the disk icon
(tooltip: **Update selected**).
To remove one, select it and click the trash icon (tooltip: **Delete preset**).
Saved batch jobs keep their settings.
Presets remember their own export area, position, frame rate and overlay language, independently of
the application's defaults.
Loading a Content-area preset hides Position; its saved placement returns if you
switch to Full frame. HUD always uses Full frame. Presets saved without an export-area
choice also use Full frame.

## Queue the current export

In the export assistant, click the new-folder icon (tooltip: **Add this export to batch…**) and choose or create
a batch. This saves the current recording, settings and interval as a job.
Use this route when you want to retain a custom **Current selection** interval.

An existing job keeps the settings saved when it was added. Updating or deleting
the original preset does not change that job. To use changed settings, remove
the old job and add it again.

## Add several recordings and presets

1. Click **Batches…** in the main window or the list icon (tooltip: **Saved batches…**) in the export assistant.
2. Select a batch, or click **New batch…** and enter a unique name.
3. Select one or more saved presets.
4. Choose **Start/end markers for each recording** or **Entire recording**.
5. Click **Add recordings × presets…** and select your `.forces` or `.zforces` files.
6. Check the job table, including the recording, range, smoothing, layout format,
   export area and output dimensions.

Every selected recording is paired with every selected preset. For example,
three recordings and two presets create six videos. Portrait and landscape jobs
can share a batch, as can Full-frame and Content-area exports.
Each job keeps its own output size. **Remove selected jobs** saves the removal immediately.
You can manage saved batches without opening a recording first.

**Add recordings × presets…** is available only after selecting a batch and at
least one saved preset, and while no preparation or export is running.

## Run the queue and find the results

1. Check the **FFmpeg** field; use **Browse…** if the executable was not found.
2. Select the batches you want and click **Run selected…**, or choose **Run all…**
   to export every saved batch. Both commands include all jobs in those batches;
   marked job rows do not restrict the run. Tooltips explain the difference.
3. Choose an output folder and follow the two progress bars.

**Overall batch** shows progress through the queue; longer videos account for
more of the bar. A finished bar does not mean every video succeeded: check the
results for failed or skipped jobs. **Current export** shows progress for the
current video and starts again for the next one. **Finalizing video…** means the
file is still being finished; its remaining time is not yet known.

**Settings → Export → Parallel render jobs** controls how many frames are prepared at once,
as described in the [video export guide](VIDEO_EXPORT.md). Videos still run one
after another.

Numbered batch folders are created directly in your chosen output folder, with
numbered video filenames. For example, choosing `E:\RF batch` for `MP4-Content`
writes videos into `E:\RF batch\001-MP4-Content`.
Existing videos are not overwritten; a job with a conflicting filename fails.
The run's `run-report.json` records completed, failed, cancelled and skipped jobs.
If a report already exists, the new report is named `run-report-<id>.json`.
The completion message shows its path. For Library recordings, right-click the
entry and choose **Export history…** to review previous attempts.

The report includes each job's saved settings, result, elapsed time and completed
file size. It also shows whether GPU encoding was actually used. Failed and
cancelled jobs retain their settings and elapsed time; skipped jobs have no
duration. Queue waiting time is not included.

**Cancel remaining exports** stops the active export and skips pending jobs.
Incomplete output is removed, while already completed videos remain saved.
There is no automatic resume; review the results before starting another run.

## Keep source recordings available

Jobs for Library recordings use the archived recording, so the original file can
be moved or deleted. Jobs saved with an external file path still need that file
at its saved location. If such a file has moved or changed, add a new job using
the correct file; the application does not search for relocated recordings.

One failed job does not prevent the remaining jobs from running. Check the
reported error, correct the file or FFmpeg setup, and retry the affected exports.
If an older saved preset or job cannot be opened, the app explains the problem
and keeps the saved data. You may need to create that preset or job again.

## Privacy

Presets and batch definitions are saved locally and survive application restarts.
Definitions and run reports can contain recording names and paths; review them
before sharing. Processing and encoding work offline after setup, and original
recordings remain unchanged.

[Video export](VIDEO_EXPORT.md) · [Installation and FFmpeg](INSTALLATION.md)
