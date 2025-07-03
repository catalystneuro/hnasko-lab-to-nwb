"""Primary NWBConverter class for this dataset."""

from typing import Optional

from pynwb import NWBFile

from hnasko_lab_to_nwb.embargo_2025.interfaces import (
    TDTDemodulatedFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.embargo_2025.utils import (
    add_auditory_stimuli,
    add_optogenetic_stimulation,
    add_shock_stimuli,
)
from neuroconv import NWBConverter
from neuroconv.datainterfaces import ExternalVideoInterface, TDTFiberPhotometryInterface


class Embargo2025NWBConverter(NWBConverter):
    """Primary conversion class for my extracellular electrophysiology dataset."""

    data_interface_classes = dict(
        FiberPhotometry=TDTFiberPhotometryInterface,
        DemodulatedFiberPhotometry_Calcium=TDTDemodulatedFiberPhotometryInterface,
        DemodulatedFiberPhotometry_Isosbestic=TDTDemodulatedFiberPhotometryInterface,
        Video=ExternalVideoInterface,
        Video_250ms=ExternalVideoInterface,
        Video_1s=ExternalVideoInterface,
        Video_4s=ExternalVideoInterface,
    )

    def __init__(self, source_data: dict, verbose: bool = True, video_time_alignment_dict: Optional[dict] = None):
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
        """
        super().__init__(source_data=source_data, verbose=verbose)
        self.video_time_alignment_dict = video_time_alignment_dict or {}

    def temporally_align_data_interfaces(self, metadata: dict | None = None, conversion_options: dict | None = None):
        if self.video_time_alignment_dict:
            for video_interface_name, video_info in self.video_time_alignment_dict.items():
                video_interface = self.data_interface_objects.get(video_interface_name)
                video_timestamps = video_interface.get_timestamps()
                aligned_timestamps = []
                for video_segment in video_timestamps:
                    aligned_timestamps.append(video_segment + video_info["video_starting_time"])
                self.data_interface_objects[video_interface_name].set_aligned_timestamps(
                    aligned_timestamps=aligned_timestamps
                )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        if "FiberPhotometry" in self.data_interface_objects.keys():
            tdt_interface = self.data_interface_objects["FiberPhotometry"]
            tdt_events = tdt_interface.get_events()

            if "OptogeneticStimulusInterval" in metadata["Stimulus"]:
                add_optogenetic_stimulation(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
            if "ShockStimulusInterval" in metadata["Stimulus"]:
                add_shock_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
                add_auditory_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
