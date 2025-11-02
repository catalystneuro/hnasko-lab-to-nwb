"""Script to convert all Water Maze sessions to NWB format, following the structure of auditory_fear_conditioning/convert_all_sessions.py."""

import traceback
from pathlib import Path
from pprint import pformat
from typing import Union
from tqdm import tqdm
import natsort
import pandas as pd
import numpy as np

from src.hnasko_lab_to_nwb.lotfi_2025.convert_session import (
    varying_durations_session_to_nwb,
    varying_frequencies_session_to_nwb,
)


def dataset_to_nwb(
    *,
    data_dir_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    overwrite: bool = False,
    verbose: bool = True,
):
    """Convert the entire dataset to NWB.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    output_dir_path : Union[str, Path]
        The path to the directory where the NWB files will be saved.
    subjects_metadata_file_path : Union[str, Path], optional
        The path to the Excel file containing subject metadata, by default None
    overwrite : bool, optional
        Whether to overwrite existing NWB files, by default False
    verbose : bool, optional
        Whether to print verbose output, by default True
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    if not data_dir_path.exists():
        raise FileNotFoundError(f"Data directory {data_dir_path} does not exist.")
    if not Path(subjects_metadata_file_path).exists():
        raise FileNotFoundError(f"Metadata file {subjects_metadata_file_path} does not exist.")

    output_dir_path.mkdir(
        parents=True,
        exist_ok=True,
    )
    session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
    )
    if verbose:
        print(f"Found {len(session_to_nwb_kwargs_per_session)} sessions to convert")

    for session_to_nwb_kwargs in tqdm(session_to_nwb_kwargs_per_session, desc="Converting sessions"):
        session_to_nwb_kwargs["output_dir_path"] = output_dir_path

        # Create meaningful error file name using subject and session info
        subject_id = f"{session_to_nwb_kwargs['subject_metadata']['Animal ID']}"
        session_id = session_to_nwb_kwargs["session_id"]

        exception_file_path = output_dir_path / f"ERROR_sub_{subject_id}-ses_{session_id}.txt"

        try:
            varying_frequencies_session_to_nwb(
                **session_to_nwb_kwargs,
                protocol_folder_path=session_to_nwb_kwargs["parent_protocol_folder_path"] / "Varying frequencies",
            )
        except Exception as e:
            with open(
                exception_file_path,
                mode="w",
            ) as f:
                f.write(f"Varying frequencies session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
                f.write(traceback.format_exc())

        try:
            varying_durations_session_to_nwb(
                **session_to_nwb_kwargs,
                protocol_folder_path=session_to_nwb_kwargs["parent_protocol_folder_path"] / "Varying durations",
            )
        except Exception as e:
            with open(
                exception_file_path,
                mode="w",
            ) as f:
                f.write(f"Varying durations session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
                f.write(traceback.format_exc())


def get_session_to_nwb_kwargs_per_session(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
):
    """Get the kwargs for session_to_nwb for each session in the dataset.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    subjects_metadata_file_path : Union[str, Path]
        The path to the file containing subject metadata.

    Returns
    -------
    list[dict[str, Any]]
        A list of dictionaries containing the kwargs for session_to_nwb for each session.

    Raises
    ------
    FileNotFoundError
        If the data directory or metadata file does not exist.
    """

    data_dir_path = Path(data_dir_path)
    subjects_metadata_file_path = Path(subjects_metadata_file_path)
    exception_file_path = data_dir_path / f"exceptions.txt"

    excel_sheet_names = pd.ExcelFile(subjects_metadata_file_path).sheet_names
    subjects_metadata = pd.read_excel(subjects_metadata_file_path)

    session_to_nwb_kwargs_per_session = []

    for subject_metadata in subjects_metadata:
        subject_id = subject_metadata["Animal ID"]
        with open(exception_file_path, mode="a") as f:
            f.write(f"Subject {subject_id}\n")

        cohort_folder_path = Path(data_dir_path) / line / f"{cohort_id}_{task_acronym}"
        if not cohort_folder_path.exists():
            # raise FileNotFoundError(f"Folder {cohort_folder_path} does not exist")
            with open(exception_file_path, mode="a") as f:
                f.write(f"Folder {cohort_folder_path} does not exist\n\n")
            continue
        for session_id in session_ids:
            video_folder_path = cohort_folder_path / session_id
            if not video_folder_path.exists():
                # raise FileNotFoundError(f"Folder {video_folder_path} does not exist")
                with open(exception_file_path, mode="a") as f:
                    f.write(f"Session {session_id}\n")
                    f.write(f"Folder {video_folder_path} does not exist\n\n")
                continue
            video_file_paths = natsort.natsorted(video_folder_path.glob(f"*{subject_id}*.ffii"))
            if len(video_file_paths) == 0:
                with open(exception_file_path, mode="a") as f:
                    f.write(f"Session {session_id}\n")
                    f.write(
                        f"No .ffii files found for subject '{subject_id}' session '{session_id}' in '{cohort_folder_path}'."
                    )
                continue
            elif len(video_file_paths) > 1:
                with open(exception_file_path, mode="a") as f:
                    f.write(f"Session {session_id}\n")
                    f.write(
                        f"Multiple video files found for subject '{subject_id}' session '{session_id}' in '{cohort_folder_path}'."
                    )
                continue

            freeze_scores_file_paths = list(video_folder_path.glob(f"*{subject_metadata['line']}*.csv"))
            if len(freeze_scores_file_paths):
                freeze_scores_file_path = freeze_scores_file_paths[0]
            else:
                freeze_scores_file_path = None

            freeze_log_file_path = video_folder_path / "Freeze_Log.xls"
            if not freeze_log_file_path.exists():
                with open(exception_file_path, mode="a") as f:
                    f.write(f"Session {session_id}\n")
                    f.write(
                        f"Freeze log file not found for subject '{subject_id}' session '{session_id}' in '{cohort_folder_path}'."
                    )
                continue

            session_to_nwb_kwargs_per_session.append(
                {
                    "session_id": f"{task_acronym}_{session_id}",
                    "subject_metadata": subject_metadata,
                    "video_file_path": video_file_paths[0],
                    "freeze_log_file_path": freeze_log_file_path,
                    "freeze_scores_file_path": freeze_scores_file_path,
                }
            )

    return session_to_nwb_kwargs_per_session


if __name__ == "__main__":
    # Parameters for conversion
    data_dir_path = Path("E:/Kind-CN-data-share/behavioural_pipeline/Auditory Fear Conditioning")
    output_dir_path = Path("E:/kind_lab_conversion_nwb/behavioural_pipeline/auditory_fear_conditioning")
    subjects_metadata_file_path = Path("E:/Kind-CN-data-share/behavioural_pipeline/general_metadata.xlsx")
    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        subjects_metadata_file_path=subjects_metadata_file_path,
        verbose=False,
        overwrite=True,
    )
