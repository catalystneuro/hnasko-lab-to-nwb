from pynwb import NWBFile 
from pynwb.base import DynamicTable, DynamicTableRegion  
from pynwb.file import TimeSeries 
def add_fiber_photometry_response_series(nwbfile: NWBFile, metadata: dict, tdt_interface):
    """
    Add a FiberPhotometryResponseSeries to the acquisition module of an NWB file.

    Parameters
    ----------
    nwbfile: NWBFile
        The NWB file where the FiberPhotometryResponseSeries will be added.
    metadata: dict
        Metadata for the FiberPhotometryResponseSeries.
    tdt_interface: object
        Instance of TDTFiberPhotometryInterface to retrieve raw signal and timestamps.
    """
    # Extract metadata for the FiberPhotometryResponseSeries.
    series_metadata = metadata["FiberPhotometryResponseSeries"]
    stream_name = series_metadata["stream_name"]  # Get the stream name from the metadata. 
    #### Should Fi1r be hardcoded into the streamname or keep flexible? 

    raw_signal = tdt_interface.get_signal(stream_name=stream_name)
    timestamps = tdt_interface.get_timestamps(stream_name=stream_name)

    ## Review the whole creation of the table what is expected vs what is done here 
    if "FiberPhotometry" not in nwbfile.processing:
        # Create a new DynamicTable for fiber photometry metadata if it doesn't exist.  (?????? Not sure) 
        fiber_photometry_table = DynamicTable(
            name="FiberPhotometryTable",
            description="Table containing metadata for fiber photometry recordings.",
        )
        # Add the table to a new processing module named "FiberPhotometry". (?????? Not sure) 
        nwbfile.add_processing_module(
            name="FiberPhotometry",
            description="Processing module for fiber photometry data.",
        ).add(fiber_photometry_table)
    else:
        # Retrieve the existing FiberPhotometryTable if it already exists.(?????? Not sure) 
        fiber_photometry_table = nwbfile.processing["FiberPhotometry"]["FiberPhotometryTable"]

    # Add a row to the FiberPhotometryTable if it is empty.(?????? Not sure) to keep ????? 
    if len(fiber_photometry_table) == 0:
        fiber_photometry_table.add_row(
            description="The raw fiber photometry signal from Tucker David Technologies (TDT) acquisition system.",
        )

    # Create a region reference to the first row of the FiberPhotometryTable.
    table_region = DynamicTableRegion(
        name="fiber_photometry_table_region",
        data=[0],  # Reference the first row of the table. ?
        description="The region of the FiberPhotometryTable corresponding to the raw signal.",
        table=fiber_photometry_table,  # Link the region to the FiberPhotometryTable.
    )

    # Create a TimeSeries object for the FiberPhotometryResponseSeries.
    fiber_photometry_series = TimeSeries( ####### Verify the use of TimeSeries
        name="fiber_photometry_modulated_signal",  
        description="The raw fiber photometry signal from Tucker David Technologies (TDT) acquisition system.", 
        data=raw_signal, 
        timestamps=timestamps,  
        unit="a.u.",  
        fiber_photometry_table_region=table_region,  
    )

    
    nwbfile.add_acquisition(fiber_photometry_series)
