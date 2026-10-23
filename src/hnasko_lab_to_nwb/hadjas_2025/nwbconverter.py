"""Primary NWBConverter class for this dataset."""

from typing import Optional

from pynwb import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.interfaces import (
    ConcatenatedTDTFiberPhotometryInterface,
    Hadjas2025ProcessedFiberPhotometryInterface,
    Hadjas2025TDTOptogeneticStimulusInterface,
)
from neuroconv import NWBConverter
from neuroconv.datainterfaces import ExternalVideoInterface


class Hadjas2025NWBConverter(NWBConverter):
    """Primary conversion class for the Hadjas 2025 fiber photometry and optogenetics dataset."""

    def __init__(
        self,
        source_data: dict,
        verbose: bool = True,
        video_time_alignment_dict: Optional[dict] = None,
        block_trials: Optional[list[dict]] = None,
    ):
        """
        Initialize the NWBConverter with source data and optional video time alignment.

        Parameters
        ----------
        source_data : dict
            Dictionary containing the source data for conversion.
        verbose : bool, optional
            Whether to print verbose output during conversion, by default True.
        video_time_alignment_dict : Optional[dict], optional
            Dictionary for aligning video timestamps with session metadata, by default None.
        block_trials : Optional[list[dict]], optional
            One trial per TDT block of a session of several blocks, or per train duration of a varying-frequencies
            session of one block, as add_trial arguments (start_time, stop_time, tags), by default None.
        """
        data_interface_name_mapping = {
            "Video": ExternalVideoInterface,
            "RawFiberPhotometry": ConcatenatedTDTFiberPhotometryInterface,
            "DemodulatedFiberPhotometry": Hadjas2025ProcessedFiberPhotometryInterface,
            "DownsampledFiberPhotometry": Hadjas2025ProcessedFiberPhotometryInterface,
            "DeltaFOverF": Hadjas2025ProcessedFiberPhotometryInterface,
            "OptogeneticStimulus": Hadjas2025TDTOptogeneticStimulusInterface,
        }
        for interface_name in source_data.keys():
            for key, interface_class in data_interface_name_mapping.items():
                if interface_name.startswith(key):
                    self.data_interface_classes[interface_name] = interface_class

        super().__init__(source_data=source_data, verbose=verbose)
        self.video_time_alignment_dict = video_time_alignment_dict or {}
        self.block_trials = block_trials or []

    def temporally_align_data_interfaces(self, metadata: dict | None = None, conversion_options: dict | None = None):
        # Keep the frame times of each .mp4 (frames were dropped in the AnyMaze export) and shift them to the TDT clock
        for video_interface_name, video_info in self.video_time_alignment_dict.items():
            video_interface = self.data_interface_objects[video_interface_name]
            temporal_alignment = video_interface.temporal_alignment
            for key, frame_times in zip(temporal_alignment.keys(), video_interface.get_original_timestamps()):
                temporal_alignment[key].set_times(frame_times + video_info["video_starting_time"])

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)

        for trial in self.block_trials:
            nwbfile.add_trial(**trial)
