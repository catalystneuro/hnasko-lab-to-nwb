"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from pathlib import Path
from typing import Union

from hnasko_lab_to_nwb.lotfi_2025.interfaces.concatenated_tdt_fp_interface import (
    ConcatenatedTDTFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.lotfi_2025.nwbconverter import Lofti2025NWBConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file


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


def varying_frequencies_session_to_nwb(
    output_dir_path: Union[str, Path],
    subject_id: str,
    protocol_folder_path: Union[str, Path],
    recording_type: None | str = None,
    stimulus_location: None | str = None,
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
):
    """Convert a single session to NWB format.
    Parameters
    ----------
    output_dir_path : Union[str, Path]
        Path to the output directory where the NWB file will be saved.
    subject_id : str
        Subject identifier.
    protocol_folder_path : Union[str, Path]
        Path to the protocol folder containing TDT data and processed .mat file.
    recording_type : None | str = None
        Type of recording (e.g., "SN pan GABA recordings", "GRABDA recordings", "SN pan DA recordings", "Str_DA_terminal recordings").
    stimulus_location : None | str = None
        Location of the stimulus (e.g., "PPN", "STN").
    stub_test : bool, optional
        If True, run a stub test (default is False).
    overwrite : bool, optional
        If True, overwrite existing NWB file (default is False).
    verbose : bool, optional
        If True, print verbose output (default is False).

    Notes
    -------
    This function assumes that the protocol_folder_path contains a TDT folder and a processed .mat
    file. The TDT folder should be named as "{subject_id}-*" and the .mat file should be the only .mat
    file in the protocol_folder_path.
    If recording_type or stimulus_location are not provided, they will be inferred
    from the protocol_folder_path, as follows:
        protocol_folder_path = data_dir_path / recording_type / stimulus_location / "Fiber photometry_TDT" / "Varying frequencies"
    The optogenetic stimulation parameters are hardcoded in this function.
    tdt stimulation channel names: ["H10_", "H20_", "H40_", "H05_"]
    stimulation frequencies: [10.0, 20.0, 40.0, 5.0]
    """
    protocol_folder_path = Path(protocol_folder_path)

    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    session_id = "varying_frequencies"

    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    # Define session description and stimulation parameters
    session_description = (
        "The subject is placed in a plastic tub and undergoes 3 recording sessions corresponding "
        "to a fixed duration of stimulation (i.e., 250ms, 1s, and 4s). Each session lasted 8 minutes. "
        "The subject receives optogenetic stimulation at varying frequencies "
        "(5 Hz, 10 Hz , 20 Hz and 40 Hz) 5 times for each duration with an ISI of 10s. "
    )
    if recording_type is None:
        recording_type = protocol_folder_path.parts[-4]
    if recording_type not in [
        "SN pan GABA recordings",
        "GRABDA recordings",
        "SN pan DA recordings",
        "Str_DA_terminal recordings",
    ]:
        raise ValueError(f"Unknown recording type: {recording_type}")
    editable_metadata_path = Path(__file__).parent / f"metadata/{recording_type.replace(' ', '_')}_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)

    if stimulus_location is None:
        stimulus_location = protocol_folder_path.parts[-3]
    if stimulus_location not in ["PPN", "STN"]:
        raise ValueError(f"Unknown stimulus location: {stimulus_location}")

    tdt_stim_ch_names = ["H10_", "H20_", "H40_", "H05_"]
    stim_frequencies = [10.0, 20.0, 40.0, 5.0]

    # Handle exception for SN pan GABA recordings
    if recording_type == "SN pan GABA recordings" and stimulus_location == "PPN":
        # TODO add behavioral video conversion
        add_video_conversion = True
        tdt_folder_paths = list(protocol_folder_path.glob(f"{subject_id}-*"))
        ordered_mat_stim_ch_names = ["AllDurs"]
    else:
        mat_stim_ch_names = ["s250ms", "s1s", "s4s"]
        if recording_type == "SN pan GABA recordings" and stimulus_location == "STN":
            mat_stim_ch_names = ["s250ms5mW", "s1s10mW"]

        tdt_folder_paths = list(protocol_folder_path.glob(f"varFreq_*/{subject_id}-*"))
        # Sort the folders based on the session_starting_time_string
        tdt_folder_paths.sort(key=lambda x: x.name.split("-")[-1])
        ordered_mat_stim_ch_names = []
        for folder in tdt_folder_paths:
            if "varFreq_250ms" in folder.parent.name:
                ordered_mat_stim_ch_names.append(mat_stim_ch_names[0])
            elif "varFreq_1s" in folder.parent.name:
                ordered_mat_stim_ch_names.append(mat_stim_ch_names[1])
            elif "varFreq_4s" in folder.parent.name:
                ordered_mat_stim_ch_names.append(mat_stim_ch_names[2])
            else:
                raise ValueError(f"Unknown sub-session folder name: {folder.parent.name}")

    source_data = dict()
    conversion_options = dict()

    # Add FiberPhotometry
    source_data.update(dict(ConcatenatedRawFiberPhotometry=dict(folder_paths=tdt_folder_paths)))
    conversion_options.update(dict(ConcatenatedRawFiberPhotometry=dict(stub_test=stub_test, stream_name="Fi1r")))

    # Add processed fp series
    mat_file_path = list(protocol_folder_path.glob("*.mat"))
    if len(mat_file_path) == 0:
        raise FileNotFoundError(f"No .mat files found in {protocol_folder_path}")
    elif len(mat_file_path) > 1:
        raise ValueError(f"Multiple .mat files found in {protocol_folder_path}")
    mat_file_path = mat_file_path[0]

    concatenated_tdt_interface = ConcatenatedTDTFiberPhotometryInterface(folder_paths=tdt_folder_paths, verbose=verbose)
    segment_starting_times = concatenated_tdt_interface.segment_starting_times
    # Add Processed Fiber Photometry
    stream_to_interface_mapping = {
        "Gc_raw": "ConcatenatedDemodulatedFiberPhotometry_Calcium",
        "af_raw": "ConcatenatedDemodulatedFiberPhotometry_Isosbestic",
        "Gc": "ConcatenatedDownsampledFiberPhotometry_Calcium",
        "af": "ConcatenatedDownsampledFiberPhotometry_Isosbestic",
        "dF": "ConcatenatedDeltaFOverF",
    }
    target_area = get_target_area_for_subject(mat_file_path, subject_id)
    for stream_name, interface_name in stream_to_interface_mapping.items():
        source_data.update(
            dict(
                **{
                    interface_name: dict(
                        file_path=mat_file_path,
                        subject_id=subject_id,
                        stream_name=stream_name,
                        target_area=target_area,
                        sampling_frequency=6103.5156 if "raw" in stream_name else 100.0,
                    )
                }
            )
        )
        conversion_options.update(
            dict(
                **{
                    interface_name: dict(
                        stub_test=stub_test,
                        stimulus_channel_names=ordered_mat_stim_ch_names,
                        segment_starting_times=segment_starting_times,
                    )
                }
            )
        )

    converter = Lofti2025NWBConverter(source_data=source_data, verbose=verbose)

    # Add OptogeneticStimulation
    # TODO add optogenetic stimulation interface to the converter and add the metadata here

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = session_description

    # Remove entries for other target areas from metadata
    for key in metadata["Ophys"]["FiberPhotometry"].keys():
        if "FiberPhotometryResponseSeries" in key:
            fp_response_series = metadata["Ophys"]["FiberPhotometry"][key]
            metadata["Ophys"]["FiberPhotometry"][key] = [
                fps for fps in fp_response_series if fps.get("target_area", None) == target_area
            ]

    # Run conversion
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
    )
    if verbose:
        print(f"Session {session_id} for subject {subject_id} converted successfully to NWB format at {nwbfile_path}")


