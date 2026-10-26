"""Compare the processed signals recomputed by hadjas_2025.processing with those of the lab's .mat files.

compare_session_processing recomputes the processed signals of each TDT block of a session from its raw Fi1r
stream and compares them with the segment of the lab's .mat file that holds the block (match_mat_segments), and can
plot the isosbestic fits and dF/F of each block (plot_session_comparison). compare_dataset_processing does this for
every session.
"""

from pathlib import Path
from typing import Union

import h5py
import numpy as np
import pandas as pd

from hnasko_lab_to_nwb.hadjas_2025.convert_all_sessions import (
    get_session_nwbfile_name,
    get_session_to_nwb_kwargs_per_session,
)
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
# Blocks whose isosbestic fit the lab adjusted by hand, by .mat file name, subject and segment, with what was
# changed. Their dF/F is not expected to match.
LAB_ADJUSTED_FITS = {
    ("STN_Vglut2_SNc_ConFonGCaMP_DAsubtypes_VG2xDA_varFreqs_DurBlocks_5mW_Demod.mat", "C2454", "s1s"): (
        "three parts of the recording fitted and scaled separately"
    ),
    ("STN_2_SN_StrSites_GRAB_varFreqs_DurBlocks_5mW_Demod.mat", "C3021", "s250ms"): (
        "fitted from the start of the recording"
    ),
    ("PPN_Vglut2_SNr_GABA_GCaMP_varFreqs_DurBlocks_ALL_5mW_Demod.mat", "C4560", "AllDurs"): (
        "last 15 s left out of the fit (fiber unplugged)"
    ),
    ("PPN_2_SN_StrSites_GRAB_varFreqs_DurBlocks_5mW_Demod.mat", "C4615", "s4s"): "first 1.2 s left out of the fit",
    ("STN_Vglut2-phiC_SNc_Anxa1_DLSterms_varFreqs_DurBlocks_5mW_Demod.mat", "C6900", "s250ms"): (
        "first 0.08 s left out of the fit"
    ),
    ("PPN_Vglut2-phiC_SNc_Anxa1_DLSterms_varFreqs_DurBlocks_5mW_Demod.mat", "C7248", "s4s"): (
        "first 20 s left out of the fit"
    ),
    ("STN_2_SN_varFreq_250ms_1s_Demod.mat", "B7532", "s250ms5mW"): (
        "two parts of the recording fitted separately and joined"
    ),
}
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
    "lab_adjusted_fit",
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


