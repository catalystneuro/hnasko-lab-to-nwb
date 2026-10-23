from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.inspection import (
    count_herd_references,
    inspect_output_folder,
    update_conversion_summary,
)


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
    assert summary.loc[0, "herd_references"] == 0
    assert (tmp_path / "inspector_reports" / "sub-C0001_ses-varying_durations.txt").exists()


def test_count_herd_references_is_zero_for_a_file_without_ontology_terms(tmp_path):
    nwbfile_path = tmp_path / "sub-C0001_ses-varying_durations.nwb"
    with NWBHDF5IO(nwbfile_path, "w") as io:
        io.write(mock_NWBFile())

    assert count_herd_references(nwbfile_path) == 0
