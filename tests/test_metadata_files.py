from pathlib import Path

import pytest

from neuroconv.utils import load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parents[1] / "src" / "hnasko_lab_to_nwb" / "hadjas_2025" / "metadata"


def find_none_strings(value, path=""):
    """Return the paths of string values "None" in a nested metadata structure."""
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in find_none_strings(item, f"{path}/{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in find_none_strings(item, f"{path}/{index}")]
    return [path] if value == "None" else []


@pytest.mark.parametrize("file_path", sorted(METADATA_FOLDER_PATH.glob("*.yaml")), ids=lambda path: path.name)
def test_metadata_has_no_none_strings(file_path):
    assert find_none_strings(load_dict_from_file(file_path)) == []
