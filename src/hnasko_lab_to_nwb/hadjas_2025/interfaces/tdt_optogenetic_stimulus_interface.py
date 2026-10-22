import logging
from pathlib import Path
from typing import List
import numpy as np

from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import read_tdt_epocs, read_tdt_start_timestamp
from hnasko_lab_to_nwb.hadjas_2025.utils.train_durations import label_train_duration
from neuroconv.basetemporalalignmentinterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import _add_device_to_nwbfile
from neuroconv.utils import DeepDict

logger = logging.getLogger(__name__)


def get_optogenetic_experiment_metadata(nwbfile: NWBFile, metadata: dict):
    """Get or create the OptogeneticExperimentMetadata in the NWBFile.

    Parameters
    ----------
    nwbfile : NWBFile
        The in-memory object to add the data to.
    metadata : dict
        Metadata dictionary with the "Optogenetics" section and the "Devices" and "DeviceModels" registry.

    Returns
    -------
    OptogeneticExperimentMetadata
        The OptogeneticExperimentMetadata object.
    """
    from ndx_optogenetics import (
        OptogeneticSitesTable,
        OptogeneticViruses,
        OptogeneticVirusInjections,
        OptogeneticEffectors,
        OptogeneticExperimentMetadata,
    )
    from ndx_ophys_devices import (
        Effector,
        ViralVector,
        ViralVectorInjection,
    )

    # Reuse the optogenetic experiment metadata if it was already added (its name is fixed by ndx-optogenetics)
    for lab_meta_data in nwbfile.lab_meta_data.values():
        if isinstance(lab_meta_data, OptogeneticExperimentMetadata):
            return lab_meta_data

    optogenetics_metadata = metadata["Optogenetics"]

    # Add Viral Vectors, Injections, and Effectors
    key_to_viral_vector = {
        key: ViralVector(**viral_vector_metadata)
        for key, viral_vector_metadata in optogenetics_metadata.get("OptogeneticViruses", {}).items()
    }
    viruses = OptogeneticViruses(viral_vectors=list(key_to_viral_vector.values())) if key_to_viral_vector else None

    key_to_injection = {}
    for key, injection_metadata in optogenetics_metadata.get("OptogeneticVirusInjections", {}).items():
        injection_metadata = dict(injection_metadata)
        injection_metadata["viral_vector"] = key_to_viral_vector[injection_metadata.pop("viral_vector_metadata_key")]
        key_to_injection[key] = ViralVectorInjection(**injection_metadata)
    virus_injections = (
        OptogeneticVirusInjections(viral_vector_injections=list(key_to_injection.values()))
        if key_to_injection
        else None
    )

    key_to_effector = {}
    for key, effector_metadata in optogenetics_metadata.get("OptogeneticEffectors", {}).items():
        effector_metadata = dict(effector_metadata)
        injection_key = effector_metadata.pop("viral_vector_injection_metadata_key", None)
        if injection_key is not None:
            effector_metadata["viral_vector_injection"] = key_to_injection[injection_key]
        key_to_effector[key] = Effector(**effector_metadata)
    if len(key_to_effector) == 0:
        raise ValueError("At least one effector must be specified in the metadata.")
    effectors = OptogeneticEffectors(effectors=list(key_to_effector.values()))

    # Optogenetic sites, with devices from the shared Devices registry
    sites_table_metadata = optogenetics_metadata["OptogeneticSitesTable"]
    optogenetic_sites_table = OptogeneticSitesTable(
        name=sites_table_metadata["name"], description=sites_table_metadata["description"]
    )
    for row_metadata in sites_table_metadata["rows"].values():
        row_data = {}
        for field in ("optical_fiber", "excitation_source"):
            if f"{field}_metadata_key" in row_metadata:
                row_data[field] = _add_device_to_nwbfile(
                    nwbfile=nwbfile, metadata=metadata, metadata_key=row_metadata[f"{field}_metadata_key"]
                )
        if "effector_metadata_key" in row_metadata:
            row_data["effector"] = key_to_effector[row_metadata["effector_metadata_key"]]
        optogenetic_sites_table.add_row(**row_data)

    # Optogenetic Experiment Metadata
    optogenetic_experiment_metadata = OptogeneticExperimentMetadata(
        stimulation_software=optogenetics_metadata["stimulation_software"],
        optogenetic_sites_table=optogenetic_sites_table,
        optogenetic_viruses=viruses,
        optogenetic_virus_injections=virus_injections,
        optogenetic_effectors=effectors,
    )
    nwbfile.add_lab_meta_data(optogenetic_experiment_metadata)

    return optogenetic_experiment_metadata


