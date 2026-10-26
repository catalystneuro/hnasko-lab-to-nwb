"""Check the data of the Hadjas 2025 sessions before converting them.

check_session runs the steps of session_to_nwb that read the TDT blocks, the overview sheet and the lab's .mat file,
and reports what would make the conversion fail or what the conversion handles in a way the lab should know about.
check_dataset does this for every session and also lists the TDT blocks that no session converts.
"""

import re
from pathlib import Path
from typing import Union

import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_to_nwb_kwargs_per_session
from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    find_mat_file_path,
    find_tdt_folder_paths,
    get_led_modulation,
    get_processed_source,
    get_raw_stream_settings,
    get_session_start_time,
    get_target_area_for_subject,
    get_train_duration_label,
    get_train_duration_trials,
    load_session_config,
    match_mat_segments,
    normalize_hemisphere,
    read_trains,
)
from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import clear_tdt_block_cache, read_tdt_start_timestamp

DATA_CHECK_COLUMNS = ["subject_id", "protocol", "protocol_folder_path", "severity", "check", "detail"]
TDT_BLOCK_FOLDER_NAME_PATTERN = re.compile(r"^[A-Za-z]\d+-\d{6}-\d{6}$")


def check_session(
    subject_metadata: dict,
    protocol_folder_path: Union[str, Path],
    recording_type: str,
    stimulus_location: str,
    protocol: str,
    data_streams: dict | None = None,
) -> list[dict]:
    """Check the data of one session before converting it.

    The parameters are those of session_to_nwb. Errors are problems that make session_to_nwb fail: an unknown
    hemisphere, a TDT block whose raw stream or stimulation trains cannot be read, a recording date without LED
    modulation frequencies, or, when the processed signals come from the lab's .mat file, a missing .mat file,
    subject or segment.
    Warnings are cases the conversion handles: a varFreq_* folder whose name disagrees with the recorded train
    duration (the conversion uses the recorded duration).

    Parameters
    ----------
    subject_metadata : dict
        Row of the overview sheet for the subject.
    protocol_folder_path : Union[str, Path]
        Protocol folder of the session.
    recording_type : str
        Cohort key of the session config.
    stimulus_location : str
        Location of the stimulus (e.g., "PPN", "STN").
    protocol : str
        Protocol key of the session config.
    data_streams : dict, optional
        Data streams to check, updating the data_streams of the session config (default is None, which uses the
        session config).

    Returns
    -------
    list[dict]
        One finding per problem, with keys "severity" ("error" or "warning"), "check" and "detail".
    """
    session_config = load_session_config()
    cohort_config = session_config["cohorts"][recording_type]
    data_streams = dict(session_config["data_streams"], **(data_streams or {}))
    epoc_names = list(session_config["protocols"][protocol]["epoc_name_to_frequency_in_hz"])
    subject_id = subject_metadata["Animal ID"]
    protocol_folder_path = Path(protocol_folder_path)
    findings = []

    def add_finding(severity: str, check: str, detail) -> None:
        findings.append(dict(severity=severity, check=check, detail=str(detail)))

    try:
        normalize_hemisphere(subject_metadata["Hemisphere"])
    except ValueError as error:
        add_finding("error", "hemisphere", error)

    tdt_folder_paths = find_tdt_folder_paths(protocol_folder_path=protocol_folder_path, subject_id=subject_id)
    try:
        for folder_path in tdt_folder_paths:
            try:
                get_raw_stream_settings(folder_path)
            except Exception as error:
                add_finding("error", "raw stream", f"{folder_path.name}: {error}")
            try:
                if protocol == "Varying frequencies" and len(tdt_folder_paths) == 1:
                    get_train_duration_trials(folder_path=folder_path, epoc_names=epoc_names)
                elif protocol == "Varying frequencies":
                    label = get_train_duration_label(folder_path=folder_path, epoc_names=epoc_names)
                    folder_name = folder_path.parent.name
                    if folder_name.startswith("varFreq_") and folder_name != f"varFreq_{label}":
                        add_finding(
                            "warning",
                            "train duration",
                            f"{folder_path.name} has {label} trains but is in {folder_name}; the conversion uses "
                            "the recorded duration",
                        )
                else:
                    read_trains(folder_path=folder_path, epoc_names=epoc_names)
            except Exception as error:
                add_finding("error", "stimulation trains", f"{folder_path.name}: {error}")

        try:
            get_led_modulation(get_session_start_time(read_tdt_start_timestamp(tdt_folder_paths[0])))
        except Exception as error:
            add_finding("error", "LED modulation", error)

        if get_processed_source(data_streams=data_streams, cohort_config=cohort_config) == "lab":
            subject_config = session_config["subjects"].get(subject_id, {})
            try:
                mat_file_path = find_mat_file_path(
                    protocol_folder_path=protocol_folder_path,
                    cohort_data_folder=cohort_config["data_folder"],
                    mat_cohort_folder=subject_config.get("mat_cohort_folder", cohort_config["data_folder"]),
                    mat_input_folder=cohort_config.get("mat_input_folder"),
                )
                target_area, mat_subject_id = get_target_area_for_subject(mat_file_path, subject_id)
                match_mat_segments(
                    mat_file_path=mat_file_path,
                    target_area=target_area,
                    mat_subject_id=mat_subject_id,
                    folder_paths=tdt_folder_paths,
                    epoc_names=epoc_names,
                )
            except Exception as error:
                add_finding("error", "processed data", error)
    finally:
        clear_tdt_block_cache()
    return findings


