import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.convert_session import filter_optogenetics_metadata, load_session_config
from hnasko_lab_to_nwb.hadjas_2025.interfaces.tdt_optogenetic_stimulus_interface import (
    Hadjas2025TDTOptogeneticStimulusInterface,
)


def make_interface(tmp_path, events: dict) -> Hadjas2025TDTOptogeneticStimulusInterface:
    interface = Hadjas2025TDTOptogeneticStimulusInterface(folder_paths=[tmp_path])
    interface.get_events = lambda: events
    return interface


@pytest.fixture
def stn_metadata(anxa1_metadata):
    filter_optogenetics_metadata(metadata=anxa1_metadata, stimulus_location="STN")
    return anxa1_metadata


def test_durations_epocs_of_the_24_khz_rig_are_written(tmp_path, stn_metadata):
    # 2022 blocks name the duration stores Sms_, S1s_, S4s_ and S6s_
    events = {
        "Sms_": dict(onset=np.array([10.0]), offset=np.array([10.25])),
        "S6s_": dict(onset=np.array([40.0]), offset=np.array([56.0])),
        "Tick": dict(onset=np.array([0.0]), offset=np.array([1.0])),
    }
    epoc_name_to_frequency = load_session_config()["protocols"]["Varying durations"]["epoc_name_to_frequency_in_hz"]
    nwbfile = mock_NWBFile()

    make_interface(tmp_path, events).add_to_nwbfile(
        nwbfile=nwbfile, metadata=stn_metadata, tdt_stimulus_channel_to_frequency=epoc_name_to_frequency
    )

    epochs = nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()
    assert sorted(epochs["start_time"]) == [10.0, 40.0]
    assert list(epochs["stimulus_frequency"]) == [40.0, 40.0]


def test_missing_stimulation_epocs_raise(tmp_path, stn_metadata):
    events = {"Tick": dict(onset=np.array([0.0]), offset=np.array([1.0]))}

    with pytest.raises(ValueError, match="None of the stimulation epocs"):
        make_interface(tmp_path, events).add_to_nwbfile(
            nwbfile=mock_NWBFile(), metadata=stn_metadata, tdt_stimulus_channel_to_frequency={"sms_": 40.0}
        )


def test_trains_without_offset_or_of_zero_length_are_dropped_and_logged(tmp_path, stn_metadata, caplog):
    # e.g. C7248 varying frequencies: an H10_ train has no offset, another one has zero length
    events = {"H10_": dict(onset=np.array([10.0, 31.0, 52.0]), offset=np.array([11.0, 31.0, np.inf]))}
    nwbfile = mock_NWBFile()

    make_interface(tmp_path, events).add_to_nwbfile(
        nwbfile=nwbfile, metadata=stn_metadata, tdt_stimulus_channel_to_frequency={"H10_": 10.0}
    )

    epochs = nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()
    assert list(epochs["start_time"]) == [10.0]
    assert "Dropped 2 of 3 H10_ trains" in caplog.text
