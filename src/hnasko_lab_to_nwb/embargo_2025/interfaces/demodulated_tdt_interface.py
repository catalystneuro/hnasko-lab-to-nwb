from typing import Literal

from ndx_fiber_photometry import FiberPhotometryResponseSeries

from ..utils.demodulate_fp_signal import demodulate_signal
from neuroconv.datainterfaces import TDTFiberPhotometryInterface


class TDTDemodulatedFiberPhotometryInterface(TDTFiberPhotometryInterface):
    """Interface for adding demodulated fiber photometry data from TDT files to NWB files.
    
    This interface extends TDTFiberPhotometryInterface with functionality to demodulate 
    raw modulated signals using specified driver frequency.
    """

    keywords = ("fiber photometry",)
    display_name = "DemodulatedTDTFiberPhotometry"
    info = "Data Interface for converting demodulated fiber photometry data from TDT files."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict,
        *,
        stub_test: bool = False,
        t1: float = 0.0,
        t2: float = 0.0,
        timing_source: Literal["original", "aligned_timestamps", "aligned_starting_time_and_rate"] = "original",
        driver_freq: float = None,  
        name: str = None,
    ):
        """
        Add demodulated fiber photometry data to an NWB file.
        
        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to which the data will be added.
        metadata : dict
            Metadata dictionary containing information about the fiber photometry data.
        stub_test : bool, optional
            Whether to just run a stub test, default is False.
        t1 : float, optional
            Start time of the data to load, default is 0.0.
        t2 : float, optional
            End time of the data to load, default is 0.0.
        timing_source : str, optional
            Timing source to use, one of 'original', 'aligned_timestamps', 
            or 'aligned_starting_time_and_rate', default is 'original'.
        driver_freq : float
            The driver frequency used for demodulation.
        name : str
            The name of the demodulated signal series.
        **kwargs : dict
            Additional keyword arguments.
        
        Raises
        ------
        ValueError
            If required parameters are missing or invalid.
        """

        if driver_freq is None or driver_freq  <= 0:
            raise ValueError("driver_freq is a required parameter and must be a positive number representing the frequency used for demodulation.")
        
        if name is None:
            raise ValueError("Required parameter 'name' is missing for demodulated signal.")
        
        # Load the TDT photometry data for the specified time
        tdt_photometry = self.load(t1=t1, t2=t2)

        # Find the metadata for the raw modulated signal
        all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"] 
        try : 
            raw_signal_metadata = next(
                series_md for series_md in all_series_metadata
                if series_md["name"] == "raw_modulated_signal" 
            )
        except StopIteration: 
            raise ValueError("Missing 'raw_modulated_signal' in metadata for demodulated signal.")

        # Access the corresponding data stream from the TDT photometry data
        stream_name = raw_signal_metadata["stream_name"]
        try:
            stream = tdt_photometry.streams[stream_name]
        except KeyError:
            raise ValueError(f"Stream '{stream_name}' not found in TDT data.")
        
        data = stream.data
        rate = stream.fs

        # Demodulate the signal with specified driver frequency in parameter
        demodulated_signal = demodulate_signal(data, rate, driver_freq=driver_freq)

        # Add demodulated signal to the NWB file
        try:
            fiber_photometry = nwbfile.lab_meta_data["fiber_photometry"]
            fiber_photometry_table = fiber_photometry.fiber_photometry_table
        except KeyError:
            raise ValueError("Fiber photometry metadata not found in NWB file.")


        # Create a new processing module for fiber photometry signals if it doesn't exist
        if "ophys" not in nwbfile.processing:
            ophys_module = nwbfile.create_processing_module(
                name="ophys",
                description="Processed fiber photometry signals"
            )
        else:
            ophys_module = nwbfile.processing["ophys"]

        # Retrieve the name of the demodulated signal from the function arguments or Raise an Error
        signal_name = name

        # Find the metadata for the demodulated signal
        try:
            response_metadata = next(
                series_md for series_md in metadata["Ophys"]["FiberPhotometry"]["DemodulatedFiberPhotometryResponseSeries"]
                if series_md["name"] == signal_name
            )
        except (KeyError, StopIteration):
            raise ValueError(f"Metadata for demodulated signal '{signal_name}' not found.")
        

        # Create a FiberPhotometryTableRegion for the demodulated signal
        table_region = fiber_photometry_table.create_fiber_photometry_table_region(
            description=response_metadata["fiber_photometry_table_region_description"],
            region=response_metadata["fiber_photometry_table_region"],
        )

        # Create a FiberPhotometryResponseSeries for the demodulated signal
        series = FiberPhotometryResponseSeries(
            name=signal_name,
            description=response_metadata["description"],
            data=demodulated_signal,
            unit=response_metadata["unit"],
            fiber_photometry_table_region=table_region,
            starting_time=stream.start_time,
            rate=rate,
        )

        # Add the FiberPhotometryResponseSeries to the NWB file
        ophys_module.add(series)