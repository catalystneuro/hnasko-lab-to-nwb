import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import (
    ConcatenatedHadjas2025ProcessedFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.hadjas_2025.utils import fill_gaps_w_nans

SEGMENT_STARTING_TIMES = [0.0, 10.0, 20.0]


def test_fill_gaps_w_nans_keeps_float32():
    data = np.ones(10, dtype="float32")
    timestamps = np.concatenate([np.arange(5), 10 + np.arange(5)]) / 100.0

    filled_data, _ = fill_gaps_w_nans(data=data, timestamps=timestamps, sampling_rate=100.0)

    assert filled_data.dtype == np.float32


@pytest.mark.parametrize("fill_gaps", [False, True])
def test_concatenated_processed_series_keeps_float32(tmp_path, anxa1_metadata, write_processed_mat_file, fill_gaps):
    segments = {name: np.ones(5, dtype="float32") for name in ("s250ms", "s1s", "s4s")}
    file_path = write_processed_mat_file(
        file_path=tmp_path / "Anxa1 DLS" / "processed.mat",
        stream_name="dF",
        target_area="PPN_to_Anxa1",
        subject_id="C0001",
        segments=segments,
    )
    interface = ConcatenatedHadjas2025ProcessedFiberPhotometryInterface(
        file_path=file_path, stream_name="dF", subject_id="C0001", target_area="PPN_to_Anxa1", sampling_frequency=100.0
    )
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(
        nwbfile=nwbfile,
        metadata=anxa1_metadata,
        stimulus_channel_names=list(segments),
        segment_starting_times=SEGMENT_STARTING_TIMES,
        fill_gaps=fill_gaps,
    )

    assert nwbfile.processing["ophys"]["deltaF_over_F_DLS"].data.dtype == np.float32


@pytest.mark.parametrize("fill_gaps", [False, True])
def test_concatenated_tdt_series_keeps_float32(anxa1_metadata, make_concatenated_tdt_interface, fill_gaps):
    interface = make_concatenated_tdt_interface(num_samples=5)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata, stream_name="Fi1r", fill_gaps=fill_gaps)

    assert nwbfile.acquisition["raw_signal_SNc"].data.dtype == np.float32
