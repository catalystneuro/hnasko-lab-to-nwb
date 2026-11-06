"""Processed fiber photometry series recomputed from the raw series of an NWB file.

compute_processed_series splits the raw photodetector series (e.g. "raw_signal_SNr" in nwbfile.acquisition) into its
TDT blocks and computes the processed signals of each block with hadjas_2025.analysis.processing; it only reads the
file, so it also works on a file streamed from DANDI.

add_recomputed_processed_series writes them to the "ophys" processing module as the lab's .mat files would be written
(Hadjas2025ProcessedFiberPhotometryInterface): the same names, units and FiberPhotometryTable rows, one series per
stream concatenated over the blocks. The series descriptions say that the signals were recomputed by this package and
not by the lab. It is used by the conversion when data_streams.processed is "recomputed", and works on an NWB file
that has only the raw series, opened in append mode.
"""

from importlib.metadata import version

import numpy as np

# Imported before any NWB file is read, so that its fiber photometry objects get the extension's classes (and their
# methods, e.g. FiberPhotometryTable.create_fiber_photometry_table_region) and not classes generated from the file
from ndx_fiber_photometry import FiberPhotometryResponseSeries
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.fiber_photometry_table import add_fiber_photometry_table_region
from hnasko_lab_to_nwb.hadjas_2025.analysis.processing import (
    PROCESSED_RATE,
    PROCESSED_STREAM_NAMES,
    process_raw_signal,
)
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.checks import calculate_regular_series_rate

LAB_PROVENANCE = "computed by the lab with custom MATLAB code"


def get_recomputed_description(description: str) -> str:
    """Return the description of a lab series with its provenance replaced by that of the recomputed series.

    Parameters
    ----------
    description : str
        Description of the series in the cohort metadata, which says it was computed by the lab.

    Returns
    -------
    str
        The description, saying that the series was recomputed from the raw signal by this package.

    Raises
    ------
    ValueError
        If the description does not state the lab's provenance.
    """
    if LAB_PROVENANCE not in description:
        raise ValueError(f"The series description does not say '{LAB_PROVENANCE}': {description}")
    recomputed_provenance = (
        f"recomputed from the raw signal with hadjas_2025.analysis.processing of hnasko-lab-to-nwb "
        f"{version('hnasko-lab-to-nwb')}, a Python port of the lab's MATLAB code (its bi-exponential fit of the "
        "isosbestic signal can differ from the lab's; see the processing module)"
    )
    return description.replace(LAB_PROVENANCE, recomputed_provenance)


def get_block_bounds(timestamps: np.ndarray, sampling_frequency: float) -> list[tuple[int, int]]:
    """Split the samples of a concatenated series into its blocks, at the gaps between consecutive timestamps.

    Parameters
    ----------
    timestamps : np.ndarray
        Timestamps of the series, in seconds.
    sampling_frequency : float
        Sampling frequency within a block, in Hz.

    Returns
    -------
    list[tuple[int, int]]
        Start (included) and end (excluded) sample of each block.
    """
    gap_indices = np.flatnonzero(np.diff(timestamps) > 1.5 / sampling_frequency) + 1
    edges = [0, *gap_indices.tolist(), len(timestamps)]
    return list(zip(edges[:-1], edges[1:]))


def get_series_blocks(series) -> tuple[list[tuple[int, int]], float, np.ndarray]:
    """Get the TDT blocks of a series written by the conversion, its rate within a block and its timestamps.

    A series with a rate is one block; a series with timestamps is split into its blocks at the gaps between them
    (get_block_bounds), and its rate is that of its first block.

    Parameters
    ----------
    series : TimeSeries
        A raw or processed fiber photometry series, e.g. nwbfile.acquisition["raw_signal_SNr"].

    Returns
    -------
    tuple[list[tuple[int, int]], float, np.ndarray]
        Start (included) and end (excluded) sample of each block, the sampling frequency in Hz, and the timestamps
        of every sample, in seconds.
    """
    number_of_samples = series.data.shape[0]
    if series.rate is not None:
        sampling_frequency = float(series.rate)
        timestamps = series.starting_time + np.arange(number_of_samples) / sampling_frequency
        return [(0, number_of_samples)], sampling_frequency, timestamps
    timestamps = np.asarray(series.timestamps[:])
    first_block_end = get_block_bounds(timestamps, 1 / np.min(np.diff(timestamps)))[0][1]
    sampling_frequency = (first_block_end - 1) / (timestamps[first_block_end - 1] - timestamps[0])
    return get_block_bounds(timestamps, sampling_frequency), sampling_frequency, timestamps


