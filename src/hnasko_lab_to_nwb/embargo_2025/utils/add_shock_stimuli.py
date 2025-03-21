import pandas as pd
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals


def get_stimulus_intervals_df(tdt_events: dict, metadata: dict):

    tdt_events_metadata = metadata["TDTEvents"]
    stream_names = tdt_events_metadata["stream_names"]
    stimulus_amplitude = tdt_events_metadata["stimulus_amplitude"]
    paired_auditory_cue = tdt_events_metadata["paired_auditory_cue"]
    rows = []
    for stream_name, amplitude, cue in zip(stream_names, stimulus_amplitude, paired_auditory_cue):
        if stream_name == "sms_" and stream_name not in tdt_events.keys():
            stream_name = "ssm_"  # fix typo
        if stream_name not in tdt_events.keys():
            continue  # to account for old protocol with paired auditory and shock stimuli
        for start_time, stop_time in zip(tdt_events[stream_name]["onset"], tdt_events[stream_name]["offset"]):
            rows.append(
                {
                    "start_time": start_time,
                    "stop_time": stop_time,
                    "stimulus_amplitude": amplitude,
                    "paired_auditory_cue": cue,
                    "stream_name": stream_name,
                }
            )
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
    stimulus_intervals_df = get_stimulus_intervals_df(metadata=metadata, tdt_events=tdt_events)

    shock_stimulus_intervals = TimeIntervals(
        name=shock_stimulus_metadata["name"],
        description=shock_stimulus_metadata["description"],
    )
    shock_stimulus_intervals.add_column(name="stimulus_amplitude", description="Amplitude of stimulus in mA")
    shock_stimulus_intervals.add_column(
        name="stream_name", description="Name of the TDT system stream used for the stimulus"
    )
    shock_stimulus_intervals.add_column(
        name="paired_auditory_cue", description="Whether the shock was paired with an auditory cue"
    )
    for _, row in stimulus_intervals_df.iterrows():
        shock_stimulus_intervals.add_interval(
            start_time=row["start_time"],
            stop_time=row["stop_time"],
            stimulus_amplitude=row["stimulus_amplitude"],
            paired_auditory_cue=row["paired_auditory_cue"],
            stream_name=row["stream_name"],
        )

    nwbfile.add_stimulus(shock_stimulus_intervals)
