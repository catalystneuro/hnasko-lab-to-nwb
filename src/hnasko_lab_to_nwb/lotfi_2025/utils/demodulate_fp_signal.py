import numpy as np
from scipy import signal


def demodulate_signal(raw_signal, fs_raw, driver_freq, cutoff_freq=6):
    """
    Demodulate a raw photodetector signal at a specific driver frequency.

    Parameters:
    -----------
    raw_signal : array-like
        Raw photodetector signal
    fs_raw : float
        Sampling rate of the raw signal in Hz
    driver_freq : float
        Driver frequency to demodulate in Hz
        Demodulation parameters
        driver_freq_465 = 330  # 465nm channel, 330 Hz
        driver_freq_405 = 210  # 405nm channel, 210 Hz
    cutoff_freq : float, optional
        Cutoff frequency for the low-pass filter in Hz

    Returns:
    --------
    demodulated_signal : array-like
        Demodulated signal
    """
    # Create time vector
    t = np.arange(len(raw_signal)) / fs_raw

    # Multiply by sin and cos
    sin_component = raw_signal * np.sin(2 * np.pi * driver_freq * t)
    cos_component = raw_signal * np.cos(2 * np.pi * driver_freq * t)

    # Design low-pass filter
    b, a = signal.butter(2, cutoff_freq / (fs_raw / 2), "low")

    # Apply low-pass filter
    filtered_sin = signal.filtfilt(b, a, sin_component)
    filtered_cos = signal.filtfilt(b, a, cos_component)

    # Square
    squared_sin = filtered_sin**2
    squared_cos = filtered_cos**2

    # Sum
    sum_squares = squared_sin + squared_cos

    # Square root
    demodulated_signal = np.sqrt(sum_squares)

    return demodulated_signal
