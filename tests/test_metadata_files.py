from pathlib import Path

import pytest

from hnasko_lab_to_nwb.hadjas_2025.convert_session import load_cohort_metadata
from neuroconv.utils import load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parents[1] / "src" / "hnasko_lab_to_nwb" / "hadjas_2025" / "metadata"


def find_values(value, is_match, path=""):
    """Return the paths of values for which is_match is true in a nested metadata structure."""
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in find_values(item, is_match, f"{path}/{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in find_values(item, is_match, f"{path}/{index}")]
    return [path] if is_match(value) else []


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_metadata_has_no_none_strings(file_path):
    assert find_values(load_dict_from_file(file_path), lambda value: value == "None") == []


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_metadata_has_no_placeholders_or_empty_entries(file_path):
    # unknown optional fields are left out, not written as "<serial number of ...>" or as an empty key
    def is_placeholder(value):
        return isinstance(value, str) and value.startswith("<") and value.endswith(">")

    metadata = load_dict_from_file(file_path)
    assert find_values(metadata, is_placeholder) == []
    assert [path for path in find_values(metadata, lambda value: value is None) if "/rigs/" not in path] == []


def test_load_cohort_metadata_merges_shared_files_with_cohort_overrides():
    metadata = load_cohort_metadata("GRABDA recordings")

    assert metadata["NWBFile"]["lab"] == "Hnasko"
    assert metadata["Subject"]["species"] == "Mus musculus"
    assert metadata["Subject"]["genotype"] == "VGlut2-cre"
    isosbestic_model = metadata["DeviceModels"]["excitation_source_model_isosbestic"]
    assert isosbestic_model["manufacturer"] == "Tucker-Davis Technologies"
    assert isosbestic_model["wavelength_range_in_nm"] == [410.0, 420.0]
