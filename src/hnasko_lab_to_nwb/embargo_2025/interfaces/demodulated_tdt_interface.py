from typing import Literal
from collections.abc import MutableMapping

from ndx_fiber_photometry import FiberPhotometryResponseSeries
from ..utils.demodulate_fp_signal import demodulate_signal
from neuroconv.datainterfaces import TDTFiberPhotometryInterface


class DemodulatedTDTInterface(TDTFiberPhotometryInterface):
    keywords = ("fiber photometry",)
    display_name = "DemodulatedTDT"
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
        driver_freq: float,  
        **kwargs
    ):
        # Load the TDT photometry data for the specified time
        tdt_photometry = self.load(t1=t1, t2=t2)

        # Find the metadata for the raw modulated signal
        all_series_metadata = metadata["Ophys"]["FiberPhotometry"]["FiberPhotometryResponseSeries"] 
        raw_signal_metadata = next(
            series_md for series_md in all_series_metadata
            if series_md["name"] == "raw_modulated_signal"
        )

        # Access the corresponding data stream from the TDT photometry data
        stream_name = raw_signal_metadata["stream_name"]
        stream = tdt_photometry.streams[stream_name]
        data = stream.data
        rate = stream.fs

        # Demodulate the signal with specified driver frequency in parameter
        demodulated_signal = demodulate_signal(data, rate, driver_freq=driver_freq)

        # Add demodulated signal to the NWB file
        fiber_photometry = nwbfile.lab_meta_data["fiber_photometry"]
        fiber_photometry_table = fiber_photometry.fiber_photometry_table

        # Create a new processing module for fiber photometry signals if it doesn't exist
        if "ophys" not in nwbfile.processing:
            ophys_module = nwbfile.create_processing_module(
                name="ophys",
                description="Processed fiber photometry signals"
            )
        else:
            ophys_module = nwbfile.processing["ophys"]

        # Retrieve the name of the demodulated signal from the function arguments or Raise an Error
        signal_name = kwargs.get("name")
        if signal_name is None:
            raise ValueError("Missing 'name' for demodulated signal in conversion_options.")

        # Find the metadata for the demodulated signal
        response_metadata = next(
            series_md for series_md in metadata["Ophys"]["FiberPhotometry"]["DemodulatedFiberphotometryResponseSeries"]
            if series_md["name"] == signal_name
        )

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