from copy import deepcopy
from datetime import datetime
from typing import List

import numpy as np
import pytz
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.tools.fiber_photometry import add_ophys_device, add_ophys_device_model


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


def get_fp_series_metadata(metadata: dict, stream_name: str) -> dict:
    """Get the metadata for the FiberPhotometryResponseSeries.

    Parameters
    ----------
    metadata : dict
        Metadata dictionary with information used to create the NWBFile.
    stream_name : str
        The name of the stream to extract.

    Returns
    -------
    dict
        The metadata dictionary for the FiberPhotometryResponseSeries.
    """
    all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"]
    # Find the metadata for the specified stream_name and target_area
    for series_metadata in all_series_metadata:
        if series_metadata["stream_name"] == stream_name:
            fiber_photometry_response_series_metadata = deepcopy(series_metadata)
            break
    return fiber_photometry_response_series_metadata


class ConcatenatedTDTFiberPhotometryInterface(TDTFiberPhotometryInterface):
    """
    Data Interface for converting and concatenating fiber photometry data from multiple TDT output folders.

    Each TDT output folder consists of a variety of TDT-specific file types (e.g. Tbk, Tdx, tev, tin, tsq).
    Data from multiple folders is read by the tdt.read_block function, concatenated, and then parsed into the ndx-fiber-photometry format.
    """

    keywords = ("fiber photometry", "concatenated")
    display_name = "ConcatenatedTDTFiberPhotometry"
    info = "Data Interface for converting and concatenating fiber photometry data from multiple TDT folders."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_paths: List[DirectoryPath],
        verbose: bool = False,
    ):
        """Initialize the ConcatenatedTDTFiberPhotometryInterface.

        Parameters
        ----------
        folder_paths : List[DirectoryPath]
            The paths to the TDT output folders containing the processed fiber photometry data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        self._tdt_interfaces = []
        session_start_datetimes = []
        for folder_path in folder_paths:
            tdt_interface = TDTFiberPhotometryInterface(folder_path, verbose=verbose)
            tdt_photometry = tdt_interface.load(evtype=["scalars"])
            start_timestamp = tdt_photometry.info.start_date.timestamp()
            session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=pytz.utc)
            session_start_datetimes.append(session_start_datetime)
            self._tdt_interfaces.append(tdt_interface)
        # check that the session start times are in chronological order
        assert session_start_datetimes == sorted(
            session_start_datetimes
        ), "Session start times are not in chronological order. Please provide folder paths in chronological order."
        # Calculate segment start times based on the session start datetimes
        # E.g. we have three consecutive sessions starting at times 10:00, 10:20, and 10:40 on the same day
        # we want segment_starting_times to be [0, 1200, 2400] (in seconds)
        self.segment_starting_times = [
            (dt - session_start_datetimes[0]).total_seconds() for dt in session_start_datetimes
        ]

        super().__init__(folder_path=folder_paths[0], verbose=verbose)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stream_name: str,
        fill_gaps: bool = False,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
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

        Raises
        ------
        AssertionError
            If the timing_source is not one of "original", "aligned_timestamps", or "aligned_starting_time_and_rate".
        """
        from ndx_fiber_photometry import FiberPhotometryResponseSeries

        # Fiber Photometry Response Series
        fiber_photometry_response_series_metadata = get_fp_series_metadata(metadata=metadata, stream_name=stream_name)
        stream_indices = fiber_photometry_response_series_metadata.get("stream_indices", None)

        fiber_photometry_table = get_fiber_photometry_table(nwbfile, metadata)
        concatenated_timestamps = []
        concatenated_data = []
        for i, tdt_interface in enumerate(self._tdt_interfaces):

            # Load Data
            if stub_test:
                assert (
                    t2 == 0.0
                ), f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
                t2 = t1 + 1.0

            tdt_photometry = tdt_interface.load(t1=t1, t2=t2)

            # timing_source is used to avoid loading the data twice if alignment is NOT used.
            # It is also used to determine whether or not to use the aligned timestamps or starting time and rate.
            stream_name_to_timestamps = tdt_interface.get_timestamps(t1=t1, t2=t2)

            # Get the timing information
            timestamps = stream_name_to_timestamps[stream_name] + self.segment_starting_times[i]

            # Get the data
            data = tdt_photometry.streams[stream_name].data
            if stream_indices is not None:
                data = tdt_photometry.streams[stream_name].data[stream_indices, :]

                # Transpose the data if it is in the wrong shape
                if data.shape[0] < data.shape[1]:
                    data = data.T
            # if data shape > 1 D, flatten it
            if len(data.shape) > 1:
                data = data.flatten()
            if len(data.shape) > 1:
                data = data.flatten()
            concatenated_data = np.concatenate((concatenated_data, data))
            concatenated_timestamps = np.concatenate((concatenated_timestamps, timestamps))

            # Add trials for each segment
            if len(self._tdt_interfaces) > 1:
                tag = tdt_interface.source_data["folder_path"].parts[-2].replace("varFreq_", "")
                nwbfile.add_trial(start_time=timestamps[0], stop_time=timestamps[-1], tags=tag)

        # Fill gaps with NaNs
        if fill_gaps:
            from hnasko_lab_to_nwb.lotfi_2025.utils import fill_gaps_w_nans

            concatenated_data, concatenated_timestamps = fill_gaps_w_nans(
                data=concatenated_data,
                timestamps=concatenated_timestamps,
                sampling_rate=tdt_photometry.streams[stream_name].fs,
            )
            from neuroconv.utils.checks import calculate_regular_series_rate

            calculated_rate = calculate_regular_series_rate(concatenated_timestamps, tolerance_decimals=2)
            if calculated_rate is not None:
                timing_kwargs = dict(starting_time=concatenated_timestamps[0], rate=calculated_rate)
            else:
                timing_kwargs = dict(timestamps=concatenated_timestamps)
        else:
            timing_kwargs = dict(timestamps=concatenated_timestamps)

        fiber_photometry_table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            description=fiber_photometry_response_series_metadata["fiber_photometry_table_region_description"],
            region=fiber_photometry_response_series_metadata["fiber_photometry_table_region"],
        )

        fiber_photometry_response_series = FiberPhotometryResponseSeries(
            name=fiber_photometry_response_series_metadata["name"],
            description=fiber_photometry_response_series_metadata["description"],
            data=concatenated_data,
            unit=fiber_photometry_response_series_metadata["unit"],
            fiber_photometry_table_region=fiber_photometry_table_region,
            timestamps=concatenated_timestamps,
        )
        nwbfile.add_acquisition(fiber_photometry_response_series)
