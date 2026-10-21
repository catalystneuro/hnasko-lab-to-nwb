from datetime import datetime
from typing import List

import numpy as np
import pytz
from pydantic import DirectoryPath, validate_call
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.fiber_photometry_table import add_fiber_photometry_table_region
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces import TDTFiberPhotometryInterface
from neuroconv.utils.checks import calculate_regular_series_rate


class ConcatenatedTDTFiberPhotometryInterface(BaseDataInterface):
    """
    Data Interface for converting and concatenating fiber photometry data from multiple TDT output folders.

    Each TDT output folder consists of a variety of TDT-specific file types (e.g. Tbk, Tdx, tev, tin, tsq).
    One stream is read from each folder with the tdt.read_block function, concatenated, and written as a single
    FiberPhotometryResponseSeries in the ndx-fiber-photometry format.
    """

    keywords = ("fiber photometry", "concatenated")
    display_name = "ConcatenatedTDTFiberPhotometry"
    info = "Data Interface for converting and concatenating fiber photometry data from multiple TDT folders."
    associated_suffixes = ("Tbk", "Tdx", "tev", "tin", "tsq")

    @validate_call
    def __init__(
        self,
        folder_paths: List[DirectoryPath],
        stream_name: str,
        metadata_key: str,
        stream_indices: list[int] | None = None,
        verbose: bool = False,
    ):
        """Initialize the ConcatenatedTDTFiberPhotometryInterface.

        Parameters
        ----------
        folder_paths : List[DirectoryPath]
            The paths to the TDT output folders, in chronological order.
        stream_name : str
            The TDT stream (store) to concatenate, e.g. "Fi1r".
        metadata_key : str
            Key of the response series metadata under metadata["FiberPhotometry"].
        stream_indices : list of int, optional
            Channels of the stream to keep. None keeps all channels.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            folder_paths=folder_paths,
            stream_name=stream_name,
            metadata_key=metadata_key,
            stream_indices=stream_indices,
            verbose=verbose,
        )
        self.stream_name = stream_name
        self.metadata_key = metadata_key
        self.stream_indices = stream_indices
        self._tdt_interfaces = []
        session_start_datetimes = []
        for folder_path in folder_paths:
            tdt_interface = TDTFiberPhotometryInterface(folder_path=folder_path, stream_names=[stream_name])
            tdt_photometry = tdt_interface.load(evtype=["scalars"])
            start_timestamp = tdt_photometry.info.start_date.timestamp()
            session_start_datetime = datetime.fromtimestamp(start_timestamp, tz=pytz.utc)
            session_start_datetimes.append(session_start_datetime)
            self._tdt_interfaces.append(tdt_interface)
        # check that the session start times are in chronological order
        assert session_start_datetimes == sorted(session_start_datetimes), (
            "Session start times are not in chronological order. Please provide folder paths in chronological order."
        )
        # Calculate segment start times based on the session start datetimes
        # E.g. we have three consecutive sessions starting at times 10:00, 10:20, and 10:40 on the same day
        # we want segment_starting_times to be [0, 1200, 2400] (in seconds)
        self.segment_starting_times = [
            (dt - session_start_datetimes[0]).total_seconds() for dt in session_start_datetimes
        ]

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
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
        fill_gaps : bool, optional
            If True, fill the gaps between segments with NaNs, default = False.
        stub_test : bool, optional
            If True, only add a subset of the data (1s) to the NWBFile for testing purposes, default = False.
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.
        """
        from ndx_fiber_photometry import FiberPhotometryResponseSeries

        fiber_photometry_response_series_metadata = metadata["FiberPhotometry"][self.metadata_key]
        fiber_photometry_table_region = add_fiber_photometry_table_region(
            nwbfile=nwbfile, metadata=metadata, metadata_key=self.metadata_key
        )

        data_segments = []
        timestamps_segments = []
        if stub_test:
            assert t2 == 0.0, (
                f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            )
            t2 = t1 + 1.0
        for i, tdt_interface in enumerate(self._tdt_interfaces):
            tdt_photometry = tdt_interface.load(t1=t1, t2=t2, evtype=["streams"], store=self.stream_name)
            stream = tdt_photometry.streams[self.stream_name]

            # TDT stores are (channels, samples); keep the selected channels as a 1D series
            data = np.asarray(stream.data)
            if data.ndim == 2:
                data = data.T
                if self.stream_indices is not None:
                    data = data[:, self.stream_indices]
                data = data.flatten()
            timestamps = self.segment_starting_times[i] + np.arange(len(data)) / stream.fs

            data_segments.append(data)
            timestamps_segments.append(timestamps)

            # Add trials for each segment
            if len(self._tdt_interfaces) > 1:
                tag = tdt_interface.source_data["folder_path"].parts[-2].replace("varFreq_", "")
                nwbfile.add_trial(start_time=timestamps[0], stop_time=timestamps[-1], tags=tag)

        concatenated_data = np.concatenate(data_segments)
        concatenated_timestamps = np.concatenate(timestamps_segments)

        # Fill gaps with NaNs
        if fill_gaps:
            from hnasko_lab_to_nwb.hadjas_2025.utils import fill_gaps_w_nans

            concatenated_data, concatenated_timestamps = fill_gaps_w_nans(
                data=concatenated_data,
                timestamps=concatenated_timestamps,
                sampling_rate=stream.fs,
            )

        # One block, or blocks padded onto one grid, are written with a rate
        if calculate_regular_series_rate(concatenated_timestamps) is not None:
            timing_kwargs = dict(starting_time=concatenated_timestamps[0], rate=float(stream.fs))
        else:
            timing_kwargs = dict(timestamps=concatenated_timestamps)

        fiber_photometry_response_series = FiberPhotometryResponseSeries(
            name=fiber_photometry_response_series_metadata["name"],
            description=fiber_photometry_response_series_metadata["description"],
            data=concatenated_data,
            unit="a.u.",
            fiber_photometry_table_region=fiber_photometry_table_region,
            **timing_kwargs,
        )
        nwbfile.add_acquisition(fiber_photometry_response_series)
