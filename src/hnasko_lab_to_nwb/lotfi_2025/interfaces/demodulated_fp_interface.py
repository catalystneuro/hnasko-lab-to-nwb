from copy import deepcopy
from typing import Dict, List, Literal

import h5py
import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict


def get_fiber_photometry_table(nwbfile: NWBFile, metadata: dict):
    """Get or create the FiberPhotometryTable in the NWBFile.

    Parameters
    ----------
    nwbfile : NWBFile
        The in-memory object to add the data to.
    metadata : dict
        Metadata dictionary with information used to create the NWBFile.

    Returns
    -------
    FiberPhotometryTable
        The FiberPhotometryTable object.
    """
    from ndx_fiber_photometry import (
        FiberPhotometry,
        FiberPhotometryIndicators,
        FiberPhotometryTable,
        FiberPhotometryViruses,
        FiberPhotometryVirusInjections,
    )
    from ndx_ophys_devices import (
        FiberInsertion,
        Indicator,
        OpticalFiber,
        ViralVector,
        ViralVectorInjection,
    )

    #  check if FiberPhotometry lab metadata already exists
    if "fiber_photometry" in nwbfile.lab_meta_data:
        fiber_photometry = nwbfile.lab_meta_data["fiber_photometry"]
        if isinstance(fiber_photometry, FiberPhotometry):
            # Check if tables have matching rows by comparing key attributes
            table_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]
            if fiber_photometry.fiber_photometry_table.name == table_metadata["name"]:
                existing_table = fiber_photometry.fiber_photometry_table
                metadata_rows = table_metadata["rows"]
                # Check if row counts match
                if len(existing_table) == len(metadata_rows):
                    return existing_table

    # Add Devices
    device_model_types = [
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ]
    for device_type in device_model_types:
        device_models_metadata = metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", [])
        for devices_metadata in device_models_metadata:
            add_ophys_device_model(
                nwbfile=nwbfile,
                device_metadata=devices_metadata,
                device_type=device_type,
            )
    device_types = [
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ]
    for device_type in device_types:
        devices_metadata = metadata["Ophys"]["FiberPhotometry"].get(device_type + "s", [])
        for device_metadata in devices_metadata:
            add_ophys_device(
                nwbfile=nwbfile,
                device_metadata=device_metadata,
                device_type=device_type,
            )

    # Add Optical Fibers (special case bc they have additional FiberInsertion objects)
    optical_fibers_metadata = metadata["Ophys"]["FiberPhotometry"].get("OpticalFibers", [])
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

    # Add Viral Vectors, Injections, and Indicators
    viral_vectors_metadata = metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryViruses", [])
    name_to_viral_vector = {}
    for viral_vector_metadata in viral_vectors_metadata:
        viral_vector = ViralVector(**viral_vector_metadata)
        name_to_viral_vector[viral_vector.name] = viral_vector
    if len(name_to_viral_vector) > 0:
        viruses = FiberPhotometryViruses(viral_vectors=list(name_to_viral_vector.values()))
    else:
        viruses = None

    viral_vector_injections_metadata = metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryVirusInjections", [])
    name_to_viral_vector_injection = {}
    for viral_vector_injection_metadata in viral_vector_injections_metadata:
        viral_vector = name_to_viral_vector[viral_vector_injection_metadata["viral_vector"]]
        viral_vector_injection_metadata = deepcopy(viral_vector_injection_metadata)
        viral_vector_injection_metadata["viral_vector"] = viral_vector
        viral_vector_injection = ViralVectorInjection(**viral_vector_injection_metadata)
        name_to_viral_vector_injection[viral_vector_injection.name] = viral_vector_injection
    if len(name_to_viral_vector_injection) > 0:
        virus_injections = FiberPhotometryVirusInjections(
            viral_vector_injections=list(name_to_viral_vector_injection.values())
        )
    else:
        virus_injections = None

    indicators_metadata = metadata["Ophys"]["FiberPhotometry"].get("FiberPhotometryIndicators", [])
    name_to_indicator = {}
    for indicator_metadata in indicators_metadata:
        if "viral_vector_injection" in indicator_metadata:
            viral_vector_injection = name_to_viral_vector_injection[indicator_metadata["viral_vector_injection"]]
            indicator_metadata = deepcopy(indicator_metadata)
            indicator_metadata["viral_vector_injection"] = viral_vector_injection
        indicator = Indicator(**indicator_metadata)
        name_to_indicator[indicator.name] = indicator
    if len(name_to_indicator) > 0:
        indicators = FiberPhotometryIndicators(indicators=list(name_to_indicator.values()))
    else:
        raise ValueError("At least one indicator must be specified in the metadata.")

    # Fiber Photometry Table
    fiber_photometry_table = FiberPhotometryTable(
        name=metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["name"],
        description=metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["description"],
    )
    required_fields = [
        "location",
        "excitation_wavelength_in_nm",
        "emission_wavelength_in_nm",
        "indicator",
        "optical_fiber",
        "excitation_source",
        "photodetector",
        "dichroic_mirror",
    ]
    device_fields = [
        "optical_fiber",
        "excitation_source",
        "photodetector",
        "dichroic_mirror",
        "excitation_filter",
        "emission_filter",
    ]
    for row_metadata in metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryTable"]["rows"]:
        for field in required_fields:
            assert (
                field in row_metadata
            ), f"FiberPhotometryTable metadata row {row_metadata['name']} is missing required field {field}."
        row_data = {field: nwbfile.devices[row_metadata[field]] for field in device_fields if field in row_metadata}
        row_data["location"] = row_metadata["location"]
        row_data["excitation_wavelength_in_nm"] = row_metadata["excitation_wavelength_in_nm"]
        row_data["emission_wavelength_in_nm"] = row_metadata["emission_wavelength_in_nm"]
        if "indicator" in row_metadata:
            row_data["indicator"] = name_to_indicator[row_metadata["indicator"]]
        if "coordinates" in row_metadata:
            row_data["coordinates"] = row_metadata["coordinates"]
        fiber_photometry_table.add_row(**row_data)
    fiber_photometry_table_metadata = FiberPhotometry(
        name="fiber_photometry",
        fiber_photometry_table=fiber_photometry_table,
        fiber_photometry_viruses=viruses,
        fiber_photometry_virus_injections=virus_injections,
        fiber_photometry_indicators=indicators,
    )
    nwbfile.add_lab_meta_data(fiber_photometry_table_metadata)

    return fiber_photometry_table


