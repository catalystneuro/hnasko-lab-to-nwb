from pathlib import Path

import h5py
import numpy as np
import pytest

from neuroconv.utils import load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parents[1] / "src" / "hnasko_lab_to_nwb" / "hadjas_2025" / "metadata"


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
