"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from pathlib import Path
from typing import Literal, Union

from hnasko_lab_to_nwb.lotfi_2025.nwbconverter import Lofti2025NWBConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file


def session_to_nwb(
    output_dir_path: Union[str, Path],
    tdtomato_injection_location: Literal["PPN", "STN"],
    subject_id: str,
    tdt_folder_path: Union[str, Path],
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
):
    session_id = "Shocks"

    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

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

    converter = Lofti2025NWBConverter(source_data=source_data, verbose=verbose)

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

            # Filter the indicators based on tdtomato_injection_location --> # TODO find better way to deal with this
            filtered_indicators = [
                indicator
                for indicator in indicators
                if not (
                    (tdtomato_injection_location == "STN" and indicator.get("injection_location") == "PPN")
                    or (tdtomato_injection_location == "PPN" and indicator.get("injection_location") == "STN")
                )
            ]

            # Update the Indicators section
            fiber_photometry["Indicators"] = filtered_indicators

    # Add stimulus metadata
    metadata = dict_deep_update(metadata, stimulus_metadata, remove_repeats=False)

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
            "folder_path": "{tdtomato_injection_location}/Fiber photometry_TDT/Shocks/{subject_id}-{session_starting_time_string}",
        }
    }

    # Instantiate LocalPathExpander
    path_expander = LocalPathExpander()
    # Expand paths and extract metadata
    metadata_list = path_expander.expand_paths(source_data_spec)
    for metadata in metadata_list:
        subject_id = metadata["metadata"]["Subject"]["subject_id"]
        tdtomato_injection_location = metadata["metadata"]["extras"]["tdtomato_injection_location"]

        session_to_nwb(
            output_dir_path=output_dir_path,
            tdtomato_injection_location=tdtomato_injection_location,
            subject_id=subject_id,
            tdt_folder_path=metadata["source_data"]["FiberPhotometry"]["folder_path"],
            stub_test=False,
            overwrite=True,
            verbose=True,
        )
