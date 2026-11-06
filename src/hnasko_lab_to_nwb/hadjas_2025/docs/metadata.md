# Metadata

The metadata of the NWB files (experiment description, subject, surgery, devices, viruses, fiber and stimulation
sites) is built from YAML files in `src/hnasko_lab_to_nwb/hadjas_2025/metadata/` and from
`src/hnasko_lab_to_nwb/hadjas_2025/cohort_metadata.py`. After a change, convert the affected sessions again with
`--overwrite`.

## Files

| File | Content |
|---|---|
| `metadata/general_metadata.yaml` | institution, lab, experimenters, related publication; species, age and strain shared by all mice; photometry and laser devices and optogenetics values shared by all cohorts; the sentences shared by the cohorts (`TextTemplates`) |
| `cohort_metadata.py` | one function per cohort: experiment description, surgery, mouse lines, fibers, viruses, recording sites and stimulated inputs; builders that fill in the fiber photometry table and series of each recording site and the optogenetics entries of each input |
| `metadata/external_resources_metadata.yaml` | ontology terms (see below) |
| `session_config.yaml` | cohorts, protocols, rigs and the devices that differ between them, LED modulation, data streams and per-subject exceptions |
| `dandiset_description.md` | name and description of DANDI:001528 |

## How a session's metadata is built

For each session, `session_to_nwb` merges, in this order:

1. `general_metadata.yaml`, then the metadata built by the cohort's function in `cohort_metadata.py`
   (`load_cohort_metadata`). The `TextTemplates` are filled in by the functions and are not written to the files.
2. For a subject implanted on the left (sheet column `Hemisphere`), every `hemisphere: right` becomes `left` and every
   positive ML coordinate becomes negative.
3. The devices of the session's rig (the `metadata` of its entry under `rigs` in the session config), identified from
   the sampling rate of its raw signal.
4. Values set by the code: subject ID and sex from the sheet, session ID and description from the protocol, session
   start time from the first TDT block, and the LED modulation frequencies.
5. The ontology terms.

The optogenetics entries are then reduced to the session's stimulated input: effectors, injections and stimulation
sites whose name does not contain the input name (the sheet column `Input`) are removed, together with viruses that
no remaining injection uses.

## Editing a cohort

A value of one cohort is in the cohort's function in `cohort_metadata.py`. A sentence or value shared by several
cohorts is in `general_metadata.yaml`, and the descriptions repeated for each recording site or input are under its
`TextTemplates`. The metadata follows these conventions:

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
   `site_in_session_id` (site subfolders, as the Cell_type cohorts) and `mat_input_folder` (the input folder whose
   `.mat` files hold the cohort's processed signals).
2. Add a function for the cohort to `cohort_metadata.py`, starting from the closest cohort's function, and add it to
   `COHORT_METADATA_FUNCTIONS` under the cohort name. The function lists the recording sites (the sheet column
   `Recording Site`, for example `DLS`) with their injection and fiber coordinates, and
   `build_fiber_photometry_metadata` gives each site the keys that the code looks up: the raw series `Fi1r_<site>`,
   the processed series `Gc_raw_<site>`, `af_raw_<site>`, `Gc_<site>`, `af_<site>` and `dF_<site>`, and the rows
   `<site>_465` and `<site>_<isosbestic wavelength>` of `FiberPhotometryTable`. A new sensor needs an entry in
   `SENSORS`, and a new site an entry in `LOCATIONS`.
3. List the stimulated inputs. An input injected with ChrimsonR in STN or PPN comes from `build_chrimsonr_input`; for
   another input, name its effector, injection and site row so that they contain the input name, as the GRAB-DA
   mCherry and SNr-input cohorts do.
4. Run the data check and convert one session with `stub_test=True` (see
   [Converting sessions](converting_sessions.md)).

If the new cohort's LEDs are modulated at other frequencies, add an entry to `led_modulation`.

## Ontology terms

`external_resources_metadata.yaml` maps metadata values to ontology terms, which are written into each NWB file as
HERD references (the `herd_references` column of the conversion summary counts them). Each map is keyed by the exact
value it annotates:

- `experimenter`: the ORCID of each experimenter, for `NWBFile.experimenter`.
- `institution`: the ROR ID of UC San Diego, for `NWBFile.institution`.
- `species`: NCBI Taxonomy, for `Subject.species`.
- `strain`: the JAX RRID of the C57BL/6J background, for `Subject.strain`.
- `anatomical_structures`: Allen Mouse Brain Atlas and UBERON terms for every location string (`LOCATIONS` in `cohort_metadata.py`).

A new location string needs an entry under `anatomical_structures`, and a new experimenter an entry under
`experimenter`, with exactly the same spelling.
