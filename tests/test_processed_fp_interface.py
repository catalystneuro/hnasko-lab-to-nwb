from pathlib import Path

import numpy as np
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import (
    ConcatenatedHadjas2025ProcessedFiberPhotometryInterface,
    get_series_target_area,
)


def test_get_series_target_area_uses_folder_name_for_anxa1():
    file_path = Path("Cell_type recordings") / "PPN" / "Fiber photometry_TDT" / "Anxa1 DLS" / "processed.mat"
    assert get_series_target_area(target_area="PPN_to_Anxa1", file_path=file_path) == "DLS"
    assert get_series_target_area(target_area="STN_to_Anxa1", file_path=file_path) == "DLS"


def test_get_series_target_area_keeps_other_target_areas():
    file_path = Path("GRABDA recordings") / "PPN" / "Fiber photometry_TDT" / "Varying durations" / "processed.mat"
    assert get_series_target_area(target_area="DLS", file_path=file_path) == "DLS"


def test_concatenated_interface_reads_anxa1_site_from_folder_name(tmp_path, anxa1_metadata, write_processed_mat_file):
    segments = {name: np.ones(5) for name in ("s250ms", "s1s", "s4s")}
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
    )

    assert "deltaF_over_F_DLS" in nwbfile.processing["ophys"].data_interfaces
