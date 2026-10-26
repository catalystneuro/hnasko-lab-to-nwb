from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    filter_optogenetics_metadata,
    find_mat_file_path,
    find_tdt_folder_paths,
    get_raw_series_site,
    get_recording_site,
    get_session_description,
    get_session_start_time,
    get_session_id,
    get_target_area_for_subject,
    load_cohort_metadata,
    load_session_config,
    normalize_hemisphere,
)


@pytest.mark.parametrize(
    "wall_clock_time, utc_offset_in_hours",
    [(datetime(2024, 1, 17, 10, 15, 0), -8), (datetime(2022, 4, 26, 13, 9, 9), -7)],
)
def test_get_session_start_time_uses_lab_time_zone(wall_clock_time, utc_offset_in_hours):
    start_timestamp = wall_clock_time.replace(tzinfo=ZoneInfo("America/Los_Angeles")).timestamp()

    session_start_time = get_session_start_time(start_timestamp)

    assert session_start_time.utcoffset() == timedelta(hours=utc_offset_in_hours)
    assert session_start_time.replace(tzinfo=None) == wall_clock_time


def test_filter_optogenetics_metadata_keeps_only_stimulus_location():
    metadata = {
        "Optogenetics": {
            "OptogeneticViruses": {"virus": {"name": "virus"}},
            "OptogeneticEffectors": {
                "ChrimsonR_STN_1": {"name": "ChrimsonR_STN_1"},
                "ChrimsonR_STN_2": {"name": "ChrimsonR_STN_2"},
                "ChrimsonR_PPN": {"name": "ChrimsonR_PPN"},
            },
            "OptogeneticVirusInjections": {
                "injection_STN_1": {"name": "injection_STN_1", "viral_vector_metadata_key": "virus"},
                "injection_STN_2": {"name": "injection_STN_2", "viral_vector_metadata_key": "virus"},
                "injection_PPN": {"name": "injection_PPN", "viral_vector_metadata_key": "virus"},
            },
            "OptogeneticSitesTable": {
                "rows": {
                    "STN_1": {"effector_metadata_key": "ChrimsonR_STN_1"},
                    "STN_2": {"effector_metadata_key": "ChrimsonR_STN_2"},
                    "PPN": {"effector_metadata_key": "ChrimsonR_PPN"},
                }
            },
        }
    }

    filter_optogenetics_metadata(metadata=metadata, stimulus_location="PPN")

    optogenetics = metadata["Optogenetics"]
    assert list(optogenetics["OptogeneticEffectors"]) == ["ChrimsonR_PPN"]
    assert list(optogenetics["OptogeneticVirusInjections"]) == ["injection_PPN"]
    assert list(optogenetics["OptogeneticSitesTable"]["rows"]) == ["PPN"]
    assert list(optogenetics["OptogeneticViruses"]) == ["virus"]


def test_filter_optogenetics_metadata_removes_viruses_of_other_stimulus_locations():
    # e.g. the ChrimsonR virus of the GRAB-DA metadata in the files of the mCherry controls
    metadata = {
        "Optogenetics": {
            "OptogeneticViruses": {"chrimsonR": {"name": "chrimsonR"}, "mCherry": {"name": "mCherry"}},
            "OptogeneticEffectors": {
                "chrimsonR_STN": {"name": "chrimsonR_STN"},
                "mCherry_STN_mCherry": {"name": "mCherry_STN_mCherry"},
            },
            "OptogeneticVirusInjections": {
                "injection_STN": {"name": "injection_STN", "viral_vector_metadata_key": "chrimsonR"},
                "injection_STN_mCherry": {"name": "injection_STN_mCherry", "viral_vector_metadata_key": "mCherry"},
            },
            "OptogeneticSitesTable": {
                "rows": {
                    "STN": {"effector_metadata_key": "chrimsonR_STN"},
                    "STN_mCherry": {"effector_metadata_key": "mCherry_STN_mCherry"},
                }
            },
        }
    }

    filter_optogenetics_metadata(metadata=metadata, stimulus_location="STN_mCherry")

    assert list(metadata["Optogenetics"]["OptogeneticViruses"]) == ["mCherry"]


