from pynwb.file import NWBFile

from neuroconv.tools.fiber_photometry import (
    add_fiber_photometry_devices,
    add_fiber_photometry_lab_metadata,
    get_fiber_photometry_table_region,
)


def add_fiber_photometry_table_region(nwbfile: NWBFile, metadata: dict, metadata_key: str):
    """Add the shared fiber photometry devices and table (once per file) and return the region of one series.

    Parameters
    ----------
    nwbfile : NWBFile
        The in-memory object to add the data to.
    metadata : dict
        Metadata dictionary with the "Devices", "DeviceModels" and "FiberPhotometry" sections.
    metadata_key : str
        Key of the response series under metadata["FiberPhotometry"].

    Returns
    -------
    FiberPhotometryTableRegion
        The rows of the FiberPhotometryTable listed in the series' fiber_photometry_table_region.
    """
    fiber_photometry_metadata = metadata["FiberPhotometry"]
    add_fiber_photometry_devices(nwbfile=nwbfile, metadata=metadata)
    fiber_photometry_table = add_fiber_photometry_lab_metadata(nwbfile=nwbfile, metadata=metadata)
    series_metadata = fiber_photometry_metadata[metadata_key]
    return get_fiber_photometry_table_region(
        fiber_photometry_table=fiber_photometry_table,
        table_rows_metadata=fiber_photometry_metadata["FiberPhotometryTable"]["rows"],
        row_metadata_keys=series_metadata["fiber_photometry_table_region"],
        description=series_metadata["fiber_photometry_table_region_description"],
    )
