"""Trial analysis of the Hadjas 2025 preprint, as in the lab's MATLAB scripts, from the dF/F series of an NWB file.

Each stimulation train gives one trial: dF/F from 5 s before to 10 s after the train onset, at 100 Hz (1501 samples),
normalized by subtracting its mean over the 101 samples before the onset sample (-1.01 s to -0.01 s).

As in the lab's code, the onset sample is counted from the start of the train's TDT block: it is the sample
floor(100 * onset time from the block start) of the block, counting from 1 as MATLAB does. The dF/F series of a
session of several blocks has a gap between blocks, so the block of each train is found from the series timestamps.

The trials are grouped by train duration and pulse frequency (the train_duration and stimulus_frequency columns of
the optogenetic epochs table). For each group and each time window of TIME_WINDOWS, get_window_statistics computes
the statistics of the lab's scripts from the normalized trials. A window (start, stop] holds the samples after start
up to and including stop, relative to the onset sample. The lab's scripts each compute a subset of these windows.

Checked against the trials and statistics of the lab's .mat files: given the lab's dF/F, the trials are the lab's and
the statistics agree to floating point precision.

add_trial_analysis writes the trial-aligned dF/F and the statistics to two tables of the "trial_analysis" module.
"""

import warnings

import numpy as np
import pandas as pd
from hdmf.common import DynamicTable, VectorData
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.analysis.processed_series import get_block_bounds, get_series_blocks
from hnasko_lab_to_nwb.hadjas_2025.analysis.processing import PROCESSED_RATE
from neuroconv.tools.nwb_helpers import get_module

PRE_ONSET_SAMPLES = 500  # 5 s at 100 Hz
POST_ONSET_SAMPLES = 1000  # 10 s at 100 Hz
# Samples of a trial relative to the onset sample
TRIAL_SAMPLE_OFFSETS = np.arange(-PRE_ONSET_SAMPLES, POST_ONSET_SAMPLES + 1)
# Samples relative to the onset sample whose mean is subtracted from a trial
BASELINE_SAMPLE_OFFSETS = np.arange(-101, 0)
# Time windows (start, stop], in seconds from the onset, by the names of the lab's scripts
TIME_WINDOWS = {
    "stm_n4_0s": (-4.0, 0.0),
    "stm_n1_0s": (-1.0, 0.0),
    "preStm250ms": (-0.25, 0.0),
    "stm0_250ms": (0.0, 0.25),
    "stm0_500ms": (0.0, 0.5),
    "stm0_1s": (0.0, 1.0),
    "stm0_2s": (0.0, 2.0),
    "stm0_4s": (0.0, 4.0),
    "stm250_500ms": (0.25, 0.5),
    "stm250_750ms": (0.25, 0.75),
    "stm250_1250ms": (0.25, 1.25),
    "stm250_2250ms": (0.25, 2.25),
    "stm750_1000ms": (0.75, 1.0),
    "stm1_2s": (1.0, 2.0),
    "stm1_3s": (1.0, 3.0),
    "stm3_4s": (3.0, 4.0),
    "stm3750_4000ms": (3.75, 4.0),
    "stm4_5s": (4.0, 5.0),
    "stm4_6s": (4.0, 6.0),
    "stm4_8s": (4.0, 8.0),
    "stm5_6s": (5.0, 6.0),
}
WINDOW_STATISTICS = {
    "mean": "mean dF/F over the window, averaged over trials",
    "auc": "area under the dF/F curve over the window (trapezoidal, in % x s), averaged over trials",
    "peak": "maximum dF/F over the window, averaged over trials",
    "peak_of_mean_trace": "maximum over the window of the dF/F averaged over trials",
    "max_absolute_deviation": "dF/F at the sample of largest absolute value in the window, averaged over trials",
    "max_absolute_deviation_of_mean_trace": (
        "value at the sample of largest absolute value in the window of the dF/F averaged over trials"
    ),
}


def get_onset_indices(timestamps: np.ndarray, onset_times: np.ndarray, rate: float = PROCESSED_RATE) -> np.ndarray:
    """Get the index of the onset sample of each train in a dF/F series, as the lab's code.

    Parameters
    ----------
    timestamps : np.ndarray
        Timestamps of the dF/F series, in seconds. Each block starts at the start of its TDT block.
    onset_times : np.ndarray
        Onset times of the trains, in seconds, on the same clock as timestamps.
    rate : float, optional
        Rate of the dF/F series within a block, in Hz (default is 100).

    Returns
    -------
    np.ndarray
        For each train, the index (from 0) of its onset sample in the series.

    Raises
    ------
    ValueError
        If a train starts before the first sample of the series.
    """
    block_starts = np.array([start for start, _ in get_block_bounds(timestamps, rate)])
    block_start_times = timestamps[block_starts]
    blocks = np.searchsorted(block_start_times, onset_times, side="right") - 1
    if np.any(blocks < 0):
        raise ValueError("A train starts before the first sample of the dF/F series.")
    # floor(rate * time from block start) counts samples from 1 in MATLAB; subtract one to count from 0
    samples_into_block = np.floor(rate * (onset_times - block_start_times[blocks])).astype(int) - 1
    return block_starts[blocks] + samples_into_block


