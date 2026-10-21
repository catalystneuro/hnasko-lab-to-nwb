from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    filter_optogenetics_metadata,
    find_mat_file_path,
    load_session_config,
    localize_session_start_time,
)


@pytest.mark.parametrize(
    "session_start_datetime, utc_offset_in_hours",
    [(datetime(2024, 1, 17, 10, 15, 0), -8), (datetime(2022, 4, 26, 13, 9, 9), -7)],
)
def test_localize_session_start_time_uses_lab_time_zone(session_start_datetime, utc_offset_in_hours):
    session_start_time = localize_session_start_time(session_start_datetime)

    assert session_start_time.utcoffset() == timedelta(hours=utc_offset_in_hours)
    assert session_start_time.replace(tzinfo=None) == session_start_datetime


def test_filter_optogenetics_metadata_keeps_only_stimulus_location():
    metadata = {
        "Optogenetics": {
            "OptogeneticEffectors": {
                "ChrimsonR_STN_1": {"name": "ChrimsonR_STN_1"},
                "ChrimsonR_STN_2": {"name": "ChrimsonR_STN_2"},
                "ChrimsonR_PPN": {"name": "ChrimsonR_PPN"},
            },
            "OptogeneticVirusInjections": {
                "injection_STN_1": {"name": "injection_STN_1"},
                "injection_STN_2": {"name": "injection_STN_2"},
                "injection_PPN": {"name": "injection_PPN"},
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
