# Data organization

The conversion reads the lab's data share as it is organized on the lab server. This page describes the layout it
expects, so that new recordings can be added and converted without changing the code.

## Folder layout

```text
<data folder>/
├── ASAP FP Overview.xlsx                      overview sheet, one tab per group of mice
└── <cohort folder>/                           e.g. "GRABDA recordings"
    └── <input>/                               stimulated input, e.g. "STN", "PPN", "SNr"
        └── Fiber photometry_TDT/
            ├── Varying durations/
            │   ├── [<prefix> <site>/]         only for the Cell_type cohorts, e.g. "Anxa1 DLS"
            │   ├── <subject>-<yymmdd>-<hhmmss>/   one TDT block
            │   ├── <lab analysis script>.m
            │   └── <lab processed signals>.mat
            └── Varying frequencies/
                ├── [<prefix> <site>/]
                ├── varFreq_250ms/<subject>-<yymmdd>-<hhmmss>/
                ├── varFreq_1s/<subject>-<yymmdd>-<hhmmss>/
                ├── varFreq_4s/<subject>-<yymmdd>-<hhmmss>/
                └── <lab processed signals>.mat
```

- A TDT block folder is named after the subject and the time the recording started. The subject ID can be in
  either case (`C4708` or `c4708`).
- A block folder must not hold another block folder. Move nested blocks out before converting; the conversion
  stops with an error if it finds one.
- Each protocol folder (or site subfolder) holds one lab `.mat` file with the processed signals of all its subjects.
  It is needed only when the processed signals come from the lab (see [Data streams](data_streams.md)).

## Overview sheet

`ASAP FP Overview.xlsx` has one tab per group of mice. Each row is one subject, with the columns `Animal ID`, `Sex`,
`Genotype`, `Input`, `Recording Site` and `Hemisphere`.

- `Input` is the name of the input folder under the cohort folder.
- `Recording Site` keys the fiber and the series of the subject (for example `DLS` or `TS`).
- `Hemisphere` is `Left`, `Right`, `L` or `R`. The metadata files give right-hemisphere coordinates; they are
  mirrored for subjects implanted on the left.

A subject is converted when its tab, input and blocks are found. The data check lists the blocks of the share that
no row of the sheet converts ("unconverted block"), for example a new subject not yet added to the sheet.

## Cohorts

Each cohort is an entry of `cohorts` in `src/hnasko_lab_to_nwb/hadjas_2025/metadata/session_config.yaml` and has a
metadata file named after it (see [Metadata](metadata.md)).

| Cohort | Data folder | Inputs | Sheet tab | Recorded |
|---|---|---|---|---|
| SN pan GABA recordings | SN pan GABA recordings | PPN, STN | SNr GABA | SNr GABA neurons, GCaMP6f |
| SN pan DA recordings | SN pan DA recordings | PPN, STN | SNc pan-DA | SNc dopamine neurons, GCaMP6f |
| GRABDA recordings | GRABDA recordings | PPN, STN | GRAB DA | dopamine release in DLS or TS, GRAB-DA2m |
| GRABDA recordings_STN_mCherry | GRABDA recordings | STN_mCherry | GRAB DA | as GRAB-DA, mCherry controls for STN stimulation |
| GRABDA recordings_SNr | GRABDA recordings | SNr | GRAB DA | as GRAB-DA, stimulation of SNr GABA neurons |
| Str_DA_terminal recordings | Str_DA_terminal recordings | STN | Striatal DA terminals | dopamine axon terminals in DLS or TS, GCaMP6f |
| Cell_type recordings_Vglut2 | Cell_type recordings | PPN, STN | DA subtypes | Vglut2+ dopamine neurons in SNc, GCaMP6f |
| Cell_type recordings_Anxa1 | Cell_type recordings | PPN, STN | DA subtypes | Anxa1+ dopamine neurons in SNc and their terminals in DLS, GCaMP8f |

Some cohorts share a data folder or a sheet tab:

- The two Cell_type cohorts are told apart by the `Genotype` column and by their site subfolders (`Vglut2 SNc`,
  `Anxa1 SNc`, `Anxa1 DLS`). Anxa1 mice recorded at two sites get one session per site.
- The three GRAB-DA cohorts are told apart by the input folder. The mCherry controls have no `.mat` file of their
  own: their processed signals are in the STN `.mat` files, under the sites `DLS_ctrl` and `TS_ctrl`.
- The processed signals of six 2022 SN pan DA STN subjects (B8364, B8369, B8370, B8427, B8429, B8612) are in the
  SN pan GABA STN `.mat` files. The `subjects` section of the session config points them there.

## Protocols

| Protocol folder | Session ID | Blocks | Stimulation |
|---|---|---|---|
| Varying durations | `varying_durations` | one | 40 Hz trains of 250 ms, 1 s and 4 s, 5 times each, 10 s apart |
| Varying frequencies | `varying_frequencies` | one per train duration | trains at 5, 10, 20 and 40 Hz, 5 times each, 20 s apart |

Some 2022 varying-durations recordings also have 16 s trains, which were not analyzed in the paper. In SN pan GABA
PPN, a varying-frequencies session is recorded in a single block that holds the three train durations one after the
other.

For a varying-frequencies session, the `varFreq_*` folder names are not used to label the blocks. The conversion
reads the train duration of each block from its stimulation events, because some folders are swapped (C4604,
C8972). The data check reports these cases as warnings.

## TDT blocks

The conversion reads these stores of each block:

- `Fi1r`: the raw photodetector signal. Its sampling rate identifies the rig (the `rigs` section of the session
  config): 6103.5 Hz on the RZ10x, 24414 Hz on the RZ5P used in 2022, where channel 2 carries the signal.
- Stimulation epocs, one store per train duration or frequency (`epoc_name_to_frequency_in_hz` in the session
  config). Varying durations: `sms_`, `s1s_`, `s4s_` (also written `ssm_`, `ss1_`, `ss4_`, or `Sms_`, `S1s_`, `S4s_`,
  `S6s_` on the 24 kHz rig). Varying frequencies: `H05_` (or `HH5_`), `H10_`, `H20_`, `H40_`.

The 465 nm and isosbestic LEDs are modulated at 210 Hz and 330 Hz. Blocks recorded before 2024 have the 465 nm LED at
210 Hz; blocks from 2024 on have it at 330 Hz (`led_modulation` in the session config). Add an entry there if the
setting changes on a rig.

The block start time is converted to the lab's time zone (America/Los_Angeles), whatever the time zone of the
computer running the conversion.

## Lab processed signals (.mat)

The lab's MATLAB scripts save their workspace as a `.mat` file. The conversion reads these variables, each grouped by
recording site, subject and block:

| Variable | Signal |
|---|---|
| `Gc_raw` | 465 nm signal, demodulated and lowpass filtered at 6 Hz, at the rate of the raw signal |
| `af_raw` | isosbestic control, demodulated and lowpass filtered at 6 Hz, at the rate of the raw signal |
| `Gc` | 465 nm signal resampled to 100 Hz |
| `af` | isosbestic control resampled to 100 Hz |
| `dF` | dF/F in percent, at 100 Hz |

The block segments of a subject are matched to its TDT blocks by their number of samples, not by their names, which
follow the folder names. A segment whose length matches no block is from another recording and stops the conversion
of that session with an error.
