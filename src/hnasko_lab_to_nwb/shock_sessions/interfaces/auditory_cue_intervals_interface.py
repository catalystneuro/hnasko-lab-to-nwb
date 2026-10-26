"""Auditory cues of a shock session, as a TimeIntervals table."""

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import DirectoryPath, validate_call
from pynwb.epoch import TimeIntervals
from pynwb.file import NWBFile

from hnasko_lab_to_nwb.hadjas_2025.utils.tdt_blocks import read_tdt_epocs
from neuroconv.basedatainterface import BaseDataInterface


class AuditoryCueIntervalsInterface(BaseDataInterface):
    """Write the auditory cues of a TDT block as a TimeIntervals table in nwbfile.intervals.

    Input files: one TDT block folder. TDT Synapse stores the onset and offset of each cue as an epoc, under a name
    per cue type (e.g. "CSp_" for the cues paired with a shock and "CSm_" for the others).

    NWB objects written: a TimeIntervals table named by metadata["AuditoryCueIntervals"]["name"], with one row per
    cue in time order and the columns cue_type and paired_with_shock.
    """

    keywords = ("auditory cues",)

    @validate_call
    def __init__(self, folder_path: DirectoryPath, cue_epocs: dict, verbose: bool = False):
        """Initialize the interface with the TDT block and its cue epocs.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to the TDT block folder.
        cue_epocs : dict
            {epoc name: {"cue_type": str, "paired_with_shock": bool}}, e.g. the cue_epocs of the shock session
            config.
        verbose : bool, optional
            Whether to print verbose output, by default False.
        """
        super().__init__(folder_path=folder_path, cue_epocs=cue_epocs, verbose=verbose)

    def get_cue_intervals(self) -> pd.DataFrame:
        """Read the cues of the block from its epocs.

        Returns
        -------
        pd.DataFrame
            One row per cue in time order, with start_time and stop_time (seconds from the block start), cue_type
            and paired_with_shock.

        Raises
        ------
        ValueError
            If the block has none of the cue epocs.
        """
        epocs = read_tdt_epocs(Path(self.source_data["folder_path"]))
        cue_epocs = self.source_data["cue_epocs"]
        frames = [
            pd.DataFrame(
                dict(
                    start_time=np.asarray(epocs[epoc_name]["onset"], dtype=float),
                    stop_time=np.asarray(epocs[epoc_name]["offset"], dtype=float),
                    cue_type=cue["cue_type"],
                    paired_with_shock=cue["paired_with_shock"],
                )
            )
            for epoc_name, cue in cue_epocs.items()
            if epoc_name in epocs
        ]
        if not frames:
            raise ValueError(f"No cue epocs {list(cue_epocs)} in {self.source_data['folder_path']}.")
        return pd.concat(frames).sort_values("start_time").reset_index(drop=True)

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict) -> None:
        """Add the cue intervals table to nwbfile.intervals.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory object to add the data to.
        metadata : dict
            Metadata dictionary with the name and description of the table under "AuditoryCueIntervals".
        """
        table_metadata = metadata["AuditoryCueIntervals"]
        cue_intervals = TimeIntervals(name=table_metadata["name"], description=table_metadata["description"])
        cue_intervals.add_column(name="cue_type", description="CS+ (paired with a shock) or CS- (not paired).")
        cue_intervals.add_column(name="paired_with_shock", description="Whether the cue was paired with a shock.")
        for cue in self.get_cue_intervals().to_dict(orient="records"):
            cue_intervals.add_row(**cue)
        nwbfile.add_time_intervals(cue_intervals)