def extract_trials(dff: np.ndarray, onset_indices: np.ndarray) -> np.ndarray:
    """Extract the dF/F of each trial, from 5 s before to 10 s after its onset sample.

    Parameters
    ----------
    dff : np.ndarray
        dF/F of the session, shape (number of samples,).
    onset_indices : np.ndarray
        Index of the onset sample of each train (get_onset_indices).

    Returns
    -------
    np.ndarray
        dF/F of each trial, shape (number of trains, 1501). Samples outside the series are NaN, with a warning.
    """
    indices = onset_indices[:, np.newaxis] + TRIAL_SAMPLE_OFFSETS[np.newaxis, :]
    outside = (indices < 0) | (indices >= len(dff))
    if np.any(outside):
        warnings.warn(f"{np.any(outside, axis=1).sum()} trials extend beyond the dF/F series; filled with NaN.")
    trials = np.asarray(dff)[np.clip(indices, 0, len(dff) - 1)].astype(float)
    trials[outside] = np.nan
    return trials


def normalize_trials(trials: np.ndarray) -> np.ndarray:
    """Subtract from each trial its mean over the 101 samples before its onset sample (-1.01 s to -0.01 s).

    Parameters
    ----------
    trials : np.ndarray
        dF/F of each trial, shape (number of trains, 1501) (extract_trials).

    Returns
    -------
    np.ndarray
        The normalized trials, same shape.
    """
    baseline_columns = PRE_ONSET_SAMPLES + BASELINE_SAMPLE_OFFSETS
    return trials - np.mean(trials[:, baseline_columns], axis=1, keepdims=True)


def get_window_columns(start: float, stop: float, rate: float = PROCESSED_RATE) -> np.ndarray:
    """Get the columns of a trial in the time window (start, stop], in seconds from the onset sample."""
    first_offset, last_offset = round(start * rate) + 1, round(stop * rate)
    return PRE_ONSET_SAMPLES + np.arange(first_offset, last_offset + 1)


def get_window_statistics(normalized_trials: np.ndarray, rate: float = PROCESSED_RATE) -> pd.DataFrame:
    """Compute the statistics of the lab's scripts in each time window, from the normalized trials of one condition.

    Parameters
    ----------
    normalized_trials : np.ndarray
        Normalized dF/F of the trials of one train duration and pulse frequency, shape (number of trains, 1501).
    rate : float, optional
        Rate of the trials, in Hz (default is 100).

    Returns
    -------
    pd.DataFrame
        One row per window of TIME_WINDOWS, with "window", "start" and "stop" (seconds from the onset) and one
        column per statistic of WINDOW_STATISTICS.
    """
    rows = []
    for window, (start, stop) in TIME_WINDOWS.items():
        values = normalized_trials[:, get_window_columns(start, stop, rate)]  # (trials, samples)
        trial_indices = np.arange(values.shape[0])
        mean_trace = values.mean(axis=0)
        rows.append(
            dict(
                window=window,
                start=start,
                stop=stop,
                mean=values.mean(axis=1).mean(),
                auc=(np.trapezoid(values, axis=1) / rate).mean(),
                peak=values.max(axis=1).mean(),
                peak_of_mean_trace=mean_trace.max(),
                max_absolute_deviation=values[trial_indices, np.abs(values).argmax(axis=1)].mean(),
                max_absolute_deviation_of_mean_trace=mean_trace[np.abs(mean_trace).argmax()],
            )
        )
    return pd.DataFrame(rows)


