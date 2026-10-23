import numpy as np
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import (
    Hadjas2025ProcessedFiberPhotometryInterface,
)

RZ10X_SAMPLING_FREQUENCY = 6103.515625
SEGMENT_STARTING_TIMES = [0.0, 10.0, 20.0]


def expected_block_times(num_samples: int, sampling_frequency: float) -> np.ndarray:
    return np.concatenate([start + np.arange(num_samples) / sampling_frequency for start in SEGMENT_STARTING_TIMES])


def test_concatenated_tdt_series_has_one_timestamp_per_sample(anxa1_metadata, make_concatenated_tdt_interface):
    # np.arange(0, 57 / fs, 1 / fs) has 58 values at this rate, which made the conversion of C4793 fail
    num_samples = 57
    assert len(np.arange(0.0, num_samples / RZ10X_SAMPLING_FREQUENCY, 1 / RZ10X_SAMPLING_FREQUENCY)) != num_samples
    interface = make_concatenated_tdt_interface(num_samples=num_samples, sampling_frequency=RZ10X_SAMPLING_FREQUENCY)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata)

    series = nwbfile.acquisition["raw_signal_SNc"]
    assert len(series.timestamps) == len(series.data) == 3 * num_samples


def test_concatenated_tdt_series_keeps_each_block_on_its_own_times(anxa1_metadata, make_concatenated_tdt_interface):
    interface = make_concatenated_tdt_interface(num_samples=57, sampling_frequency=RZ10X_SAMPLING_FREQUENCY)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata)

    series = nwbfile.acquisition["raw_signal_SNc"]
    assert not np.isnan(series.data).any()
    np.testing.assert_array_equal(series.timestamps, expected_block_times(57, RZ10X_SAMPLING_FREQUENCY))


def test_concatenated_processed_series_keeps_each_block_on_its_own_times(
    tmp_path, anxa1_metadata, write_processed_mat_file
):
    segments = {name: np.ones(57, dtype="float32") for name in ("s250ms", "s1s", "s4s")}
    file_path = write_processed_mat_file(tmp_path / "Anxa1 DLS" / "processed.mat", "Gc_raw", "DLS", "C0001", segments)
    interface = Hadjas2025ProcessedFiberPhotometryInterface(
        file_path=file_path,
        stream_name="Gc_raw",
        subject_id="C0001",
        target_area="DLS",
        sampling_frequency=RZ10X_SAMPLING_FREQUENCY,
    )
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(
        nwbfile=nwbfile,
        metadata=anxa1_metadata,
        stimulus_channel_names=list(segments),
        segment_starting_times=SEGMENT_STARTING_TIMES,
    )

    series = nwbfile.processing["ophys"]["demodulated_calcium_signal_DLS"]
    assert not np.isnan(series.data).any()
    np.testing.assert_array_equal(series.timestamps, expected_block_times(57, RZ10X_SAMPLING_FREQUENCY))


def test_single_block_series_is_written_with_its_rate(anxa1_metadata, make_concatenated_tdt_interface):
    interface = make_concatenated_tdt_interface(num_samples=57, sampling_frequency=RZ10X_SAMPLING_FREQUENCY)
    interface._folder_paths = interface._folder_paths[:1]
    interface.segment_starting_times = [0.0]
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata)

    series = nwbfile.acquisition["raw_signal_SNc"]
    assert series.timestamps is None
    assert (series.starting_time, series.rate) == (0.0, RZ10X_SAMPLING_FREQUENCY)


def test_concatenated_tdt_series_starts_each_block_at_t1(anxa1_metadata, make_concatenated_tdt_interface):
    interface = make_concatenated_tdt_interface(num_samples=500)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata, t1=0.5, t2=0.8)

    series = nwbfile.acquisition["raw_signal_SNc"]
    expected_timestamps = np.concatenate([start + 0.5 + np.arange(30) / 100.0 for start in SEGMENT_STARTING_TIMES])
    np.testing.assert_allclose(series.timestamps, expected_timestamps)
