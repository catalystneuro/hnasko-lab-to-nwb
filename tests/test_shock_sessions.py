from hnasko_lab_to_nwb.shock_sessions.convert_session import load_session_config, load_shock_session_metadata


def test_shock_session_metadata_is_the_sn_pan_gaba_metadata_without_optogenetics():
    metadata = load_shock_session_metadata()

    assert load_session_config()["base_cohort"] == "SN pan GABA recordings"
    assert metadata["Subject"]["genotype"] == "VGLUT2-Cre x VGAT-Flp"
    assert "Fi1r_SNr" in metadata["FiberPhotometry"]
    assert "Optogenetics" not in metadata
    assert "shock" in metadata["NWBFile"]["experiment_description"]
    assert "STN optogenetic stimulation" not in metadata["NWBFile"]["keywords"]


def test_shock_session_cues_are_the_cs_plus_and_cs_minus_epocs():
    cue_epocs = load_session_config()["cue_epocs"]

    assert cue_epocs["CSp_"] == dict(cue_type="CS+", paired_with_shock=True)
    assert cue_epocs["CSm_"] == dict(cue_type="CS-", paired_with_shock=False)
