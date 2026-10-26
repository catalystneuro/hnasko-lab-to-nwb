# Troubleshooting

Most problems are found by `hadjas-2025 check` before converting (see [Converting sessions](converting_sessions.md)).
This page lists its findings and the errors of the conversion, with what to do. A failed session's error is in the
`error` column of `conversion_summary.csv`, and its traceback in `convert_all_sessions.log`.

## Data check findings

| Check | Severity | Meaning | What to do |
|---|---|---|---|
| hemisphere | error | the `Hemisphere` cell of the sheet is empty or not `Left`, `Right`, `L` or `R` | correct the sheet |
| raw stream | error | the `Fi1r` store of a block cannot be read, or its rate matches no rig | check the block; for a new rig, add it to `rigs` in the session config |
| stimulation trains | error | a block has none of the protocol's stimulation epocs, or a train duration outside 250 ms, 1 s, 4 s and 16 s | check the block; for a new epoc name, add it to `epoc_name_to_frequency_in_hz` of the protocol |
| LED modulation | error | no `led_modulation` entry covers the recording date | add an entry to `led_modulation` |
| processed data | error | the lab `.mat` file is missing, has no group for the subject, or has no segment with as many samples as a block | ask the lab for the `.mat` file of these blocks, or convert with `--processed recomputed` or `--processed none` (see [Data streams](data_streams.md)) |
| train duration | warning | a block's recorded train duration disagrees with its `varFreq_*` folder | nothing; the conversion uses the recorded duration. Tell the lab |
| unconverted block | warning | no row of the sheet and no cohort of the session config converts this block | add the subject to the sheet, or the input to its cohort in the session config |

## Conversion errors

- "TDT block ... holds another block": a block folder was copied inside another one. Move the inner folder next to
  the others in the protocol folder.
- "No TDT block for ...": the sheet lists the subject, but its protocol folder has no block named after it. Check the
  folder name and the `Animal ID` cell.
- "Expected one .mat file in ...": the protocol folder has no `.mat` file or several. Keep one, or convert without the
  lab's processed signals.
- "Recomputed processed signals need whole blocks": recomputed signals cannot be combined with `stub_test=True`.
- "No bi-exponential fit of the isosbestic signal gives a baseline above zero": recomputing dF/F failed for a block,
  usually one with a large drop or jump in the signal. Look at the raw signal of the block.
- A warning "Negative slope ... scaling the isosbestic fit" while recomputing: the fit is kept, as in the lab's code.
  It is common in GRAB-DA recordings.
- "Expected 1 (or 3) video files for subject ...": see [Behavioral video](behavioral_video.md) for the expected names.

## NWB files

- A session is not converted again: `convert` skips sessions whose NWB file exists. Add `--overwrite`.
- `herd_references` is 0 in the conversion summary: the ontology terms were not written. Check that every location
  string has an entry in `external_resources_metadata.yaml` (see [Metadata](metadata.md#ontology-terms)).
- NWB Inspector messages: the report of each file is in `inspector_reports/`. `CRITICAL` and `ERROR` messages must be
  fixed before uploading; `BEST_PRACTICE_SUGGESTION` messages can be reviewed case by case.

## Staging

- `organize` stops with "already holds organized NWB files": remove the dandiset folder, or choose a new one, and run
  it again.
- `upload` stops with validation errors: nothing was uploaded. Fix the files or the dandiset metadata, then run
  `organize` and `upload` again.
