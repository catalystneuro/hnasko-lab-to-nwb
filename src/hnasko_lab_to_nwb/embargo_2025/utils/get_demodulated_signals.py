from utils.demodulate_fp_signal import demodulate_signal

def get_demodulated_signals(tdt_interface, stream_name):
    """
    Retrieve and demodulate the raw signals for calcium and isosbestic from the TDT system.

    Parameters:
    -----------
    tdt_interface : object
        Instance of TDTFiberPhotometryInterface to retrieve raw signal and sampling rate.
    stream_name : str
        Name of the data stream to retrieve.

    Returns:
    --------
    calcium_signal : array-like
        Demodulated calcium signal.
    isosbestic_signal : array-like
        Demodulated isosbestic signal.
    timestamps : array-like
        Timestamps corresponding to the signals.
    """
    raw_signal = tdt_interface.get_signal(stream_name=stream_name)
    fs_raw = tdt_interface.get_sampling_rate(stream_name=stream_name)

    # Demodulate calcium signal (driver frequency = 330 Hz)
    calcium_signal = demodulate_signal(raw_signal, fs_raw, driver_freq=330, cutoff_freq=6)

    # Demodulate isosbestic signal (driver frequency = 210 Hz)
    isosbestic_signal = demodulate_signal(raw_signal, fs_raw, driver_freq=210, cutoff_freq=6)

    # Retrieve timestamps
    timestamps = tdt_interface.get_timestamps(stream_name=stream_name)

    return calcium_signal, isosbestic_signal, timestamps
