"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from datetime import date, datetime
from pathlib import Path
from typing import Union
from zoneinfo import ZoneInfo

import numpy as np

from hnasko_lab_to_nwb.hadjas_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.hadjas_2025.nwbconverter import Hadjas2025NWBConverter
from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import (
    clear_tdt_block_cache,
    read_tdt_epocs,
    read_tdt_start_timestamp,
    read_tdt_stream,
)
from hnasko_lab_to_nwb.hadjas_2025.utils.train_durations import label_train_duration
from neuroconv.utils import dict_deep_update, load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parent / "metadata"
SHARED_METADATA_FILE_NAMES = ("general_metadata.yaml", "subject_metadata.yaml", "devices_metadata.yaml")
SESSION_CONFIG_FILE_PATH = METADATA_FOLDER_PATH / "session_config.yaml"
RIG_DEVICES_METADATA_FILE_PATH = METADATA_FOLDER_PATH / "rig_devices_metadata.yaml"


def load_session_config() -> dict:
    """Load the settings that differ between cohorts, protocols and subjects (metadata/session_config.yaml)."""
    return load_dict_from_file(SESSION_CONFIG_FILE_PATH)


def get_rig_settings(sampling_frequency: float) -> dict:
    """Identify the recording rig from the sampling frequency of the raw Fi1r stream.

    Parameters
    ----------
    sampling_frequency : float
        Sampling frequency of the Fi1r stream of a TDT block, in Hz.

    Returns
    -------
    dict
        The rig name ("rig_name") and the Fi1r channels holding the signal ("stream_indices", None for all).
    """
    for rig_name, rig_config in load_session_config()["rigs"].items():
        if abs(rig_config["fi1r_sampling_frequency"] - sampling_frequency) < 1.0:
            channel = rig_config["fi1r_signal_channel"]
            return dict(rig_name=rig_name, stream_indices=None if channel is None else [channel])
    raise ValueError(f"No rig in the session config records Fi1r at {sampling_frequency} Hz.")


def get_raw_stream_settings(folder_path: Path) -> dict:
    """Read the Fi1r sampling frequency of a TDT block and return it with the settings of its rig.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.

    Returns
    -------
    dict
        "sampling_frequency" (Hz) of Fi1r, plus "rig_name" and "stream_indices" from get_rig_settings.
    """
    sampling_frequency = float(read_tdt_stream(Path(folder_path), "Fi1r").fs)
    return dict(sampling_frequency=sampling_frequency, **get_rig_settings(sampling_frequency))


def load_cohort_metadata(recording_type: str) -> dict:
    """Load the metadata shared by all cohorts, updated with the metadata file of one cohort.

    Parameters
    ----------
    recording_type : str
        Type of recording (e.g., "SN pan GABA recordings", "Cell_type recordings_Anxa1").

    Returns
    -------
    dict
        The merged metadata.
    """
    metadata = dict()
    for file_name in SHARED_METADATA_FILE_NAMES:
        metadata = dict_deep_update(metadata, load_dict_from_file(METADATA_FOLDER_PATH / file_name))
    cohort_file_path = METADATA_FOLDER_PATH / f"{recording_type.replace(' ', '_')}_metadata.yaml"
    return dict_deep_update(metadata, load_dict_from_file(cohort_file_path))


def load_rig_devices_metadata(rig_name: str) -> dict:
    """Load the devices of one recording rig (metadata/rig_devices_metadata.yaml), which update the shared devices.

    Parameters
    ----------
    rig_name : str
        Rig name from get_rig_settings (e.g. "RZ5P", "RZ10x").

    Returns
    -------
    dict
        The rig's "DeviceModels" (and "Devices") entries.
    """
    return load_dict_from_file(RIG_DEVICES_METADATA_FILE_PATH)[rig_name]


