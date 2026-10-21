"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from datetime import datetime
from pathlib import Path
from typing import Union
from zoneinfo import ZoneInfo

from hnasko_lab_to_nwb.hadjas_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.hadjas_2025.nwbconverter import Hadjas2025NWBConverter
from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import (
    clear_tdt_block_cache,
    read_tdt_start_timestamp,
    read_tdt_stream,
)
from neuroconv.utils import dict_deep_update, load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parent / "metadata"
SHARED_METADATA_FILE_NAMES = ("general_metadata.yaml", "subject_metadata.yaml", "devices_metadata.yaml")
SESSION_CONFIG_FILE_PATH = METADATA_FOLDER_PATH / "session_config.yaml"


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

    # Segments of the lab's .mat file, one per block
    if protocol == "Varying durations":
        mat_segment_names = ["LP5mW"]
    elif len(tdt_folder_paths) == 1:
        mat_segment_names = ["AllDurs"]
    else:
        duration_mat_segment_names = ["s250ms", "s1s", "s4s"]
        if mat_cohort_folder == "SN pan GABA recordings" and stimulus_location == "STN":
            duration_mat_segment_names = ["s250ms5mW", "s1s10mW"]
        folder_name_to_index = dict(varFreq_250ms=0, varFreq_1s=1, varFreq_4s=2)
        mat_segment_names = []
        for folder_path in tdt_folder_paths:
            if folder_path.parent.name not in folder_name_to_index:
                raise ValueError(f"Unknown sub-session folder name: {folder_path.parent.name}")
            mat_segment_names.append(duration_mat_segment_names[folder_name_to_index[folder_path.parent.name]])
    if len(mat_segment_names) != len(tdt_folder_paths):
        raise ValueError(f"Expected {len(mat_segment_names)} TDT blocks in {protocol_folder_path}")

    raw_stream_settings = get_raw_stream_settings(tdt_folder_paths[0])
    # Gaps between blocks are NaN-padded on the 6 kHz rig only, as before
    fill_gaps = raw_stream_settings["rig_name"] == "RZ10x"

    mat_file_path = find_mat_file_path(
        protocol_folder_path=protocol_folder_path,
        cohort_data_folder=cohort_config["data_folder"],
        mat_cohort_folder=mat_cohort_folder,
    )
    target_area, mat_subject_id = get_target_area_for_subject(mat_file_path, subject_id)
    # The Anxa1 .mat files group subjects by stimulus site; their series are keyed by recording site
    raw_target_area = recording_site if target_area in ("STN_to_Anxa1", "PPN_to_Anxa1") else target_area

    source_data = dict()
    conversion_options = dict()

    # Raw fiber photometry
    raw_source_data = dict(
        folder_paths=tdt_folder_paths,
        stream_name="Fi1r",
        metadata_key=f"Fi1r_{raw_target_area}",
        stream_indices=raw_stream_settings["stream_indices"],
    )
    source_data.update(RawFiberPhotometry=raw_source_data)
    conversion_options.update(RawFiberPhotometry=dict(stub_test=stub_test, fill_gaps=fill_gaps))

    session_start_time = get_session_start_time(read_tdt_start_timestamp(tdt_folder_paths[0]))

    segment_starting_times = ConcatenatedTDTFiberPhotometryInterface(**raw_source_data).segment_starting_times

    # Processed fiber photometry from the lab's .mat file
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
            fill_gaps=fill_gaps,
        )

    # Behavioral video
    video_time_alignment_dict = None
    if stimulus_location in cohort_config.get("behavioral_video_inputs", []):
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
        source_data=source_data, verbose=verbose, video_time_alignment_dict=video_time_alignment_dict
    )

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["sex"] = subject_metadata["Sex"]
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = protocol_config["session_description"]
    metadata["NWBFile"]["session_start_time"] = session_start_time

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
