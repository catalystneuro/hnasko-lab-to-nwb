from types import SimpleNamespace

import numpy as np
import pytest
import tdt

from hnasko_lab_to_nwb.hadjas_2025.convert_session import get_raw_stream_settings, get_rig_settings


def test_get_rig_settings_keeps_channel_2_of_the_24_khz_rig():
    assert get_rig_settings(24414.0625) == dict(rig_name="RZ5P", stream_indices=[2])
    assert get_rig_settings(6103.515625) == dict(rig_name="RZ10x", stream_indices=None)


def test_get_rig_settings_fails_on_an_unknown_rate():
    with pytest.raises(ValueError, match="No rig"):
        get_rig_settings(1017.2526)


def test_get_raw_stream_settings_reads_the_rate_from_the_block(monkeypatch, tmp_path):
    # e.g. C1496 (Vglut2, STN): a 24 kHz block in a cohort recorded mostly on the 6 kHz rig
    stream = SimpleNamespace(fs=24414.0625, data=np.zeros((3, 10), dtype="float32"))
    monkeypatch.setattr(tdt, "read_block", lambda *args, **kwargs: SimpleNamespace(streams=dict(Fi1r=stream)))

    settings = get_raw_stream_settings(tmp_path / "C1496-230405-173324")

    assert settings == dict(sampling_frequency=24414.0625, rig_name="RZ5P", stream_indices=[2])