def varying_durations_session_to_nwb(  #
    output_dir_path: Union[str, Path],
    subject_id: str,
    protocol_folder_path: Union[str, Path],
    recording_type: None | str = None,
    stimulus_location: None | str = None,
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
):
    """Convert a single session to NWB format.
    Parameters
    ----------
    output_dir_path : Union[str, Path]
        Path to the output directory where the NWB file will be saved.
    subject_id : str
        Subject identifier.
    protocol_folder_path : Union[str, Path]
        Path to the protocol folder containing TDT data and processed .mat file.
    recording_type : None | str = None
        Type of recording (e.g., "SN pan GABA recordings", "GRABDA recordings", "SN pan DA recordings", "Str_DA_terminal recordings").
    stimulus_location : None | str = None
        Location of the stimulus (e.g., "PPN", "STN").
    stub_test : bool, optional
        If True, run a stub test (default is False).
    overwrite : bool, optional
        If True, overwrite existing NWB file (default is False).
    verbose : bool, optional
        If True, print verbose output (default is False).

    Notes
    -------
    This function assumes that the protocol_folder_path contains a TDT folder and a processed .mat
    file. The TDT folder should be named as "{subject_id}-*" and the .mat file should be the only .mat
    file in the protocol_folder_path.
    If recording_type or stimulus_location are not provided, they will be inferred
    from the protocol_folder_path, as follows:
        protocol_folder_path = data_dir_path / recording_type / stimulus_location / "Fiber photometry_TDT" / "Varying durations"
    The optogenetic stimulation parameters are hardcoded in this function.
    tdt stimulation channel names: ["sms_", "s1s_", "s4s_"]
    stimulation frequencies: [40.0, 40.0, 40.0]
    """
    protocol_folder_path = Path(protocol_folder_path)

    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    session_id = "varying_durations"

    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    # Define session description and stimulation parameters
    session_description = (
        "The subject is placed in a plastic tub and is recorded for 3.5 minutes. "
        "The subject receives a 40 Hz stimulation at various durations (i.e. 250ms, 1s and 4s) "
        "5 times for each duration) with an inter-stimulus interval (ISI) of 10s. "
    )
    if recording_type is None:
        recording_type = protocol_folder_path.parts[-4]
    if recording_type not in [
        "SN pan GABA recordings",
        "GRABDA recordings",
        "SN pan DA recordings",
        "Str_DA_terminal recordings",
    ]:
        raise ValueError(f"Unknown recording type: {recording_type}")
    editable_metadata_path = Path(__file__).parent / f"metadata/{recording_type.replace(' ', '_')}_metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)

    if stimulus_location is None:
        stimulus_location = protocol_folder_path.parts[-3]
    if stimulus_location not in ["PPN", "STN"]:
        raise ValueError(f"Unknown stimulus location: {stimulus_location}")

    tdt_stim_ch_names = ["sms_", "s1s_", "s4s_"]
    stim_frequencies = [40.0, 40.0, 40.0]
    mat_stim_ch_name = "LP5mW"

    # Handle exception for SN pan GABA recordings
    if recording_type == "SN pan GABA recordings" and stimulus_location == "PPN":
        # TODO add behavioral video conversion
        add_video_conversion = True

    source_data = dict()
    conversion_options = dict()

    # Add FiberPhotometry
    tdt_folder_path = list(protocol_folder_path.glob(f"{subject_id}-*"))
    if len(tdt_folder_path) == 0:
        raise FileNotFoundError(f"No TDT folder found in {protocol_folder_path}")
    elif len(tdt_folder_path) > 1:
        raise ValueError(f"Multiple TDT folders found in {protocol_folder_path}")
    tdt_folder_path = tdt_folder_path[0]
    source_data.update(dict(RawFiberPhotometry=dict(folder_path=tdt_folder_path)))
    conversion_options.update(dict(RawFiberPhotometry=dict(stub_test=stub_test)))

    # Add processed fp series
    mat_file_path = list(protocol_folder_path.glob("*.mat"))
    if len(mat_file_path) == 0:
        raise FileNotFoundError(f"No .mat files found in {protocol_folder_path}")
    elif len(mat_file_path) > 1:
        raise ValueError(f"Multiple .mat files found in {protocol_folder_path}")
    mat_file_path = mat_file_path[0]
    # Add Processed Fiber Photometry
    stream_to_interface_mapping = {
        "Gc_raw": "DemodulatedFiberPhotometry_Calcium",
        "af_raw": "DemodulatedFiberPhotometry_Isosbestic",
        "Gc": "DownsampledFiberPhotometry_Calcium",
        "af": "DownsampledFiberPhotometry_Isosbestic",
        "dF": "DeltaFOverF",
    }
    target_area = get_target_area_for_subject(mat_file_path, subject_id)
    for stream_name, interface_name in stream_to_interface_mapping.items():
        source_data.update(
            dict(
                **{
                    interface_name: dict(
                        file_path=mat_file_path,
                        subject_id=subject_id,
                        stream_name=stream_name,
                        target_area=target_area,
                        sampling_frequency=6103.5156 if "raw" in stream_name else 100.0,
                    )
                }
            )
        )
        conversion_options.update(
            dict(
                **{
                    interface_name: dict(
                        stub_test=stub_test,
                        stimulus_channel_name=mat_stim_ch_name,
                    )
                }
            )
        )

    converter = Lofti2025NWBConverter(source_data=source_data, verbose=verbose)

    # Add OptogeneticStimulation
    # TODO add optogenetic stimulation interface to the converter and add the metadata here

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = session_description

    # Remove entries for other target areas from metadata
    for key in metadata["Ophys"]["FiberPhotometry"].keys():
        if "FiberPhotometryResponseSeries" in key:
            fp_response_series = metadata["Ophys"]["FiberPhotometry"][key]
            metadata["Ophys"]["FiberPhotometry"][key] = [
                fps for fps in fp_response_series if fps.get("target_area", None) == target_area
            ]

    # Run conversion
    converter.run_conversion(
        metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
    )
    if verbose:
        print(f"Session {session_id} for subject {subject_id} converted successfully to NWB format at {nwbfile_path}")


if __name__ == "__main__":

    # Parameters for conversion
    data_dir_path = Path("D:/Hnasko-CN-data-share/")
    output_dir_path = Path("D:/hnasko_lab_conversion_nwb")

    recording_type = "GRABDA recordings"  # "GRABDA recordings"  "SN pan DA recordings" "Str_DA_terminal recordings" "SN pan GABA recordings"
    stimulus_location = "STN"  # "PPN" "STN"
    subject_id = "C3017"
    parent_protocol_folder_path = data_dir_path / recording_type / stimulus_location / "Fiber photometry_TDT"

    varying_frequencies_session_to_nwb(
        output_dir_path=output_dir_path,
        subject_id=subject_id,
        protocol_folder_path=parent_protocol_folder_path / "Varying frequencies",
        recording_type=recording_type,
        stimulus_location=stimulus_location,
        stub_test=False,
        overwrite=True,
        verbose=True,
    )

    varying_durations_session_to_nwb(
        output_dir_path=output_dir_path,
        subject_id=subject_id,
        protocol_folder_path=parent_protocol_folder_path / "Varying durations",
        recording_type=recording_type,
        stimulus_location=stimulus_location,
        stub_test=False,
        overwrite=True,
        verbose=True,
    )
