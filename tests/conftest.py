from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import load_cohort_metadata
from hnasko_lab_to_nwb.hadjas_2025.interfaces import concatenated_tdt_fp_interface
from hnasko_lab_to_nwb.hadjas_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)

SEGMENT_STARTING_TIMES = [0.0, 10.0, 20.0]


@pytest.fixture
def anxa1_metadata() -> dict:
    return load_cohort_metadata("Cell_type recordings_Anxa1")


@pytest.fixture
def write_processed_mat_file():
    """Return a function that writes a .mat (HDF5) file with the layout of the lab's processed files."""

    def write(file_path: Path, stream_name: str, target_area: str, subject_id: str, segments: dict) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(file_path, "w") as file:
            subject_group = file.create_group(f"{stream_name}/{target_area}/{subject_id}")
            for segment_name, data in segments.items():
                subject_group.create_dataset(segment_name, data=np.asarray(data)[np.newaxis, :])
        return file_path

    return write


@pytest.fixture
def make_concatenated_tdt_interface(monkeypatch):
    """Return a function that builds a ConcatenatedTDTFiberPhotometryInterface over three fake blocks.

    Each block has a float32 Fi1r stream of num_samples ones; the blocks start at SEGMENT_STARTING_TIMES.
    """

    def make(num_samples: int, sampling_frequency: float = 100.0) -> ConcatenatedTDTFiberPhotometryInterface:
        folder_paths = [Path(f"varFreq_{duration}") / "C0001-240101-120000" for duration in ("250ms", "1s", "4s")]
        stream = SimpleNamespace(data=np.ones(num_samples, dtype="float32"), fs=sampling_frequency)
        monkeypatch.setattr(concatenated_tdt_fp_interface, "read_tdt_stream", lambda folder_path, store: stream)
        interface = ConcatenatedTDTFiberPhotometryInterface.__new__(ConcatenatedTDTFiberPhotometryInterface)
        interface._folder_paths = folder_paths
        interface.segment_starting_times = SEGMENT_STARTING_TIMES
        interface.stream_name = "Fi1r"
        interface.metadata_key = "Fi1r_SNc"
        interface.stream_indices = None
        return interface

    return make
