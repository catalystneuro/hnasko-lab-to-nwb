"""Processing of the raw fiber photometry signal, as in the lab's MATLAB analysis code.

The lab processes each TDT block separately: the raw Fi1r photodetector signal is demodulated at the modulation
frequency of each LED ("Gc_raw" for the 465 nm calcium signal, "af_raw" for the 405 nm isosbestic control),
resampled to 100 Hz ("Gc" and "af"), and dF/F ("dF", in percent) is computed against a baseline fitted to the
isosbestic control. process_raw_signal runs these steps on the raw signal of one block.
"""

import warnings

import numpy as np
from scipy import optimize, signal

PROCESSED_RATE = 100.0  # Hz, rate of the resampled signals and dF/F
LOWPASS_CUTOFF = 6.0  # Hz, cutoff of the lowpass filter of the demodulation


def demodulate(raw_signal: np.ndarray, sampling_frequency: float, carrier_frequency: float) -> np.ndarray:
    """Demodulate the raw photodetector signal at the modulation frequency of one LED.

    The signal is multiplied by a sine and a cosine at the carrier frequency, both products are lowpass filtered
    (2nd-order Butterworth, 6 Hz, forward and backward with the end padding of MATLAB's filtfilt) and the amplitude
    is the square root of the sum of their squares.

    Parameters
    ----------
    raw_signal : np.ndarray
        Raw photodetector signal of one TDT block, shape (number of samples,).
    sampling_frequency : float
        Sampling frequency of the raw signal, in Hz.
    carrier_frequency : float
        Modulation frequency of the LED, in Hz.

    Returns
    -------
    np.ndarray
        Demodulated signal at the rate of the raw signal, shape (number of samples,).
    """
    raw_signal = np.asarray(raw_signal, dtype=float)
    b, a = signal.butter(2, LOWPASS_CUTOFF / (sampling_frequency / 2), "low")
    # MATLAB's filtfilt pads each end with 3 * (filter order) samples; scipy's default pads with one more per order
    padlen = 3 * (max(len(a), len(b)) - 1)
    t = np.arange(len(raw_signal)) / sampling_frequency
    filtered_sin = signal.filtfilt(b, a, raw_signal * np.sin(2 * np.pi * carrier_frequency * t), padlen=padlen)
    filtered_cos = signal.filtfilt(b, a, raw_signal * np.cos(2 * np.pi * carrier_frequency * t), padlen=padlen)
    return np.sqrt(filtered_sin**2 + filtered_cos**2)


def resample(demodulated_signal: np.ndarray, sampling_frequency: float, rate: float = PROCESSED_RATE) -> np.ndarray:
    """Resample a demodulated signal to a lower rate by linear interpolation, as MATLAB's griddedInterpolant.

    As in the lab's code, sample i (from 1) of the demodulated signal is at time i / sampling_frequency, and the
    resampled signal has a sample at each time k / rate (k from 1) up to the time of the last sample.

    Parameters
    ----------
    demodulated_signal : np.ndarray
        Demodulated signal, shape (number of samples,).
    sampling_frequency : float
        Sampling frequency of the demodulated signal, in Hz.
    rate : float, optional
        Rate of the resampled signal, in Hz (default is 100).

    Returns
    -------
    np.ndarray
        Resampled signal.
    """
    number_of_samples = len(demodulated_signal)
    t_raw = np.arange(1, number_of_samples + 1) / sampling_frequency
    t_resampled = np.arange(1, int(np.floor(t_raw[-1] * rate)) + 1) / rate
    return np.interp(t_resampled, t_raw, demodulated_signal)


