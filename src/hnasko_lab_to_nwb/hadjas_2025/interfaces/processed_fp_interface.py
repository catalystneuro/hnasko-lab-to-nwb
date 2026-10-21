from pathlib import Path
from typing import Dict, List

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
        return self._sites

    @property
    def available_subjects(self) -> Dict[str, List[str]]:
        """Get dictionary of available subjects per site"""
        return self._subjects

    @property
    def available_stimulus_channel_names(self) -> Dict[str, List[str]]:
        """Get dictionary of available stimulus channel names per site and subject"""
        return self._stimulus_channel_names

    def _scan_file_structure(self) -> None:
        """Scan file to determine available sites, subjects and stimulus channel names."""
        try:
            with h5py.File(self.source_data["file_path"], "r") as f:
                signal_group = f[self._stream_name]  # type: ignore
                self._sites = list(signal_group.keys())
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

    def _extract_signal(self, stimulus_channel_name: str, t1: float = 0.0, t2: float = 0.0) -> np.ndarray:
        """
        Extract one segment of the processed signal of the subject.

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
        try:
            with h5py.File(self.source_data["file_path"], "r") as f:
                dataset: h5py.Dataset = f[self._stream_name][self._target_area][self._subject_id][stimulus_channel_name]
                signal = dataset[:].flatten()
                start_index = int(t1 * self._sampling_frequency) if t1 != 0.0 else 0
                end_index = int(t2 * self._sampling_frequency) if t2 != 0.0 else signal.shape[0]
                return signal[start_index:end_index]
        except Exception as e:
            raise RuntimeError(f"Error extracting signals for {self._subject_id} {self._target_area}: {e}.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        *,
        stimulus_channel_names: list[str],
        segment_starting_times: list[float],
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
        stimulus_channel_names : list[str]
            Segments of the .mat file to concatenate, one per TDT block.
        segment_starting_times : list[float]
            Starting time (in seconds) of each segment.
        fill_gaps : bool, optional
            If True, fill the gaps between segments with NaNs, default = False.
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
            if stimulus_channel_name not in self.available_stimulus_channel_names[self._target_area][self._subject_id]:
                raise ValueError(
                    f"stimulus channel name '{stimulus_channel_name}' not found for {self._subject_id} in {self._target_area}. "
                    f"Available: {self.available_stimulus_channel_names[self._target_area][self._subject_id]}"
                )
            data = self._extract_signal(t1=t1, t2=t2, stimulus_channel_name=stimulus_channel_name)
            timestamps = segment_starting_times[i] + t1 + np.arange(len(data)) / self._sampling_frequency
            data_segments.append(data)
            timestamps_segments.append(timestamps)

        concatenated_data = np.concatenate(data_segments)
        concatenated_timestamps = np.concatenate(timestamps_segments)

        # Fill gaps with NaNs
        if fill_gaps:
            from hnasko_lab_to_nwb.hadjas_2025.utils import fill_gaps_w_nans

            concatenated_data, concatenated_timestamps = fill_gaps_w_nans(
                data=concatenated_data,
                timestamps=concatenated_timestamps,
                sampling_rate=self._sampling_frequency,
            )

        # One segment, or segments padded onto one grid, are written with a rate
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
