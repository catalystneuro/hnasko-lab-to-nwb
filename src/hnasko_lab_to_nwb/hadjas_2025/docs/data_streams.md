# Data streams

Each NWB file can hold three data streams, switched on or off in `data_streams` at the top of
`src/hnasko_lab_to_nwb/hadjas_2025/metadata/session_config.yaml`:

```yaml
data_streams:
  raw: true  # Fi1r photodetector signal of the TDT blocks
  processed: lab  # lab, recomputed or false
  behavioral_video: false  # AnyMaze videos of the cohorts' behavioral_video_inputs, not part of the Hadjas 2025 paper
```

The session start time, the trials and the optogenetic stimulation epochs come from the TDT blocks and are always
written.

## Raw signal

`raw: true` writes the raw photodetector signal (`Fi1r`) of the session's blocks, concatenated in time, as
`raw_signal_<site>` in the acquisition group.

## Processed signals

`processed` sets where the demodulated, resampled and dF/F signals come from:

- `lab`: read from the lab's `.mat` file of the protocol folder. The `.mat` file must have a segment for every block
  of the session.
- `recomputed`: computed from the raw signal by `hadjas_2025.processing`, the Python port of the lab's MATLAB steps.
  This needs `raw: true` and whole blocks (it cannot be combined with a stub test). The series have the same names
  and units as the lab's, and their descriptions say that they were recomputed and with which package version. See
  [Processing](processing.md) for how they compare with the lab's.
- `false`: no processed signals. The conversion then needs only the TDT blocks.

A cohort can set its own `processed` value in its `cohorts` entry, for example `recomputed` for a cohort without a
lab `.mat` file (the GRAB-DA SNr-input mice). It applies unless `processed` is `false` at the top.

To change the source for one run without editing the file, use `--processed` on the command line:

```bash
hadjas-2025 check "<data folder>" "<output folder>" --processed none
hadjas-2025 convert "<data folder>" "<output folder>" --processed none
```

From Python, `session_to_nwb(..., data_streams=dict(processed=False))` updates the session config for that call.

## Raw-only conversion

To convert sessions before the lab's `.mat` files exist, set `processed: false` (or pass `--processed none`). The
files hold the raw signal, the stimulation epochs, the trials and all metadata.

Processed signals can be added later to such a file without converting it again.
`hadjas_2025.recompute.add_recomputed_processed_series` opens the raw series of the file, splits it into its blocks,
and writes the recomputed series to the `ophys` processing module. The notebook
`src/hnasko_lab_to_nwb/hadjas_2025/tutorials/recompute_processed_signals.ipynb` shows the steps on one session.

## Behavioral video

`behavioral_video: true` adds the AnyMaze videos of the cohorts that list the input in `behavioral_video_inputs`.
The videos are not part of the Hadjas 2025 paper and are off by default; see
[Behavioral video](behavioral_video.md) for the files they need.
