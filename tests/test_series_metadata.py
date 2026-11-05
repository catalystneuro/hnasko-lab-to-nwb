from pathlib import Path

import pytest

from hnasko_lab_to_nwb.hadjas_2025.analysis.processing import PROCESSED_STREAM_NAMES
from hnasko_lab_to_nwb.hadjas_2025.convert_session import load_cohort_metadata, load_session_config
from hnasko_lab_to_nwb.hadjas_2025.interfaces.processed_fp_interface import get_series_target_area


@pytest.mark.parametrize("recording_type", list(load_session_config()["cohorts"]))
def test_every_raw_series_has_processed_series_of_its_site(recording_type):
    # add_recomputed_processed_series looks up the processed series of "Fi1r_<site>" as "<stream>_<site>"
    series_metadata = load_cohort_metadata(recording_type)["FiberPhotometry"]
    sites = [key.removeprefix("Fi1r_") for key in series_metadata if key.startswith("Fi1r_")]
    missing = [f"{stream}_{site}" for site in sites for stream in PROCESSED_STREAM_NAMES]
    missing = [key for key in missing if key not in series_metadata]
    assert missing == []


def test_vglut2_mat_group_gives_the_snc_series():
    assert get_series_target_area("VG2", Path("STN_Vglut2_SNc_VG2xDA_varFreqs_DurBlocks_5mW_Demod.mat")) == "SNc"
