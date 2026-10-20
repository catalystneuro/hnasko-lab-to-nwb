import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import filter_optogenetics_metadata


@pytest.mark.xfail(strict=True, reason="list.remove while iterating skips the entry after each removal")
def test_filter_optogenetics_metadata_keeps_only_stimulus_location():
    metadata = {
        "Optogenetics": {
            "OptogeneticEffectors": [
                {"name": "ChrimsonR_STN_1"},
                {"name": "ChrimsonR_STN_2"},
                {"name": "ChrimsonR_PPN"},
            ],
            "OptogeneticVirusInjections": [
                {"name": "injection_STN_1"},
                {"name": "injection_STN_2"},
                {"name": "injection_PPN"},
            ],
            "OptogeneticSitesTable": {
                "rows": [
                    {"effector": "ChrimsonR_STN_1"},
                    {"effector": "ChrimsonR_STN_2"},
                    {"effector": "ChrimsonR_PPN"},
                ]
            },
        }
    }

    filter_optogenetics_metadata(metadata=metadata, stimulus_location="PPN")

    optogenetics = metadata["Optogenetics"]
    assert [item["name"] for item in optogenetics["OptogeneticEffectors"]] == ["ChrimsonR_PPN"]
    assert [item["name"] for item in optogenetics["OptogeneticVirusInjections"]] == ["injection_PPN"]
    assert [row["effector"] for row in optogenetics["OptogeneticSitesTable"]["rows"]] == ["ChrimsonR_PPN"]
