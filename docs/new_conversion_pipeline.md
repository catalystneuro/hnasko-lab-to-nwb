# Building a new conversion pipeline

This page outlines how to convert a new experiment to NWB, using this repository as an example. It is a starting
point; the linked documentation covers each step in detail.

## 1. List the data and metadata

Write down, for one session:

- the files of each data stream (for example TDT blocks, processed signals, videos) and how they are organized;
- how the streams are synchronized, and which clock is the reference;
- the metadata: subject, surgery, devices, viruses, coordinates, stimulation parameters, and where each value comes
  from (a sheet, the paper, the lab's notes).

[Data organization](data_organization.md) is this list for the Hadjas 2025 conversion.

## 2. Find NeuroConv interfaces for each stream

[NeuroConv](https://neuroconv.readthedocs.io/) reads many acquisition formats and writes them to NWB. Each format has
a data interface; the [conversion gallery](https://neuroconv.readthedocs.io/en/main/conversion_examples_gallery/index.html)
shows a short example for each one, for example
[TDT fiber photometry](https://neuroconv.readthedocs.io/en/main/conversion_examples_gallery/fiberphotometry/tdt_fp.html).

For data no interface reads, such as the lab's `.mat` files here, write a small interface that subclasses
`BaseDataInterface` (see `src/hnasko_lab_to_nwb/hadjas_2025/interfaces/`).

## 3. Combine them in a converter

An `NWBConverter` combines the interfaces of a session and aligns their times (see
`src/hnasko_lab_to_nwb/hadjas_2025/nwbconverter.py`). Write a function that converts one session, then one that finds
and converts all sessions (`convert_session.py` and `convert_all_sessions.py` here).

## 4. Keep the metadata in YAML files

Put the metadata that does not come from the data files in YAML files, one per group of sessions that share it, and
merge them into the converter's metadata (see [Metadata](metadata.md)).

## 5. Check and share

- Convert one session with `stub_test=True` and open it with PyNWB or [Neurosift](https://neurosift.app).
- Run [NWB Inspector](https://nwbinspector.readthedocs.io/) on the files and fix its critical messages.
- Upload to [DANDI](https://docs.dandiarchive.org/user-guide-sharing/uploading-data/), trying the sandbox first.

## Starting a new repository

[cookiecutter-my-lab-to-nwb-template](https://github.com/catalystneuro/cookiecutter-my-lab-to-nwb-template) creates a
conversion repository with the same layout as this one. For conversions without code,
[NWB GUIDE](https://nwb-guide.readthedocs.io/) is a desktop application that walks through the same steps for the
formats NeuroConv supports.
