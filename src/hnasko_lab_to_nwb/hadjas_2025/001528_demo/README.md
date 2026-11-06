# DANDI:001528 notebooks

These notebooks show how to read and analyze [DANDI:001528](https://dandiarchive.org/dandiset/001528/draft), the
fiber photometry recordings of Hadjas et al. (2025),
[Parkinson's disease-vulnerable and -resilient dopamine neurons display opposite responses to excitatory input](https://www.biorxiv.org/content/10.1101/2025.06.03.657460v1).
Each NWB file holds one session of one mouse: the fluorescence of a calcium or dopamine sensor recorded through one
fiber while inputs from the subthalamic nucleus (STN) or the pedunculopontine nucleus (PPN) are stimulated
optogenetically.

## Notebooks

- `read_a_session.ipynb`: opens one session, lists what the file holds, and plots dF/F with the stimulation trains,
  the raw photodetector signal and the signals computed from it, and the stimulation and recording site metadata.

## Running the notebooks

The notebooks stream the files from the DANDI Archive, so nothing needs to be downloaded first. In a Python 3.12 or
3.13 environment, install the packages with `pip install -r requirements.in` and open the notebooks with Jupyter.