def get_target_area_for_subject(file_path: Path, subject_id: str) -> tuple[str, str]:
    """Find the target area group of a subject in a lab .mat file, matching the subject ID case-insensitively.

    Parameters
    ----------
    file_path : Path
        Path to the .mat file.
    subject_id : str
        The subject ID of the overview sheet.

    Returns
    -------
    tuple[str, str]
        The target area group and the subject group name as written in the .mat file (e.g. "c4708").
    """
    import h5py

    with h5py.File(file_path, "r") as f:
        signal_group = f["Gc_raw"]  # the same groups are in every stream
        for target_area, target_area_group in signal_group.items():
            for mat_subject_id in target_area_group.keys():
                if mat_subject_id.lower() == subject_id.lower():
                    return target_area, mat_subject_id
    raise ValueError(f"Subject {subject_id} not found in {file_path}.")


def find_tdt_folder_paths(protocol_folder_path: Path, subject_id: str) -> list[Path]:
    """Find the TDT blocks of a subject in a protocol folder, in chronological order.

    Blocks are named {subject_id}-{yymmdd}-{HHMMSS}, with the subject ID in either case, and are in the
    protocol folder or in its varFreq_* subfolders. A block folder holding another block raises.

    Parameters
    ----------
    protocol_folder_path : Path
        The protocol folder.
    subject_id : str
        The subject ID of the overview sheet.

    Returns
    -------
    list[Path]
        The block folders, sorted by recording date and time.
    """
    candidate_folder_paths = list(protocol_folder_path.iterdir())
    candidate_folder_paths += list(protocol_folder_path.glob("varFreq_*/*"))
    tdt_folder_paths = [
        folder_path
        for folder_path in candidate_folder_paths
        if folder_path.is_dir() and folder_path.name.lower().startswith(f"{subject_id.lower()}-")
    ]
    if len(tdt_folder_paths) == 0:
        raise FileNotFoundError(f"No TDT block for {subject_id} in {protocol_folder_path}")
    for folder_path in tdt_folder_paths:
        nested_tsq_file_paths = list(folder_path.glob("*/*.tsq"))
        if nested_tsq_file_paths:
            raise ValueError(
                f"TDT block {folder_path} holds another block, {nested_tsq_file_paths[0].parent.name}. "
                "Move nested blocks out of block folders before converting."
            )
    return sorted(tdt_folder_paths, key=lambda folder_path: folder_path.name.split("-", 1)[1])


def normalize_hemisphere(hemisphere) -> str:
    """Return "Left" or "Right" for a hemisphere value of the overview sheet ("Left", "L", "Right", "R").

    Parameters
    ----------
    hemisphere
        The Hemisphere cell of the overview sheet.

    Returns
    -------
    str
        "Left" or "Right".
    """
    hemisphere_values = dict(left="Left", l="Left", right="Right", r="Right")
    if not isinstance(hemisphere, str) or hemisphere.strip().lower() not in hemisphere_values:
        raise ValueError(f"Unknown hemisphere {hemisphere!r} in the overview sheet.")
    return hemisphere_values[hemisphere.strip().lower()]


def update_coordinates_for_left_hemisphere(metadata: dict) -> dict:
    """
    Update medio-lateral coordinates and hemisphere references in metadata dictionary.

    This function converts all positive ML (medio-lateral) coordinates to negative values
    and updates hemisphere references from "right" to the specified hemisphere (default "left").

    Parameters
    ----------
    metadata : dict
        The metadata dictionary to update (typically loaded from YAML file)

    Returns
    -------
    dict
        The updated metadata dictionary with modified coordinates and hemisphere references
    """
    import copy

    # Create a deep copy to avoid modifying the original
    updated_metadata = copy.deepcopy(metadata)

    def update_value(value):
        """Recursively update values in nested structures."""
        if isinstance(value, dict):
            # Check for hemisphere field
            if "hemisphere" in value and isinstance(value["hemisphere"], str):
                if value["hemisphere"].lower() == "right":
                    value["hemisphere"] = "left"

            # Check for ML coordinate fields and convert positive to negative
            ml_fields = ["insertion_position_ml_in_mm", "ml_in_mm"]
            for field in ml_fields:
                if field in value and isinstance(value[field], (int, float)):
                    if value[field] > 0:
                        value[field] = -value[field]

            # Recursively process nested dictionaries
            for key, nested_value in value.items():
                value[key] = update_value(nested_value)

        elif isinstance(value, list):
            # Recursively process list items
            return [update_value(item) for item in value]

        return value

    # Update the metadata in place
    update_value(updated_metadata)
    return updated_metadata