def calculate_dff_with_biexponential_fit(
    calcium_signal: np.ndarray,
    isosbestic_signal: np.ndarray,
    sampling_rate: float = PROCESSED_RATE,
    exclude_first_seconds: float = 1.0,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Calculate dF/F using a bi-exponential fit to the isosbestic signal.

    The baseline is fitted in two steps:
    1. Fit a bi-exponential function to the isosbestic (405 nm) signal.
    2. Scale the fitted baseline to the calcium (465 nm) signal by robust linear regression.

    Parameters
    ----------
    calcium_signal : np.ndarray
        465 nm calcium-sensitive signal, shape (number of samples,).
    isosbestic_signal : np.ndarray
        405 nm isosbestic control signal, shape (number of samples,).
    sampling_rate : float, optional
        Sampling rate of both signals, in Hz (default is 100).
    exclude_first_seconds : float, optional
        Seconds at the start of the recording left out of the fits (default is 1).

    Returns
    -------
    dff : np.ndarray
        dF/F in percent, shape (number of samples,).
    fit_results : dict
        "fitted_baseline", the baseline used for dF/F; "isosbestic_fit", the bi-exponential fit to the isosbestic
        signal; "linear_coefficients", the slope and intercept that scale the isosbestic fit to the calcium signal.

    Raises
    ------
    ValueError
        If the two signals do not have the same length.
    """
    if len(calcium_signal) != len(isosbestic_signal):
        raise ValueError(f"Signal length mismatch: calcium={len(calcium_signal)}, isosbestic={len(isosbestic_signal)}")

    n_samples = len(isosbestic_signal)
    time_points = np.arange(n_samples)

    exclude_indices = int(exclude_first_seconds * sampling_rate)
    include_mask = np.ones(n_samples, dtype=bool)
    include_mask[:exclude_indices] = False

    def biexponential(x, a, b, c, d):
        return a * np.exp(b * x) + c * np.exp(d * x)

    p0 = [isosbestic_signal[exclude_indices], -1e-5, isosbestic_signal[exclude_indices], -1e-6]

    try:
        popt, _ = optimize.curve_fit(
            biexponential, time_points[include_mask], isosbestic_signal[include_mask], p0=p0, maxfev=10000
        )
        isosbestic_fit = biexponential(time_points, *popt)
    except (RuntimeError, ValueError) as e:
        warnings.warn(f"Bi-exponential fit failed: {e}. Using linear fit as fallback.", RuntimeWarning)
        fit_coeffs = np.polyfit(time_points[include_mask], isosbestic_signal[include_mask], 1)
        isosbestic_fit = np.polyval(fit_coeffs, time_points)

    try:
        from statsmodels.robust.robust_linear_model import RLM

        rlm_results = RLM(calcium_signal[include_mask], isosbestic_fit[include_mask].reshape(-1, 1)).fit()
        slope = rlm_results.params[0]
        intercept = 0.0
    except ImportError:
        warnings.warn("Statsmodels not available. Using standard linear regression.", RuntimeWarning)
        slope, intercept = np.polyfit(isosbestic_fit[include_mask], calcium_signal[include_mask], 1)

    if slope < 0:
        warnings.warn(
            f"Negative regression coefficient ({slope:.4f}). This may indicate signal quality issues.", RuntimeWarning
        )

    fitted_baseline = slope * isosbestic_fit + intercept
    dff = 100.0 * (calcium_signal - fitted_baseline) / fitted_baseline
    fit_results = {
        "fitted_baseline": fitted_baseline,
        "isosbestic_fit": isosbestic_fit,
        "linear_coefficients": np.array([slope, intercept]),
    }
    return dff, fit_results


def process_raw_signal(
    raw_signal: np.ndarray,
    sampling_frequency: float,
    calcium_signal_in_hz: float,
    isosbestic_control_in_hz: float,
) -> dict[str, np.ndarray]:
    """Compute the processed signals of one TDT block from its raw photodetector signal.

    Parameters
    ----------
    raw_signal : np.ndarray
        Raw photodetector signal of one TDT block, shape (number of samples,).
    sampling_frequency : float
        Sampling frequency of the raw signal, in Hz.
    calcium_signal_in_hz : float
        Modulation frequency of the 465 nm LED, in Hz (get_led_modulation).
    isosbestic_control_in_hz : float
        Modulation frequency of the 405 nm LED, in Hz (get_led_modulation).

    Returns
    -------
    dict[str, np.ndarray]
        The signals by stream name of the lab's .mat files: "Gc_raw" and "af_raw" at the rate of the raw signal,
        "Gc", "af" and "dF" at 100 Hz.
    """
    processed = dict(
        Gc_raw=demodulate(raw_signal, sampling_frequency, calcium_signal_in_hz),
        af_raw=demodulate(raw_signal, sampling_frequency, isosbestic_control_in_hz),
    )
    processed["Gc"] = resample(processed["Gc_raw"], sampling_frequency)
    processed["af"] = resample(processed["af_raw"], sampling_frequency)
    processed["dF"], _ = calculate_dff_with_biexponential_fit(processed["Gc"], processed["af"])
    return processed
