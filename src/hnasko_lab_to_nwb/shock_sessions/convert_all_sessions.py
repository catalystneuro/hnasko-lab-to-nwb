"""Convert every shock session of the data folder to NWB."""

import logging
from pathlib import Path
from typing import Union

import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_session import find_tdt_folder_paths, get_nwbfile_name
from hnasko_lab_to_nwb.hadjas_2025.inspection import (
    NWBFILE_SUMMARY_COLUMNS,
    summarize_nwbfile,
    update_conversion_summary,
)
from hnasko_lab_to_nwb.shock_sessions.convert_session import load_session_config, session_to_nwb

logger = logging.getLogger(__name__)


def get_session_to_nwb_kwargs_per_session(
    *, data_dir_path: Union[str, Path], subjects_metadata_file_path: Union[str, Path]
) -> list[dict]:
    """Get the session_to_nwb kwargs of every shock session.

    The subjects are the rows of the overview sheet tab of the session config whose input is converted; each has one
    TDT block in <data folder>/<data_folder>/<input>/Fiber photometry_TDT/<protocol_folder>. Subjects without a
    block are logged as warnings.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.

    Returns
    -------
    list[dict]
        "subject_metadata" (the row of the overview sheet) and "tdt_folder_path" of each session.

    Raises
    ------
    ValueError
        If a subject has more than one block (the session ID would be the same for both files).
    """
    session_config = load_session_config()
    subjects_metadata = pd.read_excel(subjects_metadata_file_path, sheet_name=session_config["sheet_name"])
    session_to_nwb_kwargs_per_session = []
    for subject_metadata in subjects_metadata.to_dict(orient="records"):
        if subject_metadata["Input"] not in session_config["inputs"]:
            continue
        protocol_folder_path = (
            Path(data_dir_path)
            / session_config["data_folder"]
            / subject_metadata["Input"]
            / "Fiber photometry_TDT"
            / session_config["protocol_folder"]
        )
        try:
            tdt_folder_paths = find_tdt_folder_paths(
                protocol_folder_path=protocol_folder_path, subject_id=subject_metadata["Animal ID"]
            )
        except FileNotFoundError as error:
            logger.warning(f"Subject {subject_metadata['Animal ID']}: {error}")
            continue
        if len(tdt_folder_paths) > 1:
            raise ValueError(
                f"Subject {subject_metadata['Animal ID']} has {len(tdt_folder_paths)} shock blocks in "
                f"{protocol_folder_path}; expected one."
            )
        session_to_nwb_kwargs_per_session.append(
            dict(subject_metadata=subject_metadata, tdt_folder_path=tdt_folder_paths[0])
        )
    return session_to_nwb_kwargs_per_session


def dataset_to_nwb(
    *,
    data_dir_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    overwrite: bool = False,
    processed: bool = True,
) -> list[dict]:
    """Convert every shock session, skipping those whose NWB file exists.

    As for hadjas_2025, a session that fails is logged with its traceback and the conversion moves on. The log is
    appended to convert_all_sessions.log in the output folder; each converted file is inspected with NWB Inspector
    and each converted or failed session updates the conversion summary (hadjas_2025.inspection).

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    output_dir_path : Union[str, Path]
        The path to the directory where the NWB files will be saved.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.
    overwrite : bool, optional
        Whether to convert again the sessions whose NWB file exists, overwriting it, by default False.
    processed : bool, optional
        Whether to write the processed signals recomputed from the raw signal, by default True.

    Returns
    -------
    list[dict]
        The session_to_nwb kwargs of the sessions that failed.
    """
    output_dir_path = Path(output_dir_path)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    session_config = load_session_config()

    log_handler = logging.FileHandler(output_dir_path / "convert_all_sessions.log", encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)
    try:
        session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(
            data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
        )
        logger.info(f"Found {len(session_to_nwb_kwargs_per_session)} shock sessions")
        failed_sessions = []
        for session_to_nwb_kwargs in session_to_nwb_kwargs_per_session:
            subject_id = session_to_nwb_kwargs["subject_metadata"]["Animal ID"]
            nwbfile_name = get_nwbfile_name(subject_id=subject_id, session_id=session_config["session_id"])
            if not overwrite and (output_dir_path / nwbfile_name).exists():
                logger.info(f"Skipped {subject_id}: {nwbfile_name} exists")
                continue
            summary_row = dict(
                nwbfile_name=nwbfile_name,
                subject_id=subject_id,
                protocol=session_config["protocol_folder"],
                protocol_folder_path=str(session_to_nwb_kwargs["tdt_folder_path"].parent),
                **dict.fromkeys(NWBFILE_SUMMARY_COLUMNS, ""),
            )
            try:
                session_to_nwb(
                    output_dir_path=output_dir_path, overwrite=overwrite, processed=processed, **session_to_nwb_kwargs
                )
                logger.info(f"Converted {subject_id}")
                summary_row.update(status="converted", error="")
            except Exception as error:
                logger.exception(f"Failed {subject_id}")
                failed_sessions.append(session_to_nwb_kwargs)
                summary_row.update(status="failed", error=f"{type(error).__name__}: {error}")
            if summary_row["status"] == "converted":
                try:
                    summary_row.update(summarize_nwbfile(output_dir_path / nwbfile_name))
                except Exception:
                    logger.exception(f"NWB Inspector failed on {nwbfile_name}")
            update_conversion_summary(output_dir_path=output_dir_path, rows=[summary_row])
        logger.info(f"{len(failed_sessions)} of {len(session_to_nwb_kwargs_per_session)} shock sessions failed")
    finally:
        logger.removeHandler(log_handler)
        log_handler.close()
    return failed_sessions
