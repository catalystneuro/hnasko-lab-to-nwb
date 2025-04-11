from pynwb import NWBFile
from pynwb.base import DynamicTable, DynamicTableRegion
from pynwb.file import TimeSeries

def add_demodulated_signals_to_processing(nwbfile: NWBFile, calcium_signal, isosbestic_signal, timestamps):
    """
    Add demodulated calcium and isosbestic signals to the processing module.

    Parameters:
    -----------
    nwbfile : NWBFile
        The NWB file where the signals will be added.
    calcium_signal : array-like
        Demodulated calcium signal.
    isosbestic_signal : array-like
        Demodulated isosbestic signal.
    timestamps : array-like
        Timestamps corresponding to the signals.
    """

    ###### Review the table same as add_fiber_photometry_response_series
    # Create or retrieve the FiberPhotometryTable
    if "FiberPhotometry" not in nwbfile.processing:
        fiber_photometry_table = DynamicTable(
            name="FiberPhotometryTable",
            description="Table containing metadata for fiber photometry recordings.",
        )
        nwbfile.add_processing_module(
            name="FiberPhotometry",
            description="Processing module for fiber photometry data.",
        ).add(fiber_photometry_table)
    else:
        fiber_photometry_table = nwbfile.processing["FiberPhotometry"]["FiberPhotometryTable"]

    
    # Add rows to the FiberPhotometryTable if empty 
    if len(fiber_photometry_table) == 0:
        fiber_photometry_table.add_row(
            description="The region of the FiberPhotometryTable corresponding to the raw calcium signal.",
        )
        fiber_photometry_table.add_row(
            description="The region of the FiberPhotometryTable corresponding to the raw isosbestic signal.",
        )

    # Create region references for the table rows
    calcium_region = DynamicTableRegion(
        name="fiber_photometry_table_region",
        data=[0],  # First row for calcium signal
        description="The region of the FiberPhotometryTable corresponding to the raw calcium signal.",
        table=fiber_photometry_table,
    )
    isosbestic_region = DynamicTableRegion(
        name="fiber_photometry_table_region",
        data=[1],  # Second row for isosbestic signal  
        description="The region of the FiberPhotometryTable corresponding to the raw isosbestic signal.",
        table=fiber_photometry_table,
    )

    # Add FiberPhotometryResponseSeries for calcium signal
    calcium_series = TimeSeries(
        name="calcium_signal",
        description="The raw fiber photometry signal from Tucker David Technologies (TDT) acquisition system.",
        data=calcium_signal,
        timestamps=timestamps,
        unit="a.u.",
        fiber_photometry_table_region=calcium_region,
    )

    # Add FiberPhotometryResponseSeries for isosbestic signal
    isosbestic_series = TimeSeries(
        name="isosbestic_signal",
        description="The raw fiber photometry signal from Tucker David Technologies (TDT) acquisition system.",
        data=isosbestic_signal,
        timestamps=timestamps,
        unit="a.u.",
        fiber_photometry_table_region=isosbestic_region,
    )

    # Add the series to the processing module
    nwbfile.processing["FiberPhotometry"].add(calcium_series)
    nwbfile.processing["FiberPhotometry"].add(isosbestic_series)
