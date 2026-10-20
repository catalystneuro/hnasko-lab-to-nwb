import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import (
    ConcatenatedHadjas2025ProcessedFiberPhotometryInterface,
)


@pytest.mark.xfail(strict=True, reason="t2 is set inside the segment loop and the next segment fails the stub assert")
def test_concatenated_processed_interface_stub_test_keeps_one_second_per_segment(
    tmp_path, anxa1_metadata, write_processed_mat_file
):
    segments = {name: np.ones(500, dtype="float32") for name in ("s250ms", "s1s", "s4s")}
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
        segment_starting_times=[0.0, 10.0, 20.0],
        stub_test=True,
    )

    assert len(nwbfile.processing["ophys"]["deltaF_over_F_DLS"].data) == 3 * 100


@pytest.mark.xfail(strict=True, reason="t2 is set inside the segment loop and the next segment fails the stub assert")
def test_concatenated_tdt_interface_stub_test_keeps_one_second_per_segment(
    anxa1_metadata, make_concatenated_tdt_interface
):
    interface = make_concatenated_tdt_interface(num_samples=500)
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata, stream_name="Fi1r", stub_test=True)

    assert len(nwbfile.acquisition["raw_signal_SNc"].data) == 3 * 100
