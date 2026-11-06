# Behavioral video

The conversion can add the AnyMaze videos of a session to its NWB file. They are not part of the Hadjas 2025 paper,
so they are off by default. This page lists what to prepare and how to switch them on.

## 1. Prepare the videos

1. Export each AnyMaze video to `.mp4` with the AnyMaze export tool.
2. Put the videos of one protocol in `<data folder>/<cohort folder>/<input>/AnyMaze videos_mp4/<protocol>/`, next to
   the `Fiber photometry_TDT` folder of the same input. For example:

   ```text
   SN pan GABA recordings/PPN/
   ├── Fiber photometry_TDT/
   └── AnyMaze videos_mp4/
       ├── Varying durations/
       │   ├── C4550.mp4
       │   └── video_metadata.xlsx
       └── Varying frequencies/
           ├── C4550_250ms.mp4
           ├── C4550_1s.mp4
           ├── C4550_4s.mp4
           └── video_metadata.xlsx
   ```

3. Name each video after its subject. A varying-durations session has one video. A varying-frequencies session has
   three, one per train duration, whose names end with `_250ms`, `_1s` and `_4s`.
4. In each protocol folder, add `video_metadata.xlsx` with one row per video and two columns:
   - `file_name`: the video file name, for example `C4550_250ms.mp4`.
   - `start_time`: the date and time the video started, in the local time of the recording computer.

The start time aligns the video to the TDT recording: the frames are shifted by the time between the start of the
session's first TDT block and the start of the video. A video that starts before the session stops the conversion.

## 2. Switch the videos on

In `src/hnasko_lab_to_nwb/hadjas_2025/metadata/session_config.yaml`:

1. Set `behavioral_video: true` under `data_streams`.
2. List the input in `behavioral_video_inputs` of its cohort. Only SN pan GABA PPN is listed today:

   ```yaml
   SN pan GABA recordings:
     ...
     behavioral_video_inputs: [PPN]  # AnyMaze videos, aligned to the TDT clock
   ```

From Python, `session_to_nwb(..., data_streams=dict(behavioral_video=True))` switches them on for one call.

## 3. Convert

Convert as usual (see [Converting sessions](converting_sessions.md)). Sessions converted before the videos were added
have to be converted again with `--overwrite` to include them.

## What is written

Each video is written to the acquisition group as an `ImageSeries` named `BehavioralVideo` (varying durations) or
`BehavioralVideo_<duration>` (varying frequencies), with frame times on the TDT clock. The video stays a separate
`.mp4` file, as NWB recommends for compressed video: the `ImageSeries` stores the path of the video in the data
share. `hadjas-2025 organize` copies the videos next to the NWB files and updates these paths when preparing the
upload (see [DANDI staging](dandi_staging.md)).
