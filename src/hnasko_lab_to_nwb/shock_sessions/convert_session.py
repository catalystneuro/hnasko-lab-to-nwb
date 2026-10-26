"""Convert one shock session to NWB.

A shock session is one TDT block of an SN pan GABA PPN mouse, recorded while it heard auditory cues paired (CS+) or
not paired (CS-) with a shock. The conversion reuses the parts of hadjas_2025: the metadata of the base cohort, the
raw TDT interface, and the processed signals recomputed from the raw signal (there is no lab .mat file for these
sessions).
"""

from pathlib import Path
from typing import Union

from hnasko_lab_to_nwb.hadjas_2025.convert_session import (
    add_led_modulation_to_metadata,
    get_led_modulation,
    get_nwbfile_name,
    get_raw_stream_settings,
    get_session_start_time,
    load_cohort_metadata,
    load_external_resources_metadata,
    load_rig_devices_metadata,
    normalize_hemisphere,
    update_coordinates_for_left_hemisphere,
)
from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import clear_tdt_block_cache, read_tdt_start_timestamp
from hnasko_lab_to_nwb.shock_sessions.nwbconverter import ShockSessionsNWBConverter
from neuroconv.utils import dict_deep_update, load_dict_from_file

METADATA_FOLDER_PATH = Path(__file__).parent / "metadata"
SESSION_CONFIG_FILE_PATH = METADATA_FOLDER_PATH / "session_config.yaml"
SHOCK_SESSIONS_METADATA_FILE_PATH = METADATA_FOLDER_PATH / "shock_sessions_metadata.yaml"


def load_session_config() -> dict:
    """Load the settings of the shock session conversion (metadata/session_config.yaml)."""
    return load_dict_from_file(SESSION_CONFIG_FILE_PATH)


def load_shock_session_metadata() -> dict:
    """Load the metadata of the shock sessions: the base cohort's, updated with metadata/shock_sessions_metadata.yaml.

    Lists of the shock file (e.g. keywords) replace those of the base cohort. The optogenetics metadata is removed:
    there is no optogenetic stimulation in these sessions.

    Returns
    -------
    dict
        The merged metadata.
    """
    metadata = load_cohort_metadata(load_session_config()["base_cohort"])
    metadata = dict_deep_update(metadata, load_dict_from_file(SHOCK_SESSIONS_METADATA_FILE_PATH), append_list=False)
    metadata.pop("Optogenetics")
    return metadata


def session_to_nwb(
    output_dir_path: Union[str, Path],
    subject_metadata: dict,
    tdt_folder_path: Union[str, Path],
    processed: bool = True,
    stub_test: bool = False,
    overwrite: bool = False,
    verbose: bool = False,
) -> Path:
    """Convert one shock session (one TDT block) to NWB.

    The file is written to output_dir_path / sub-<subject ID>_ses-<session ID>.nwb, or to the nwb_stub subfolder
    for a stub test. It holds the raw Fi1r signal, the processed signals recomputed from it (hadjas_2025.recompute)
    and the auditory cue intervals.

    Parameters
    ----------
    output_dir_path : Union[str, Path]
        Path to the output directory where the NWB file will be saved.
    subject_metadata : dict
        Row of the overview sheet for the subject.
    tdt_folder_path : Union[str, Path]
        Path to the TDT block of the session.
    processed : bool, optional
        If True, write the processed signals recomputed from the raw signal (default is True).
    stub_test : bool, optional
        If True, convert only the first second of the block (default is False). Needs processed=False, since the
        processed signals are computed from the whole block.
    overwrite : bool, optional
        If True, overwrite an existing NWB file (default is False).
    verbose : bool, optional
        If True, print verbose output (default is False).

    Returns
    -------
    Path
        The path of the NWB file.

    Notes
    -----
    The metadata is merged in this order: the shock session metadata (load_shock_session_metadata), moved to the
    left hemisphere if the subject was implanted on the left, the devices of the rig, then the subject, session and
    LED modulation fields set here. The ontology terms are set after the last merge.
    """
    if processed and stub_test:
        raise ValueError("Recomputed processed signals need the whole block; use processed=False with stub_test.")
    session_config = load_session_config()
    subject_id = subject_metadata["Animal ID"]
    tdt_folder_path = Path(tdt_folder_path)
    output_dir_path = Path(output_dir_path)
    if stub_test:
        output_dir_path = output_dir_path / "nwb_stub"
    output_dir_path.mkdir(parents=True, exist_ok=True)
    nwbfile_path = output_dir_path / get_nwbfile_name(subject_id=subject_id, session_id=session_config["session_id"])

    editable_metadata = load_shock_session_metadata()
    if normalize_hemisphere(subject_metadata["Hemisphere"]) == "Left":
        editable_metadata = update_coordinates_for_left_hemisphere(editable_metadata)
    raw_stream_settings = get_raw_stream_settings(tdt_folder_path)
    editable_metadata = dict_deep_update(editable_metadata, load_rig_devices_metadata(raw_stream_settings["rig_name"]))
    session_start_time = get_session_start_time(read_tdt_start_timestamp(tdt_folder_path))
    led_modulation = get_led_modulation(session_start_time)

    raw_metadata_key = f"Fi1r_{subject_metadata['Recording Site']}"
    source_data = dict(
        RawFiberPhotometry=dict(
            folder_paths=[tdt_folder_path],
            stream_name="Fi1r",
            metadata_key=raw_metadata_key,
            stream_indices=raw_stream_settings["stream_indices"],
        ),
        AuditoryCueIntervals=dict(folder_path=tdt_folder_path, cue_epocs=session_config["cue_epocs"]),
    )
    conversion_options = dict(RawFiberPhotometry=dict(stub_test=stub_test))
    recomputed_processed_series_kwargs = None
    if processed:
        recomputed_processed_series_kwargs = dict(raw_metadata_key=raw_metadata_key, led_modulation=led_modulation)
    converter = ShockSessionsNWBConverter(
        source_data=source_data,
        verbose=verbose,
        recomputed_processed_series_kwargs=recomputed_processed_series_kwargs,
    )

    metadata = dict_deep_update(converter.get_metadata(), editable_metadata)
    metadata["ExternalResources"] = load_external_resources_metadata()
    metadata["Subject"]["subject_id"] = subject_id
    metadata["Subject"]["sex"] = subject_metadata["Sex"]
    metadata["NWBFile"]["session_id"] = session_config["session_id"]
    metadata["NWBFile"]["session_description"] = session_config["session_description"]
    metadata["NWBFile"]["session_start_time"] = session_start_time
    add_led_modulation_to_metadata(metadata=metadata, led_modulation=led_modulation)

    try:
        converter.run_conversion(
            metadata=metadata, nwbfile_path=nwbfile_path, conversion_options=conversion_options, overwrite=overwrite
        )
    finally:
        clear_tdt_block_cache()
    if verbose:
        print(f"Shock session of {subject_id} converted to {nwbfile_path}")
    return nwbfile_path
