import numpy as np
import pandas as pd
from pynwb import NWBFile
from pynwb.epoch import TimeIntervals
from pynwb.ogen import OptogeneticSeries, OptogeneticStimulusSite


def create_optogenetic_timeseries(stimulus_intervals_df: pd.DataFrame):
    """
    Generates a timeseries as a square wave based on stimulus intervals and frequencies.

    Parameters:
    - stimulus_intervals_df (pd.DataFrame): DataFrame with columns ['start_time', 'stop_time', 'stimulus_frequency'].

    Returns:
    - np.ndarray: Time array for the TimeSeries.
    - np.ndarray: Optogenetic TimeSeries (square wave).
    """
    # Determine the maximum frequency in the stimulus_frequency column
    max_frequency = stimulus_intervals_df["stimulus_frequency"].max()

    # Calculate the sampling rate as twice the maximum frequency (Nyquist criterion)
    sampling_rate = 2 * max_frequency

    # Find the total duration of the signal
    total_duration = stimulus_intervals_df["stop_time"].max()

    # Create the time array with the required sampling rate
    timestamps = np.arange(0, total_duration, 1 / sampling_rate)

    # Initialize the TTL signal with zeros
    data = np.zeros_like(timestamps)

    # Iterate through each interval in the DataFrame
    for _, row in stimulus_intervals_df.iterrows():
        start_time = row["start_time"]
        stop_time = row["stop_time"]
        frequency = row["stimulus_frequency"]

        # Calculate the period of the square wave
        period = 1 / frequency

        # Get the indices of the time array corresponding to this interval
        start_idx = np.searchsorted(timestamps, start_time)
        stop_idx = np.searchsorted(timestamps, stop_time)

        # Generate the square wave for this interval
        interval_time = timestamps[start_idx:stop_idx]
        square_wave = ((interval_time % period) < (period / 2)).astype(int)

        # Set the TTL signal to the square wave in this interval
        data[start_idx:stop_idx] = square_wave

    return timestamps, data


def get_stimulus_intervals_df(tdt_events: dict, metadata: dict):

    tdt_events_metadata = metadata["TDTEvents"]
    stream_names = tdt_events_metadata["stream_names"]
    stimuli_frequencies = tdt_events_metadata["stimuli_frequencies"]
    rows = []
    for stream_name, stimulus_frequency in zip(stream_names, stimuli_frequencies):
        for start_time, stop_time in zip(tdt_events[stream_name]["onset"], tdt_events[stream_name]["offset"]):
            rows.append(
                {
                    "start_time": start_time,
                    "stop_time": stop_time,
                    "stimulus_frequency": stimulus_frequency,
                }
            )
    return pd.DataFrame(rows)


def add_optogenetic_stimulation(nwbfile: NWBFile, metadata: dict, tdt_events: dict):
    """
    Add optogenetics series to the NWB file.

    Parameters
    ----------
    nwbfile: NWBFile
        The NWB file where the optogenetics series will be added as stimulus.
    metadata: dict
        The metadata to use for adding the optogenetics series. The metadata should be located in the "Stimulus" key,
        with the "OptogeneticSeries" and "OptogeneticStimulusSite" keys containing the metadata for the optogenetic
        series and stimulus site, respectively.

    """

    optical_fiber_device = nwbfile.devices.get("optical_fiber")
    if optical_fiber_device is None:
        raise ValueError(
            "No OpticalFiber device found in the NWB file. Please add a OpticalFiber device before adding optogenetics series."
        )

    optogenetics_metadata = metadata["Stimulus"]
    optogenetic_series_metadata = optogenetics_metadata["OptogeneticSeries"]
    optogenetic_stimulus_sites_metadata = optogenetics_metadata["OptogeneticStimulusSite"]
    optogenetic_stimulus_site_name = optogenetic_series_metadata["site"]

    optogenetic_stimulus_site_metadata = next(
        (
            site_metadata
            for site_metadata in optogenetic_stimulus_sites_metadata
            if site_metadata["name"] == optogenetic_stimulus_site_name
        ),
        None,
    )
    if optogenetic_stimulus_site_metadata is None:
        raise ValueError(f"Optogenetic stimulus site {optogenetic_stimulus_site_name} not found in metadata.")

    ogen_stim_site = OptogeneticStimulusSite(
        name=optogenetic_stimulus_site_name,
        description=optogenetic_stimulus_site_metadata["description"],
        device=optical_fiber_device,
        excitation_lambda=optogenetic_stimulus_site_metadata["excitation_lambda"],
        location=optogenetic_stimulus_site_metadata["location"],
    )

    nwbfile.add_ogen_site(ogen_stim_site)

    timestamps, data = create_optogenetic_timeseries(metadata=metadata, tdt_events=tdt_events)

    optogenetic_series = OptogeneticSeries(
        name=optogenetic_series_metadata["name"],
        description=optogenetic_series_metadata["description"],
        site=ogen_stim_site,
        data=data,
        timestamps=timestamps,
    )

    nwbfile.add_stimulus(optogenetic_series)

    optogenetic_stimulus_intervals_metadata = optogenetics_metadata["OptogeneticStimulusInterval"]
    tdt_events_metadata = optogenetics_metadata["TDTEvents"]

    optogenetic_stimulus_intervals = TimeIntervals(
        name=optogenetic_stimulus_intervals_metadata["name"],
        description=optogenetic_stimulus_intervals_metadata["description"],
    )
    optogenetic_stimulus_intervals.add_column(name="stimulus_frequency", description="Frequency of stimulus")
    for tdt_event_name in tdt_events.keys():
        stimulus_frequency = tdt_events_metadata["stimuli_frequencies"][
            tdt_events_metadata["stream_names"] == tdt_event_name
        ]
        optogenetic_stimulus_intervals.add_interval(
            start_time=tdt_events[tdt_event_name]["onset"],
            end_time=tdt_events[tdt_event_name]["offset"],
            timeseries=data,
            stimulus_frequency=stimulus_frequency,
        )

    nwbfile.add_stimulus(optogenetic_stimulus_intervals)
