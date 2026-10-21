"""Primary script to run to convert an entire session for of data using the NWBConverter."""

import io
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Union
from zoneinfo import ZoneInfo

from hnasko_lab_to_nwb.hadjas_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.hadjas_2025.nwbconverter import Hadjas2025NWBConverter
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
    import tdt

    with redirect_stdout(io.StringIO()):
        stream = tdt.read_block(str(folder_path), evtype=["streams"], store="Fi1r", t2=1.0).streams["Fi1r"]
    sampling_frequency = float(stream.fs)
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


def get_target_area_for_subject(file_path: Path, subject_id: str) -> str:
    """Extract available sites for a specific subject.

    Parameters
    ----------
    file_path : Path
        Path to the .mat file.
    subject_id : str
        The subject ID to extract sites for.

    Returns
    -------
    str
        The target area associated with the subject.
    """
    import h5py

    try:
        with h5py.File(file_path, "r") as f:
            signal_group = f["Gc_raw"]  # assuming the structure is the same for all streams
            for target_area in signal_group.keys():
                target_area_group: h5py.Group = signal_group[target_area]
                # Assuming one target area per subject
                if subject_id in target_area_group.keys():
                    return target_area
        raise ValueError(f"Subject ID {subject_id} not found in the .mat file.")
    except Exception as e:
        raise RuntimeError(f"Error extracting the target area for subject {subject_id}: {e}.")


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


def localize_session_start_time(session_start_datetime: datetime) -> datetime:
    """Attach the lab's time zone (America/Los_Angeles) to a session start time read from a TDT block folder name.

    Parameters
    ----------
    session_start_datetime : datetime
        Naive session start time, in the local time of the recording computer.

    Returns
    -------
    datetime
        The session start time with its time zone.
    """
    return session_start_datetime.replace(tzinfo=ZoneInfo("America/Los_Angeles"))


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
    if subject_id in ["C4708", "C4709", "C4977", "C4978", "C3015", "C3016", "C4379", "C5113"]:
        subject_id = subject_id.lower()

    session_config = load_session_config()
    protocol_config = session_config["protocols"][protocol]
    cohort_config = session_config["cohorts"][recording_type]
    session_id = protocol_config["session_id"]
    if subject_id in ["C5904", "C5966", "C5964", "C6609", "C6299", "C6612", "C6901", "C7241", "C7242"]:
        session_id = f"{session_id}_{subject_metadata['Recording Site']}"

    protocol_folder_path = Path(protocol_folder_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    editable_metadata = load_cohort_metadata(recording_type)
    if subject_metadata["Hemisphere"] == "Left":
        editable_metadata = update_coordinates_for_left_hemisphere(editable_metadata)

    # TDT blocks, in chronological order (folders are named {subject_id}-{yymmdd}-{HHMMSS})
    tdt_folder_paths = list(protocol_folder_path.glob(f"{subject_id}-*"))
    tdt_folder_paths += list(protocol_folder_path.glob(f"varFreq_*/{subject_id}-*"))
    if len(tdt_folder_paths) == 0:
        raise FileNotFoundError(f"No TDT block for {subject_id} in {protocol_folder_path}")
    tdt_folder_paths.sort(key=lambda folder_path: folder_path.name.split("-")[-2] + folder_path.name.split("-")[-1])

    # Segments of the lab's .mat file, one per block
    if protocol == "Varying durations":
        mat_segment_names = ["LP5mW"]
    elif len(tdt_folder_paths) == 1:
        mat_segment_names = ["AllDurs"]
    else:
        duration_mat_segment_names = ["s250ms", "s1s", "s4s"]
        if recording_type == "SN pan GABA recordings" and stimulus_location == "STN":
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

    mat_file_path = list(protocol_folder_path.glob("*.mat"))
    if len(mat_file_path) == 0:
        raise FileNotFoundError(f"No .mat files found in {protocol_folder_path}")
    elif len(mat_file_path) > 1:
        raise ValueError(f"Multiple .mat files found in {protocol_folder_path}")
    mat_file_path = mat_file_path[0]
    target_area = get_target_area_for_subject(mat_file_path, subject_id)
    raw_target_area = target_area
    if target_area in ("STN_to_Anxa1", "PPN_to_Anxa1"):
        raw_target_area = subject_metadata["Recording Site"]

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

    # Extract session starting time from TDT data
    # Assume that the tdt folders are named as {subject_id}-{session_starting_time_string}
    session_starting_time_string = tdt_folder_paths[0].name.replace(f"{subject_id}-", "")
    session_start_datetime = datetime.strptime(session_starting_time_string, "%y%m%d-%H%M%S")

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
            subject_id=subject_id,
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
                session_starting_time=session_start_datetime,
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
    metadata["NWBFile"]["session_start_time"] = localize_session_start_time(session_start_datetime)

    # Remove entries for other stimulus sites from metadata
    filter_optogenetics_metadata(metadata=metadata, stimulus_location=stimulus_location)

    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
    )
    if verbose:
        print(f"Session {session_id} for subject {subject_id} converted successfully to NWB format at {nwbfile_path}")
