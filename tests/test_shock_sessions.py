import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.shock_sessions.convert_session import (
    load_session_config,
    load_shock_session_metadata,
    session_to_nwb,
)
from hnasko_lab_to_nwb.shock_sessions.interfaces import AuditoryCueIntervalsInterface, auditory_cue_intervals_interface
from hnasko_lab_to_nwb.shock_sessions.nwbconverter import ShockSessionsNWBConverter


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


def test_cue_intervals_are_read_from_both_cue_epocs_in_time_order(tmp_path, monkeypatch):
    epocs = {
        "CSp_": dict(onset=np.array([79.1, 207.1]), offset=np.array([87.1, 215.1])),
        "CSm_": dict(onset=np.array([127.1]), offset=np.array([135.1])),
        "Tick": dict(onset=np.arange(3.0), offset=np.arange(3.0) + 1.0),
    }
    monkeypatch.setattr(auditory_cue_intervals_interface, "read_tdt_epocs", lambda folder_path: epocs)
    interface = AuditoryCueIntervalsInterface(folder_path=tmp_path, cue_epocs=load_session_config()["cue_epocs"])

    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=load_shock_session_metadata())

    cues = nwbfile.intervals["auditory_cue_intervals"].to_dataframe()
    assert cues["start_time"].tolist() == [79.1, 127.1, 207.1]
    assert cues["stop_time"].tolist() == [87.1, 135.1, 215.1]
    assert cues["cue_type"].tolist() == ["CS+", "CS-", "CS+"]
    assert cues["paired_with_shock"].tolist() == [True, False, True]


def test_cue_intervals_fail_on_a_block_without_cue_epocs(tmp_path, monkeypatch):
    monkeypatch.setattr(auditory_cue_intervals_interface, "read_tdt_epocs", lambda folder_path: {"Tick": {}})
    interface = AuditoryCueIntervalsInterface(folder_path=tmp_path, cue_epocs=load_session_config()["cue_epocs"])

    with pytest.raises(ValueError, match="No cue epocs"):
        interface.get_cue_intervals()


def test_shock_sessions_converter_has_the_cue_interface(tmp_path):
    source_data = dict(AuditoryCueIntervals=dict(folder_path=tmp_path, cue_epocs=load_session_config()["cue_epocs"]))
    converter = ShockSessionsNWBConverter(source_data=source_data, verbose=False)

    assert isinstance(converter.data_interface_objects["AuditoryCueIntervals"], AuditoryCueIntervalsInterface)


def test_shock_session_to_nwb_refuses_a_stub_with_recomputed_signals(tmp_path):
    subject_metadata = {"Animal ID": "C0001", "Sex": "M", "Recording Site": "SNr", "Hemisphere": "Right"}

    with pytest.raises(ValueError, match="whole block"):
        session_to_nwb(tmp_path, subject_metadata, tmp_path, processed=True, stub_test=True)


def test_shock_sessions_are_found_for_the_subjects_of_the_sheet_with_a_block(tmp_path):
    import pandas as pd

    from hnasko_lab_to_nwb.shock_sessions.convert_all_sessions import get_session_to_nwb_kwargs_per_session

    rows = [
        ["C0001", "M", "VGlut2-cre x VGAT-flp", "PPN", "SNr", "R"],
        ["C0002", "F", "VGlut2-cre x VGAT-flp", "PPN", "SNr", "L"],  # no shock block
        ["C0003", "F", "VGlut2-cre x VGAT-flp", "STN", "SNr", "L"],  # input without shock sessions
    ]
    columns = ["Animal ID", "Sex", "Genotype", "Input", "Recording Site", "Hemisphere"]
    overview_file_path = tmp_path / "overview.xlsx"
    pd.DataFrame(rows, columns=columns).to_excel(overview_file_path, sheet_name="SNr GABA", index=False)
    shocks_folder_path = tmp_path / "SN pan GABA recordings" / "PPN" / "Fiber photometry_TDT" / "Shocks"
    (shocks_folder_path / "C0001-240123-140606").mkdir(parents=True)
    (tmp_path / "SN pan GABA recordings" / "STN" / "Fiber photometry_TDT" / "Shocks" / "C0003-240123-1").mkdir(
        parents=True
    )

    kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=tmp_path, subjects_metadata_file_path=overview_file_path
    )

    assert [kwargs["subject_metadata"]["Animal ID"] for kwargs in kwargs_per_session] == ["C0001"]
    assert kwargs_per_session[0]["tdt_folder_path"] == shocks_folder_path / "C0001-240123-140606"
