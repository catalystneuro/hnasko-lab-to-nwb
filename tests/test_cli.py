import pandas as pd
import pytest

from hnasko_lab_to_nwb.hadjas_2025.cli import main
from test_convert_all_sessions import make_blocks, write_overview
from test_data_check import block_train_durations  # noqa: F401 (fixture)


def test_check_writes_the_inventory_and_the_data_check(tmp_path, block_train_durations):  # noqa: F811
    data_dir_path = tmp_path / "data"
    data_dir_path.mkdir()
    write_overview(
        data_dir_path / "ASAP FP Overview.xlsx", {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]}
    )
    make_blocks(data_dir_path, "C0001", "GRABDA recordings", "PPN")
    output_dir_path = tmp_path / "nwb"

    exit_code = main(["check", str(data_dir_path), str(output_dir_path)])

    assert exit_code == 1  # no lab .mat file for the processed stream
    inventory = pd.read_csv(output_dir_path / "session_inventory.csv")
    assert list(inventory["nwbfile_name"]) == [
        "sub-C0001_ses-varying_durations.nwb",
        "sub-C0001_ses-varying_frequencies.nwb",
    ]
    data_check = pd.read_csv(output_dir_path / "data_check.csv")
    assert list(data_check["check"]) == ["processed data", "processed data"]


@pytest.mark.parametrize("command", ["organize", "upload"])
def test_organize_and_upload_need_the_dandi_instance(tmp_path, command):
    folder_paths = [str(tmp_path)] * (2 if command == "organize" else 1)

    with pytest.raises(SystemExit) as exit_info:
        main([command, *folder_paths])

    assert exit_info.value.code == 2
