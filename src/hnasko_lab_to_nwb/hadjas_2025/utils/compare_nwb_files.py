"""Compare the contents of NWB files written by two conversions.

Compares groups, datasets and attributes at the HDF5 level: names, neurodata types, dtypes, shapes and values.
Object references are compared by the path of the object they point to. Values that differ between any two
conversions by construction (object ids, file creation date, identifier, cached namespaces) are skipped.

Usage::

    python -m hnasko_lab_to_nwb.hadjas_2025.utils.compare_nwb_files <before> <after>

where <before> and <after> are two NWB files, or two folders whose NWB files are paired by file name.
"""

import sys
from pathlib import Path

import h5py
import numpy as np

IGNORED_PATHS = ("/file_create_date", "/identifier", "/specifications")
IGNORED_ATTRIBUTES = ("object_id", ".specloc")


def _is_ignored(path: str) -> bool:
    return any(path == ignored or path.startswith(f"{ignored}/") for ignored in IGNORED_PATHS)


def _normalize(value, file: h5py.File):
    """Turn a dataset or attribute value into a comparable numpy array or Python object."""
    if isinstance(value, h5py.Reference):
        return file[value].name if value else None
    if isinstance(value, bytes):
        return value.decode()
    if not isinstance(value, np.ndarray):
        return value
    if value.dtype.names is not None:
        return [tuple(_normalize(item, file) for item in row) for row in value.tolist()]
    if value.dtype.kind == "O":
        return np.array([_normalize(item, file) for item in value.flat], dtype=object).reshape(value.shape)
    if value.dtype.kind == "S":
        return value.astype(str)
    return value


def _values_differ(value_a, value_b) -> str | None:
    """Return a description of how two normalized values differ, or None if they are equal."""
    if isinstance(value_a, np.ndarray) and isinstance(value_b, np.ndarray):
        if value_a.shape != value_b.shape:
            return f"shape {value_a.shape} != {value_b.shape}"
        if value_a.dtype.kind in "fc" and value_b.dtype.kind in "fc":
            if np.array_equal(value_a, value_b, equal_nan=True):
                return None
            difference = np.nanmax(np.abs(value_a.astype("float64") - value_b.astype("float64")))
            return f"values differ (max absolute difference {difference:g})"
        if np.array_equal(value_a, value_b):
            return None
        return "values differ"
    if isinstance(value_a, np.ndarray) or isinstance(value_b, np.ndarray):
        value_a, value_b = np.asarray(value_a).tolist(), np.asarray(value_b).tolist()
    if value_a == value_b:
        return None
    return f"{value_a!r} != {value_b!r}"


def _collect(file: h5py.File) -> dict[str, h5py.Group | h5py.Dataset]:
    objects = {"/": file}

    def visit(name, item):
        path = f"/{name}"
        if not _is_ignored(path):
            objects[path] = item

    file.visititems(visit)
    return objects


def compare_nwb_files(file_path_a: Path, file_path_b: Path) -> list[str]:
    """Compare two NWB files and return one line per difference.

    Parameters
    ----------
    file_path_a : Path
        The first NWB file (e.g. from the conversion before a change).
    file_path_b : Path
        The second NWB file (e.g. from the conversion after a change).

    Returns
    -------
    list[str]
        The differences found; empty if the files have the same content.
    """
    differences = []
    with h5py.File(file_path_a, "r") as file_a, h5py.File(file_path_b, "r") as file_b:
        objects_a, objects_b = _collect(file_a), _collect(file_b)
        for path in sorted(objects_a.keys() - objects_b.keys()):
            differences.append(f"only in first: {path}")
        for path in sorted(objects_b.keys() - objects_a.keys()):
            differences.append(f"only in second: {path}")
        for path in sorted(objects_a.keys() & objects_b.keys()):
            object_a, object_b = objects_a[path], objects_b[path]
            if type(object_a) is not type(object_b):
                differences.append(f"{path}: group in one file, dataset in the other")
                continue
            attribute_names = (set(object_a.attrs) | set(object_b.attrs)) - set(IGNORED_ATTRIBUTES)
            for attribute_name in sorted(attribute_names):
                if attribute_name not in object_a.attrs or attribute_name not in object_b.attrs:
                    side = "first" if attribute_name in object_a.attrs else "second"
                    differences.append(f"{path}: attribute {attribute_name} only in {side}")
                    continue
                difference = _values_differ(
                    _normalize(object_a.attrs[attribute_name], file_a),
                    _normalize(object_b.attrs[attribute_name], file_b),
                )
                if difference is not None:
                    differences.append(f"{path}: attribute {attribute_name}: {difference}")
            if isinstance(object_a, h5py.Dataset):
                if object_a.dtype != object_b.dtype:
                    differences.append(f"{path}: dtype {object_a.dtype} != {object_b.dtype}")
                difference = _values_differ(_normalize(object_a[()], file_a), _normalize(object_b[()], file_b))
                if difference is not None:
                    differences.append(f"{path}: {difference}")
    return differences


def main(path_a: str, path_b: str) -> None:
    path_a, path_b = Path(path_a), Path(path_b)
    if path_a.is_dir():
        file_names = sorted({path.name for path in path_a.glob("*.nwb")} | {path.name for path in path_b.glob("*.nwb")})
        pairs = [(path_a / name, path_b / name) for name in file_names]
    else:
        pairs = [(path_a, path_b)]
    for file_path_a, file_path_b in pairs:
        print(f"== {file_path_a.name}")
        if not file_path_a.exists() or not file_path_b.exists():
            print(f"  missing: {file_path_a if not file_path_a.exists() else file_path_b}")
            continue
        differences = compare_nwb_files(file_path_a, file_path_b)
        for difference in differences:
            print(f"  {difference}")
        if not differences:
            print("  no differences")


if __name__ == "__main__":
    main(*sys.argv[1:3])
