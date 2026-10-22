from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from pynwb import NWBHDF5IO

from hnasko_lab_to_nwb.hadjas_2025.convert_session import session_to_nwb
from hnasko_lab_to_nwb.hadjas_2025.utils import tdt_blocks

SAMPLING_FREQUENCY = 6103.515625
NUMBER_OF_SAMPLES = 61035
BLOCK_START_TIME = datetime(2024, 1, 17, 10, 15, tzinfo=ZoneInfo("America/Los_Angeles"))
SUBJECT_METADATA = {"Animal ID": "C0001", "Sex": "M", "Hemisphere": "R", "Recording Site": "DLS"}


@pytest.fixture
def fake_tdt_block(monkeypatch):
    """Serve every TDT block as a 10 s RZ10x block with one 250 ms, one 1 s and one 4 s train."""
    epocs = {
        name: SimpleNamespace(onset=np.array([onset]), offset=np.array([offset]), data=np.array([1.0]))
        for name, onset, offset in (("sms_", 1.0, 1.25), ("s1s_", 2.0, 3.0), ("s4s_", 4.0, 8.0))
    }
    block = SimpleNamespace(
        streams=dict(Fi1r=SimpleNamespace(data=np.ones(NUMBER_OF_SAMPLES, dtype="float32"), fs=SAMPLING_FREQUENCY)),
        epocs=epocs,
        info=SimpleNamespace(start_date=BLOCK_START_TIME),
    )
    monkeypatch.setattr(tdt_blocks, "_read_block", lambda folder_path, **kwargs: block)
    tdt_blocks.clear_tdt_block_cache()
    yield
    tdt_blocks.clear_tdt_block_cache()


def test_raw_only_conversion_runs_without_the_lab_mat(tmp_path, fake_tdt_block):
    protocol_folder_path = tmp_path / "GRABDA recordings" / "PPN" / "Fiber photometry_TDT" / "Varying durations"
    (protocol_folder_path / "C0001-240117-101500").mkdir(parents=True)
    output_dir_path = tmp_path / "nwb"

    session_to_nwb(
        output_dir_path=output_dir_path,
        subject_metadata=SUBJECT_METADATA,
        protocol_folder_path=protocol_folder_path,
        recording_type="GRABDA recordings",
        stimulus_location="PPN",
        protocol="Varying durations",
        data_streams=dict(processed=False),
    )

    with NWBHDF5IO(output_dir_path / "sub-C0001_ses-varying_durations.nwb", "r") as io:
        nwbfile = io.read()
        assert list(nwbfile.acquisition) == ["raw_signal_DLS"]
        assert nwbfile.acquisition["raw_signal_DLS"].data.shape == (NUMBER_OF_SAMPLES,)
        assert "ophys" not in nwbfile.processing
        epochs = nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()
        assert list(epochs["start_time"]) == [1.0, 2.0, 4.0]


def test_unknown_data_streams_raise(tmp_path, fake_tdt_block):
    with pytest.raises(ValueError, match="Unknown data streams"):
        session_to_nwb(
            output_dir_path=tmp_path,
            subject_metadata=SUBJECT_METADATA,
            protocol_folder_path=tmp_path,
            recording_type="GRABDA recordings",
            stimulus_location="PPN",
            protocol="Varying durations",
            data_streams=dict(processd=False),
        )