def get_fp_series_metadata(metadata: dict, stream_name: str, target_area: str) -> dict:
    """Get the metadata for the FiberPhotometryResponseSeries.

    Parameters
    ----------
    metadata : dict
        Metadata dictionary with information used to create the NWBFile.
    stream_name : str
        The name of the stream to extract.
    target_area : str
        The target area to extract.

    Returns
    -------
    dict
        The metadata dictionary for the FiberPhotometryResponseSeries.
    """
    all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["ProcessedFiberPhotometryResponseSeries"]
    # Find the metadata for the specified stream_name and target_area
    for series_metadata in all_series_metadata:
        if series_metadata["stream_name"] == stream_name and series_metadata.get("target_area") == target_area:
            fiber_photometry_response_series_metadata = deepcopy(series_metadata)
            break
    return fiber_photometry_response_series_metadata


class Lofti2025DemodulatedFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting processed fiber photometry data from a Hnasko Lab custom .mat files.

    Extracts demodulated fiber photometry signals from MATLAB v7.3 files created by
    the Hnasko lab analysis pipeline, then parses into the ndx-fiber-photometry format.

    Verified to work with:
    - SNr GABA recordings (PPN stimulation)
    - GRAB-DA recordings (DLS & TS sites, PPN stimulation)
    - SNc pan-DA recordings (STN stimulation)
    """

    keywords = ("processed fiber photometry",)
    display_name = "DemodulatedFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from processed .mat files from Hnasko Lab."
    associated_suffixes = ".mat"

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        stream_name: str,
        subject_id: str,
        target_area: str,
        sampling_frequency: float,
        verbose: bool = False,
    ):
        """Initialize the DemodulatedFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the .mat file containing the processed fiber photometry data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        super().__init__(
            file_path=file_path,
            verbose=verbose,
        )
        # This module should be here so ndx_fiber_photometry is in the global namespace when an pynwb.io object is created

        # Cache available sites and subjects
        self._sites = None
        self._subjects = None
        self._stream_name = stream_name
        self._target_area = target_area
        self._subject_id = subject_id
        self._sampling_frequency = sampling_frequency
        self._starting_time = 0.0
        self._num_samples = None

        self._scan_file_structure()
        if target_area not in self.available_sites:
            raise ValueError(f"Target area '{target_area}' not found. Available: {self.available_sites}")
        if subject_id not in self.available_subjects[target_area]:
            raise ValueError(
                f"Subject '{subject_id}' not found in {target_area}. Available: {self.available_subjects[target_area]}"
            )

    @property
    def available_sites(self) -> List[str]:
        """Get list of available recording sites"""
        if self._sites is None:
            self._scan_file_structure()
        return self._sites

    @property
    def available_subjects(self) -> Dict[str, List[str]]:
        """Get dictionary of available subjects per site"""
        if self._subjects is None:
            self._scan_file_structure()
        return self._subjects

    @property
    def available_stimulus_channel_names(self) -> Dict[str, List[str]]:
        """Get dictionary of available stimulus channel names per site and subject"""
        if self._stimulus_channel_names is None:
            self._scan_file_structure()
        return self._stimulus_channel_names

    def _scan_file_structure(self) -> None:
        """Scan file to determine available sites, subjects and stimulus channel names."""
        try:
            with h5py.File(self.source_data["file_path"], "r") as f:
                signal_group = f[self._stream_name]  # type: ignore
                # Get sites
                self._sites = list(signal_group.keys())

                # Get subjects per site
                self._stimulus_channel_names = {}
                self._subjects = {}
                for site in self._sites:
                    self._stimulus_channel_names[site] = {}
                    self._subjects[site] = list(signal_group[site].keys())
                    for subject in self._subjects[site]:
                        subject_group: h5py.Group = signal_group[site][subject]  # type: ignore
                        self._stimulus_channel_names[site][subject] = list(subject_group.keys())

        except Exception as e:
            raise RuntimeError(f"Error scanning file structure: {e}")

    def _extract_signal(
        self,
        stimulus_channel_name: str,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> Dict[str, np.ndarray]:
        """
        Extract processed fiber photometry signal for a specific subject.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        np.ndarray
            The extracted signal data.
        """
        try:
            with h5py.File(self.source_data["file_path"], "r") as f:
                stream_group: h5py.Group = f[self._stream_name]  # type: ignore
                site_group: h5py.Group = stream_group[self._target_area]  # type: ignore
                subject_group: h5py.Group = site_group[self._subject_id]  # type: ignore
                dataset: h5py.Dataset = subject_group[stimulus_channel_name]  # type: ignore
                signal = dataset[:].flatten()
                rate = self.get_sampling_frequency()
                start_index = int(t1 * rate) if t1 != 0.0 else 0
                end_index = int(t2 * rate) if t2 != 0.0 else signal.shape[0]

                return signal[start_index:end_index]

        except Exception as e:
            # TODO expose what are the objects in the subject group for easier debugging
            raise RuntimeError(f"Error extracting signals for {self._subject_id} {self._target_area}: {e}.")

    def get_metadata(self) -> DeepDict:
        """
        Get metadata for the DemodulatedFiberPhotometryInterface.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        return metadata

    def get_metadata_schema(self) -> dict:
        """
        Get the metadata schema for the DemodulatedFiberPhotometryInterface.

        Returns
        -------
        dict
            The metadata schema for this interface.
        """
        metadata_schema = super().get_metadata_schema()
        return metadata_schema

    def get_sampling_frequency(self) -> float:
        """
        Get the sampling rate for a specific stream.

        Returns
        -------
        float
            The sampling rate in Hz.
        """
        return self._sampling_frequency

    def get_num_samples(self) -> int:
        """
        Get the number of samples in the data.
        Returns
        -------
        int
            The number of samples.
        """
        if self._num_samples is None:
            signal = self._extract_signal()
            self._num_samples = len(signal)
        return self._num_samples

    def get_original_timestamps(self) -> np.ndarray:
        """
        Get the original timestamps for the data.

        Returns
        -------
        np.ndarray
            The original timestamps.
        """
        num_samples = self.get_num_samples()
        rate = self.get_sampling_frequency()
        original_timestamps = np.arange(0.0, num_samples / rate, 1 / rate)

        return original_timestamps

    def get_timestamps(self, t1: float = 0.0, t2: float = 0.0) -> np.ndarray:
        """
        Get the timestamps for the data.

        Parameters
        ----------
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        np.ndarray
            The timestamps.
        """
        if hasattr(self, "aligned_timestamps"):
            timestamps = self.aligned_timestamps
        else:
            timestamps = self.get_original_timestamps() + self._starting_time

        timestamps = timestamps[timestamps >= t1]
        if t2 != 0.0:
            timestamps = timestamps[timestamps < t2]
        return timestamps

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        """
        Set the aligned timestamps for the data.

        Parameters
        ----------
        aligned_timestamps : np.ndarray
            The aligned timestamps.
        """
        self.aligned_timestamps = aligned_timestamps

    def set_aligned_starting_time(self, aligned_starting_time: float) -> None:
        """
        Set the aligned starting time for the data.

        Parameters
        ----------
        aligned_starting_time : float
            The aligned starting time.
        """
        self._starting_time = aligned_starting_time

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stimulus_channel_name: str,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
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
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        timing_source : Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"], optional
            Source of timing information for the data, default = "original".

        Raises
        ------
        AssertionError
            If the timing_source is not one of "original", "aligned_timestamps", or "aligned_starting_time_and_rate".
        """
        from ndx_fiber_photometry import (
            FiberPhotometryResponseSeries,
        )

        if stimulus_channel_name not in self.available_stimulus_channel_names[self._target_area][self._subject_id]:
            raise ValueError(
                f"stimulus channel name '{stimulus_channel_name}' not found for {self._subject_id} in {self._target_area}. Available: {self.available_stimulus_channel_names[self._target_area][self._subject_id]}"
            )

        # Load Data
        if stub_test:
            assert (
                t2 == 0.0
            ), f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            t2 = t1 + 1.0
        data = self._extract_signal(t1=t1, t2=t2, stimulus_channel_name=stimulus_channel_name)

        # Get series metadata
        fiber_photometry_response_series_metadata = get_fp_series_metadata(
            metadata=metadata, stream_name=self._stream_name, target_area=self._target_area
        )

        # Get or create FiberPhotometryTable
        fiber_photometry_table = get_fiber_photometry_table(nwbfile=nwbfile, metadata=metadata)
        fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            description=fiber_photometry_response_series_metadata["fiber_photometry_table_region_description"],
            region=fiber_photometry_response_series_metadata["fiber_photometry_table_region"],
        )

        # Get the timing information
        if timing_source == "aligned_timestamps":
            timestamps = self.get_timestamps(t1=t1, t2=t2)
            timing_kwargs = dict(timestamps=timestamps)
        elif timing_source == "aligned_starting_time_and_rate":
            rate = self.get_sampling_frequency()
            starting_time = self.get_timestamps(t1=t1, t2=t2)[0]
            timing_kwargs = dict(starting_time=starting_time, rate=rate)
        else:
            assert (
                timing_source == "original"
            ), "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."
            rate = self.get_sampling_frequency()
            starting_time = 0.0
            timing_kwargs = dict(starting_time=starting_time, rate=rate)

        fiber_photometry_response_series = FiberPhotometryResponseSeries(
            name=fiber_photometry_response_series_metadata["name"],
            description=fiber_photometry_response_series_metadata["description"],
            data=data,
            unit=fiber_photometry_response_series_metadata["unit"],
            fiber_photometry_table_region=fiber_photometry_table_region,
            **timing_kwargs,
        )

        # Add ophys module for processed fiber photometry signals if it doesn't exist
        ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="Processed fiber photometry signals")
        ophys_module.add(fiber_photometry_response_series)
