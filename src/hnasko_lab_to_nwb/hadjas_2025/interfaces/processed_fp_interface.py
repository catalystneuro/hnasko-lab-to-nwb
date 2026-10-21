from pathlib import Path
from typing import Dict, List, Literal

import h5py
import numpy as np
from pydantic import FilePath, validate_call
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces.fiber_photometry_table import add_fiber_photometry_table_region
from neuroconv.basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict


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


class Hadjas2025ProcessedFiberPhotometryInterface(BaseTemporalAlignmentInterface):
    """
    Data Interface for converting processed fiber photometry data from a Hnasko Lab custom .mat files.

    Extracts demodulated fiber photometry signals from MATLAB v7.3 files created by
    the Hnasko lab analysis pipeline, then parses into the ndx-fiber-photometry format.

    Verified to work with:
    - SNr GABA recordings
    - GRAB-DA recordings
    - SNc pan-DA recordings
    - Str_DA terminal recordings
    - Cell-type specific recordings
    """

    keywords = ("processed fiber photometry",)
    display_name = "DemodulatedFiberPhotometry"
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
        stimulus_channel_name: None | str = None,
        t1: float = 0.0,
        t2: float = 0.0,
    ) -> np.ndarray:
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
        if stimulus_channel_name is None:
            stimulus_channel_name = self.available_stimulus_channel_names[self._target_area][self._subject_id][0]
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

    def get_num_samples(self, stimulus_channel_name: None | str = None) -> int:
        """
        Get the number of samples in the data.
        Returns
        -------
        int
            The number of samples.
        """
        signal = self._extract_signal(stimulus_channel_name=stimulus_channel_name)
        return len(signal)

    def get_original_timestamps(self, stimulus_channel_name: None | str = None) -> np.ndarray:
        """
        Get the original timestamps for the data.

        Returns
        -------
        np.ndarray
            The original timestamps.
        """
        num_samples = self.get_num_samples(stimulus_channel_name=stimulus_channel_name)
        rate = self.get_sampling_frequency()
        original_timestamps = np.arange(num_samples) / rate

        return original_timestamps

    def get_timestamps(self, t1: float = 0.0, t2: float = 0.0, stimulus_channel_name: None | str = None) -> np.ndarray:
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
            timestamps = self.get_original_timestamps(stimulus_channel_name=stimulus_channel_name) + self._starting_time

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

        fiber_photometry_response_series_metadata = metadata["FiberPhotometry"][self.metadata_key]
        fiber_photometry_table_region = add_fiber_photometry_table_region(
            nwbfile=nwbfile, metadata=metadata, metadata_key=self.metadata_key
        )
        # Validate stimulus channel name
        if stimulus_channel_name not in self.available_stimulus_channel_names[self._target_area][self._subject_id]:
            raise ValueError(
                f"stimulus channel name '{stimulus_channel_name}' not found for {self._subject_id} in {self._target_area}. Available: {self.available_stimulus_channel_names[self._target_area][self._subject_id]}"
            )
        # Load Data
        if stub_test:
            assert t2 == 0.0, (
                f"stub_test cannot be used with a specified t2 ({t2}). Use t2=0.0 for stub_test or set stub_test=False."
            )
            t2 = t1 + 1.0
        data = self._extract_signal(t1=t1, t2=t2, stimulus_channel_name=stimulus_channel_name)
        # Get the timing information
        if timing_source == "aligned_timestamps":
            timestamps = self.get_timestamps(t1=t1, t2=t2)
            timing_kwargs = dict(timestamps=timestamps)
        elif timing_source == "aligned_starting_time_and_rate":
            rate = self.get_sampling_frequency()
            starting_time = self.get_timestamps(t1=t1, t2=t2)[0]
            timing_kwargs = dict(starting_time=starting_time, rate=rate)
        else:
            assert timing_source == "original", (
                "timing_source must be one of 'original', 'aligned_timestamps', or 'aligned_starting_time_and_rate'."
            )
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


class ConcatenatedHadjas2025ProcessedFiberPhotometryInterface(Hadjas2025ProcessedFiberPhotometryInterface):
    """
    Data Interface for converting and concatenating multiple processed fiber photometry data files from Hnasko Lab custom .mat files.

    Extracts demodulated fiber photometry signals from multiple MATLAB v7.3 files created by
    the Hnasko lab analysis pipeline, then parses into the ndx-fiber-photometry format.

    Verified to work with:
    - SNr GABA recordings (PPN stimulation)
    - GRAB-DA recordings (DLS & TS sites, PPN stimulation)
    - SNc pan-DA recordings (STN stimulation)
    """

    keywords = ("processed fiber photometry", "concatenated")
    display_name = "ConcatenatedDemodulatedFiberPhotometry"
    info = "Data Interface for converting and concatenating multiple fiber photometry data from processed .mat files from Hnasko Lab."
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
        """Initialize the ConcatenatedHadjas2025ProcessedFiberPhotometryInterface.

        Parameters
        ----------
        file_path: FilePath
            The path to the .mat file containing the processed fiber photometry data.
        verbose : bool, optional
            Whether to print status messages, default = True.
        """
        super().__init__(
            file_path=file_path,
            stream_name=stream_name,
            subject_id=subject_id,
            target_area=target_area,
            sampling_frequency=sampling_frequency,
            verbose=verbose,
        )

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
            List of stimulus channel names to concatenate.
        segment_starting_times : list[float]
            List of starting times (in seconds) for each segment to concatenate.
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
        from ndx_fiber_photometry import (
            FiberPhotometryResponseSeries,
        )

        fiber_photometry_response_series_metadata = metadata["FiberPhotometry"][self.metadata_key]
        fiber_photometry_table_region = add_fiber_photometry_table_region(
            nwbfile=nwbfile, metadata=metadata, metadata_key=self.metadata_key
        )
        # Validate stimulus channel name
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
            # Load Data
            data = self._extract_signal(t1=t1, t2=t2, stimulus_channel_name=stimulus_channel_name)

            # Get the timing information
            timestamps = segment_starting_times[i] + t1 + np.arange(len(data)) / self.get_sampling_frequency()
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
                sampling_rate=self.get_sampling_frequency(),
            )

            from neuroconv.utils.checks import calculate_regular_series_rate

            calculated_rate = calculate_regular_series_rate(concatenated_timestamps)
            if calculated_rate is not None:
                timing_kwargs = dict(starting_time=concatenated_timestamps[0], rate=calculated_rate)
            else:
                timing_kwargs = dict(timestamps=concatenated_timestamps)
        else:
            timing_kwargs = dict(timestamps=concatenated_timestamps)

        fiber_photometry_response_series = FiberPhotometryResponseSeries(
            name=fiber_photometry_response_series_metadata["name"],
            description=fiber_photometry_response_series_metadata["description"],
            data=concatenated_data.T,
            unit=fiber_photometry_response_series_metadata["unit"],
            fiber_photometry_table_region=fiber_photometry_table_region,
            **timing_kwargs,
        )

        # Add ophys module for processed fiber photometry signals if it doesn't exist
        ophys_module = get_module(nwbfile=nwbfile, name="ophys", description="Processed fiber photometry signals")
        ophys_module.add(fiber_photometry_response_series)
