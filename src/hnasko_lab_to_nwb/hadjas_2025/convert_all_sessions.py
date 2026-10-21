"""Script to convert all Water Maze sessions to NWB format, following the structure of auditory_fear_conditioning/convert_all_sessions.py."""

import traceback
from pathlib import Path
from pprint import pformat
from typing import Union
from tqdm import tqdm
import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    find_tdt_folder_paths,
    load_session_config,
    session_to_nwb,
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
            session_to_nwb(protocol=session_id, **session_to_nwb_kwargs)
        except Exception:
            with open(
                exception_file_path,
                mode="w",
            ) as f:
                f.write(f"Varying frequencies session_to_nwb_kwargs: \n {pformat(session_to_nwb_kwargs)}\n\n")
                f.write(traceback.format_exc())
                f.write(traceback.format_exc())


def has_tdt_blocks(protocol_folder_path: Path, subject_id: str) -> bool:
    """Whether a protocol folder holds TDT blocks of the subject."""
    try:
        find_tdt_folder_paths(protocol_folder_path=protocol_folder_path, subject_id=subject_id)
    except FileNotFoundError:
        return False
    return True


def get_session_to_nwb_kwargs_per_session(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
):
    """Get the kwargs for session_to_nwb for each session in the dataset.

    Cohorts, their overview sheet, data folder and converted inputs come from metadata/session_config.yaml.
    Sessions whose protocol folder does not exist are listed in exceptions.txt in the data folder.

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
    """
    data_dir_path = Path(data_dir_path)
    subjects_metadata_file_path = Path(subjects_metadata_file_path)
    exception_file_path = data_dir_path / "exceptions.txt"
    session_to_nwb_kwargs_per_session = []
    session_ids = ["Varying durations", "Varying frequencies"]
    session_config = load_session_config()
    for recording_type, cohort_config in session_config["cohorts"].items():
        subjects_metadata = pd.read_excel(subjects_metadata_file_path, sheet_name=cohort_config["sheet_name"])
        if "genotype" in cohort_config:
            subjects_metadata = subjects_metadata[
                subjects_metadata["Genotype"].str.contains(cohort_config["genotype"], case=False)
            ]
        for subject_metadata in subjects_metadata.to_dict(orient="records"):
            stimulus_location = subject_metadata["Input"]
            if stimulus_location not in cohort_config["inputs"]:
                continue
            parent_protocol_folder_path = (
                data_dir_path / cohort_config["data_folder"] / stimulus_location / "Fiber photometry_TDT"
            )
            for session_id in session_ids:
                protocol_folder_path = parent_protocol_folder_path / session_id
                if not protocol_folder_path.exists():
                    with open(exception_file_path, mode="a") as f:
                        f.write(f"Subject {subject_metadata['Animal ID']}, session {session_id}\n")
                        f.write(f"Folder {protocol_folder_path} does not exist\n\n")
                    continue
                # Cell_type sessions are in one subgroup folder per recording site, "<prefix> <site>"; a session is
                # converted for each subgroup folder holding blocks of the subject, whatever site the sheet gives
                protocol_folder_paths = [protocol_folder_path]
                if "subgroup_folder_prefix" in cohort_config:
                    protocol_folder_paths = [
                        subgroup_folder_path
                        for subgroup_folder_path in sorted(
                            protocol_folder_path.glob(f"{cohort_config['subgroup_folder_prefix']} *")
                        )
                        if has_tdt_blocks(subgroup_folder_path, subject_metadata["Animal ID"])
                    ]
                for subject_protocol_folder_path in protocol_folder_paths:
                    session_to_nwb_kwargs_per_session.append(
                        {
                            "session_id": session_id,
                            "subject_metadata": subject_metadata,
                            "protocol_folder_path": subject_protocol_folder_path,
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
