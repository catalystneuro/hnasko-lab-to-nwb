from copy import deepcopy
from logging import warning

from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseDataInterface
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model
from neuroconv.utils import DeepDict


def get_optogenetic_experiment_metadata(nwbfile: NWBFile, metadata: dict):
    """Get or create the OptogeneticExperimentMetadata in the NWBFile.

    Parameters
    ----------
    nwbfile : NWBFile
        The in-memory object to add the data to.
    metadata : dict
        Metadata dictionary with information used to create the NWBFile.

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
        ExcitationSourceModel,
        ExcitationSource,
        ViralVector,
        ViralVectorInjection,
        OpticalFiber,
        FiberInsertion,
    )

    #  check if Optogenetic lab metadata already exists
    if "optogenetics" in nwbfile.lab_meta_data:
        optogenetics = nwbfile.lab_meta_data["optogenetics"]
        if isinstance(optogenetics, OptogeneticExperimentMetadata):
            return optogenetics

    # Add Devices
    device_model_types = ["OpticalFiberModel", "ExcitationSourceModel"]
    for device_model_type in device_model_types:
        device_models_metadata = metadata["Optogenetics"].get(device_model_type + "s", [])
        for devices_metadata in device_models_metadata:
            add_ophys_device_model(
                nwbfile=nwbfile,
                device_metadata=devices_metadata,
                device_type=device_model_type,
            )
    device_type = "ExcitationSource"
    device_models_metadata = metadata["Optogenetics"].get(device_type + "s", [])
    for devices_metadata in device_models_metadata:
        add_ophys_device(
            nwbfile=nwbfile,
            device_metadata=devices_metadata,
            device_type=device_type,
        )

    # Add a dummy Optical Fibers (special case bc they have additional FiberInsertion objects)
    optical_fibers_metadata = metadata["Optogenetics"].get("OpticalFibers", [])
    for optical_fiber_metadata in optical_fibers_metadata:
        fiber_insertion_metadata = optical_fiber_metadata["fiber_insertion"]
        fiber_insertion = FiberInsertion(**fiber_insertion_metadata)
        optical_fiber_metadata = deepcopy(optical_fiber_metadata)
        optical_fiber_metadata["fiber_insertion"] = fiber_insertion
        assert (
            optical_fiber_metadata["model"] in nwbfile.device_models
        ), f"Device model {optical_fiber_metadata['model']} not found in NWBFile device_models for {optical_fiber_metadata['name']}."
        optical_fiber_metadata["model"] = nwbfile.device_models[optical_fiber_metadata["model"]]
        optical_fiber = OpticalFiber(**optical_fiber_metadata)
        nwbfile.add_device(optical_fiber)

    # Add Viral Vectors, Injections, and Effectors
    viral_vectors_metadata = metadata["Optogenetics"].get("OptogeneticViruses", [])
    name_to_viral_vector = {}
    for viral_vector_metadata in viral_vectors_metadata:
        viral_vector = ViralVector(**viral_vector_metadata)
        name_to_viral_vector[viral_vector.name] = viral_vector
    if len(name_to_viral_vector) > 0:
        viruses = OptogeneticViruses(viral_vectors=list(name_to_viral_vector.values()))
    else:
        viruses = None

    viral_vector_injections_metadata = metadata["Optogenetics"].get("OptogeneticVirusInjections", [])
    name_to_viral_vector_injection = {}
    for viral_vector_injection_metadata in viral_vector_injections_metadata:
        viral_vector = name_to_viral_vector[viral_vector_injection_metadata["viral_vector"]]
        viral_vector_injection_metadata = deepcopy(viral_vector_injection_metadata)
        viral_vector_injection_metadata["viral_vector"] = viral_vector
        viral_vector_injection = ViralVectorInjection(**viral_vector_injection_metadata)
        name_to_viral_vector_injection[viral_vector_injection.name] = viral_vector_injection
    if len(name_to_viral_vector_injection) > 0:
        virus_injections = OptogeneticVirusInjections(
            viral_vector_injections=list(name_to_viral_vector_injection.values())
        )
    else:
        virus_injections = None

    effectors_metadata = metadata["Optogenetics"].get("OptogeneticEffectors", [])
    name_to_indicator = {}
    for effector_metadata in effectors_metadata:
        if "viral_vector_injection" in effector_metadata:
            viral_vector_injection = name_to_viral_vector_injection[effector_metadata["viral_vector_injection"]]
            effector_metadata = deepcopy(effector_metadata)
            effector_metadata["viral_vector_injection"] = viral_vector_injection
        effector = Effector(**effector_metadata)
        name_to_indicator[effector.name] = effector
    if len(name_to_indicator) > 0:
        effectors = OptogeneticEffectors(effectors=list(name_to_indicator.values()))
    else:
        raise ValueError("At least one effector must be specified in the metadata.")

    sites_table_metadata = metadata["Optogenetics"].get("OptogeneticSitesTable", {})
    optogenetic_sites_table = OptogeneticSitesTable(
        name=sites_table_metadata["name"], description=sites_table_metadata["description"]
    )
    device_fields = [
        "optical_fiber",
        "excitation_source",
    ]
    for row_metadata in metadata["Optogenetics"]["OptogeneticSitesTable"]["rows"]:
        row_data = {field: nwbfile.devices[row_metadata[field]] for field in device_fields if field in row_metadata}
        if "effector" in row_metadata:
            row_data["effector"] = name_to_indicator[row_metadata["effector"]]
        optogenetic_sites_table.add_row(**row_data)

    # Optogenetic Experiment Metadata
    optogenetic_experiment_metadata = OptogeneticExperimentMetadata(
        stimulation_software=metadata["Optogenetics"]["stimulation_software"],
        optogenetic_sites_table=optogenetic_sites_table,
        optogenetic_viruses=viruses,
        optogenetic_virus_injections=virus_injections,
        optogenetic_effectors=effectors,
    )
    nwbfile.add_lab_meta_data(optogenetic_experiment_metadata)

    return optogenetic_experiment_metadata


class Lofti2025TDTOptogeneticStimulusInterface(BaseDataInterface):
    """
    Data Interface for converting processed optogenetic stimulus data from a Hnasko Lab tdt files.

    Extracts demodulated optogenetic stimulus signals from TDT system, then parses into the ndx-optogenetic format.

    Verified to work with:
    - SNr GABA recordings (PPN stimulation)
    - GRAB-DA recordings (DLS & TS sites, PPN stimulation)
    - SNc pan-DA recordings (STN stimulation)
    """

    keywords = ("processed optogenetic stimulus",)
    display_name = "Lofti2025TDTOptogeneticStimulus"
    info = "Data Interface for converting optogenetic stimulus data from processed .tdt files from Hnasko Lab."
    associated_suffixes = (".tdt",)

    @validate_call
    def __init__(
        self,
        folder_path: DirectoryPath,
        stimulus_site: str,
        verbose: bool = True,
    ):
        """Initialize the Lofti2025TDTOptogeneticStimulusInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the .mat file containing the processed optogenetic stimulus data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        super().__init__(
            folder_path=folder_path,
            verbose=verbose,
        )
        # This module should be here so ndx_optogenetics is in the global namespace when an pynwb.io object is created

        # Cache available sites and subjects
        self._stimulus_site = stimulus_site

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the Lofti2025TDTOptogeneticStimulusInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the Lofti2025TDTOptogeneticStimulusInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def get_events(self) -> dict:
        """
        Get the events from the Lofti2025TDTOptogeneticStimulusInterface.

        Returns
        -------
        dict
            The events dictionary for this interface.
        """
        from neuroconv.datainterfaces import TDTFiberPhotometryInterface

        tdt_interface = TDTFiberPhotometryInterface(folder_path=self.source_data["folder_path"])
        events = tdt_interface.get_events()
        return events

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        tdt_stimulus_channel_to_frequency: dict,
        stub_test: bool = False,
    ):
        """
        Add the data to an NWBFile.

        Parameters
        ----------
        nwbfile : pynwb.NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary with information used to create the NWBFile.
        stub_test : bool, optional
            If True, only add a subset of the data (1s) to the NWBFile for testing purposes, default = False.
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
        # Populate
        tdt_events = self.get_events()
        for stream_name, stimulus_frequency in tdt_stimulus_channel_to_frequency.items():
            if stream_name not in tdt_events:
                warning(f"Stream name {stream_name} not found in TDT events. Skipping.")
                continue
            for start_time, stop_time in zip(tdt_events[stream_name]["onset"], tdt_events[stream_name]["offset"]):
                number_pulses_per_pulse_train = int((stop_time - start_time) * stimulus_frequency)
                opto_epochs_table.add_row(
                    start_time=start_time,
                    stop_time=stop_time,
                    stimulus_frequency=stimulus_frequency,
                    stimulation_on=True,
                    pulse_length_in_ms=1.0,  # Unknown
                    period_in_ms=(1 / stimulus_frequency) * 1000,
                    number_pulses_per_pulse_train=number_pulses_per_pulse_train,
                    number_trains=1,
                    intertrain_interval_in_ms=0.0,
                    power_in_mW=metadata["Optogenetics"]["power_in_mW"],
                    wavelength_in_nm=metadata["Optogenetics"]["excitation_wavelength_in_nm"],
                    optogenetic_sites=[0],  # TODO select the correct site by stimulus location
                )

        nwbfile.add_time_intervals(opto_epochs_table)
