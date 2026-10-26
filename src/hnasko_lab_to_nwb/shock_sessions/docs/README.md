# Shock sessions conversion

Conversion of the shock sessions of the SN pan GABA PPN mice to NWB. These sessions are not part of the Hadjas et al.
(2025) paper or of its dandiset; the NWB files stay local. For the conversion pipeline in general, see the
[repository docs](../../../../docs/).

## Sessions

In each session the mouse is placed in a shock chamber for 15 minutes and hears 10 auditory cues of 8 s paired with a
shock (CS+) and 10 cues of 8 s not paired with a shock (CS-). Fluorescence of GCaMP6f in SNr GABA neurons is recorded
through a fiber in SNr. There is no optogenetic stimulation.

The data share has one session per mouse for 8 mice (C4550, C4551, C4552, C4560, C4561, C4562, C4565, C4608), all
recorded on 2024-01-23:

```text
<data folder>/SN pan GABA recordings/PPN/Fiber photometry_TDT/Shocks/<subject>-<yymmdd>-<hhmmss>/
```

Each TDT block has the raw photodetector signal (`Fi1r`, 6103.5 Hz) and one epoc per cue type: `CSp_` (CS+) and
`CSm_` (CS-). The shocks were controlled by MedPC and are not in the TDT blocks, so the files hold the cue times but not
the shock times. There is no lab `.mat` file for these sessions.

## Converting

```bash
shock-sessions convert "<data folder>" "<output folder>"
shock-sessions inspect "<output folder>"
```

`convert` converts the sessions without an NWB file (all with `--overwrite`), runs NWB Inspector on each new file and
updates `conversion_summary.csv` and `convert_all_sessions.log` in the output folder, as `hadjas-2025 convert` does
(see [Converting sessions](../../hadjas_2025/docs/converting_sessions.md)). `--no-processed` leaves out the processed
signals. `inspect` inspects every file again.

From Python, `session_to_nwb` in `shock_sessions/convert_session.py` converts one session from the subject's row of
the overview sheet and its TDT block.

## What is written

Each session becomes `sub-<subject>_ses-shocks.nwb`, with:

| Path in the file | Content |
|---|---|
| `acquisition/raw_signal_SNr` | raw photodetector signal |
| `processing/ophys/...` | demodulated, 100 Hz and dF/F signals, recomputed from the raw signal by `hadjas_2025.processing` (see [Processing](../../hadjas_2025/docs/processing.md)) |
| `intervals/auditory_cue_intervals` | one row per cue: start and stop time, `cue_type` (CS+ or CS-) and `paired_with_shock` |
| `general/fiber_photometry`, `general/devices`, `general/subject` | as in the Hadjas 2025 files |

## Code and metadata

The conversion reuses the parts of `hadjas_2025`:

- Metadata: the SN pan GABA cohort file of `hadjas_2025/metadata/`, updated with
  `shock_sessions/metadata/shock_sessions_metadata.yaml` (experiment description, keywords, cue table). The
  optogenetics metadata is left out.
- Settings: `shock_sessions/metadata/session_config.yaml` (sheet tab, data folder, session description and cue epocs).
- The raw TDT interface, the recomputed processed signals and the inspection of `hadjas_2025`.
- `AuditoryCueIntervalsInterface` (`shock_sessions/interfaces/`) reads the cue epocs.

## Open

The shock times, duration and amplitude, and the cue tone, are not in the TDT data. Once the lab provides them or the
MedPC files, they can be added as a shock intervals table.
