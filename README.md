# hnasko-lab-to-nwb

Conversion of the Hnasko lab's fiber photometry and optogenetics recordings to the
[Neurodata Without Borders](https://nwb-overview.readthedocs.io/) (NWB) format, built on
[NeuroConv](https://neuroconv.readthedocs.io/).

The `hadjas_2025` conversion covers the recordings of Hadjas et al. (2025), "Parkinson's Disease-vulnerable and
-resilient dopamine neurons display opposite responses to excitatory input"
([bioRxiv, doi:10.1101/2025.06.03.657460](https://doi.org/10.1101/2025.06.03.657460)). In freely moving mice, inputs to
the substantia nigra were stimulated optogenetically while fluorescence was recorded by fiber photometry with a TDT
system. Each NWB file holds one session: the raw photodetector signal, the demodulated and dF/F signals, the
stimulation trains, and the subject, surgery and device metadata. The files are shared in
[DANDI:001528](https://dandiarchive.org/dandiset/001528).

## Installation

Install [git](https://github.com/git-guides/install-git) and [conda](https://docs.conda.io/en/latest/miniconda.html),
then, from a terminal:

```bash
git clone https://github.com/catalystneuro/hnasko-lab-to-nwb
cd hnasko-lab-to-nwb
conda env create --file make_env.yml
conda activate hnasko-lab-to-nwb-env
```

This creates a conda environment with the package installed in editable mode, so that changes to the code and
metadata files apply without installing again. Without conda, use Python 3.11 or later and run
`pip install --editable ".[analysis]"` in the cloned folder (the `analysis` extra adds Jupyter and matplotlib for the
notebooks).

## Quick start

```bash
hadjas-2025 check "<data folder>" "<output folder>"
hadjas-2025 convert "<data folder>" "<output folder>"
```

`check` reports problems in the data before converting; `convert` writes one NWB file per session to the output
folder and inspects it with NWB Inspector. See [Converting sessions](src/hnasko_lab_to_nwb/hadjas_2025/docs/converting_sessions.md).

## Documentation

The conversion pipeline in general, in [docs/](docs/):

- [The conversion pipeline](docs/conversion_pipeline.md): NWB, NeuroConv, the parts of a conversion and the steps from
  recordings to DANDI.
- [Building a new conversion pipeline](docs/new_conversion_pipeline.md): converting another experiment to NWB.

The Hadjas 2025 conversion, in [hadjas_2025/docs/](src/hnasko_lab_to_nwb/hadjas_2025/docs/):

- [Data organization](src/hnasko_lab_to_nwb/hadjas_2025/docs/data_organization.md): the data share layout, cohorts, protocols and lab files.
- [Converting sessions](src/hnasko_lab_to_nwb/hadjas_2025/docs/converting_sessions.md): checking the data, converting sessions, and the output files.
- [Data streams](src/hnasko_lab_to_nwb/hadjas_2025/docs/data_streams.md): raw and processed signals, raw-only conversion, recomputed signals.
- [Metadata](src/hnasko_lab_to_nwb/hadjas_2025/docs/metadata.md): editing the metadata files, adding a cohort, ontology terms.
- [NWB file structure](src/hnasko_lab_to_nwb/hadjas_2025/docs/nwb_file_structure.md): what is stored where, and how to read a file.
- [Processing](src/hnasko_lab_to_nwb/hadjas_2025/docs/processing.md): the Python port of the lab's processing and how it compares with the lab's.
- [DANDI staging](src/hnasko_lab_to_nwb/hadjas_2025/docs/dandi_staging.md): organizing, validating and uploading the files.
- [Troubleshooting](src/hnasko_lab_to_nwb/hadjas_2025/docs/troubleshooting.md): data check findings and conversion errors.

Notebooks in `src/hnasko_lab_to_nwb/hadjas_2025/tutorials/` show how to read the files and how to add processed
signals to a raw-only file.

## Repository layout

```text
src/hnasko_lab_to_nwb/hadjas_2025/
├── cli.py                    hadjas-2025 command
├── convert_session.py        conversion of one session
├── convert_all_sessions.py   conversion of all sessions
├── data_check.py             checks before converting
├── nwbconverter.py           NWBConverter of the dataset
├── interfaces/               data interfaces (raw, processed, optogenetic stimulation)
├── processing.py             Python port of the lab's processing
├── recompute.py              processed signals recomputed from the raw signal
├── inspection.py             NWB Inspector reports and conversion summary
├── upload_to_DANDI.py        organizing and uploading to DANDI
├── metadata/                 metadata files and session config
├── docs/                     documentation of this conversion
└── tutorials/                notebooks
```

## Citation

If you use these files, please cite the paper above, and [NeuroConv](https://github.com/catalystneuro/neuroconv) and
[NWB](https://www.nwb.org/) for the conversion.

## License

See [LICENSE](LICENSE).
