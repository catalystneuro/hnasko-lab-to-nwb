"""Compare the processed signals recomputed by hadjas_2025.processing with those of the lab's .mat files.

compare_session_processing recomputes the processed signals of each TDT block of a session from its raw Fi1r
stream and compares them with the segment of the lab's .mat file that holds the block (match_mat_segments).
compare_dataset_processing does this for every session.
"""

from pathlib import Path
from typing import Union

import h5py
import numpy as np
import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import get_session_to_nwb_kwargs_per_session
from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    find_mat_file_path,
    find_tdt_folder_paths,
    get_led_modulation,
    get_raw_stream_settings,
    get_session_start_time,
    get_target_area_for_subject,
    load_session_config,
    match_mat_segments,
)
from hnasko_lab_to_nwb.hadjas_2025.processing import process_raw_signal
from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import (
    clear_tdt_block_cache,
    read_tdt_start_timestamp,
    read_tdt_stream,
)

PROCESSED_STREAM_NAMES = ("Gc_raw", "af_raw", "Gc", "af", "dF")
PROCESSING_COMPARISON_COLUMNS = [
    "subject_id",
    "protocol",
    "protocol_folder_path",
    "block",
    "segment",
    "stream",
    "recomputed_samples",
    "lab_samples",
    "correlation",
    "mean_difference",
    "max_absolute_difference",
    "lab_standard_deviation",
    "error",
]


def read_raw_signal(folder_path: Path) -> tuple[np.ndarray, float]:
    """Read the raw photodetector signal of a TDT block, from the Fi1r channel of its rig.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.

    Returns
    -------
    tuple[np.ndarray, float]
        The signal, shape (number of samples,), and its sampling frequency in Hz.
    """
    raw_stream_settings = get_raw_stream_settings(folder_path)
    data = np.asarray(read_tdt_stream(folder_path, "Fi1r").data)
    if data.ndim == 2:
        data = data[raw_stream_settings["stream_indices"][0]]
    return data, raw_stream_settings["sampling_frequency"]


def read_lab_segment(mat_file_path: Path, stream_name: str, target_area: str, mat_subject_id: str, segment: str):
    """Read one segment of one stream of the lab's .mat file, as a 1D array.

    Parameters
    ----------
    mat_file_path : Path
        The lab's .mat file.
    stream_name : str
        The processed stream, e.g. "Gc_raw" or "dF".
    target_area : str
        The target area group of the subject.
    mat_subject_id : str
        The subject group, as written in the .mat file.
    segment : str
        The segment of the subject group, e.g. "s1s".

    Returns
    -------
    np.ndarray
        The segment, shape (number of samples,).
    """
    with h5py.File(mat_file_path, "r") as f:
        # segments are (1, number of samples), or (number of samples, 1) in some files
        return np.asarray(f[stream_name][target_area][mat_subject_id][segment]).ravel()


def compare_signals(recomputed: np.ndarray, lab: np.ndarray) -> dict:
    """Compare a recomputed signal with the lab's signal over their common samples.

    Parameters
    ----------
    recomputed : np.ndarray
        The recomputed signal.
    lab : np.ndarray
        The lab's signal.

    Returns
    -------
    dict
        The number of samples of each signal, and over the common samples the correlation, the mean of the
        difference (recomputed minus lab), the maximum absolute difference and the standard deviation of the lab's
        signal.
    """
    number_of_samples = min(len(recomputed), len(lab))
    difference = recomputed[:number_of_samples] - lab[:number_of_samples]
    return dict(
        recomputed_samples=len(recomputed),
        lab_samples=len(lab),
        correlation=np.corrcoef(recomputed[:number_of_samples], lab[:number_of_samples])[0, 1],
        mean_difference=np.mean(difference),
        max_absolute_difference=np.max(np.abs(difference)),
        lab_standard_deviation=np.std(lab[:number_of_samples]),
    )


def compare_session_processing(
    subject_metadata: dict,
    protocol_folder_path: Union[str, Path],
    recording_type: str,
    stimulus_location: str,
    protocol: str,
) -> list[dict]:
    """Recompute the processed signals of each block of a session and compare them with the lab's .mat file.

    The parameters are those of session_to_nwb.

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

    Returns
    -------
    list[dict]
        One comparison (compare_signals) per block and stream, with keys "block", "segment" and "stream".
    """
    session_config = load_session_config()
    cohort_config = session_config["cohorts"][recording_type]
    subject_id = subject_metadata["Animal ID"]
    subject_config = session_config["subjects"].get(subject_id, {})
    epoc_names = list(session_config["protocols"][protocol]["epoc_name_to_frequency_in_hz"])
    protocol_folder_path = Path(protocol_folder_path)

    tdt_folder_paths = find_tdt_folder_paths(protocol_folder_path=protocol_folder_path, subject_id=subject_id)
    mat_file_path = find_mat_file_path(
        protocol_folder_path=protocol_folder_path,
        cohort_data_folder=cohort_config["data_folder"],
        mat_cohort_folder=subject_config.get("mat_cohort_folder", cohort_config["data_folder"]),
    )
    target_area, mat_subject_id = get_target_area_for_subject(mat_file_path, subject_id)
    segments = match_mat_segments(
        mat_file_path=mat_file_path,
        target_area=target_area,
        mat_subject_id=mat_subject_id,
        folder_paths=tdt_folder_paths,
        epoc_names=epoc_names,
    )
    led_modulation = get_led_modulation(get_session_start_time(read_tdt_start_timestamp(tdt_folder_paths[0])))

    rows = []
    for folder_path, segment in zip(tdt_folder_paths, segments):
        raw_signal, sampling_frequency = read_raw_signal(folder_path)
        processed = process_raw_signal(raw_signal, sampling_frequency, **led_modulation)
        for stream_name in PROCESSED_STREAM_NAMES:
            lab = read_lab_segment(mat_file_path, stream_name, target_area, mat_subject_id, segment)
            comparison = compare_signals(recomputed=processed[stream_name], lab=lab)
            rows.append(dict(block=folder_path.name, segment=segment, stream=stream_name, **comparison))
    return rows


def compare_dataset_processing(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    subject_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Compare the recomputed and lab processed signals of every session.

    A session whose comparison fails (e.g. no .mat file) gets one row with the error in "error".

    Parameters
    ----------
    data_dir_path : Union[str, Path]
        The path to the directory containing the raw data.
    subjects_metadata_file_path : Union[str, Path]
        The path to the overview Excel file with subject metadata.
    subject_ids : list[str], optional
        Compare only the sessions of these subjects (default is None, which compares all sessions).

    Returns
    -------
    pd.DataFrame
        One row per block and stream, with the columns of PROCESSING_COMPARISON_COLUMNS.
    """
    rows = []
    for session_to_nwb_kwargs in get_session_to_nwb_kwargs_per_session(
        data_dir_path=data_dir_path, subjects_metadata_file_path=subjects_metadata_file_path
    ):
        subject_id = session_to_nwb_kwargs["subject_metadata"]["Animal ID"]
        if subject_ids is not None and subject_id not in subject_ids:
            continue
        session = dict(
            subject_id=subject_id,
            protocol=session_to_nwb_kwargs["protocol"],
            protocol_folder_path=str(session_to_nwb_kwargs["protocol_folder_path"]),
        )
        try:
            for comparison in compare_session_processing(**session_to_nwb_kwargs):
                rows.append(dict(session, **comparison))
        except Exception as error:
            rows.append(dict(session, error=str(error)))
        finally:
            clear_tdt_block_cache()
    return pd.DataFrame(rows, columns=PROCESSING_COMPARISON_COLUMNS)
