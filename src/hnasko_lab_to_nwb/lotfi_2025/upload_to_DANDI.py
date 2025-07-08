from pathlib import Path
from shutil import rmtree

from pydantic import DirectoryPath


def dandi_upload(
    nwb_folder_path: DirectoryPath,
    dandiset_folder_path: DirectoryPath,
    dandiset_id: str,
    version: str = "draft",
    files_mode: str = "copy",
    media_files_mode: str = "copy",
    cleanup: bool = True,
):
    """
    Upload NWB files to a Dandiset on the DANDI archive (https://dandiarchive.org/).

    This function automates the process of uploading NWB files to a DANDI archive. It performs the following steps:
    1. Downloads the specified Dandiset from the DANDI archive (metadata only, not assets).
    2. Organizes the provided NWB files into the downloaded Dandiset folder structure using DANDI's organize utility.
    3. Uploads the organized NWB files to the DANDI instance.
    4. Cleans up any temporary folders created during the process.

    Parameters
    ----------
    nwb_folder_path : DirectoryPath
        Path to the folder containing the NWB files to be uploaded.
    dandiset_folder_path : DirectoryPath
        Path to a folder where the Dandiset will be downloaded and organized. This folder will be created if it does not exist and will be deleted after upload.
    dandiset_id : str
        The identifier for the Dandiset to which the NWB files will be uploaded (e.g., "000199").
    version : str, optional
        The version of the Dandiset to download from the archive (default is "draft").
    files_mode : str, optional
        The file operation mode for organizing files: 'copy' or 'move' (default is 'copy').
    media_files_mode : str, optional
        The file operation mode for media files: 'copy' or 'move' (default is 'copy').
    cleanup : bool, optional
        Whether to clean up the temporary Dandiset folder and NWB folder after upload (default is True).

    Raises
    ------
    AssertionError
        If the Dandiset download or organization fails.
    Exception
        If the upload process encounters an error, it will be logged and the function will proceed to clean up temporary files.

    Notes
    -----
    - This function will delete both the dandiset_folder_path and nwb_folder_path after upload, so ensure these are temporary or backed up if needed.
    - Uses DANDI's Python API for download, organize, and upload operations.
    - Designed for use with the DANDI archive (https://dandiarchive.org/).
    """
    from dandi.download import download as dandi_download
    from dandi.organize import CopyMode, FileOperationMode
    from dandi.organize import organize as dandi_organize
    from dandi.upload import upload as dandi_upload

    # Map string to enum
    files_mode_enum = FileOperationMode.COPY if files_mode.lower() == "copy" else FileOperationMode.MOVE
    media_files_mode_enum = CopyMode.COPY if media_files_mode.lower() == "copy" else CopyMode.MOVE

    dandiset_folder_path = Path(dandiset_folder_path)
    dandiset_folder_path.mkdir(parents=True, exist_ok=True)

    dandiset_path = dandiset_folder_path / dandiset_id
    dandiset_url = f"https://dandiarchive.org/dandiset/{dandiset_id}/{version}"
    dandi_download(urls=dandiset_url, output_dir=str(dandiset_folder_path), get_metadata=True, get_assets=False)
    assert dandiset_path.exists(), "DANDI download failed!"

    dandi_organize(
        paths=str(nwb_folder_path),
        dandiset_path=str(dandiset_path),
        devel_debug=True,
        update_external_file_paths=True,
        files_mode=files_mode_enum,
        media_files_mode=media_files_mode_enum,
    )
    assert len(list(dandiset_path.iterdir())) > 1, "DANDI organize failed!"

    try:
        organized_nwbfiles = [str(x) for x in dandiset_path.rglob("*.nwb")]
        dandi_upload(
            paths=organized_nwbfiles,
            dandi_instance="dandi",
        )
    except Exception as e:
        print(f"Error during DANDI upload: {e}")

    finally:
        # Clean up the temporary DANDI folder
        if cleanup:
            rmtree(path=dandiset_folder_path)
            rmtree(path=nwb_folder_path)


if __name__ == "__main__":

    dandi_upload(
        nwb_folder_path=Path(r"D:\hnasko_lab_conversion_nwb"),  # Replace with actual path
        dandiset_folder_path=Path(r"D:\hnasko_lab_conversion_nwb"),  # Replace with actual path
        dandiset_id="001528",  # Replace with actual Dandiset ID
        version="draft",  # Replace with actual version if needed
        files_mode="move",  # or "copy"
        media_files_mode="copy",  # or "move"
        cleanup=False,  # Set to True if you want to clean up after upload
    )