def analyse_trials(dff_series, epochs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the trial analysis of the lab's scripts on the dF/F series of a session.

    Parameters
    ----------
    dff_series : FiberPhotometryResponseSeries
        The dF/F series, e.g. nwbfile.processing["ophys"]["deltaF_over_F_SNr"].
    epochs : pd.DataFrame
        The optogenetic epochs table (nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()), with one row
        per train and the columns start_time, train_duration and stimulus_frequency.

    Returns
    -------
    trials : pd.DataFrame
        One row per train, indexed by the row of the epochs table, with "train_duration", "stimulus_frequency",
        "dff" and "normalized_dff" (arrays of 1501 samples, from 5 s before to 10 s after the onset sample).
    statistics : pd.DataFrame
        One row per condition (train duration and pulse frequency) and time window, with "train_duration",
        "stimulus_frequency", "number_of_trials" and the columns of get_window_statistics.
    """
    _, rate, timestamps = get_series_blocks(dff_series)
    dff = dff_series.data[:]
    onset_indices = get_onset_indices(timestamps, epochs["start_time"].to_numpy(), rate)
    dff_trials = extract_trials(dff, onset_indices)
    normalized = normalize_trials(dff_trials)
    trials = pd.DataFrame(
        dict(
            train_duration=epochs["train_duration"].to_numpy(),
            stimulus_frequency=epochs["stimulus_frequency"].to_numpy(),
            dff=list(dff_trials),
            normalized_dff=list(normalized),
        ),
        index=epochs.index,
    )

    statistics = []
    conditions = trials.groupby(["train_duration", "stimulus_frequency"], sort=False).indices
    for (train_duration, stimulus_frequency), positions in conditions.items():
        condition_statistics = get_window_statistics(normalized[positions], rate)
        condition_statistics.insert(0, "number_of_trials", len(positions))
        condition_statistics.insert(0, "stimulus_frequency", stimulus_frequency)
        condition_statistics.insert(0, "train_duration", train_duration)
        statistics.append(condition_statistics)
    return trials, pd.concat(statistics, ignore_index=True)


def add_trial_analysis(nwbfile: NWBFile, dff_series_name: str, site: str) -> None:
    """Add the trial-aligned dF/F and the window statistics of a dF/F series to the "trial_analysis" module.

    Two tables are added, named with the recording site: "trial_aligned_dff_<site>", one row per train of the
    optogenetic epochs table, and "trial_window_statistics_<site>", one row per condition (train duration and pulse
    frequency) and time window (analyse_trials).

    Parameters
    ----------
    nwbfile : NWBFile
        The NWBFile, with the dF/F series in its "ophys" processing module and the optogenetic epochs table.
    dff_series_name : str
        Name of the dF/F series, e.g. "deltaF_over_F_SNr".
    site : str
        The recording site, e.g. "SNr", which names the tables.
    """
    epochs_table = nwbfile.intervals["optogenetic_epochs_table"]
    dff_series = nwbfile.processing["ophys"][dff_series_name]
    trials, statistics = analyse_trials(dff_series=dff_series, epochs=epochs_table.to_dataframe())
    epoch_row_of_id = {row_id: row for row, row_id in enumerate(epochs_table.id[:])}
    trial_window = f"from {PRE_ONSET_SAMPLES / PROCESSED_RATE:g} s before to {POST_ONSET_SAMPLES / PROCESSED_RATE:g} s"
    trial_window += f" after the onset sample of the train, at {PROCESSED_RATE:g} Hz, in percent"

    module = get_module(
        nwbfile=nwbfile,
        name="trial_analysis",
        description="Trial analysis of the lab's MATLAB scripts, computed by hnasko-lab-to-nwb from the dF/F series.",
    )
    module.add(
        DynamicTable(
            name=f"trial_aligned_dff_{site}",
            description=f"dF/F of {dff_series_name} around each stimulation train ({trial_window}).",
            columns=[
                # Row numbers and not a DynamicTableRegion: the validator rejects a region of an extension table
                VectorData(
                    name="epoch_row",
                    data=np.array([epoch_row_of_id[row_id] for row_id in trials.index]),
                    description="Row of the train in the optogenetic epochs table, from 0.",
                ),
                VectorData(
                    name="start_time",
                    data=np.asarray(epochs_table["start_time"][:])[
                        [epoch_row_of_id[row_id] for row_id in trials.index]
                    ],
                    description="Onset time of the train, in seconds.",
                ),
                VectorData(
                    name="train_duration", data=trials["train_duration"].tolist(), description="Duration of the train."
                ),
                VectorData(
                    name="stimulus_frequency",
                    data=trials["stimulus_frequency"].to_numpy(),
                    description="Pulse frequency of the train, in Hz.",
                ),
                VectorData(name="dff", data=np.stack(trials["dff"]), description=f"dF/F {trial_window}."),
                VectorData(
                    name="normalized_dff",
                    data=np.stack(trials["normalized_dff"]),
                    description=f"dF/F {trial_window}, minus its mean over the 101 samples before the onset sample.",
                ),
            ],
        )
    )
    column_descriptions = dict(
        train_duration="Duration of the trains.",
        stimulus_frequency="Pulse frequency of the trains, in Hz.",
        number_of_trials="Number of trains of this duration and frequency.",
        window="Name of the time window in the lab's scripts.",
        start="Start of the window, in seconds from the onset sample (excluded).",
        stop="End of the window, in seconds from the onset sample (included).",
        **{
            statistic: f"{description}, of the normalized dF/F." for statistic, description in WINDOW_STATISTICS.items()
        },
    )
    module.add(
        DynamicTable(
            name=f"trial_window_statistics_{site}",
            description=f"Statistics of the normalized trial-aligned dF/F of {dff_series_name} in each time window, "
            "per train duration and pulse frequency.",
            columns=[
                VectorData(
                    name=column,
                    data=statistics[column].tolist()
                    if statistics[column].dtype == object
                    else statistics[column].to_numpy(),
                    description=column_descriptions[column],
                )
                for column in statistics.columns
            ],
        )
    )
