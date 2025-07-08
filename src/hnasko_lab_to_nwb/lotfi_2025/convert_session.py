"""Primary script to run to convert an entire session for of data using the NWBConverter."""

import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Union

from hnasko_lab_to_nwb.lotfi_2025.nwbconverter import Lofti2025NWBConverter
from hnasko_lab_to_nwb.lotfi_2025.utils import get_video_aligned_starting_time
from neuroconv.utils import dict_deep_update, load_dict_from_file


def session_to_nwb(
    output_dir_path: Union[str, Path],
    session_starting_time: datetime,
    subject_id: str,
    tdt_folder_path: Union[str, Path],
    video_file_paths: List[Union[str, Path]],
    protocol_type: str,
    ogen_stimulus_location: str,
    video_metadata_file_path: None | Union[str, Path] = None,
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
):
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    session_id = protocol_type.replace(" ", "_").lower()
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    valid_protocols = {"Varying durations", "Varying frequencies", "Shocks"}
    if protocol_type not in valid_protocols:
        raise ValueError(f"Invalid protocol_type: {protocol_type}. Must be one of {valid_protocols}.")
    if protocol_type == "Varying durations":
        session_description = (
            "The subject is placed in a plastic tub and is recorded for 3.5 minutes. "
            "The subject receives a 40 Hz stimulation at various durations (i.e. 250ms, 1s and 4s) "
            "5 times for each duration) with an inter-stimulus interval (ISI) of 10s. "
        )
        stimulus_metadata_path = Path(__file__).parent / "metadata/varying_durations_ogen_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)
    elif protocol_type == "Varying frequencies":
        session_description = (
            "The subject is placed in a plastic tub and undergoes 3 recording sessions corresponding "
            "to a fixed duration of stimulation (i.e., 250ms, 1s, and 4s). Each session lasted 8 minutes. "
            "The subject receives optogenetic stimulation at varying frequencies "
            "(5 Hz, 10 Hz , 20 Hz and 40 Hz) 5 times for each duration with an ISI of 10s. "
        )
        stimulus_metadata_path = Path(__file__).parent / "metadata/varying_frequencies_ogen_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)
    elif protocol_type == "Shocks":
        session_description = (
            "The subject is placed in a shock chamber and recorded for 6 minutes. "
            "Auditory cues of 8 sec not paired or paired with shock are delivered during the session."
        )
        stimulus_metadata_path = Path(__file__).parent / "metadata/shock_stimulus_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)

    source_data = dict()
    conversion_options = dict()

    # Add FiberPhotometry
    source_data.update(dict(FiberPhotometry=dict(folder_path=tdt_folder_path)))
    conversion_options.update(dict(FiberPhotometry=dict()))

    # Add DemodulatedFiberPhotometry for calcium and isosbestic

    source_data.update(
        dict(
            DemodulatedFiberPhotometry_Calcium=dict(folder_path=tdt_folder_path),
            DemodulatedFiberPhotometry_Isosbestic=dict(folder_path=tdt_folder_path),
        )
    )
    source_data.update(
        dict(
            DemodulatedFiberPhotometry_Calcium=dict(folder_path=tdt_folder_path),
            DemodulatedFiberPhotometry_Isosbestic=dict(folder_path=tdt_folder_path),
        )
    )

    conversion_options.update(
        dict(
            DemodulatedFiberPhotometry_Calcium=dict(driver_freq=330, name="calcium_signal"),
            DemodulatedFiberPhotometry_Isosbestic=dict(driver_freq=210, name="isosbestic_signal"),
        )
    )

    # Add Video
    video_time_alignment_dict = dict()
    if not video_file_paths:
        warnings.warn("No video file paths found. Skipping video data addition.")

    elif len(video_file_paths) == 1:
        source_data.update(dict(Video=dict(file_paths=video_file_paths, video_name="BehavioralVideo")))
        video_starting_time = get_video_aligned_starting_time(
            video_metadata_file_path=video_metadata_file_path,
            video_file_path=video_file_paths[0],
            session_starting_time=session_starting_time,
        )
        video_time_alignment_dict.update(dict(Video=dict(video_starting_time=video_starting_time)))

    elif len(video_file_paths) == 3:
        for video_file_path in video_file_paths:
            suffix = video_file_path.name.split("_")[-1].split(".")[0]  # Extract suffix from filename
            source_data.update(
                {f"Video_{suffix}": dict(file_paths=[video_file_path], video_name=f"BehavioralVideo_{suffix}")}
            )
            video_starting_time = get_video_aligned_starting_time(
                video_metadata_file_path=video_metadata_file_path,
                video_file_path=video_file_path,
                session_starting_time=session_starting_time,
            )
            video_time_alignment_dict.update({f"Video_{suffix}": dict(video_starting_time=video_starting_time)})

    else:
        raise NotImplementedError(
            f"Support for {len(video_file_paths)} video files is not implemented. "
            "Currently only 1 or 3 video files are supported."
        )

    converter = Lofti2025NWBConverter(
        source_data=source_data, verbose=verbose, video_time_alignment_dict=video_time_alignment_dict
    )

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    editable_metadata_path = Path(__file__).parent / "metadata/general_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = session_description

    if "Ophys" in metadata and "FiberPhotometry" in metadata["Ophys"]:
        fiber_photometry = metadata["Ophys"]["FiberPhotometry"]
        if "Indicators" in fiber_photometry:
            indicators = fiber_photometry["Indicators"]

            # Filter the indicators based on ogen_stimulus_location
            filtered_indicators = [
                indicator
                for indicator in indicators
                if not (
                    (ogen_stimulus_location == "STN" and indicator.get("injection_location") == "PPN")
                    or (ogen_stimulus_location == "PPN" and indicator.get("injection_location") == "STN")
                )
            ]

            # Update the Indicators section
            fiber_photometry["Indicators"] = filtered_indicators

    # Add stimulus metadata
    metadata = dict_deep_update(metadata, stimulus_metadata, remove_repeats=False)
    if "OptogeneticStimulusSite" in metadata["Stimulus"]:
        metadata["Stimulus"]["OptogeneticStimulusSite"][0]["location"] = ogen_stimulus_location

    # Run conversion
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
    )
    if verbose:
        print(f"Session {session_id} for subject {subject_id} converted successfully to NWB format at {nwbfile_path}")


