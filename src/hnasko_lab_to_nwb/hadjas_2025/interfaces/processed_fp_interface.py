from pathlib import Path
import h5py
import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.fiber_photometry_table import add_fiber_photometry_table_region
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils.checks import calculate_regular_series_rate


def get_series_target_area(target_area: str, file_path: Path) -> str:
    """Get the target area used to look up the series metadata.

    The Anxa1 .mat files group subjects by stimulus site ("STN_to_Anxa1", "PPN_to_Anxa1").
    For these files the recording site is taken from the name of the folder holding the file
    (e.g. "Anxa1 DLS" gives "DLS").

    Parameters
    ----------
    target_area : str
        The target area group of the subject in the .mat file.
    file_path : Path
        Path to the .mat file.

    Returns
    -------
    str
        The target area of the series metadata.
    """
    if target_area in ("STN_to_Anxa1", "PPN_to_Anxa1"):
        return Path(file_path).parent.name.replace("Anxa1 ", "")
    return target_area


class Hadjas2025ProcessedFiberPhotometryInterface(BaseDataInterface):
    """
    Data Interface for converting processed fiber photometry data from Hnasko Lab custom .mat files.

    Extracts demodulated fiber photometry signals from MATLAB v7.3 files created by the Hnasko lab analysis
    pipeline. One segment of the .mat file is read per TDT block of the session, and the segments are written,
    concatenated, as one series in the ndx-fiber-photometry format.
    """

    keywords = ("processed fiber photometry",)
    display_name = "Hadjas2025ProcessedFiberPhotometry"
    info = "Data Interface for converting fiber photometry data from processed .mat files from Hnasko Lab."
    associated_suffixes = (".mat",)

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
        """Initialize the Hadjas2025ProcessedFiberPhotometryInterface.

        Parameters
        ----------
        file_path : FilePath
            The path to the .mat file containing the processed fiber photometry data.
        stream_name : str
            The processed stream, e.g. "Gc_raw", "af_raw", "Gc", "af" or "dF".
        subject_id : str
            The subject group in the .mat file.
        target_area : str
            The target area group of the subject in the .mat file.
        sampling_frequency : float
            The sampling frequency of the stream, in Hz.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(
            file_path=file_path,
            stream_name=stream_name,
            subject_id=subject_id,
            target_area=target_area,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
        )
        self._stream_name = stream_name
        self._target_area = target_area
        self._subject_id = subject_id
        self._sampling_frequency = sampling_frequency
        series_target_area = get_series_target_area(target_area=target_area, file_path=file_path)
        self.metadata_key = f"{stream_name}_{series_target_area}"

        with h5py.File(file_path, "r") as f:
            if target_area not in f[stream_name]:
                raise ValueError(f"Target area '{target_area}' not found. Available: {list(f[stream_name])}")
            if subject_id not in f[stream_name][target_area]:
                raise ValueError(
                    f"Subject '{subject_id}' not found in {target_area}. Available: {list(f[stream_name][target_area])}"
                )
            self._segment_names = list(f[stream_name][target_area][subject_id])

    def _extract_signal(self, stimulus_channel_name: str, t1: float = 0.0, t2: float = 0.0) -> np.ndarray:
        """
        Read one segment of the processed signal of the subject, between t1 and t2.

        Parameters
        ----------
        stimulus_channel_name : str
            The segment of the subject group, e.g. "LP5mW" or "s1s".
        t1 : float, optional
            Retrieve data starting at t1 (in seconds), default = 0 for start of recording.
        t2 : float, optional
            Retrieve data ending at t2 (in seconds), default = 0 for end of recording.

        Returns
        -------
        np.ndarray
            The extracted signal data.
        """
        start_index = int(t1 * self._sampling_frequency)
        end_index = int(t2 * self._sampling_frequency) if t2 != 0.0 else None
        with h5py.File(self.source_data["file_path"], "r") as f:
            dataset: h5py.Dataset = f[self._stream_name][self._target_area][self._subject_id][stimulus_channel_name]
            return dataset[0, start_index:end_index]  # segments are stored as (1, number of samples)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stimulus_channel_names: list[str],
        segment_starting_times: list[float],
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
        stimulus_channel_names : list[str]
            Segments of the .mat file to concatenate, one per TDT block.
        segment_starting_times : list[float]
            Starting time (in seconds) of each segment.
        stub_test : bool, optional
            If True, only add a subset of the data (1s per segment) to the NWBFile for testing purposes, default = False.
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
        for i, stimulus_channel_name in enumerate(stimulus_channel_names):
            if stimulus_channel_name not in self._segment_names:
                raise ValueError(
                    f"Segment '{stimulus_channel_name}' not found for {self._subject_id} in {self._target_area}. "
                    f"Available: {self._segment_names}"
                )
            data = self._extract_signal(t1=t1, t2=t2, stimulus_channel_name=stimulus_channel_name)
            timestamps = segment_starting_times[i] + t1 + np.arange(len(data)) / self._sampling_frequency
            data_segments.append(data)
            timestamps_segments.append(timestamps)

        concatenated_data = np.concatenate(data_segments)
        concatenated_timestamps = np.concatenate(timestamps_segments)

        # One segment is written with a rate; several segments keep each block's own times as timestamps
        if calculate_regular_series_rate(concatenated_timestamps) is not None:
            timing_kwargs = dict(starting_time=concatenated_timestamps[0], rate=self._sampling_frequency)
        else:
            timing_kwargs = dict(timestamps=concatenated_timestamps)

        fiber_photometry_response_series = FiberPhotometryResponseSeries(
            name=fiber_photometry_response_series_metadata["name"],
            description=fiber_photometry_response_series_metadata["description"],
            data=concatenated_data,
            unit=fiber_photometry_response_series_metadata["unit"],
            fiber_photometry_table_region=fiber_photometry_table_region,
            **timing_kwargs,
        )

        # Add ophys module for processed fiber photometry signals if it doesn't exist
        ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="Processed fiber photometry signals")
        ophys_module.add(fiber_photometry_response_series)