class Hadjas2025TDTOptogeneticStimulusInterface(BaseDataInterface):
    """
    Data Interface for converting and concatenating optogenetic stimulus data from multiple Hnasko Lab tdt folders.

    Extracts optogenetic stimulus signals from TDT system, then parses into the ndx-optogenetic format.

    Verified to work with:
    - SNr GABA recordings (PPN stimulation)
    - GRAB-DA recordings (DLS & TS sites, PPN stimulation)
    - SNc pan-DA recordings (STN stimulation)
    """

    keywords = ("processed optogenetic stimulus",)
    display_name = "Hadjas2025TDTOptogeneticStimulus"
    info = "Data Interface for converting optogenetic stimulus data from .tdt files from Hnasko Lab."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_paths: List[DirectoryPath],
        verbose: bool = True,
    ):
        """Initialize the Hadjas2025TDTOptogeneticStimulusInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the .mat file containing the processed optogenetic stimulus data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        super().__init__(
            folder_paths=folder_paths,
            verbose=verbose,
        )
        # This module should be here so ndx_optogenetics is in the global namespace when an pynwb.io object is created

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Hadjas2025TDTOptogeneticStimulusInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the Hadjas2025TDTOptogeneticStimulusInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def get_events(self) -> dict:
        """
        Get the epocs of all blocks, with times in seconds from the start of the first block.

        Returns
        -------
        dict
            {epoc name: {"onset": list, "offset": list, "block_name": list}}, with the name of the TDT block folder
            of each event.
        """
        folder_paths = self.source_data["folder_paths"]
        start_timestamps = [read_tdt_start_timestamp(folder_path) for folder_path in folder_paths]
        assert start_timestamps == sorted(start_timestamps), (
            "Session start times are not in chronological order. Please provide folder paths in chronological order."
        )
        all_events = {}
        for folder_path, start_timestamp in zip(folder_paths, start_timestamps):
            segment_start_time = start_timestamp - start_timestamps[0]
            for stream_name, stream_events in read_tdt_epocs(folder_path).items():
                if stream_name not in all_events:
                    all_events[stream_name] = {"onset": [], "offset": [], "block_name": []}
                all_events[stream_name]["onset"].extend(stream_events["onset"] + segment_start_time)
                all_events[stream_name]["offset"].extend(stream_events["offset"] + segment_start_time)
                all_events[stream_name]["block_name"].extend([Path(folder_path).name] * len(stream_events["onset"]))

        return all_events

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        tdt_stimulus_channel_to_frequency: dict,
    ):
        """
        Add the data to an NWBFile.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary with information used to create the NWBFile.
        tdt_stimulus_channel_to_frequency : dict
            Mapping of TDT stimulus channel names to their corresponding frequencies.
        """
        from ndx_optogenetics import (
            OptogeneticEpochsTable,
        )

        # Get or create OptogeneticEpochsTable
        optogenetic_experiment_metadata = get_optogenetic_experiment_metadata(nwbfile=nwbfile, metadata=metadata)
        optogenetic_sites_table = optogenetic_experiment_metadata.optogenetic_sites_table
        # Create stimulation epochs table if it doesn't exist
        opto_epochs_table = OptogeneticEpochsTable(
            **metadata["Optogenetics"]["OptogeneticEpochsTable"],
            target_tables={"optogenetic_sites": optogenetic_sites_table},
        )
        opto_epochs_table.add_column(name="stimulus_frequency", description="Frequency of the stimulation in Hz.")
        opto_epochs_table.add_column(
            name="train_duration",
            description="Duration of the train in the protocol (250ms, 1s, 4s or 16s); the recorded duration is "
            "stop_time - start_time.",
        )
        opto_epochs_table.add_column(name="tdt_block", description="Name of the TDT block folder of the train.")
        # Populate
        tdt_events = self.get_events()
        if not set(tdt_stimulus_channel_to_frequency) & set(tdt_events):
            raise ValueError(
                f"None of the stimulation epocs {list(tdt_stimulus_channel_to_frequency)} is in the TDT events "
                f"{list(tdt_events)}."
            )
        trains = []  # (start time, stop time, pulse frequency, TDT block) of every train
        for stream_name, stimulus_frequency in tdt_stimulus_channel_to_frequency.items():
            if stream_name not in tdt_events:
                continue
            onsets = np.asarray(tdt_events[stream_name]["onset"], dtype=float)
            offsets = np.asarray(tdt_events[stream_name]["offset"], dtype=float)
            block_names = np.asarray(tdt_events[stream_name]["block_name"])
            # Trains without an offset (recording stopped first), of zero length, or of a duration that is not the
            # protocol's (electrical artifacts, e.g. the 0.54 s events of C2659) are not written
            train_durations = [label_train_duration(duration) for duration in offsets - onsets]
            is_valid = (
                np.isfinite(onsets)
                & np.isfinite(offsets)
                & (offsets > onsets)
                & np.array([train_duration is not None for train_duration in train_durations], dtype=bool)
            )
            if not is_valid.all():
                logger.warning(
                    f"Dropped {np.count_nonzero(~is_valid)} of {is_valid.size} {stream_name} trains without an "
                    f"offset, of zero length or of a duration that is not the protocol's."
                )
            trains.extend(
                (start_time, stop_time, stimulus_frequency, block_name)
                for start_time, stop_time, block_name in zip(onsets[is_valid], offsets[is_valid], block_names[is_valid])
            )
        for start_time, stop_time, stimulus_frequency, block_name in sorted(trains):
            number_pulses_per_pulse_train = int((stop_time - start_time) * stimulus_frequency)
            opto_epochs_table.add_row(
                start_time=start_time,
                stop_time=stop_time,
                stimulus_frequency=stimulus_frequency,
                train_duration=label_train_duration(stop_time - start_time),
                tdt_block=str(block_name),
                stimulation_on=True,
                pulse_length_in_ms=np.nan,  # TDT stores only the train onsets and offsets
                period_in_ms=(1 / stimulus_frequency) * 1000,
                number_pulses_per_pulse_train=number_pulses_per_pulse_train,
                number_trains=1,
                intertrain_interval_in_ms=0.0,
                power_in_mW=metadata["Optogenetics"]["power_in_mW"],
                wavelength_in_nm=metadata["Optogenetics"]["excitation_wavelength_in_nm"],
                optogenetic_sites=[0],  # assuming single stimulation site for now
            )

        nwbfile.add_time_intervals(opto_epochs_table)
