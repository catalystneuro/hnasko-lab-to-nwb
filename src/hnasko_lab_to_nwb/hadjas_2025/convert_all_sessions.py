"""Convert every session of the Hadjas 2025 dataset to NWB."""

import logging
from pathlib import Path
from typing import Union

import pandas as pd
from tqdm import tqdm

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    find_tdt_folder_paths,
    get_nwbfile_name,
    get_recording_site,
    get_session_id,
    load_session_config,
    session_to_nwb,
)
from hnasko_lab_to_nwb.hadjas_2025.inspection import (
    NWBFILE_SUMMARY_COLUMNS,
    summarize_nwbfile,
    update_conversion_summary,
)

logger = logging.getLogger(__name__)

INVENTORY_COLUMNS = [
    "recording_type",
    "subject_id",
    "stimulus_location",
    "protocol",
    "session_id",
    "nwbfile_name",
    "protocol_folder_path",
    "tdt_blocks",
]


def dataset_to_nwb(
    *,
    data_dir_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    overwrite: bool = False,
    verbose: bool = True,
) -> list[dict]:
    """Convert the entire dataset to NWB.

    Sessions are converted one by one; a session that fails is logged with its traceback and the conversion moves on.
    Sessions whose NWB file is already in the output folder are skipped, unless overwrite is True, so that new
    sessions can be added to the data folder and converted without converting the others again. The log is appended
    to convert_all_sessions.log in the output folder. Each converted file is inspected with NWB Inspector and its HERD
    references are counted; each converted or failed session updates the conversion summary (see the inspection
    module).

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    output_dir_path : Union[str, Path]
        The path to the directory where the NWB files will be saved.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.
    overwrite : bool, optional
        Whether to convert again the sessions whose NWB file exists, overwriting it, by default False
    verbose : bool, optional
        Whether to print verbose output, by default True

    Returns
    -------
    list[dict]
        The session_to_nwb kwargs of the sessions that failed.
    """
    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    if not data_dir_path.exists():
        raise FileNotFoundError(f"Data directory {data_dir_path} does not exist.")
    if not Path(subjects_metadata_file_path).exists():
        raise FileNotFoundError(f"Metadata file {subjects_metadata_file_path} does not exist.")
    output_dir_path.mkdir(parents=True, exist_ok=True)

    log_handler = logging.FileHandler(output_dir_path / "convert_all_sessions.log", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    try:
        session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(
            data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
        )
        logger.info(f"Found {len(session_to_nwb_kwargs_per_session)} sessions")
        failed_sessions = []
        for session_to_nwb_kwargs in tqdm(session_to_nwb_kwargs_per_session, desc="Converting sessions"):
            subject_id = session_to_nwb_kwargs["subject_metadata"]["Animal ID"]
            session_name = (
                f"{subject_id} {session_to_nwb_kwargs['protocol']} ({session_to_nwb_kwargs['protocol_folder_path']})"
            )
            nwbfile_name = get_session_nwbfile_name(session_to_nwb_kwargs)
            if not overwrite and (output_dir_path / nwbfile_name).exists():
                logger.info(f"Skipped {session_name}: {nwbfile_name} exists")
                continue
            summary_row = dict(
                nwbfile_name=nwbfile_name,
                subject_id=subject_id,
                protocol=session_to_nwb_kwargs["protocol"],
                protocol_folder_path=str(session_to_nwb_kwargs["protocol_folder_path"]),
                **dict.fromkeys(NWBFILE_SUMMARY_COLUMNS, ""),
            )
            try:
                session_to_nwb(
                    output_dir_path=output_dir_path, overwrite=overwrite, verbose=verbose, **session_to_nwb_kwargs
                )
                logger.info(f"Converted {session_name}")
                summary_row.update(status="converted", error="")
            except Exception as error:
                logger.exception(f"Failed {session_name}")
                failed_sessions.append(session_to_nwb_kwargs)
                summary_row.update(status="failed", error=f"{type(error).__name__}: {error}")
            if summary_row["status"] == "converted":
                try:
                    summary_row.update(summarize_nwbfile(output_dir_path / nwbfile_name))
                except Exception:
                    logger.exception(f"NWB Inspector failed on {nwbfile_name}")
            update_conversion_summary(output_dir_path=output_dir_path, rows=[summary_row])
        logger.info(f"{len(failed_sessions)} of {len(session_to_nwb_kwargs_per_session)} sessions failed")
    finally:
        logger.removeHandler(log_handler)
        log_handler.close()
    return failed_sessions


def has_tdt_blocks(protocol_folder_path: Path, subject_id: str) -> bool:
    """Whether a protocol folder holds TDT blocks of the subject (find_tdt_folder_paths finds at least one)."""
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
    Sessions whose protocol folder does not exist are logged as warnings.

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
    session_to_nwb_kwargs_per_session = []
    protocols = ["Varying durations", "Varying frequencies"]
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
            for protocol in protocols:
                protocol_folder_path = parent_protocol_folder_path / protocol
                if not protocol_folder_path.exists():
                    logger.warning(f"Subject {subject_metadata['Animal ID']}: no folder {protocol_folder_path}")
                    continue
                # Cell_type sessions are in one subgroup folder per recording site, "<prefix> <site>"; a session is
                # converted for each subgroup folder holding blocks of the subject, whatever site the sheet gives
                candidate_folder_paths = [protocol_folder_path]
                if "subgroup_folder_prefix" in cohort_config:
                    candidate_folder_paths = sorted(
                        protocol_folder_path.glob(f"{cohort_config['subgroup_folder_prefix']} *")
                    )
                protocol_folder_paths = [
                    folder_path
                    for folder_path in candidate_folder_paths
                    if has_tdt_blocks(folder_path, subject_metadata["Animal ID"])
                ]
                if not protocol_folder_paths:
                    logger.warning(f"Subject {subject_metadata['Animal ID']}: no TDT block in {protocol_folder_path}")
                for subject_protocol_folder_path in protocol_folder_paths:
                    session_to_nwb_kwargs_per_session.append(
                        {
                            "protocol": protocol,
                            "subject_metadata": subject_metadata,
                            "protocol_folder_path": subject_protocol_folder_path,
                            "recording_type": recording_type,
                            "stimulus_location": stimulus_location,
                        }
                    )

    return session_to_nwb_kwargs_per_session


def get_session_id_of_session(session_to_nwb_kwargs: dict) -> str:
    """Get the session ID that session_to_nwb gives a session, from its session_to_nwb kwargs."""
    recording_site = get_recording_site(
        recording_type=session_to_nwb_kwargs["recording_type"],
        protocol_folder_path=session_to_nwb_kwargs["protocol_folder_path"],
    )
    return get_session_id(
        protocol=session_to_nwb_kwargs["protocol"],
        recording_type=session_to_nwb_kwargs["recording_type"],
        recording_site=recording_site,
    )


def get_session_nwbfile_name(session_to_nwb_kwargs: dict) -> str:
    """Get the name of the NWB file that session_to_nwb writes for a session, from its session_to_nwb kwargs."""
    return get_nwbfile_name(
        subject_id=session_to_nwb_kwargs["subject_metadata"]["Animal ID"],
        session_id=get_session_id_of_session(session_to_nwb_kwargs),
    )


def get_session_inventory(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
) -> pd.DataFrame:
    """List the sessions of the dataset with their TDT blocks and the name of their NWB file.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.

    Returns
    -------
    pd.DataFrame
        One row per session of get_session_to_nwb_kwargs_per_session, with the columns of INVENTORY_COLUMNS.
        tdt_blocks lists the block folder names in recording order, separated by "; ".
    """
    rows = []
    for session_to_nwb_kwargs in get_session_to_nwb_kwargs_per_session(
        data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
    ):
        subject_id = session_to_nwb_kwargs["subject_metadata"]["Animal ID"]
        protocol_folder_path = session_to_nwb_kwargs["protocol_folder_path"]
        session_id = get_session_id_of_session(session_to_nwb_kwargs)
        tdt_folder_paths = find_tdt_folder_paths(protocol_folder_path=protocol_folder_path, subject_id=subject_id)
        rows.append(
            dict(
                recording_type=session_to_nwb_kwargs["recording_type"],
                subject_id=subject_id,
                stimulus_location=session_to_nwb_kwargs["stimulus_location"],
                protocol=session_to_nwb_kwargs["protocol"],
                session_id=session_id,
                nwbfile_name=get_nwbfile_name(subject_id=subject_id, session_id=session_id),
                protocol_folder_path=str(protocol_folder_path),
                tdt_blocks="; ".join(folder_path.name for folder_path in tdt_folder_paths),
            )
        )
    return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)


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
