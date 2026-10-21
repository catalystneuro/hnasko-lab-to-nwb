from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)
from neuroconv.utils import load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parents[1] / "src" / "hnasko_lab_to_nwb" / "hadjas_2025" / "metadata"
SEGMENT_STARTING_TIMES = [0.0, 10.0, 20.0]


class FakeTDTInterface:
    """Stands in for a TDTFiberPhotometryInterface of one block with a float32 Fi1r stream."""

    def __init__(self, folder_path: Path, data: np.ndarray, sampling_frequency: float):
        self.source_data = dict(folder_path=folder_path)
        self._data = data
        self._sampling_frequency = sampling_frequency

    def _end_index(self, t2: float) -> int:
        return int(t2 * self._sampling_frequency) if t2 != 0.0 else len(self._data)

    def load(self, t1: float = 0.0, t2: float = 0.0, evtype: list[str] = ["all"], store: str | None = None):
        stream = SimpleNamespace(data=self._data[: self._end_index(t2)], fs=self._sampling_frequency)
        return SimpleNamespace(streams=dict(Fi1r=stream))


@pytest.fixture
def anxa1_metadata() -> dict:
    return load_dict_from_file(METADATA_FOLDER_PATH / "Cell_type_recordings_Anxa1_metadata.yaml")


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
def make_concatenated_tdt_interface():
    """Return a function that builds a ConcatenatedTDTFiberPhotometryInterface over three fake blocks."""

    def make(num_samples: int, sampling_frequency: float = 100.0) -> ConcatenatedTDTFiberPhotometryInterface:
        interface = ConcatenatedTDTFiberPhotometryInterface.__new__(ConcatenatedTDTFiberPhotometryInterface)
        interface._tdt_interfaces = [
            FakeTDTInterface(
                folder_path=Path(f"varFreq_{duration}") / "C0001-240101-120000",
                data=np.ones(num_samples, dtype="float32"),
                sampling_frequency=sampling_frequency,
            )
            for duration in ("250ms", "1s", "4s")
        ]
        interface.segment_starting_times = SEGMENT_STARTING_TIMES
        interface.stream_name = "Fi1r"
        interface.metadata_key = "Fi1r_SNc"
        interface.stream_indices = None
        return interface

    return make