def compute_processed_series(raw_series, led_modulation: dict) -> list[dict]:
    """Compute the processed signals of each TDT block of a raw photodetector series.

    The blocks are those of get_series_blocks.

    Parameters
    ----------
    raw_series : FiberPhotometryResponseSeries
        The raw series, e.g. nwbfile.acquisition["raw_signal_SNr"].
    led_modulation : dict
        Modulation frequencies of the LEDs, "calcium_signal_in_hz" and "isosbestic_control_in_hz"
        (get_led_modulation of the session start time).

    Returns
    -------
    list[dict]
        One dict per block, in time order: "starting_time", the timestamp of the block's first raw sample, at which
        its processed signals start, as for the lab's signals; "sampling_frequency", the rate of the raw signal in Hz;
        and the signals of process_raw_signal by stream name.

    Raises
    ------
    ValueError
        If the processed signals of a block cannot be computed (calculate_dff_with_biexponential_fit).
    """
    block_bounds, sampling_frequency, raw_timestamps = get_series_blocks(raw_series)
    blocks = []
    for start, end in block_bounds:
        processed = process_raw_signal(np.asarray(raw_series.data[start:end]), sampling_frequency, **led_modulation)
        blocks.append(dict(starting_time=raw_timestamps[start], sampling_frequency=sampling_frequency, **processed))
    return blocks


def add_recomputed_processed_series(
    nwbfile: NWBFile,
    metadata: dict,
    raw_metadata_key: str,
    led_modulation: dict,
) -> None:
    """Add the processed series recomputed from the raw series of an NWBFile to its "ophys" processing module.

    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile with the raw series in its acquisition.
    metadata : dict
        Metadata dictionary with the "Devices", "DeviceModels" and "FiberPhotometry" sections, as for the
        conversion (load_cohort_metadata). metadata["FiberPhotometry"] has the raw series under raw_metadata_key
        (e.g. "Fi1r_SNr") and the processed series under f"{stream}_{site}" (e.g. "dF_SNr").
    raw_metadata_key : str
        Key of the raw series in metadata["FiberPhotometry"], "Fi1r_" followed by the recording site.
    led_modulation : dict
        Modulation frequencies of the LEDs, "calcium_signal_in_hz" and "isosbestic_control_in_hz"
        (get_led_modulation of the session start time).

    Raises
    ------
    ValueError
        If the processed signals of a block cannot be computed (calculate_dff_with_biexponential_fit).
    """
    site = raw_metadata_key.removeprefix("Fi1r_")
    raw_series = nwbfile.acquisition[metadata["FiberPhotometry"][raw_metadata_key]["name"]]
    blocks = compute_processed_series(raw_series=raw_series, led_modulation=led_modulation)

    ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="Processed fiber photometry signals")
    for stream_name in PROCESSED_STREAM_NAMES:
        metadata_key = f"{stream_name}_{site}"
        series_metadata = metadata["FiberPhotometry"][metadata_key]
        rate = blocks[0]["sampling_frequency"] if stream_name.endswith("_raw") else PROCESSED_RATE
        series_timestamps = np.concatenate(
            [block["starting_time"] + np.arange(len(block[stream_name])) / rate for block in blocks]
        )
        if calculate_regular_series_rate(series_timestamps) is not None:
            timing_kwargs = dict(starting_time=series_timestamps[0], rate=rate)
        else:
            timing_kwargs = dict(timestamps=series_timestamps)
        ophys_module.add(
            FiberPhotometryResponseSeries(
                name=series_metadata["name"],
                description=get_recomputed_description(series_metadata["description"]),
                data=np.concatenate([block[stream_name] for block in blocks]),
                unit=series_metadata["unit"],
                fiber_photometry_table_region=add_fiber_photometry_table_region(
                    nwbfile=nwbfile, metadata=metadata, metadata_key=metadata_key
                ),
                **timing_kwargs,
            )
        )
