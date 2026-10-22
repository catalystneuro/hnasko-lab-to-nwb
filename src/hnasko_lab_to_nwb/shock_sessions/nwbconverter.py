"""Primary NWBConverter class for this dataset."""

from typing import Optional

from pynwb import NWBFile

from hnasko_lab_to_nwb.shock_sessions.interfaces import (
    TDTDemodulatedFiberPhotometryInterface,
)
from hnasko_lab_to_nwb.shock_sessions.utils import (
    add_auditory_stimuli,
    add_shock_stimuli,
)
from neuroconv import NWBConverter
from neuroconv.datainterfaces import TDTFiberPhotometryInterface


class Hadjas2025NWBConverter(NWBConverter):
    """Primary conversion class for the fiber photometry shock sessions."""

    data_interface_classes = dict(
        FiberPhotometry=TDTFiberPhotometryInterface,
        DemodulatedFiberPhotometry_Calcium=TDTDemodulatedFiberPhotometryInterface,
        DemodulatedFiberPhotometry_Isosbestic=TDTDemodulatedFiberPhotometryInterface,
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        if "FiberPhotometry" in self.data_interface_objects.keys():
            tdt_interface = self.data_interface_objects["FiberPhotometry"]
            tdt_events = tdt_interface.get_events()
            if "ShockStimulusInterval" in metadata["Stimulus"]:
                add_shock_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
                add_auditory_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
