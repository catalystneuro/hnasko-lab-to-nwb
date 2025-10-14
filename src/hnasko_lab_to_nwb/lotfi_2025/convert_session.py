"""Primary script to run to convert an entire session for of data using the NWBConverter."""

import warnings
from pathlib import Path
from typing import Union

from hnasko_lab_to_nwb.lotfi_2025.nwbconverter import Lofti2025NWBConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file


def extract_processed_fp_metadata(series_list, stream_name):
    """Extract metadata for a specific stream from the session metadata."""

    # Find the matching series by stream_name
    series_metadata = next((series for series in series_list if series.get("stream_name") == stream_name), None)

    if series_metadata is None:
        raise ValueError(f"Stream name '{stream_name}' not found in the provided series list.")

    # Extract only the keys we need
    return {
        key: series_metadata.get(key)
        for key in ["stream_name", "sampling_frequency", "target_area"]
        if key in series_metadata
    }


def session_to_nwb(
    output_dir_path: Union[str, Path],
    subject_id: str,
    protocol_folder_path: Union[str, Path],
    recording_type: None | str = None,
    stimulus_location: None | str = None,
    protocol_type: None | str = None,
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
    protocol_type : None | str = None
        Type of protocol (e.g., "Varying durations", "Varying frequencies").
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
    If recording_type, stimulus_location, or protocol_type are not provided, they will be inferred
    from the protocol_folder_path, as follows:
        protocol_folder_path = data_dir_path / recording_type / stimulus_location / "Fiber photometry_TDT" / protocol_type
    """
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    protocol_folder_path = Path(protocol_folder_path)
    if protocol_type is None:
        protocol_type = protocol_folder_path.parts[-1]
    session_id = protocol_type.replace(" ", "_").lower()

    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    if protocol_type == "Varying durations":
        session_description = (
            "The subject is placed in a plastic tub and is recorded for 3.5 minutes. "
            "The subject receives a 40 Hz stimulation at various durations (i.e. 250ms, 1s and 4s) "
            "5 times for each duration) with an inter-stimulus interval (ISI) of 10s. "
        )
        # TODO define optogenetic stimulation parameters directly here instead of loading from a yaml file
        stimulus_metadata_path = Path(__file__).parent / "metadata/varying_durations_ogen_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)
        stimulus_channel_name = "LP5mW"
    elif protocol_type == "Varying frequencies":
        session_description = (
            "The subject is placed in a plastic tub and undergoes 3 recording sessions corresponding "
            "to a fixed duration of stimulation (i.e., 250ms, 1s, and 4s). Each session lasted 8 minutes. "
            "The subject receives optogenetic stimulation at varying frequencies "
            "(5 Hz, 10 Hz , 20 Hz and 40 Hz) 5 times for each duration with an ISI of 10s. "
        )
        # TODO define optogenetic stimulation parameters directly here instead of loading from a yaml file
        stimulus_metadata_path = Path(__file__).parent / "metadata/varying_frequencies_ogen_metadata.yaml"
        stimulus_metadata = load_dict_from_file(stimulus_metadata_path)
        # TODO extract stimulus_channel_name from tdt_events streams instead of hardcoding it here
        stimulus_channel_names = ["s250ms", "s1s", "s4s"]
    else:
        raise ValueError(f"Unknown protocol type: {protocol_type}")

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

    source_data = dict()
    conversion_options = dict()

    # Add FiberPhotometry
    if protocol_type == "Varying frequencies":
        warnings.warn(
            "The TDT interface for concatenated sessions is not implemented yet. Only the varFreq_4s session will be converted for now."
        )
        stimulus_channel_name = stimulus_channel_names[2]  # Use the stimulus channel name for the 4s protocol
        # TODO implement TDT interface for concatenated sessions
        tdt_folder_path = list(protocol_folder_path.glob(f"varFreq_4s/{subject_id}-*"))
    else:
        tdt_folder_path = list(protocol_folder_path.glob(f"{subject_id}-*"))
    if len(tdt_folder_path) == 0:
        raise FileNotFoundError(f"No TDT folder found in {protocol_folder_path}")
    elif len(tdt_folder_path) > 1:
        raise ValueError(f"Multiple TDT folders found in {protocol_folder_path}")
    tdt_folder_path = tdt_folder_path[0]
    source_data.update(dict(FiberPhotometry=dict(folder_path=tdt_folder_path)))
    conversion_options.update(dict(FiberPhotometry=dict(stub_test=stub_test)))

    # Add processed fp series
    mat_file_path = list(protocol_folder_path.glob("*.mat"))
    if len(mat_file_path) == 0:
        raise FileNotFoundError(f"No .mat files found in {protocol_folder_path}")
    elif len(mat_file_path) > 1:
        raise ValueError(f"Multiple .mat files found in {protocol_folder_path}")
    mat_file_path = mat_file_path[0]
    series_list = (
        editable_metadata.get("Ophys", {}).get("FiberPhotometry", {}).get("ProcessedFiberPhotometryResponseSeries", [])
    )
    # TODO implement concatenated varying frequencies session  --> instead of passing a single stimulus_channel_name,
    #  we should pass a list of stimulus_channel_names corresponding to each concatenated session

    # Add DemodulatedFiberPhotometry for calcium and isosbestic
    stream_name = "Gc_raw"
    source_data.update(
        dict(
            DemodulatedFiberPhotometry_Calcium=dict(
                file_path=mat_file_path,
                subject_id=subject_id,
                **extract_processed_fp_metadata(series_list, stream_name),
            )
        )
    )
    conversion_options.update(
        dict(DemodulatedFiberPhotometry_Calcium=dict(stub_test=stub_test, stimulus_channel_name=stimulus_channel_name))
    )

    stream_name = "af_raw"
    source_data.update(
        dict(
            DemodulatedFiberPhotometry_Isosbestic=dict(
                file_path=mat_file_path,
                subject_id=subject_id,
                **extract_processed_fp_metadata(series_list, stream_name),
            )
        )
    )
    conversion_options.update(
        dict(
            DemodulatedFiberPhotometry_Isosbestic=dict(stub_test=stub_test, stimulus_channel_name=stimulus_channel_name)
        )
    )

    # Add DownsampledFiberPhotometry for calcium and isosbestic
    stream_name = "Gc"
    source_data.update(
        dict(
            DownsampledFiberPhotometry_Calcium=dict(
                file_path=mat_file_path,
                subject_id=subject_id,
                **extract_processed_fp_metadata(series_list, stream_name),
            )
        )
    )
    conversion_options.update(
        dict(DownsampledFiberPhotometry_Calcium=dict(stub_test=stub_test, stimulus_channel_name=stimulus_channel_name))
    )

    stream_name = "af"
    source_data.update(
        dict(
            DownsampledFiberPhotometry_Isosbestic=dict(
                file_path=mat_file_path,
                subject_id=subject_id,
                **extract_processed_fp_metadata(series_list, stream_name),
            )
        )
    )
    conversion_options.update(
        dict(
            DownsampledFiberPhotometry_Isosbestic=dict(stub_test=stub_test, stimulus_channel_name=stimulus_channel_name)
        )
    )

    # Add DeltaFOverF
    stream_name = "dF"
    source_data.update(
        dict(
            DeltaFOverF=dict(
                file_path=mat_file_path,
                subject_id=subject_id,
                **extract_processed_fp_metadata(series_list, stream_name),
            )
        )
    )
    conversion_options.update(dict(DeltaFOverF=dict(stub_test=stub_test, stimulus_channel_name=stimulus_channel_name)))

    converter = Lofti2025NWBConverter(source_data=source_data, verbose=verbose)

    # Add OptogeneticStimulation
    # TODO add optogenetic stimulation interface to the converter and add the metadata here

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id
    metadata["NWBFile"]["session_id"] = session_id
    metadata["NWBFile"]["session_description"] = session_description

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

    recording_type = "SN pan DA recordings"  # "GRABDA recordings"  "SN pan DA recordings" "Str_DA_terminal recordings" "SN pan GABA recordings"
    stimulus_location = "STN"  # "PPN" "STN"
    protocol_type = "Varying frequencies"  # "Varying durations" "Varying frequencies"
    subject_id = "C4217"
    protocol_folder_path = data_dir_path / recording_type / stimulus_location / "Fiber photometry_TDT" / protocol_type

    session_to_nwb(
        output_dir_path=output_dir_path,
        subject_id=subject_id,
        protocol_folder_path=protocol_folder_path,
        recording_type=recording_type,
        stimulus_location=stimulus_location,
        protocol_type=protocol_type,
        stub_test=False,
        overwrite=True,
        verbose=True,
    )
