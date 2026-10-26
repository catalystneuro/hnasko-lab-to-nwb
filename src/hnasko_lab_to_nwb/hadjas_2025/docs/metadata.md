# Metadata

The metadata of the NWB files (experiment description, subject, surgery, devices, viruses, fiber and stimulation
sites) is kept in YAML files in `src/hnasko_lab_to_nwb/hadjas_2025/metadata/`, so that it can be corrected without
changing code. After editing a file, convert the affected sessions again with `--overwrite`.

## Files

| File | Content |
|---|---|
| `general_metadata.yaml` | institution, lab, experimenters, related publication |
| `subject_metadata.yaml` | species, age and strain shared by all mice |
| `devices_metadata.yaml` | photometry and laser devices shared by all cohorts |
| `rig_devices_metadata.yaml` | devices that differ between the RZ5P and RZ10x rigs |
| `<cohort>_metadata.yaml` | one file per cohort: experiment description, surgery, mouse lines, fibers, viruses, fiber photometry table and series, optogenetics |
| `external_resources_metadata.yaml` | ontology terms (see below) |
| `session_config.yaml` | cohorts, protocols, rigs, LED modulation, data streams and per-subject exceptions |
| `dandiset_description.md` | name and description of DANDI:001528 |

## How a session's metadata is built

For each session, `session_to_nwb` merges, in this order:

1. The shared files (`general`, `subject`, `devices`), then the cohort file. A cohort with a `base_cohort` in the
   session config (the GRAB-DA mCherry and SNr-input cohorts) has a file that only gives what differs from the base
   cohort's file; lists in it, such as keywords, replace those of the base cohort.
2. For a subject implanted on the left (sheet column `Hemisphere`), every `hemisphere: right` becomes `left` and every
   positive ML coordinate becomes negative.
3. The devices of the session's rig, identified from the sampling rate of its raw signal.
4. Values set by the code: subject ID and sex from the sheet, session ID and description from the protocol, session
   start time from the first TDT block, and the LED modulation frequencies.
5. The ontology terms.

The optogenetics entries are then reduced to the session's stimulated input: effectors, injections and stimulation
sites whose name does not contain the input name (the sheet column `Input`) are removed, together with viruses that
no remaining injection uses.

## Editing a cohort

Find the value in the cohort file and change it. Some conventions the tests check
(`tests/test_metadata_files.py`):

- Locations are full anatomical names followed by the abbreviation, for example
  `substantia nigra pars compacta (SNc)`, and each has ontology terms.
- An unknown optional field is left out. Do not write placeholders such as `<serial number>` or empty keys.
- When the paper gives a range (for example 150 to 200 nl), the field holds the upper bound and the description gives
  the range.

## Adding a cohort

1. Add an entry to `cohorts` in `session_config.yaml`:

   ```yaml
   cohorts:
     New recordings:
       sheet_name: New tab  # tab of ASAP FP Overview.xlsx
       data_folder: New recordings  # cohort folder in the data share
       inputs: [STN]  # input folders (sheet column Input) to convert
   ```

   Optional keys: `genotype` (keep only the sheet rows whose genotype contains it), `subgroup_folder_prefix` and
   `site_in_session_id` (site subfolders, as the Cell_type cohorts), `base_cohort`, `mat_input_folder` (the input
   folder whose `.mat` files hold the cohort's processed signals) and `processed` (see
   [Data streams](data_streams.md)).
2. Add `New_recordings_metadata.yaml` (the cohort name with spaces replaced by underscores). Copy the file of the
   closest cohort, or, if most values are shared with an existing cohort, set `base_cohort` and give only what differs.
3. Check the keys that the code looks up for each recording site (the sheet column `Recording Site`, for example
   `DLS`):
   - `Fi1r_<site>`: the raw series.
   - `Gc_raw_<site>`, `af_raw_<site>`, `Gc_<site>`, `af_<site>` and `dF_<site>`: the processed series.
   - `<site>_465` and the isosbestic row in `FiberPhotometryTable.rows`.
4. Name the optogenetics effectors, injections and site rows so that they contain the input name, for example
   `chrimsonR_STN`.
5. Run the tests (`pytest tests`), convert one session with `stub_test=True` (see
   [Converting sessions](converting_sessions.md)) and run the data check.

If the new cohort's LEDs are modulated at other frequencies, add an entry to `led_modulation`.

## Ontology terms

`external_resources_metadata.yaml` maps values of the files to ontology terms, which are written into each NWB file as
HERD references (the `herd_references` column of the conversion summary counts them). Each map is keyed by the exact
value it annotates:

- `species`: NCBI Taxonomy, for `Subject.species`.
- `strain`: the JAX RRID of the C57BL/6J background, for `Subject.strain`.
- `brain_regions`: Allen Mouse Brain Atlas and UBERON terms for every location string of the cohort files.

A new location string needs an entry under `brain_regions`, with exactly the same spelling.