def find_unconverted_tdt_blocks(
    data_dir_path: Union[str, Path], session_to_nwb_kwargs_per_session: list[dict]
) -> list[Path]:
    """Find the TDT blocks of the protocol folders that no session converts.

    These are blocks of inputs or subjects that the session config or the overview sheet do not list yet, for
    example new recordings added to the data folder.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    session_to_nwb_kwargs_per_session : list[dict]
        The sessions, from get_session_to_nwb_kwargs_per_session.

    Returns
    -------
    list[Path]
        The block folders under <cohort folder>/<input>/Fiber photometry_TDT/<protocol> that are in no session, sorted.
    """
    converted_folder_paths = set()
    for session_to_nwb_kwargs in session_to_nwb_kwargs_per_session:
        converted_folder_paths.update(
            find_tdt_folder_paths(
                protocol_folder_path=session_to_nwb_kwargs["protocol_folder_path"],
                subject_id=session_to_nwb_kwargs["subject_metadata"]["Animal ID"],
            )
        )
    block_folder_paths = set()
    for protocol in load_session_config()["protocols"]:
        for protocol_folder_path in Path(data_dir_path).glob(f"*/*/Fiber photometry_TDT/{protocol}"):
            block_folder_paths.update(
                folder_path
                for folder_path in protocol_folder_path.rglob("*")
                if folder_path.is_dir() and TDT_BLOCK_FOLDER_NAME_PATTERN.match(folder_path.name)
            )
    return sorted(block_folder_paths - converted_folder_paths)


def check_dataset(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    data_streams: dict | None = None,
) -> pd.DataFrame:
    """Check the data of every session, and list the TDT blocks that no session converts.

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.
    data_streams : dict, optional
        Data streams to check, passed to check_session.

    Returns
    -------
    pd.DataFrame
        One row per finding, with the columns of DATA_CHECK_COLUMNS. A block that no session converts is a warning
        with check "unconverted block" and the block folder as protocol_folder_path.
    """
    session_to_nwb_kwargs_per_session = get_session_to_nwb_kwargs_per_session(
        data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
    )
    rows = []
    for session_to_nwb_kwargs in session_to_nwb_kwargs_per_session:
        session = dict(
            subject_id=session_to_nwb_kwargs["subject_metadata"]["Animal ID"],
            protocol=session_to_nwb_kwargs["protocol"],
            protocol_folder_path=str(session_to_nwb_kwargs["protocol_folder_path"]),
        )
        for finding in check_session(**session_to_nwb_kwargs, data_streams=data_streams):
            rows.append(dict(session, **finding))
    for folder_path in find_unconverted_tdt_blocks(data_dir_path, session_to_nwb_kwargs_per_session):
        rows.append(
            dict(
                subject_id=folder_path.name.split("-")[0],
                protocol=folder_path.parts[folder_path.parts.index("Fiber photometry_TDT") + 1],
                protocol_folder_path=str(folder_path),
                severity="warning",
                check="unconverted block",
                detail="no session of the overview sheet and session config converts this block",
            )
        )
    return pd.DataFrame(rows, columns=DATA_CHECK_COLUMNS)
