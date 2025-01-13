"""Primary NWBConverter class for this dataset."""
from neuroconv import NWBConverter
from neuroconv.datainterfaces import TDTFiberPhotometryInterface


class Embargo2025NWBConverter(NWBConverter):
    """Primary conversion class for my extracellular electrophysiology dataset."""

    data_interface_classes = dict(
        FiberPhotometry=TDTFiberPhotometryInterface,
    )
