"""Primary script to run to convert an entire session for of data using the NWBConverter."""

from pathlib import Path
from typing import Union

from nwbconverter import Embargo2025NWBConverter

from neuroconv.utils import dict_deep_update, load_dict_from_file


def session_to_nwb(
    data_dir_path: Union[str, Path],
    output_dir_path: Union[str, Path],
    subject_id: str,
    session_id: str,
    stub_test: bool = False,
):

    data_dir_path = Path(data_dir_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)

    nwbfile_path = output_dir_path / f"sub-{subject_id}_ses-{session_id}.nwb"

    source_data = dict()
    conversion_options = dict()

    # Add Recording
    folder_path = data_dir_path / "Fiber photometry_TDT/Varying durations" / f"{subject_id}-{session_id}"
    source_data.update(dict(FiberPhotometry=dict(folder_path=folder_path)))
    conversion_options.update(dict(FiberPhotometry=dict()))

    converter = Embargo2025NWBConverter(source_data=source_data)

    # Update default metadata with the editable in the corresponding yaml file
    metadata = converter.get_metadata()
    editable_metadata_path = Path(__file__).parent / "metadata.yaml"
    editable_metadata = load_dict_from_file(editable_metadata_path)
    metadata = dict_deep_update(metadata, editable_metadata)

    metadata["Subject"]["subject_id"] = subject_id  # Modify here or in the yaml file

    # Run conversion
    converter.run_conversion(metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options)


if __name__ == "__main__":

    # Parameters for conversion
    data_dir_path = Path("D:/Hnasko-CN-data-share/SN pan GABA recordings/PPN/")
    output_dir_path = Path("D:/hnasko_lab_conversion_nwb")
    stub_test = False
    subject_id = "C4550"
    session_id = "240118-094128"
    session_to_nwb(
        data_dir_path=data_dir_path,
        output_dir_path=output_dir_path,
        subject_id=subject_id,
        session_id=session_id,
        stub_test=stub_test,
    )
