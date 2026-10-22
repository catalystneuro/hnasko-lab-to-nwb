from types import SimpleNamespace

import numpy as np
import pytest
from pynwb.testing.mock.file import mock_NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces import concatenated_tdt_fp_interface

# A 24 kHz block: Fi1r has three channels and only channel 2 holds the photodetector signal
THREE_CHANNEL_STREAM = SimpleNamespace(data=np.arange(3)[:, np.newaxis] * np.ones((3, 50), dtype="float32"), fs=100.0)


def test_concatenated_tdt_series_keeps_the_selected_channel(
    monkeypatch, anxa1_metadata, make_concatenated_tdt_interface
):
    interface = make_concatenated_tdt_interface(num_samples=50)
    monkeypatch.setattr(
        concatenated_tdt_fp_interface, "read_tdt_stream", lambda folder_path, store: THREE_CHANNEL_STREAM
    )
    interface.stream_indices = [2]
    nwbfile = mock_NWBFile()

    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=anxa1_metadata)

    series = nwbfile.acquisition["raw_signal_SNc"]
    assert len(series.data) == len(series.timestamps) == 3 * 50
    assert (np.asarray(series.data) == 2.0).all()


def test_concatenated_tdt_series_of_several_channels_raises(
    monkeypatch, anxa1_metadata, make_concatenated_tdt_interface
):
    interface = make_concatenated_tdt_interface(num_samples=50)
    monkeypatch.setattr(
        concatenated_tdt_fp_interface, "read_tdt_stream", lambda folder_path, store: THREE_CHANNEL_STREAM
    )

    with pytest.raises(ValueError, match="3 channels"):
        interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=anxa1_metadata)
