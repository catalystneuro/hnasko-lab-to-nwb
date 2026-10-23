"""Upload converted NWB files to the draft of a dandiset on DANDI.

Uploading takes two steps, so that the organized files can be checked before anything is sent:

1. organize_nwbfiles copies the NWB files into a local dandiset folder, named and placed as DANDI expects
   (sub-<subject>/sub-<subject>_ses-<session>.nwb). The NWB files in the output folder are not changed.
2. upload_organized_files uploads the organized folder to the draft of the dandiset.

Both take the DANDI instance: "dandi" for the archive, "dandi-sandbox" for the sandbox.
"""

from pathlib import Path
from typing import Union

DANDI_INSTANCES = ("dandi", "dandi-sandbox")


def check_dandi_instance(dandi_instance: str) -> None:
    """Raise if dandi_instance is not one of DANDI_INSTANCES."""
    if dandi_instance not in DANDI_INSTANCES:
        raise ValueError(f"Unknown DANDI instance {dandi_instance!r}; use one of {DANDI_INSTANCES}.")


def organize_nwbfiles(
    *,
    nwb_folder_path: Union[str, Path],
    dandiset_folder_path: Union[str, Path],
    dandiset_id: str,
    dandi_instance: str,
) -> Path:
    """Copy the NWB files of a folder into a local dandiset folder, organized as DANDI expects.

    The dandiset metadata (dandiset.yaml, no assets) of the draft is downloaded to
    dandiset_folder_path / dandiset_id, then dandi organize copies the NWB files there. External video files are
    copied next to the NWB files that link them. File names always have the session
    (sub-<subject>_ses-<session>.nwb), also for a subject with one file in the folder.

    Parameters
    ----------
    nwb_folder_path : Union[str, Path]
        Folder of the NWB files to upload. It is not changed.
    dandiset_folder_path : Union[str, Path]
        Folder in which the dandiset folder is created.
    dandiset_id : str
        The dandiset, e.g. "001528".
    dandi_instance : str
        "dandi" or "dandi-sandbox".

    Returns
    -------
    Path
        The dandiset folder, dandiset_folder_path / dandiset_id.

    Raises
    ------
    FileExistsError
        If the dandiset folder already holds NWB files, from an earlier organize. Remove it first.
    """
    from dandi.consts import known_instances
    from dandi.download import download
    from dandi.organize import CopyMode, FileOperationMode, organize

    check_dandi_instance(dandi_instance)
    dandiset_folder_path = Path(dandiset_folder_path)
    dandiset_path = dandiset_folder_path / dandiset_id
    if any(dandiset_path.rglob("*.nwb")):
        raise FileExistsError(f"{dandiset_path} already holds organized NWB files. Remove it before organizing again.")
    dandiset_folder_path.mkdir(parents=True, exist_ok=True)
    dandiset_url = f"{known_instances[dandi_instance].gui}/dandiset/{dandiset_id}/draft"
    download(urls=dandiset_url, output_dir=str(dandiset_folder_path), get_metadata=True, get_assets=False)
    if not (dandiset_path / "dandiset.yaml").exists():
        raise FileNotFoundError(f"Downloading the metadata of {dandiset_url} did not create {dandiset_path}.")
    organize(
        paths=[str(nwb_folder_path)],
        dandiset_path=str(dandiset_path),
        update_external_file_paths=True,
        files_mode=FileOperationMode.COPY,
        media_files_mode=CopyMode.COPY,
        required_fields=["session_id"],  # dandi organize leaves out the session of a subject's only file otherwise
    )
    return dandiset_path


def upload_organized_files(*, dandiset_path: Union[str, Path], dandi_instance: str) -> None:
    """Upload an organized dandiset folder to the draft of its dandiset.

    Parameters
    ----------
    dandiset_path : Union[str, Path]
        The dandiset folder from organize_nwbfiles.
    dandi_instance : str
        "dandi" or "dandi-sandbox", as for organize_nwbfiles.
    """
    from dandi.upload import upload

    check_dandi_instance(dandi_instance)
    upload(paths=[str(dandiset_path)], dandi_instance=dandi_instance)
