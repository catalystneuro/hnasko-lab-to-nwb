"""Primary NWBConverter class for this dataset."""

from typing import Optional

import pynwb
from pynwb import NWBFile

from utils.add_fiber_photometry_response_series import add_fiber_photometry_response_series
from utils import add_auditory_stimuli, add_optogenetic_stimulation, add_shock_stimuli
from utils.add_demodulated_signals import add_demodulated_signals_to_processing
from utils.get_demodulated_signals import get_demodulated_signals

from neuroconv import NWBConverter
from neuroconv.datainterfaces import TDTFiberPhotometryInterface


class CustomTDTFiberPhotometryInterface(TDTFiberPhotometryInterface):
    def add_demodulated_signals_to_processing(self, nwbfile: NWBFile, stream_name: str):
        """
        Add demodulated calcium and isosbestic signals to the processing module.

        Parameters:
        -----------
        nwbfile : NWBFile
            The NWB file where the signals will be added.
        stream_name : str
            Name of the data stream to retrieve.
        """
        # Retrieve demodulated signals and timestamps
        calcium_signal, isosbestic_signal, timestamps = get_demodulated_signals(self, stream_name)
 
        # Add the demodulated signals to the processing module
        add_demodulated_signals_to_processing(nwbfile, calcium_signal, isosbestic_signal, timestamps)


class Embargo2025NWBConverter(NWBConverter):
    """Primary conversion class for my extracellular electrophysiology dataset."""

    data_interface_classes = dict(
        FiberPhotometry=CustomTDTFiberPhotometryInterface # Custom interface for TDT fiber photometry data
    )

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata, conversion_options: Optional[dict] = None) -> None:
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        if "FiberPhotometry" in self.data_interface_objects.keys():
            tdt_interface = self.data_interface_objects["FiberPhotometry"]
            tdt_events = tdt_interface.get_events()
            
            # Add FiberPhotometryResponseSeries
            if "FiberPhotometryResponseSeries" in metadata["Ophys"]["FiberPhotometry"]:
                add_fiber_photometry_response_series(
                    nwbfile=nwbfile,
                    metadata=metadata["Ophys"]["FiberPhotometry"], 
                    tdt_interface=tdt_interface,
                )

            if "OptogeneticStimulusInterval" in metadata["Stimulus"]:
                add_optogenetic_stimulation(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
            if "ShockStimulusInterval" in metadata["Stimulus"]:
                add_shock_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
                add_auditory_stimuli(nwbfile=nwbfile, metadata=metadata, tdt_events=tdt_events)
