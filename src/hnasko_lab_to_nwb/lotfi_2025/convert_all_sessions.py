"""Script to convert all Water Maze sessions to NWB format, following the structure of auditory_fear_conditioning/convert_all_sessions.py."""

import traceback
from pathlib import Path
from pprint import pformat
from typing import Union
from tqdm import tqdm
import natsort
import pandas as pd
import numpy as np

from hnasko_lab_to_nwb.lotfi_2025.convert_session import (
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
        session_to_nwb_kwargs["overwrite"] = overwrite
        session_to_nwb_kwargs["verbose"] = verbose

        # Create meaningful error file name using subject and session info
        subject_id = f"{session_to_nwb_kwargs['subject_metadata']['Animal ID']}"
        session_id = session_to_nwb_kwargs["session_id"]
        del session_to_nwb_kwargs["session_id"]

        exception_file_path = output_dir_path / f"ERROR_sub_{subject_id}-ses_{session_id}.txt"

        try:
            if session_id == "Varying durations":
                varying_durations_session_to_nwb(
                    **session_to_nwb_kwargs,
                )
            elif session_id == "Varying frequencies":
                varying_frequencies_session_to_nwb(
                    **session_to_nwb_kwargs,
                )
        except Exception as e:
            with open(
                exception_file_path,
                mode="w",
            ) as f:
                f.write(f"Varying frequencies session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
                f.write(traceback.format_exc())
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
    session_to_nwb_kwargs_per_session = []
    session_ids = ["Varying durations", "Varying frequencies"]
    excel_sheet_names = pd.ExcelFile(subjects_metadata_file_path).sheet_names
    for sheet_name in excel_sheet_names:
        with open(exception_file_path, mode="a") as f:
            f.write(f"Recording type: {sheet_name}\n")
        subjects_metadata = pd.read_excel(subjects_metadata_file_path, sheet_name=sheet_name).to_dict(orient="records")
        for subject_metadata in subjects_metadata:
            with open(exception_file_path, mode="a") as f:
                f.write(f"Subject {subject_metadata['Animal ID']}\n")
            stimulus_location = subject_metadata["Input"]
            parent_protocol_folder_path = data_dir_path / sheet_name / stimulus_location / "Fiber photometry_TDT"
            if not parent_protocol_folder_path.exists():
                # raise FileNotFoundError(f"Folder {cohort_folder_path} does not exist")
                with open(exception_file_path, mode="a") as f:
                    f.write(f"Folder {parent_protocol_folder_path} does not exist\n\n")
                continue
            for session_id in session_ids:
                protocol_folder_path = parent_protocol_folder_path / session_id
                if sheet_name == "Cell_type recordings":
                    genotype = subject_metadata["Genotype"]
                    if "Anxa1" in genotype:
                        genotype = "Anxa1"
                    if "VGlut2" in genotype:
                        genotype = "Vglut2"
                    recording_site = subject_metadata["Recording Site"]
                    protocol_folder_path = protocol_folder_path / f"{genotype} {recording_site}"
                    recording_type = f"{sheet_name}_{genotype}"
                else:
                    recording_type = sheet_name
                if not protocol_folder_path.exists():
                    # raise FileNotFoundError(f"Folder {video_folder_path} does not exist")
                    with open(exception_file_path, mode="a") as f:
                        f.write(f"Session {session_id}\n")
                        f.write(f"Folder {protocol_folder_path} does not exist\n\n")
                    continue

                session_to_nwb_kwargs_per_session.append(
                    {
                        "session_id": session_id,
                        "subject_metadata": subject_metadata,
                        "protocol_folder_path": protocol_folder_path,
                        "recording_type": recording_type,
                        "stimulus_location": stimulus_location,
                    }
                )

    return session_to_nwb_kwargs_per_session


if __name__ == "__main__":
    # Parameters for conversion
    data_dir_path = Path("D:/Hnasko-CN-data-share/")
    output_dir_path = Path("D:/hnasko_lab_conversion_nwb")
    subjects_metadata_file_path = data_dir_path / "ASAP FP Overview.xlsx"
    dataset_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        subjects_metadata_file_path=subjects_metadata_file_path,
        verbose=False,
        overwrite=False,
    )