def test_find_mat_file_path_uses_the_mat_cohort_folder(tmp_path):
    relative_protocol_folder_path = Path("STN") / "Fiber photometry_TDT" / "Varying durations"
    own_folder_path = tmp_path / "SN pan DA recordings" / relative_protocol_folder_path
    gaba_folder_path = tmp_path / "SN pan GABA recordings" / relative_protocol_folder_path
    for folder_path in (own_folder_path, gaba_folder_path):
        folder_path.mkdir(parents=True)
        (folder_path / "processed.mat").touch()

    mat_file_path = find_mat_file_path(
        protocol_folder_path=own_folder_path,
        cohort_data_folder="SN pan DA recordings",
        mat_cohort_folder="SN pan GABA recordings",
    )

    assert mat_file_path == gaba_folder_path / "processed.mat"


def test_find_mat_file_path_uses_the_mat_input_folder(tmp_path):
    # the GRAB-DA mCherry controls are in the .mat file of the STN input
    cohort_folder_path = tmp_path / "GRABDA recordings"
    relative_protocol_folder_path = Path("Fiber photometry_TDT") / "Varying durations"
    control_folder_path = cohort_folder_path / "STN_mCherry" / relative_protocol_folder_path
    stn_folder_path = cohort_folder_path / "STN" / relative_protocol_folder_path
    control_folder_path.mkdir(parents=True)
    stn_folder_path.mkdir(parents=True)
    (stn_folder_path / "processed.mat").touch()

    mat_file_path = find_mat_file_path(
        protocol_folder_path=control_folder_path,
        cohort_data_folder="GRABDA recordings",
        mat_cohort_folder="GRABDA recordings",
        mat_input_folder="STN",
    )

    assert mat_file_path == stn_folder_path / "processed.mat"


def test_find_mat_file_path_in_a_subgroup_folder(tmp_path):
    protocol_folder_path = (
        tmp_path / "Cell_type recordings" / "STN" / "Fiber photometry_TDT" / "Varying durations" / "Anxa1 DLS"
    )
    protocol_folder_path.mkdir(parents=True)
    (protocol_folder_path / "processed.mat").touch()

    mat_file_path = find_mat_file_path(
        protocol_folder_path=protocol_folder_path,
        cohort_data_folder="Cell_type recordings",
        mat_cohort_folder="Cell_type recordings",
    )

    assert mat_file_path == protocol_folder_path / "processed.mat"


def test_session_config_points_2022_sn_pan_da_stn_subjects_to_the_sn_pan_gaba_mat():
    subjects_config = load_session_config()["subjects"]
    for subject_id in ("B8364", "B8369", "B8370", "B8427", "B8429", "B8612"):
        assert subjects_config[subject_id]["mat_cohort_folder"] == "SN pan GABA recordings"


@pytest.mark.parametrize("value, hemisphere", [("Left", "Left"), ("L", "Left"), ("Right", "Right"), ("R", "Right")])
def test_normalize_hemisphere_reads_full_and_short_values(value, hemisphere):
    assert normalize_hemisphere(value) == hemisphere


@pytest.mark.parametrize("value", [np.nan, "", "both"])
def test_normalize_hemisphere_fails_on_missing_or_unknown_values(value):
    # e.g. C3096 (DA subtypes) has no hemisphere in the overview sheet
    with pytest.raises(ValueError, match="Unknown hemisphere"):
        normalize_hemisphere(value)


def test_find_tdt_folder_paths_matches_lowercase_block_names(tmp_path):
    # e.g. C4708 (GRAB-DA): block folders and .mat keys are written c4708
    for relative_path in ("varFreq_4s/c4708-240313-142052", "varFreq_250ms/c4708-240313-140222", "C4709-240313-1"):
        (tmp_path / relative_path).mkdir(parents=True)

    tdt_folder_paths = find_tdt_folder_paths(protocol_folder_path=tmp_path, subject_id="C4708")

    assert [folder_path.name for folder_path in tdt_folder_paths] == ["c4708-240313-140222", "c4708-240313-142052"]


