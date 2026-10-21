import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_to_nwb_kwargs_per_session
from hnasko_lab_to_nwb.hadjas_2025.convert_session import METADATA_FOLDER_PATH, load_session_config

SHEET_COLUMNS = ["Animal ID", "Sex", "Genotype", "Input", "Recording Site", "Hemisphere"]
EMPTY_SHEETS = dict.fromkeys(["SNr GABA", "SNc pan-DA", "GRAB DA", "Striatal DA terminals", "DA subtypes"], [])


def write_overview(file_path, sheets: dict) -> None:
    with pd.ExcelWriter(file_path) as writer:
        for sheet_name, rows in dict(EMPTY_SHEETS, **sheets).items():
            pd.DataFrame(rows, columns=SHEET_COLUMNS).to_excel(writer, sheet_name=sheet_name, index=False)


def make_blocks(data_dir_path, subject_id, cohort_folder, stimulus_location, subgroup_folder=""):
    for protocol in ("Varying durations", "Varying frequencies"):
        protocol_folder_path = data_dir_path / cohort_folder / stimulus_location / "Fiber photometry_TDT" / protocol
        (protocol_folder_path / subgroup_folder / f"{subject_id}-240101-120000").mkdir(parents=True)


def list_sessions(kwargs_per_session) -> list:
    return sorted(
        (
            kwargs["recording_type"],
            kwargs["subject_metadata"]["Animal ID"],
            kwargs["session_id"],
            kwargs["protocol_folder_path"].name,
        )
        for kwargs in kwargs_per_session
    )


def test_every_configured_cohort_has_a_metadata_file():
    for recording_type in load_session_config()["cohorts"]:
        assert (METADATA_FOLDER_PATH / f"{recording_type.replace(' ', '_')}_metadata.yaml").exists()


def test_sessions_are_found_in_the_cohort_folder_of_each_overview_sheet(tmp_path):
    sheets = {
        "GRAB DA": [
            ["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"],
            ["C0002", "F", "Vgat-Cre", "SNr", "DLS", "R"],
        ],
        "DA subtypes": [["C0003", "M", "VGlut2-cre X DAT-flp", "STN", "SNc", "L"]],
    }
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, sheets)
    make_blocks(tmp_path, "C0001", "GRABDA recordings", "PPN")
    make_blocks(tmp_path, "C0002", "GRABDA recordings", "SNr")
    make_blocks(tmp_path, "C0003", "Cell_type recordings", "STN", "Vglut2 SNc")

    kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path
    )

    assert list_sessions(kwargs_per_session) == [
        ("Cell_type recordings_Vglut2", "C0003", "Varying durations", "Vglut2 SNc"),
        ("Cell_type recordings_Vglut2", "C0003", "Varying frequencies", "Vglut2 SNc"),
        ("GRABDA recordings", "C0001", "Varying durations", "Varying durations"),
        ("GRABDA recordings", "C0001", "Varying frequencies", "Varying frequencies"),
    ]


def test_anxa1_sessions_follow_the_block_folders_not_the_sheet_site(tmp_path):
    # e.g. C5903: "SNc" in the overview sheet, blocks only in the Anxa1 DLS folders (issue #21, findings 1 and 2)
    sheets = {
        "DA subtypes": [
            ["C0004", "F", "Vglut2-phiC X Anxa1-cre", "STN", "SNc", "R"],
            ["C0005", "M", "Vglut2-phiC X Anxa1-cre", "STN", "DLS and SNc", "R"],
        ]
    }
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, sheets)
    make_blocks(tmp_path, "C0004", "Cell_type recordings", "STN", "Anxa1 DLS")
    make_blocks(tmp_path, "C0005", "Cell_type recordings", "STN", "Anxa1 DLS")
    make_blocks(tmp_path, "C0005", "Cell_type recordings", "STN", "Anxa1 SNc")

    kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path
    )

    anxa1 = "Cell_type recordings_Anxa1"
    assert list_sessions(kwargs_per_session) == [
        (anxa1, "C0004", "Varying durations", "Anxa1 DLS"),
        (anxa1, "C0004", "Varying frequencies", "Anxa1 DLS"),
        (anxa1, "C0005", "Varying durations", "Anxa1 DLS"),
        (anxa1, "C0005", "Varying durations", "Anxa1 SNc"),
        (anxa1, "C0005", "Varying frequencies", "Anxa1 DLS"),
        (anxa1, "C0005", "Varying frequencies", "Anxa1 SNc"),
    ]
