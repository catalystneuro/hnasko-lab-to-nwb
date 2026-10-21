from datetime import datetime, timedelta

import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    filter_optogenetics_metadata,
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
