import warnings

import pandas as pd
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals


def get_shock_stimulus_intervals_df(tdt_events: dict, metadata: dict):

    tdt_events_metadata = metadata["ShockTDTEvents"]
    stream_names = tdt_events_metadata["stream_names"]
    stimulus_amplitude = tdt_events_metadata["stimulus_amplitude"]
    rows = []
    for stream_name, amplitude in zip(stream_names, stimulus_amplitude):
        if stream_name == "sms_" and stream_name not in tdt_events.keys():
            stream_name = "ssm_"  # fix typo
        if stream_name not in tdt_events.keys():
            warnings.warn(f"Stream name '{stream_name}' not found in TDT events. Skipping this stream.")
            continue
        for start_time, stop_time in zip(tdt_events[stream_name]["onset"], tdt_events[stream_name]["offset"]):
            rows.append(
                {
                    "start_time": start_time,
                    "stop_time": stop_time,
                    "stimulus_amplitude": amplitude,
                    "stream_name": stream_name,
                }
            )
    # Check if the DataFrame is empty and RETURN None if it is
    if not rows:
        return None
    else:
        return pd.DataFrame(rows)


def add_shock_stimuli(nwbfile: NWBFile, metadata: dict, tdt_events: dict):
    """
    Add shock stimuli to the NWB file.

    Parameters
    ----------
    nwbfile: NWBFile
        The NWB file where the shock stimuli will be added as stimulus.
    metadata: dict
        The metadata to use for adding the shock stimuli. The metadata should be located in the "Stimulus" key,
        with the "ShockStimulusInterval" key containing the metadata for the shock stimuli.
    tdt_events: dict
        The TDT events dictionary containing the onset and offset times for the shock stimuli.
    """

    shock_stimulus_metadata = metadata["Stimulus"]["ShockStimulusInterval"]
    stimulus_intervals_df = get_shock_stimulus_intervals_df(metadata=metadata["Stimulus"], tdt_events=tdt_events)
    if stimulus_intervals_df is None:
        return
    shock_stimulus_intervals = TimeIntervals(
        name=shock_stimulus_metadata["name"],
        description=shock_stimulus_metadata["description"],
    )
    shock_stimulus_intervals.add_column(name="stimulus_amplitude", description="Amplitude of stimulus in mA")
    shock_stimulus_intervals.add_column(
        name="stream_name", description="Name of the TDT system stream used for the stimulus"
    )
    for _, row in stimulus_intervals_df.iterrows():
        shock_stimulus_intervals.add_interval(
            start_time=row["start_time"],
            stop_time=row["stop_time"],
            stimulus_amplitude=row["stimulus_amplitude"],
            stream_name=row["stream_name"],
        )

    nwbfile.add_stimulus(shock_stimulus_intervals)


def get_auditory_stimulus_intervals_df(tdt_events: dict, metadata: dict):

    tdt_events_metadata = metadata["AuditoryTDTEvents"]
    stream_names = tdt_events_metadata["stream_names"]
    paired_shock = tdt_events_metadata["paired_shock"]
    rows = []
    for stream_name, paired_shock in zip(stream_names, paired_shock):
        if stream_name not in tdt_events.keys():
            warnings.warn(f"Stream name '{stream_name}' not found in TDT events. Skipping this stream.")
            continue
        for start_time, stop_time in zip(tdt_events[stream_name]["onset"], tdt_events[stream_name]["offset"]):
            rows.append(
                {
                    "start_time": start_time,
                    "stop_time": stop_time,
                    "paired_shock": paired_shock,
                    "stream_name": stream_name,
                }
            )
        # Check if the DataFrame is empty and RETURN None if it is
    if not rows:
        return None
    else:
        return pd.DataFrame(rows)


def add_auditory_stimuli(nwbfile: NWBFile, metadata: dict, tdt_events: dict):
    """
    Add auditory stimuli to the NWB file.

    Parameters
    ----------
    nwbfile: NWBFile
        The NWB file where the auditory stimuli will be added as stimulus.
    metadata: dict
        The metadata to use for adding the auditory stimuli. The metadata should be located in the "Stimulus" key,
        with the "AuditoryStimulusInterval" key containing the metadata for the auditory stimuli.
    tdt_events: dict
        The TDT events dictionary containing the onset and offset times for the auditory stimuli.
    """

    auditory_stimulus_metadata = metadata["Stimulus"]["AuditoryStimulusInterval"]
    stimulus_intervals_df = get_auditory_stimulus_intervals_df(metadata=metadata["Stimulus"], tdt_events=tdt_events)
    if stimulus_intervals_df is None:
        return
    auditory_stimulus_intervals = TimeIntervals(
        name=auditory_stimulus_metadata["name"],
        description=auditory_stimulus_metadata["description"],
    )
    auditory_stimulus_intervals.add_column(
        name="stream_name", description="Name of the TDT system stream used for the stimulus"
    )
    auditory_stimulus_intervals.add_column(
        name="paired_shock_stimulus", description="Whether the auditory cue was paired with a shock stimulus"
    )
    for _, row in stimulus_intervals_df.iterrows():
        auditory_stimulus_intervals.add_interval(
            start_time=row["start_time"],
            stop_time=row["stop_time"],
            paired_shock_stimulus=row["paired_shock"],
            stream_name=row["stream_name"],
        )

    nwbfile.add_stimulus(auditory_stimulus_intervals)