def plot_session_comparison(blocks: list[dict], title: str, file_path: Path) -> None:
    """Plot, for each block of a session, the lab's and the recomputed isosbestic fits and dF/F.

    Needs matplotlib (the "analysis" extra).

    Parameters
    ----------
    blocks : list[dict]
        One dict per block with "block", "segment", "lab_adjusted_fit" (or None), and the 100 Hz signals "af" (the
        isosbestic signal), "lab_af_fit" and "af_fit" (the lab's and the recomputed bi-exponential fits), "lab_dF"
        and "dF".
    title : str
        Title of the figure.
    file_path : Path
        The image file to write.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(len(blocks), 2, figsize=(15, 3.6 * len(blocks) + 0.6), squeeze=False)
    for row, block in enumerate(blocks):
        minutes = np.arange(1, len(block["af"]) + 1) / 100.0 / 60
        number_of_samples = min(len(block["dF"]), len(block["lab_dF"]))
        difference = np.max(np.abs(block["dF"][:number_of_samples] - block["lab_dF"][:number_of_samples]))
        label = f"{block['block']} ({block['segment']})"
        if block["lab_adjusted_fit"]:
            label += f", lab fit adjusted by hand: {block['lab_adjusted_fit']}"

        ax = axes[row, 0]
        ax.plot(minutes, 1000 * block["af"], color="0.75", lw=0.5, label="405 nm signal")
        ax.plot(
            minutes[: len(block["lab_af_fit"])],
            1000 * block["lab_af_fit"],
            color="tab:blue",
            lw=2,
            label="lab fit (MATLAB)",
        )
        ax.plot(minutes, 1000 * block["af_fit"], color="tab:orange", lw=1.5, ls="--", label="recomputed fit (Python)")
        low, high = np.percentile(1000 * block["af"], [0.5, 99.5])
        ax.set_ylim(low - 0.2 * (high - low), high + 0.2 * (high - low))
        ax.set(title=f"{label}\nbi-exponential fit of the 405 nm signal", xlabel="time (min)", ylabel="405 nm (mV)")
        ax.legend(fontsize=8, loc="upper right")

        ax = axes[row, 1]
        ax.plot(minutes[: len(block["lab_dF"])], block["lab_dF"], color="tab:blue", lw=0.8, label="lab dF/F")
        ax.plot(minutes, block["dF"], color="tab:orange", lw=0.8, alpha=0.8, label="recomputed dF/F")
        low, high = np.percentile(block["lab_dF"], [0.5, 99.5])
        ax.set_ylim(low - 0.5 * (high - low), high + 0.5 * (high - low))
        ax.set(title=f"dF/F, largest difference {difference:.3g} %", xlabel="time (min)", ylabel="dF/F (%)")
        ax.legend(fontsize=8, loc="upper right")
    figure.suptitle(title)
    figure.tight_layout()
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(file_path, dpi=80)
    plt.close(figure)


def compare_session_processing(
    subject_metadata: dict,
    protocol_folder_path: Union[str, Path],
    recording_type: str,
    stimulus_location: str,
    protocol: str,
    plot_file_path: Path | None = None,
) -> list[dict]:
    """Recompute the processed signals of each block of a session and compare them with the lab's .mat file.

    The parameters are those of session_to_nwb, and the image file of the plot.

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
    plot_file_path : Path, optional
        If given, plot the isosbestic fits and dF/F of each block to this image file (plot_session_comparison).

    Returns
    -------
    list[dict]
        One comparison (compare_signals) per block and stream, with keys "block", "segment", "stream" and
        "lab_adjusted_fit" (what the lab adjusted by hand in the isosbestic fit of the block, LAB_ADJUSTED_FITS, or
        None).
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
        mat_input_folder=cohort_config.get("mat_input_folder"),
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
    plotted_blocks = []
    for folder_path, segment in zip(tdt_folder_paths, segments):
        raw_signal, sampling_frequency = read_raw_signal(folder_path)
        processed = process_raw_signal(raw_signal, sampling_frequency, **led_modulation)
        lab_adjusted_fit = LAB_ADJUSTED_FITS.get((mat_file_path.name, mat_subject_id, segment))
        lab = {
            stream_name: read_lab_segment(mat_file_path, stream_name, target_area, mat_subject_id, segment)
            for stream_name in PROCESSED_STREAM_NAMES
        }
        for stream_name in PROCESSED_STREAM_NAMES:
            comparison = compare_signals(recomputed=processed[stream_name], lab=lab[stream_name])
            rows.append(
                dict(
                    block=folder_path.name,
                    segment=segment,
                    stream=stream_name,
                    lab_adjusted_fit=lab_adjusted_fit,
                    **comparison,
                )
            )
        if plot_file_path is not None:
            plotted_blocks.append(
                dict(
                    block=folder_path.name,
                    segment=segment,
                    lab_adjusted_fit=lab_adjusted_fit,
                    af=processed["af"],
                    af_fit=processed["af_fit"],
                    lab_af_fit=read_lab_segment(mat_file_path, "FP/af_fit", target_area, mat_subject_id, segment),
                    dF=processed["dF"],
                    lab_dF=lab["dF"],
                )
            )
    if plot_file_path is not None:
        title = f"{subject_id}, {recording_type}, {stimulus_location}, {protocol}: lab (MATLAB) and recomputed (Python)"
        plot_session_comparison(blocks=plotted_blocks, title=title, file_path=plot_file_path)
    return rows


def compare_dataset_processing(
    *,
    data_dir_path: Union[str, Path],
    subjects_metadata_file_path: Union[str, Path],
    subject_ids: list[str] | None = None,
    plot_dir_path: Union[str, Path, None] = None,
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
    plot_dir_path : Union[str, Path, None], optional
        If given, write one plot per session to this folder, named as the session's NWB file with a .png suffix
        (default is None, no plots).

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
        plot_file_path = None
        if plot_dir_path is not None:
            plot_file_name = get_session_nwbfile_name(session_to_nwb_kwargs).replace(".nwb", ".png")
            plot_file_path = Path(plot_dir_path) / plot_file_name
        try:
            for comparison in compare_session_processing(**session_to_nwb_kwargs, plot_file_path=plot_file_path):
                rows.append(dict(session, **comparison))
        except Exception as error:
            rows.append(dict(session, error=str(error)))
        finally:
            clear_tdt_block_cache()
    return pd.DataFrame(rows, columns=PROCESSING_COMPARISON_COLUMNS)
