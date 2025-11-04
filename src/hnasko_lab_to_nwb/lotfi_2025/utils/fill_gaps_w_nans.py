# This utility function takes in an array of data and fills in the gaps with NaNs.
# The gaps are defined as the difference between consecutive timestamps that is greater than a sampling rate.
# The input arguments are:
# data: np.ndarray - the data array to be filled with NaNs
# timestamps: np.ndarray - the timestamps corresponding to the data array
# sampling_rate: float - the expected sampling rate in seconds
import numpy as np


def fill_gaps_w_nans(data: np.ndarray, timestamps: np.ndarray, sampling_rate: float) -> (np.ndarray, np.ndarray):
    """Fill gaps in data with NaNs based on timestamps and a given sampling rate.

    Args:
        data (np.ndarray):
            The data array to be filled with NaNs.
        timestamps (np.ndarray):
            The timestamps corresponding to the data array.
        sampling_rate (float):
            The expected sampling rate in seconds.
    Returns:
        np.ndarray:
            The data array with gaps filled with NaNs.
        np.ndarray:
            The timestamps array with gaps filled with NaNs.
    """
    assert len(data) == len(timestamps), "Data and timestamps must have the same length."
    assert sampling_rate > 0, "Sampling rate must be a positive number."

    filled_data = []
    filled_timestamps = []

    # Calculate time differences between consecutive timestamps
    time_diffs = np.diff(timestamps)
    expected_interval = 1 / sampling_rate

    # Find indices where gaps occur
    gap_indices = np.where(time_diffs > expected_interval)[0]

    if len(gap_indices) == 0:
        # No gaps, return original data
        return data.copy(), timestamps.copy()

    # Build filled arrays by processing segments between gaps
    filled_data = [data[0 : gap_indices[0] + 1]]
    filled_timestamps = [timestamps[0 : gap_indices[0] + 1]]

    for idx, gap_idx in enumerate(gap_indices):
        # Calculate number of NaNs to insert
        time_diff = timestamps[gap_idx + 1] - timestamps[gap_idx]
        num_nans = int(np.floor(time_diff * sampling_rate)) - 1

        # Create NaN arrays for the gap
        nan_data = np.full(num_nans, np.nan)
        nan_timestamps = timestamps[gap_idx] + (np.arange(1, num_nans + 1) * expected_interval)

        filled_data.append(nan_data)
        filled_timestamps.append(nan_timestamps)

        # Add data segment until next gap (or end)
        next_start = gap_idx + 1
        next_end = gap_indices[idx + 1] + 1 if idx + 1 < len(gap_indices) else len(data)
        filled_data.append(data[next_start:next_end])
        filled_timestamps.append(timestamps[next_start:next_end])

    filled_data = np.concatenate(filled_data)
    filled_timestamps = np.concatenate(filled_timestamps)

    return np.array(filled_data), np.array(filled_timestamps)
