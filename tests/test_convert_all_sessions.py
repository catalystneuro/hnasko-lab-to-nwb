import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_to_nwb_kwargs_per_session
from hnasko_lab_to_nwb.hadjas_2025.convert_session import METADATA_FOLDER_PATH, load_session_config

SHEET_COLUMNS = ["Animal ID", "Sex", "Genotype", "Input", "Recording Site", "Hemisphere"]


def write_overview(file_path, sheets: dict) -> None:
    with pd.ExcelWriter(file_path) as writer:
        for sheet_name, rows in sheets.items():
            pd.DataFrame(rows, columns=SHEET_COLUMNS).to_excel(writer, sheet_name=sheet_name, index=False)


def make_protocol_folders(data_dir_path, *parts):
    for protocol in ("Varying durations", "Varying frequencies"):
        (data_dir_path.joinpath(*parts[:2]) / "Fiber photometry_TDT" / protocol / "/".join(parts[2:])).mkdir(
            parents=True
        )


def test_every_configured_cohort_has_a_metadata_file():
    for recording_type in load_session_config()["cohorts"]:
        assert (METADATA_FOLDER_PATH / f"{recording_type.replace(' ', '_')}_metadata.yaml").exists()


def test_sessions_are_found_in_the_cohort_folder_of_each_overview_sheet(tmp_path):
    empty = dict.fromkeys(["SNr GABA", "SNc pan-DA", "Striatal DA terminals"], [])
    sheets = dict(
        empty,
        **{
            "GRAB DA": [
                ["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"],
                ["C0002", "F", "Vgat-Cre", "SNr", "DLS", "R"],
            ],
            "DA subtypes": [
                ["C0003", "M", "VGlut2-cre X DAT-flp", "STN", "SNc", "L"],
                ["C0004", "F", "Vglut2-phiC X Anxa1-cre", "PPN", "DLS", "R"],
            ],
        },
    )
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, sheets)
    make_protocol_folders(tmp_path, "GRABDA recordings", "PPN")
    make_protocol_folders(tmp_path, "GRABDA recordings", "SNr")
    make_protocol_folders(tmp_path, "Cell_type recordings", "STN", "Vglut2 SNc")
    make_protocol_folders(tmp_path, "Cell_type recordings", "PPN", "Anxa1 DLS")

    kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path
    )

    found = sorted(
        (kwargs["recording_type"], kwargs["subject_metadata"]["Animal ID"], kwargs["session_id"])
        for kwargs in kwargs_per_session
    )
    assert found == [
        ("Cell_type recordings_Anxa1", "C0004", "Varying durations"),
        ("Cell_type recordings_Anxa1", "C0004", "Varying frequencies"),
        ("Cell_type recordings_Vglut2", "C0003", "Varying durations"),
        ("Cell_type recordings_Vglut2", "C0003", "Varying frequencies"),
        ("GRABDA recordings", "C0001", "Varying durations"),
        ("GRABDA recordings", "C0001", "Varying frequencies"),
    ]
    anxa1_frequencies = next(
        kwargs for kwargs in kwargs_per_session if kwargs["recording_type"] == "Cell_type recordings_Anxa1"
    )
    assert anxa1_frequencies["protocol_folder_path"].parts[-3:] == (
        "Fiber photometry_TDT",
        "Varying durations",
        "Anxa1 DLS",
    )
