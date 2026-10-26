"""NWBConverter of the shock sessions."""

from hnasko_lab_to_nwb.hadjas_2025.nwbconverter import Hadjas2025NWBConverter
from hnasko_lab_to_nwb.shock_sessions.interfaces import AuditoryCueIntervalsInterface


class ShockSessionsNWBConverter(Hadjas2025NWBConverter):
    """Conversion class for the shock sessions.

    It has the interfaces of Hadjas2025NWBConverter (the shock sessions use "RawFiberPhotometry" and the processed
    series recomputed from it) and "AuditoryCueIntervals": AuditoryCueIntervalsInterface (cue intervals in
    nwbfile.intervals).
    """

    data_interface_classes = dict(AuditoryCueIntervals=AuditoryCueIntervalsInterface)
