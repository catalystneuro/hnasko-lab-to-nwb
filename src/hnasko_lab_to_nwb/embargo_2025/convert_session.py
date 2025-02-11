"""Primary script to run to convert an entire session for of data using the NWBConverter."""

import warnings
from pathlib import Path
from typing import List, Union

from nwbconverter import Embargo2025NWBConverter

from neuroconv.utils import dict_deep_update, load_dict_from_file


def session_to_nwb(
    output_dir_path: Union[str, Path],
    subject_id: str,
    session_id: str,
    tdt_folder_path: Union[str, Path],
    video_file_paths: List[Union[str, Path]],
    protocol_type: str,
    ogen_stimulus_location: str,
    stub_test: bool = False,
    overwrite: bool = False,
):
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

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
            "Uncued shocks (0.3 mA) at various durations (250ms, 1s and 4s, 5 times for each duration) "
            "are delivered in a randomized order and ISI."
        )
        stimulus_metadata_path = Path(__file__).parent / "metadata/shock_stimulus_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)

    source_data = dict()
    conversion_options = dict()

    # Add FiberPhotometry
    source_data.update(dict(FiberPhotometry=dict(folder_path=tdt_folder_path)))
    conversion_options.update(dict(FiberPhotometry=dict()))

    # Add Video
    if not video_file_paths:
        warnings.warn("No video file paths found. Skipping video data addition.")
    else:
        # TODO converted video does not timestamps as the original video
        source_data.update(dict(Video=dict(file_paths=video_file_paths)))
        conversion_options.update(dict(Video=dict(stub_test=stub_test, external_mode=True)))

    converter = Embargo2025NWBConverter(source_data=source_data)

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
    metadata = dict_deep_update(metadata, stimulus_metadata)
    if "OptogeneticStimulusSite" in metadata["Stimulus"]:
        metadata["Stimulus"]["OptogeneticStimulusSite"][0]["location"] = ogen_stimulus_location

    # Run conversion
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
    )


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
            "folder_path": "{ogen_stimulus_location}/Fiber photometry_TDT/{protocol_type}/{subject_id}-{session_id}",
        }
    }
    # Instantiate LocalPathExpander
    path_expander = LocalPathExpander()
    # Expand paths and extract metadata
    metadata_list = path_expander.expand_paths(source_data_spec)
    for metadata in metadata_list[-5:]:
        ogen_stimulus_location = metadata["metadata"]["extras"]["ogen_stimulus_location"]
        protocol_type = metadata["metadata"]["extras"]["protocol_type"]
        subject_id = metadata["metadata"]["Subject"]["subject_id"]
        video_folder_path = (
            data_dir_path / ogen_stimulus_location / "AnyMaze videos_slk/converted_video" / protocol_type
        )

        video_file_paths = list(video_folder_path.glob(f"{subject_id}*.mp4"))
        session_to_nwb(
            output_dir_path=output_dir_path,
            subject_id=metadata["metadata"]["Subject"]["subject_id"],
            session_id=metadata["metadata"]["NWBFile"]["session_id"],
            tdt_folder_path=metadata["source_data"]["FiberPhotometry"]["folder_path"],
            video_file_paths=video_file_paths,
            protocol_type=protocol_type,
            ogen_stimulus_location=ogen_stimulus_location,
            stub_test=True,
            overwrite=True,
        )