if __name__ == "__main__":

    # Parameters for conversion
    data_dir_path = Path("D:/Hnasko-CN-data-share/SN pan GABA recordings/")
    output_dir_path = Path("D:/hnasko_lab_conversion_nwb")

    from neuroconv.tools.path_expansion import LocalPathExpander

    # data_dir_path = "D:/Hnasko-CN-data-share/SN pan GABA recordings/"
    # Specify source data
    source_data_spec = {
        "FiberPhotometry": {
            "base_directory": data_dir_path,
            "folder_path": "{ogen_stimulus_location}/Fiber photometry_TDT/{protocol_type}/{subject_id}-{session_starting_time_string}",
        }
    }

    # Instantiate LocalPathExpander
    path_expander = LocalPathExpander()
    # Expand paths and extract metadata
    metadata_list = path_expander.expand_paths(source_data_spec)
    for metadata in metadata_list:
        protocol_type = metadata["metadata"]["extras"]["protocol_type"]
        session_starting_time_string = metadata["metadata"]["extras"]["session_starting_time_string"]
        session_starting_time = datetime.strptime(session_starting_time_string, "%y%m%d-%H%M%S")
        ogen_stimulus_location = metadata["metadata"]["extras"]["ogen_stimulus_location"]

        subject_id = metadata["metadata"]["Subject"]["subject_id"]
        video_folder_path = (
            data_dir_path / ogen_stimulus_location / "AnyMaze videos_slk/converted_video" / protocol_type
        )
        video_metadata_file_path = video_folder_path / "video_metadata.xlsx"
        video_file_paths = list(video_folder_path.glob(f"{subject_id}*.mp4"))
        session_to_nwb(
            output_dir_path=output_dir_path,
            session_starting_time=session_starting_time,
            subject_id=subject_id,
            protocol_type=protocol_type,
            ogen_stimulus_location=ogen_stimulus_location,
            tdt_folder_path=metadata["source_data"]["FiberPhotometry"]["folder_path"],
            video_file_paths=video_file_paths,
            video_metadata_file_path=video_metadata_file_path,
            stub_test=False,
            overwrite=True,
            verbose=True,
        )
