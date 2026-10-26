# The conversion pipeline

This page explains how a conversion in this repository turns a lab's recordings into NWB files and shares them on
DANDI. Each conversion project has its own documentation next to its code:

- [hadjas_2025](../src/hnasko_lab_to_nwb/hadjas_2025/docs/): the recordings of Hadjas et al. (2025), shared in
  DANDI:001528.
- [shock_sessions](../src/hnasko_lab_to_nwb/shock_sessions/docs/): the shock sessions of the SN pan GABA PPN mice,
  converted to local files.

## NWB and NeuroConv

[NWB](https://nwb-overview.readthedocs.io/) (Neurodata Without Borders) is a standard file format for neurophysiology
data. One NWB file holds the data of a session together with its metadata: subject, devices, surgery, and the
meaning and units of each signal. Files that follow the standard can be read by the same tools and shared on
[DANDI](https://dandiarchive.org), the archive for NWB data.

The conversions are built on [NeuroConv](https://neuroconv.readthedocs.io/), which reads acquisition formats and
writes them to NWB, and on NWB extensions for the data types the core standard does not cover (here
ndx-fiber-photometry and ndx-optogenetics).

## Parts of a conversion

A conversion project is a folder under `src/hnasko_lab_to_nwb/`, named after the paper or experiment it converts:

| Part | Role |
|---|---|
| data interfaces (`interfaces/`) | Each reads one data stream (for example the raw signal of the TDT blocks, or the lab's processed signals) and adds it to an NWB file. NeuroConv provides interfaces for common formats; the project adds its own for lab-specific files. |
| converter (`nwbconverter.py`) | Combines the interfaces of a session into one file and puts their times on one clock. |
| metadata files (`metadata/`) | YAML files with the metadata that is not in the data files, such as surgery, viruses and devices, and a session config with the settings that differ between groups of sessions. |
| session conversion (`convert_session.py`) | Finds the files of one session, builds its metadata and runs the converter. |
| batch conversion (`convert_all_sessions.py`) | Lists every session of the data folder and converts them one by one. |
| checks and staging | Checks of the data before converting, NWB Inspector reports after, and the upload to DANDI. |
| `docs/` and `tutorials/` | How to run the conversion, and notebooks that read the files. |

## From recordings to DANDI

A conversion runs in these steps:

1. Check: read the data folder and the metadata, and report problems before writing anything, for example a
   missing file or a value the code does not know.
2. Convert: write one NWB file per session. Sessions already converted are skipped, so new recordings can be added
   and converted without converting the others again.
3. Inspect: run [NWB Inspector](https://nwbinspector.readthedocs.io/) on each file, which checks it against the
   standard and its best practices.
4. Review: look at the files and the inspection summary, and fix the metadata or the code where needed.
5. Stage: organize the files as DANDI expects, validate them, and upload them to the draft of the dandiset.
   Publishing a version freezes the draft and gives it a DOI.

## Keeping a conversion correct

- Metadata lives in YAML files, so that it can be corrected and reviewed without changing code.
- Tests in `tests/` check the code and the metadata files (for example that every location has its ontology terms).
  They run on every pull request.
- A bug fix comes with a test that fails without the fix.
- Ontology terms (species, strain, brain regions) are written into the files, so that the values can be found by
  their standard identifiers.

To convert a new experiment, see [Building a new conversion pipeline](new_conversion_pipeline.md).
