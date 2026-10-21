import numpy as np
from pynwb.testing.mock.file import mock_NWBFile

RZ10X_SAMPLING_FREQUENCY = 6103.515625


def test_concatenated_tdt_series_has_one_timestamp_per_sample(anxa1_metadata, make_concatenated_tdt_interface):
    # np.arange(0, 57 / fs, 1 / fs) has 58 values at this rate, which made gap filling fail on C4793
    num_samples = 57
    assert len(np.arange(0.0, num_samples / RZ10X_SAMPLING_FREQUENCY, 1 / RZ10X_SAMPLING_FREQUENCY)) != num_samples
    interface = make_concatenated_tdt_interface(num_samples=num_samples, sampling_frequency=RZ10X_SAMPLING_FREQUENCY)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata, fill_gaps=True)

    series = nwbfile.acquisition["raw_signal_SNc"]
    assert np.count_nonzero(~np.isnan(series.data)) == 3 * num_samples
    assert series.timestamps is None or len(series.timestamps) == len(series.data)