def read_trains(folder_path: Path, epoc_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Read the onsets and offsets of the stimulation trains of a TDT block that have an offset.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.
    epoc_names : list[str]
        Names of the stimulation epocs of the protocol.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Onsets and offsets of the trains, in seconds from the block start.
    """
    epocs = read_tdt_epocs(Path(folder_path))
    names = [name for name in epoc_names if name in epocs]
    onsets = np.concatenate([np.asarray(epocs[name]["onset"]) for name in names] or [np.array([])])
    offsets = np.concatenate([np.asarray(epocs[name]["offset"]) for name in names] or [np.array([])])
    has_offset = np.isfinite(offsets)
    if not has_offset.any():
        raise ValueError(f"No stimulation epocs {epoc_names} with an offset in {folder_path}.")
    return onsets[has_offset], offsets[has_offset]


def get_train_duration_label(folder_path: Path, epoc_names: list[str]) -> str:
    """Label a TDT block by the duration of its stimulation trains, read from the epocs (e.g. "250ms").

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.
    epoc_names : list[str]
        Names of the stimulation epocs of the protocol.

    Returns
    -------
    str
        The label of the median train duration of the block.
    """
    onsets, offsets = read_trains(folder_path, epoc_names)
    median_duration = float(np.median(offsets - onsets))
    label = label_train_duration(median_duration)
    if label is None:
        raise ValueError(f"Train duration {median_duration} s of {folder_path} is not one of the protocol's.")
    return label


def get_train_duration_trials(folder_path: Path, epoc_names: list[str]) -> list[dict]:
    """Get one trial per train duration of a block that holds the train durations one after the other.

    This is the varying-frequencies protocol recorded in a single block (SN pan GABA PPN). Each trial spans the
    trains of one duration, from the onset of the first to the offset of the last. Trains of zero length are left
    out, as in the optogenetic epochs.

    Parameters
    ----------
    folder_path : Path
        Path to the TDT block folder.
    epoc_names : list[str]
        Names of the stimulation epocs of the protocol.

    Returns
    -------
    list[dict]
        add_trial arguments (start_time, stop_time, tags), in time order.
    """
    onsets, offsets = read_trains(folder_path, epoc_names)
    has_length = offsets > onsets
    onsets, offsets = onsets[has_length], offsets[has_length]
    labels = np.array([label_train_duration(duration) for duration in offsets - onsets])
    trials = []
    for label in set(labels):
        if label is None:
            raise ValueError(f"A train of {folder_path} has a duration that is not one of the protocol's.")
        trials.append(
            dict(
                start_time=float(onsets[labels == label].min()),
                stop_time=float(offsets[labels == label].max()),
                tags=str(label),
            )
        )
    trials = sorted(trials, key=lambda trial: trial["start_time"])
    for trial, next_trial in zip(trials, trials[1:]):
        if trial["stop_time"] > next_trial["start_time"]:
            raise ValueError(f"Trains of different durations alternate in {folder_path}.")
    return trials


def get_block_trials(
    folder_paths: list[Path], segment_starting_times: list[float], epoc_names: list[str]
) -> list[dict]:
    """Get one trial per TDT block of a session of several blocks, tagged with the block's train duration.

    Parameters
    ----------
    folder_paths : list[Path]
        The TDT blocks of the session, in chronological order.
    segment_starting_times : list[float]
        Start of each block, in seconds from the start of the first block.
    epoc_names : list[str]
        Names of the stimulation epocs of the protocol.

    Returns
    -------
    list[dict]
        add_trial arguments (start_time, stop_time, tags) from the first to the last Fi1r sample of each block;
        empty for a session of one block.
    """
    if len(folder_paths) == 1:
        return []
    block_trials = []
    for folder_path, start_time in zip(folder_paths, segment_starting_times):
        stream = read_tdt_stream(Path(folder_path), "Fi1r")
        number_of_samples = np.asarray(stream.data).shape[-1]
        block_trials.append(
            dict(
                start_time=start_time,
                stop_time=start_time + (number_of_samples - 1) / stream.fs,
                tags=get_train_duration_label(folder_path, epoc_names),
            )
        )
    return block_trials


def match_mat_segments(
    mat_file_path: Path, target_area: str, mat_subject_id: str, folder_paths: list[Path], *, epoc_names: list[str]
) -> list[str]:
    """Find the segment of the lab's .mat file that holds each TDT block, by number of samples.

    Each segment of the demodulated raw-rate signal (Gc_raw) has as many samples as the Fi1r stream of its block.
    Segment names follow the lab's folder names, which are wrong for some blocks (e.g. the swapped varFreq_250ms
    and varFreq_4s folders of C4604 and C8972), so they are not used. A segment whose length differs from that of
    every block is from another recording (e.g. the SN pan DA PPN varying-durations segments, computed from blocks of
    2024-03-05 that are not in the data share), so it is never used. When several segments have the length of a
    block (e.g. s250ms and s1s of C0926), the one named after the block's recorded train duration (s<label>, from
    get_train_duration_label) is used.

    Parameters
    ----------
    mat_file_path : Path
        The lab's .mat file.
    target_area : str
        The target area group of the subject.
    mat_subject_id : str
        The subject group, as written in the .mat file.
    folder_paths : list[Path]
        The TDT blocks of the session.
    epoc_names : list[str]
        Names of the stimulation epocs of the protocol, to read the train duration of a block whose length matches
        several segments.

    Returns
    -------
    list[str]
        One segment name per block.
    """
    import h5py

    with h5py.File(mat_file_path, "r") as f:
        subject_group = f["Gc_raw"][target_area][mat_subject_id]
        # segments are (1, number of samples), or (number of samples, 1) in some files
        segment_name_to_length = {name: max(subject_group[name].shape) for name in subject_group}
    segment_names = []
    for folder_path in folder_paths:
        number_of_samples = np.asarray(read_tdt_stream(Path(folder_path), "Fi1r").data).shape[-1]
        matches = [name for name, length in segment_name_to_length.items() if length == number_of_samples]
        if len(matches) > 1:
            label = get_train_duration_label(folder_path=folder_path, epoc_names=epoc_names)
            matches = [name for name in matches if name == f"s{label}"]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one segment of {mat_subject_id} in {mat_file_path.name} with {number_of_samples} samples "
                f"for {folder_path.name}; segment lengths are {segment_name_to_length}."
            )
        segment_names.append(matches[0])
    return segment_names


def get_recording_site(recording_type: str, protocol_folder_path: Path) -> str | None:
    """Get the recording site of a Cell_type session from its subgroup folder ("Anxa1 DLS" gives "DLS").

    Parameters
    ----------
    recording_type : str
        Cohort key of the session config.
    protocol_folder_path : Path
        Protocol folder of the session.

    Returns
    -------
    str or None
        The recording site, or None for cohorts without subgroup folders.
    """
    cohort_config = load_session_config()["cohorts"][recording_type]
    if "subgroup_folder_prefix" not in cohort_config:
        return None
    return Path(protocol_folder_path).name.removeprefix(f"{cohort_config['subgroup_folder_prefix']} ")


def get_raw_series_site(subject_metadata: dict, recording_site: str | None) -> str:
    """Get the recording site that keys the raw series metadata (e.g. "Fi1r_DLS").

    Parameters
    ----------
    subject_metadata : dict
        Row of the overview sheet for the subject.
    recording_site : str or None
        The recording site from get_recording_site.

    Returns
    -------
    str
        The site of the Cell_type subgroup folder, or else the Recording Site of the overview sheet.
    """
    return recording_site if recording_site is not None else subject_metadata["Recording Site"]


def get_session_id(protocol: str, recording_type: str, recording_site: str | None) -> str:
    """Get the session ID: the protocol's, followed by the recording site for cohorts recorded at several sites.

    Parameters
    ----------
    protocol : str
        Protocol key of the session config.
    recording_type : str
        Cohort key of the session config.
    recording_site : str or None
        The recording site from get_recording_site.

    Returns
    -------
    str
        The session ID, e.g. "varying_durations" or "varying_durations_DLS".
    """
    session_config = load_session_config()
    session_id = session_config["protocols"][protocol]["session_id"]
    if session_config["cohorts"][recording_type].get("site_in_session_id", False):
        session_id = f"{session_id}_{recording_site}"
    return session_id


def get_session_description(protocol: str, epoc_names: list[str], number_of_blocks: int) -> str:
    """Get the session description of a protocol, which differs for 2022 blocks and for sessions of one block.

    Parameters
    ----------
    protocol : str
        Protocol key of the session config.
    epoc_names : list[str]
        Epoc names of the session's first block.
    number_of_blocks : int
        Number of TDT blocks of the session.

    Returns
    -------
    str
        The session_description_by_epoc of the first epoc in epoc_names that has one (blocks with the 2022 16 s
        trains, S6s_), else the session_description_single_block for a session of one block, else the
        session_description of the protocol.
    """
    protocol_config = load_session_config()["protocols"][protocol]
    for epoc_name, session_description in protocol_config.get("session_description_by_epoc", {}).items():
        if epoc_name in epoc_names:
            return session_description
    if number_of_blocks == 1 and "session_description_single_block" in protocol_config:
        return protocol_config["session_description_single_block"]
    return protocol_config["session_description"]


def find_mat_file_path(protocol_folder_path: Path, cohort_data_folder: str, mat_cohort_folder: str) -> Path:
    """Find the lab's processed .mat file of a protocol folder, possibly in another cohort's folder.

    Parameters
    ----------
    protocol_folder_path : Path
        Protocol folder of the session, <data folder>/<cohort data folder>/<input>/Fiber photometry_TDT/<protocol>,
        possibly followed by a subgroup folder (e.g. "Anxa1 DLS").
    cohort_data_folder : str
        Data folder of the session's cohort.
    mat_cohort_folder : str
        Data folder of the cohort whose protocol folder holds the .mat file (the session's own by default).

    Returns
    -------
    Path
        The only .mat file in the matching protocol folder.
    """
    parts = protocol_folder_path.parts
    cohort_index = len(parts) - 1 - parts[::-1].index(cohort_data_folder)
    data_dir_path = Path(*parts[:cohort_index])
    relative_protocol_folder_path = Path(*parts[cohort_index + 1 :])
    mat_folder_path = data_dir_path / mat_cohort_folder / relative_protocol_folder_path
    mat_file_paths = list(mat_folder_path.glob("*.mat"))
    if len(mat_file_paths) != 1:
        raise FileNotFoundError(f"Expected one .mat file in {mat_folder_path}, found {len(mat_file_paths)}.")
    return mat_file_paths[0]


def get_led_modulation(session_start_time: datetime) -> dict:
    """Get the modulation frequencies of the excitation LEDs of a session from its recording date.

    Parameters
    ----------
    session_start_time : datetime
        Start time of the session's first block, in the lab's time zone.

    Returns
    -------
    dict
        "calcium_signal_in_hz" (465 nm LED) and "isosbestic_control_in_hz", from the last led_modulation entry of
        the session config whose first_recording_date is on or before the recording date.
    """
    recording_date = session_start_time.date()
    entries = [
        entry
        for entry in load_session_config()["led_modulation"]
        if date.fromisoformat(str(entry["first_recording_date"])) <= recording_date
    ]
    if len(entries) == 0:
        raise ValueError(f"No LED modulation in the session config for a recording on {recording_date}.")
    entry = max(entries, key=lambda entry: date.fromisoformat(str(entry["first_recording_date"])))
    return dict(
        calcium_signal_in_hz=entry["calcium_signal_in_hz"], isosbestic_control_in_hz=entry["isosbestic_control_in_hz"]
    )


def add_led_modulation_to_metadata(metadata: dict, led_modulation: dict) -> None:
    """State the LED modulation frequencies in the excitation sources and the demodulated series, in place.

    Parameters
    ----------
    metadata : dict
        The session metadata.
    led_modulation : dict
        The modulation frequencies from get_led_modulation.
    """
    signal_to_frequency = dict(
        calcium_signal=led_modulation["calcium_signal_in_hz"],
        isosbestic_control=led_modulation["isosbestic_control_in_hz"],
    )
    for signal, frequency in signal_to_frequency.items():
        excitation_source = metadata["Devices"][f"excitation_source_{signal}"]
        excitation_source["description"] = f"{excitation_source['description']} Modulated at {frequency:g} Hz."
    demodulated_series_prefix_to_signal = dict(Gc_raw_="calcium_signal", af_raw_="isosbestic_control")
    for key, series_metadata in metadata["FiberPhotometry"].items():
        for prefix, signal in demodulated_series_prefix_to_signal.items():
            if key.startswith(prefix):
                series_metadata["description"] = (
                    f"{series_metadata['description']} Demodulated at {signal_to_frequency[signal]:g} Hz, the "
                    "modulation frequency of its LED."
                )


def get_session_start_time(start_timestamp: float) -> datetime:
    """Return the start time of a TDT block in the lab's time zone (America/Los_Angeles).

    Parameters
    ----------
    start_timestamp : float
        POSIX timestamp of the block start, from read_tdt_start_timestamp. It does not depend on the time zone of
        the computer reading the block, unlike the start_date of tdt.read_block.

    Returns
    -------
    datetime
        The start time with its time zone.
    """
    return datetime.fromtimestamp(start_timestamp, tz=ZoneInfo("America/Los_Angeles"))


def filter_optogenetics_metadata(metadata: dict, stimulus_location: str) -> None:
    """Remove optogenetics entries for stimulus sites other than stimulus_location, in place.

    Parameters
    ----------
    metadata : dict
        The metadata dictionary with an "Optogenetics" section.
    stimulus_location : str
        Location of the stimulus (e.g., "PPN", "STN").
    """
    optogenetics = metadata["Optogenetics"]
    optogenetics["OptogeneticEffectors"] = {
        key: item for key, item in optogenetics["OptogeneticEffectors"].items() if stimulus_location in item["name"]
    }
    optogenetics["OptogeneticVirusInjections"] = {
        key: item
        for key, item in optogenetics["OptogeneticVirusInjections"].items()
        if stimulus_location in item["name"]
    }
    optogenetics["OptogeneticSitesTable"]["rows"] = {
        key: row
        for key, row in optogenetics["OptogeneticSitesTable"]["rows"].items()
        if stimulus_location in row["effector_metadata_key"]
    }


def session_to_nwb(
    output_dir_path: Union[str, Path],
    subject_metadata: dict,
    protocol_folder_path: Union[str, Path],
    recording_type: str,
    stimulus_location: str,
    protocol: str,
    data_streams: dict | None = None,
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
):
    """Convert one session (one protocol of one subject) to NWB.

    Parameters
    ----------
    output_dir_path : Union[str, Path]
        Path to the output directory where the NWB file will be saved.
    subject_metadata : dict
        Row of the overview sheet for the subject.
    protocol_folder_path : Union[str, Path]
        Path to the protocol folder containing the TDT blocks and the lab's processed .mat file.
    recording_type : str
        Cohort key of the session config (e.g., "SN pan GABA recordings", "Cell_type recordings_Anxa1").
    stimulus_location : str
        Location of the stimulus (e.g., "PPN", "STN").
    protocol : str
        Protocol key of the session config: "Varying durations" or "Varying frequencies".
    data_streams : dict, optional
        Data streams to write ("raw", "processed", "behavioral_video": True or False), updating the data_streams
        of the session config (default is None, which uses the session config).
    stub_test : bool, optional
        If True, convert only the first second of each block (default is False).
    overwrite : bool, optional
        If True, overwrite existing NWB file (default is False).
    verbose : bool, optional
        If True, print verbose output (default is False).

    Notes
    -----
    Varying-durations sessions have one TDT block in the protocol folder. Varying-frequencies sessions have one
    block per train duration in varFreq_* subfolders, written as one concatenated series, except SN pan GABA PPN,
    which has one block for all durations.
    """
    subject_id = subject_metadata["Animal ID"]

    session_config = load_session_config()
    protocol_config = session_config["protocols"][protocol]
    cohort_config = session_config["cohorts"][recording_type]
    subject_config = session_config["subjects"].get(subject_id, {})
    mat_cohort_folder = subject_config.get("mat_cohort_folder", cohort_config["data_folder"])
    data_streams = dict(session_config["data_streams"], **(data_streams or {}))
    unknown_data_streams = set(data_streams) - set(session_config["data_streams"])
    if unknown_data_streams:
        raise ValueError(f"Unknown data streams {sorted(unknown_data_streams)}.")
    protocol_folder_path = Path(protocol_folder_path)
    recording_site = get_recording_site(recording_type=recording_type, protocol_folder_path=protocol_folder_path)
    session_id = get_session_id(protocol=protocol, recording_type=recording_type, recording_site=recording_site)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    editable_metadata = load_cohort_metadata(recording_type)
    if normalize_hemisphere(subject_metadata["Hemisphere"]) == "Left":
        editable_metadata = update_coordinates_for_left_hemisphere(editable_metadata)

    tdt_folder_paths = find_tdt_folder_paths(protocol_folder_path=protocol_folder_path, subject_id=subject_id)

    raw_stream_settings = get_raw_stream_settings(tdt_folder_paths[0])
    editable_metadata = dict_deep_update(editable_metadata, load_rig_devices_metadata(raw_stream_settings["rig_name"]))
    raw_source_data = dict(
        folder_paths=tdt_folder_paths,
        stream_name="Fi1r",
        metadata_key=f"Fi1r_{get_raw_series_site(subject_metadata=subject_metadata, recording_site=recording_site)}",
        stream_indices=raw_stream_settings["stream_indices"],
    )
    session_start_time = get_session_start_time(read_tdt_start_timestamp(tdt_folder_paths[0]))
    segment_starting_times = ConcatenatedTDTFiberPhotometryInterface(**raw_source_data).segment_starting_times
    epoc_names = list(protocol_config["epoc_name_to_frequency_in_hz"])
    if protocol == "Varying frequencies" and len(tdt_folder_paths) == 1:
        # SN pan GABA PPN records the three train durations one after the other in one block
        block_trials = get_train_duration_trials(folder_path=tdt_folder_paths[0], epoc_names=epoc_names)
    else:
        block_trials = get_block_trials(
            folder_paths=tdt_folder_paths, segment_starting_times=segment_starting_times, epoc_names=epoc_names
        )

    source_data = dict()
    conversion_options = dict()

    # Raw fiber photometry
    if data_streams["raw"]:
        source_data.update(RawFiberPhotometry=raw_source_data)
        conversion_options.update(RawFiberPhotometry=dict(stub_test=stub_test))

    # Processed fiber photometry from the lab's .mat file
    if data_streams["processed"]:
        mat_file_path = find_mat_file_path(
            protocol_folder_path=protocol_folder_path,
            cohort_data_folder=cohort_config["data_folder"],
            mat_cohort_folder=mat_cohort_folder,
        )
        target_area, mat_subject_id = get_target_area_for_subject(mat_file_path, subject_id)
        mat_segment_names = match_mat_segments(
            mat_file_path=mat_file_path,
            target_area=target_area,
            mat_subject_id=mat_subject_id,
            folder_paths=tdt_folder_paths,
            epoc_names=epoc_names,
        )
        stream_to_interface_name = {
            "Gc_raw": "DemodulatedFiberPhotometry_Calcium",
            "af_raw": "DemodulatedFiberPhotometry_Isosbestic",
            "Gc": "DownsampledFiberPhotometry_Calcium",
            "af": "DownsampledFiberPhotometry_Isosbestic",
            "dF": "DeltaFOverF",
        }
        for stream_name, interface_name in stream_to_interface_name.items():
            source_data[interface_name] = dict(
                file_path=mat_file_path,
                subject_id=mat_subject_id,
                stream_name=stream_name,
                target_area=target_area,
                sampling_frequency=raw_stream_settings["sampling_frequency"] if "raw" in stream_name else 100.0,
            )
            conversion_options[interface_name] = dict(
                stub_test=stub_test,
                stimulus_channel_names=mat_segment_names,
                segment_starting_times=segment_starting_times,
            )

    # Behavioral video
    video_time_alignment_dict = None
    if data_streams["behavioral_video"] and stimulus_location in cohort_config.get("behavioral_video_inputs", []):
        from hnasko_lab_to_nwb.hadjas_2025.utils import get_video_aligned_starting_time

        video_time_alignment_dict = dict()
        video_folder_path = protocol_folder_path.parents[1] / "AnyMaze videos_mp4" / protocol
        video_metadata_file_path = video_folder_path / "video_metadata.xlsx"
        video_file_paths = list(video_folder_path.glob(f"{subject_id}*.mp4"))
        expected_number_of_videos = 1 if protocol == "Varying durations" else 3
        if len(video_file_paths) != expected_number_of_videos:
            raise FileNotFoundError(
                f"Expected {expected_number_of_videos} video files for subject {subject_id}, "
                f"found {len(video_file_paths)}."
            )
        for video_file_path in video_file_paths:
            if expected_number_of_videos == 1:
                interface_name, video_name = "Video", "BehavioralVideo"
            else:
                suffix = video_file_path.name.split("_")[-1].split(".")[0]  # train duration, e.g. "250ms"
                interface_name, video_name = f"Video_{suffix}", f"BehavioralVideo_{suffix}"
            source_data[interface_name] = dict(file_paths=[video_file_path], video_name=video_name)
            video_starting_time = get_video_aligned_starting_time(
                video_metadata_file_path=video_metadata_file_path,
                video_file_path=video_file_path,
                session_starting_time=session_start_time.replace(tzinfo=None),  # video metadata times are local
            )
            video_time_alignment_dict[interface_name] = dict(video_starting_time=video_starting_time)

    # Optogenetic stimulation
    source_data.update(OptogeneticStimulus=dict(folder_paths=tdt_folder_paths))
    conversion_options.update(
        OptogeneticStimulus=dict(tdt_stimulus_channel_to_frequency=protocol_config["epoc_name_to_frequency_in_hz"])
    )

    converter = Hadjas2025NWBConverter(
        source_data=source_data,
        verbose=verbose,
        video_time_alignment_dict=video_time_alignment_dict,
        block_trials=block_trials,
    )

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["sex"] = subject_metadata["Sex"]
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = get_session_description(
        protocol=protocol, epoc_names=list(read_tdt_epocs(tdt_folder_paths[0])), number_of_blocks=len(tdt_folder_paths)
    )
    if cohort_config.get("site_in_session_id", False):
        # Anxa1 mice have one session per recording site
        site_location = metadata["FiberPhotometry"]["FiberPhotometryTable"]["rows"][f"{recording_site}_465"]["location"]
        metadata["NWBFile"]["session_description"] += f" Fluorescence was recorded through the {site_location} fiber."
    metadata["NWBFile"]["session_start_time"] = session_start_time
    add_led_modulation_to_metadata(metadata=metadata, led_modulation=get_led_modulation(session_start_time))

    # Remove entries for other stimulus sites from metadata
    filter_optogenetics_metadata(metadata=metadata, stimulus_location=stimulus_location)

    try:
        converter.run_conversion(
            metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
        )
    finally:
        clear_tdt_block_cache()
    if verbose:
        print(f"Session {session_id} for subject {subject_id} converted successfully to NWB format at {nwbfile_path}")