def test_get_target_area_for_subject_matches_lowercase_mat_keys(tmp_path, write_processed_mat_file):
    file_path = write_processed_mat_file(
        file_path=tmp_path / "processed.mat",
        stream_name="Gc_raw",
        target_area="DLS",
        subject_id="c4708",
        segments=dict(s1s=np.ones(5)),
    )

    assert get_target_area_for_subject(file_path, "C4708") == ("DLS", "c4708")


def test_every_anxa1_session_id_carries_the_recording_site_of_its_folder():
    # issue #21, finding 15: nine Anxa1 mice had session IDs without a site
    protocol_folder_path = (
        Path("Cell_type recordings") / "STN" / "Fiber photometry_TDT" / "Varying durations" / "Anxa1 DLS"
    )
    recording_site = get_recording_site("Cell_type recordings_Anxa1", protocol_folder_path)

    assert recording_site == "DLS"
    assert get_session_id("Varying durations", "Cell_type recordings_Anxa1", recording_site) == "varying_durations_DLS"
    assert get_session_id("Varying frequencies", "Cell_type recordings_Vglut2", "SNc") == "varying_frequencies"
    assert get_session_id("Varying durations", "GRABDA recordings", None) == "varying_durations"


@pytest.mark.parametrize(
    "recording_type, sheet_site, recording_site",
    [
        ("GRABDA recordings", "TS", None),
        ("SN pan GABA recordings", "SNr", None),
        ("Cell_type recordings_Vglut2", "SNc", "SNc"),
        ("Cell_type recordings_Anxa1", "SNc", "DLS"),  # e.g. C5903: "SNc" in the sheet, blocks in Anxa1 DLS
    ],
)
def test_raw_series_site_has_metadata_without_the_lab_mat(recording_type, sheet_site, recording_site):
    raw_series_site = get_raw_series_site(
        subject_metadata={"Recording Site": sheet_site}, recording_site=recording_site
    )

    assert raw_series_site == (recording_site or sheet_site)
    assert f"Fi1r_{raw_series_site}" in load_cohort_metadata(recording_type)["FiberPhotometry"]


def test_find_tdt_folder_paths_fails_on_a_block_nested_in_another_block(tmp_path):
    # e.g. varFreq_1s/C3164-240314-120848/C5008-240314-154241 in the lab's data share
    block_folder_path = tmp_path / "varFreq_1s" / "C3164-240314-120848"
    nested_block_folder_path = block_folder_path / "C5008-240314-154241"
    nested_block_folder_path.mkdir(parents=True)
    (block_folder_path / "block.tsq").touch()
    (nested_block_folder_path / "block.tsq").touch()

    with pytest.raises(ValueError, match="holds another block, C5008-240314-154241"):
        find_tdt_folder_paths(protocol_folder_path=tmp_path, subject_id="C3164")


def test_varying_durations_with_16_s_trains_have_their_own_description():
    # 2022 recordings (24 kHz rig) add 16 s trains (S6s_); C1496 is on the same rig with the 3-duration protocol
    description = get_session_description(
        "Varying durations", ["Sms_", "S1s_", "S4s_", "S6s_", "Tick"], number_of_blocks=1
    )

    assert "250 ms, 1 s, 4 s and 16 s" in description
    assert "not analyzed in the paper" in description
    assert (
        get_session_description("Varying durations", ["sms_", "s1s_", "s4s_", "Cam1", "Tick"], number_of_blocks=1)
        != description
    )


def test_varying_frequencies_descriptions_give_the_order_and_interval_of_the_trains():
    # issue #21, finding 10: the trains of the frequencies protocol are 20 s apart, not 10 s
    epoc_names = ["H05_", "H10_", "H20_", "H40_"]
    description = get_session_description("Varying frequencies", epoc_names, number_of_blocks=3)
    single_block_description = get_session_description("Varying frequencies", epoc_names, number_of_blocks=1)

    for text in (description, single_block_description):
        assert "5, 10, 20 and 40 Hz, in this order" in text
        assert "20 s between the end of one train" in text
    assert "one trial per block" in description
    assert "one trial per train duration" in single_block_description
