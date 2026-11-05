import numpy as np
import pandas as pd
from pynwb.base import TimeSeries

from hnasko_lab_to_nwb.hadjas_2025.analysis.trial_analysis import (
    TIME_WINDOWS,
    analyse_trials,
    get_onset_indices,
    get_window_columns,
)

RATE = 100.0


def make_two_block_series(first_block_samples: int = 3000, second_block_start: float = 1000.5) -> TimeSeries:
    """A dF/F series of two blocks with a gap between them; each sample's value is its index in the series."""
    second_block_samples = 4000
    timestamps = np.concatenate(
        [
            np.arange(first_block_samples) / RATE,
            second_block_start + np.arange(second_block_samples) / RATE,
        ]
    )
    return TimeSeries(
        name="deltaF_over_F_SNr", data=np.arange(len(timestamps), dtype=float), unit="%", timestamps=timestamps
    )


def test_onset_index_is_counted_from_the_start_of_the_train_block():
    series = make_two_block_series(first_block_samples=3000, second_block_start=1000.5)
    onset_times = np.array([12.345, 1000.5 + 12.345])
    # floor(100 * 12.345) = 1234, counted from 1 in MATLAB, so sample 1233 of each block
    np.testing.assert_array_equal(get_onset_indices(series.timestamps, onset_times, RATE), [1233, 3000 + 1233])


def test_trials_of_a_train_in_the_second_block_come_from_that_block():
    series = make_two_block_series(first_block_samples=3000, second_block_start=1000.5)
    epochs = pd.DataFrame(
        dict(start_time=[1000.5 + 12.345], train_duration=["1s"], stimulus_frequency=[40.0]), index=[7]
    )
    trials, statistics = analyse_trials(series, epochs)

    onset_index = 3000 + 1233
    np.testing.assert_array_equal(trials.loc[7, "dff"], np.arange(onset_index - 500, onset_index + 1001))
    # the series is a ramp of one per sample, so the normalized trial is the sample offset plus 51 (the baseline is
    # the mean of the offsets -101 to -1)
    np.testing.assert_allclose(trials.loc[7, "normalized_dff"], np.arange(-500, 1001) + 51)
    window = statistics.set_index("window").loc["stm0_250ms"]
    assert window["number_of_trials"] == 1
    np.testing.assert_allclose(window["peak"], 25 + 51)  # last sample of (0, 0.25 s]


def test_windows_exclude_their_start_and_include_their_stop():
    # stm0_250ms holds the 25 samples after the onset sample, the onset sample being column 500
    np.testing.assert_array_equal(get_window_columns(*TIME_WINDOWS["stm0_250ms"]), np.arange(501, 526))
    np.testing.assert_array_equal(get_window_columns(*TIME_WINDOWS["preStm250ms"]), np.arange(476, 501))
