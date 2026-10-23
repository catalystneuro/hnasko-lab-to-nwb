import pandas as pd
from pynwb import NWBHDF5IO
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025 import convert_all_sessions
from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import (
    dataset_to_nwb,
    get_session_inventory,
    get_session_to_nwb_kwargs_per_session,
)
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
            kwargs["protocol"],
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


def test_session_inventory_lists_the_blocks_and_nwb_file_of_each_session(tmp_path):
    sheets = {"DA subtypes": [["C0005", "M", "Vglut2-phiC X Anxa1-cre", "STN", "DLS and SNc", "R"]]}
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, sheets)
    make_blocks(tmp_path, "C0005", "Cell_type recordings", "STN", "Anxa1 DLS")
    frequencies_folder_path = (
        tmp_path / "Cell_type recordings" / "STN" / "Fiber photometry_TDT" / "Varying frequencies" / "Anxa1 DLS"
    )
    (frequencies_folder_path / "C0005-240101-120000").rmdir()
    for duration, time in (("4s", "130000"), ("250ms", "110000")):
        (frequencies_folder_path / f"varFreq_{duration}" / f"C0005-240101-{time}").mkdir(parents=True)

    inventory = get_session_inventory(data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path)

    assert inventory[["subject_id", "session_id", "nwbfile_name", "tdt_blocks"]].values.tolist() == [
        ["C0005", "varying_durations_DLS", "sub-C0005_ses-varying_durations_DLS.nwb", "C0005-240101-120000"],
        [
            "C0005",
            "varying_frequencies_DLS",
            "sub-C0005_ses-varying_frequencies_DLS.nwb",
            "C0005-240101-110000; C0005-240101-130000",
        ],
    ]


def test_listing_sessions_writes_nothing_to_the_data_folder(tmp_path):
    data_dir_path = tmp_path / "data"
    data_dir_path.mkdir()
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]})

    get_session_to_nwb_kwargs_per_session(data_dir_path=data_dir_path, subjects_metadata_file_path=overview_file_path)

    assert list(data_dir_path.iterdir()) == []


def test_dataset_to_nwb_logs_a_failed_session_and_converts_the_others(tmp_path, monkeypatch):
    sheets = {
        "GRAB DA": [
            ["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"],
            ["C0002", "F", "VGlut2-cre", "PPN", "TS", "L"],
        ]
    }
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, sheets)
    make_blocks(tmp_path, "C0001", "GRABDA recordings", "PPN")
    make_blocks(tmp_path, "C0002", "GRABDA recordings", "PPN")
    converted = []

    def session_to_nwb(subject_metadata, protocol, **kwargs):
        if subject_metadata["Animal ID"] == "C0001" and protocol == "Varying durations":
            raise ValueError("broken block")
        converted.append((subject_metadata["Animal ID"], protocol))

    monkeypatch.setattr(convert_all_sessions, "session_to_nwb", session_to_nwb)
    output_dir_path = tmp_path / "nwb"

    failed_sessions = dataset_to_nwb(
        data_dir_path=tmp_path, output_dir_path=output_dir_path, subjects_metadata_file_path=overview_file_path
    )

    assert [(kwargs["subject_metadata"]["Animal ID"], kwargs["protocol"]) for kwargs in failed_sessions] == [
        ("C0001", "Varying durations")
    ]
    assert len(converted) == 3
    log = (output_dir_path / "convert_all_sessions.log").read_text(encoding="utf-8")
    assert "Failed C0001 Varying durations" in log
    assert "ValueError: broken block" in log
    assert "1 of 4 sessions failed" in log


def test_dataset_to_nwb_skips_sessions_already_converted(tmp_path, monkeypatch):
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]})
    make_blocks(tmp_path, "C0001", "GRABDA recordings", "PPN")
    output_dir_path = tmp_path / "nwb"
    output_dir_path.mkdir()
    (output_dir_path / "sub-C0001_ses-varying_durations.nwb").touch()
    converted = []

    def session_to_nwb(subject_metadata, protocol, **kwargs):
        converted.append(protocol)

    monkeypatch.setattr(convert_all_sessions, "session_to_nwb", session_to_nwb)
    convert_kwargs = dict(
        data_dir_path=tmp_path, output_dir_path=output_dir_path, subjects_metadata_file_path=overview_file_path
    )

    dataset_to_nwb(**convert_kwargs)
    assert converted == ["Varying frequencies"]
    log = (output_dir_path / "convert_all_sessions.log").read_text(encoding="utf-8")
    assert "Skipped C0001 Varying durations" in log

    converted.clear()
    dataset_to_nwb(**convert_kwargs, overwrite=True)
    assert sorted(converted) == ["Varying durations", "Varying frequencies"]


def test_dataset_to_nwb_inspects_each_converted_file_and_summarizes_the_sessions(tmp_path, monkeypatch):
    overview_file_path = tmp_path / "overview.xlsx"
    write_overview(overview_file_path, {"GRAB DA": [["C0001", "M", "VGlut2-cre", "PPN", "DLS", "R"]]})
    make_blocks(tmp_path, "C0001", "GRABDA recordings", "PPN")

    def session_to_nwb(output_dir_path, protocol, **kwargs):
        if protocol == "Varying frequencies":
            raise ValueError("broken block")
        with NWBHDF5IO(output_dir_path / "sub-C0001_ses-varying_durations.nwb", "w") as io:
            io.write(mock_NWBFile())  # no subject, a critical issue for DANDI

    monkeypatch.setattr(convert_all_sessions, "session_to_nwb", session_to_nwb)
    output_dir_path = tmp_path / "nwb"

    dataset_to_nwb(
        data_dir_path=tmp_path, output_dir_path=output_dir_path, subjects_metadata_file_path=overview_file_path
    )

    report = (output_dir_path / "inspector_reports" / "sub-C0001_ses-varying_durations.txt").read_text()
    assert "check_subject_exists" in report
    summary = pd.read_csv(output_dir_path / "conversion_summary.csv", dtype=str, keep_default_na=False)
    assert summary[["nwbfile_name", "status", "error"]].values.tolist() == [
        ["sub-C0001_ses-varying_durations.nwb", "converted", ""],
        ["sub-C0001_ses-varying_frequencies.nwb", "failed", "ValueError: broken block"],
    ]
    assert int(summary.loc[0, "CRITICAL"]) >= 1
    assert summary.loc[1, "CRITICAL"] == ""
