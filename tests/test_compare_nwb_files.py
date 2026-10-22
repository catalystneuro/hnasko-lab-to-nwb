import numpy as np
from pynwb import NWBHDF5IO, TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.utils.compare_nwb_files import compare_nwb_files


def write_nwbfile(file_path, data):
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(TimeSeries(name="signal", data=data, unit="a.u.", rate=10.0))
    with NWBHDF5IO(file_path, "w") as io:
        io.write(nwbfile)
    return file_path


def test_compare_nwb_files_ignores_identifiers_and_object_ids(tmp_path):
    file_path_a = write_nwbfile(tmp_path / "a.nwb", data=np.arange(5, dtype="float32"))
    file_path_b = write_nwbfile(tmp_path / "b.nwb", data=np.arange(5, dtype="float32"))

    assert compare_nwb_files(file_path_a, file_path_b) == []


def test_compare_nwb_files_reports_dtype_and_value_differences(tmp_path):
    file_path_a = write_nwbfile(tmp_path / "a.nwb", data=np.arange(5, dtype="float32"))
    file_path_b = write_nwbfile(tmp_path / "b.nwb", data=np.arange(5, dtype="float64") + 1)

    differences = compare_nwb_files(file_path_a, file_path_b)

    assert differences == [
        "/acquisition/signal/data: dtype float32 != float64",
        "/acquisition/signal/data: values differ (max absolute difference 1)",
    ]
