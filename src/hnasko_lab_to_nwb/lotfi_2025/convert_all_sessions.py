"""Primary script to run to convert all sessions in a dataset using session_to_nwb."""

import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Union

from tqdm import tqdm

from hnasko_lab_to_nwb.lotfi_2025.convert_session import session_to_nwb
from neuroconv.tools.path_expansion import LocalPathExpander


def dataset_to_nwb(
    *,
    data_dir_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    max_workers: int = 1,
    verbose: bool = True,
):
    """Convert the entire dataset to NWB.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    output_dir_path : Union[str, Path]
        The path to the directory where the NWB files will be saved.
    max_workers : int, optional
        The number of workers to use for parallel processing, by default 1
    verbose : bool, optional
        Whether to print verbose output, by default True
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=data_dir_path,
    )

    futures = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for session_to_nwb_kwargs in session_to_nwb_kwargs_per_session:
            session_to_nwb_kwargs["output_dir_path"] = output_dir_path
            session_to_nwb_kwargs["verbose"] = verbose

            # Create meaningful error file name based on session info
            subject_id = session_to_nwb_kwargs["subject_id"]
            protocol_type = session_to_nwb_kwargs["protocol_type"].replace(" ", "_").lower()
            exception_file_path = output_dir_path / f"ERROR_sub-{subject_id}_ses-{protocol_type}.txt"

            futures.append(
                executor.submit(
                    safe_session_to_nwb,
                    session_to_nwb_kwargs=session_to_nwb_kwargs,
                    exception_file_path=exception_file_path,
                )
            )
        for _ in tqdm(as_completed(futures), total=len(futures)):
            pass


def safe_session_to_nwb(*, session_to_nwb_kwargs: dict, exception_file_path: Union[Path, str]):
    """Convert a session to NWB while handling any errors by recording error messages to the exception_file_path.

    Parameters
    ----------
    session_to_nwb_kwargs : dict
        The arguments for session_to_nwb.
    exception_file_path : Path
        The path to the file where the exception messages will be saved.
    """
    exception_file_path = Path(exception_file_path)
    try:
        session_to_nwb(**session_to_nwb_kwargs)
    except Exception as e:
        with open(exception_file_path, mode="w") as f:
            f.write(f"session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
            f.write(traceback.format_exc())


def get_session_to_nwb_kwargs_per_session(
    *,
    data_dir_path: Union[str, Path],
):
    """Get the kwargs for session_to_nwb for each session in the dataset.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.

    Returns
    -------
    list[dict[str, Any]]
        A list of dictionaries containing the kwargs for session_to_nwb for each session.
    """
    data_dir_path = Path(data_dir_path)

    # Specify source data spec for path expansion (adapted from convert_session.py)
    source_data_spec = {
        "FiberPhotometry": {
            "base_directory": data_dir_path,
            "folder_path": "{ogen_stimulus_location}/Fiber photometry_TDT/{protocol_type}/{subject_id}-{session_starting_time_string}",
        }
    }

    # Instantiate LocalPathExpander and expand paths
    path_expander = LocalPathExpander()
    metadata_list = path_expander.expand_paths(source_data_spec)

    session_to_nwb_kwargs_per_session = []

    for metadata in metadata_list:
        # Extract metadata from path expansion
        protocol_type = metadata["metadata"]["extras"]["protocol_type"]
        session_starting_time_string = metadata["metadata"]["extras"]["session_starting_time_string"]
        session_starting_time = datetime.strptime(session_starting_time_string, "%y%m%d-%H%M%S")
        ogen_stimulus_location = metadata["metadata"]["extras"]["ogen_stimulus_location"]
        subject_id = metadata["metadata"]["Subject"]["subject_id"]

        # Build video file paths
        video_folder_path = (
            data_dir_path / ogen_stimulus_location / "AnyMaze videos_slk/converted_video" / protocol_type
        )
        video_metadata_file_path = video_folder_path / "video_metadata.xlsx"
        video_file_paths = list(video_folder_path.glob(f"{subject_id}*.mp4"))

        # Build kwargs dictionary for this session
        session_kwargs = {
            "session_starting_time": session_starting_time,
            "subject_id": subject_id,
            "protocol_type": protocol_type,
            "ogen_stimulus_location": ogen_stimulus_location,
            "tdt_folder_path": metadata["source_data"]["FiberPhotometry"]["folder_path"],
            "video_file_paths": video_file_paths,
            "video_metadata_file_path": video_metadata_file_path,
            "stub_test": False,
            "overwrite": True,
        }

        session_to_nwb_kwargs_per_session.append(session_kwargs)

    return session_to_nwb_kwargs_per_session


if __name__ == "__main__":

    # Parameters for conversion
    data_dir_path = Path("D:/Hnasko-CN-data-share/SN pan GABA recordings/")
    output_dir_path = Path("D:/hnasko_lab_conversion_nwb")
    max_workers = 1
    verbose = True

    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        max_workers=max_workers,
        verbose=verbose,
    )
