from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.inspection import inspect_output_folder, update_conversion_summary


def test_inspect_output_folder_updates_the_counts_and_keeps_the_session_of_each_file(tmp_path):
    with NWBHDF5IO(tmp_path / "sub-C0001_ses-varying_durations.nwb", "w") as io:
        io.write(mock_NWBFile())
    update_conversion_summary(
        output_dir_path=tmp_path,
        rows=[dict(nwbfile_name="sub-C0001_ses-varying_durations.nwb", subject_id="C0001", status="converted")],
    )

    summary = inspect_output_folder(tmp_path)

    assert summary[["nwbfile_name", "subject_id", "status"]].values.tolist() == [
        ["sub-C0001_ses-varying_durations.nwb", "C0001", "converted"]
    ]
    assert summary.loc[0, "CRITICAL"] >= 1
    assert (tmp_path / "inspector_reports" / "sub-C0001_ses-varying_durations.txt").exists()
