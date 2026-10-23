"""Processing of the raw fiber photometry signal, as in the lab's MATLAB analysis code.

The lab processes each TDT block separately: the raw Fi1r photodetector signal is demodulated at the modulation
frequency of each LED ("Gc_raw" for the 465 nm calcium signal, "af_raw" for the 405 nm isosbestic control),
resampled to 100 Hz ("Gc" and "af"), and dF/F ("dF", in percent) is computed against a baseline fitted to the
isosbestic control. process_raw_signal runs these steps on the raw signal of one block.

Differences from the lab's MATLAB code
--------------------------------------
Checked against the lab's .mat files with hadjas-2025 compare-processing, which also plots each session.

- Demodulation (demodulate) and resampling to 100 Hz (resample) give the lab's signals to floating point
  precision (differences below 1e-12).
- The scaling of the isosbestic fit to the calcium signal (robustfit) and the dF/F formula give the lab's values to
  floating point precision when given the lab's isosbestic fit.
- The bi-exponential fit of the isosbestic signal differs. MATLAB's fit refines one start point that it computes
  itself, and stops at the first fit it cannot improve, which is not always the best fit. Its start point is not
  available outside MATLAB. calculate_dff_with_biexponential_fit refines several start points and keeps the fit
  closest to the data among those with a positive scaling slope and a baseline above zero. Where MATLAB stopped at
  the same fit, dF/F is the lab's; where it stopped at another one, the baseline differs by a slowly varying amount,
  most often where the closest fit follows a fast decay right after the first second and MATLAB's does not.
- The lab's code only warns when the scaling slope is negative; here such fits are not used, and a ValueError is
  raised if no fit has a positive slope and a baseline above zero.
- The lab adjusted the fit by hand for seven blocks, which are not reproduced here (LAB_ADJUSTED_FITS in
  processing_comparison): it left out other lead-in times (1.2 s, 20 s, or 0.08 s instead of 1 s), fitted from the
  start of the recording, left out the end of a recording where the fiber was unplugged, or joined separate fits
  of two or three parts of a recording with a jump in the signal.
"""

import warnings

import numpy as np
from scipy import optimize, signal

PROCESSED_RATE = 100.0  # Hz, rate of the resampled signals and dF/F
LOWPASS_CUTOFF = 6.0  # Hz, cutoff of the lowpass filter of the demodulation
# Rates of the two exponentials searched for start points of the bi-exponential fit, per sample at 100 Hz: time
# constants from 1 s to about 30 years, decaying or growing, and a constant term
BIEXPONENTIAL_RATES = np.concatenate([-np.logspace(-9, -2, 36), [0.0], np.logspace(-9, -2, 36)])
# Bands of the larger absolute rate of a start point: one start point per band, from time constants of 1 s to 10 s
# (1e-3 to 1e-2 per sample) to slower than 10^4 s
START_POINT_RATE_BANDS = [0.0, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2]


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


def robustfit(x: np.ndarray, y: np.ndarray, tune: float = 4.685, max_iterations: int = 50) -> np.ndarray:
    """Fit y = intercept + slope * x by robust regression with bisquare weights, as MATLAB's robustfit.

    Iteratively reweighted least squares starting from the ordinary least squares fit. The residuals are adjusted
    by their leverage, scaled by their median absolute value (leaving out the smallest, as MATLAB's madsigma) and
    weighted by the bisquare function with tuning constant 4.685.

    Parameters
    ----------
    x : np.ndarray
        Predictor, shape (number of samples,).
    y : np.ndarray
        Response, shape (number of samples,).
    tune : float, optional
        Tuning constant of the bisquare weights (default is 4.685, as in MATLAB).
    max_iterations : int, optional
        Maximum number of reweighting iterations (default is 50, as in MATLAB).

    Returns
    -------
    np.ndarray
        The intercept and the slope.
    """
    X = np.column_stack([np.ones(len(x)), x])
    number_of_coefficients = X.shape[1]
    Q, R = np.linalg.qr(X)
    coefficients = np.linalg.solve(R, Q.T @ y)
    leverage = np.minimum(0.9999, np.sum(Q**2, axis=1))
    adjustment = 1 / np.sqrt(1 - leverage)
    tiny_scale = 1e-6 * np.std(y, ddof=1) or 1.0
    tolerance = np.sqrt(np.finfo(float).eps)

    previous_coefficients = np.zeros(number_of_coefficients)
    for iteration in range(max_iterations):
        if iteration > 0 and not np.any(
            np.abs(coefficients - previous_coefficients)
            > tolerance * np.maximum(np.abs(coefficients), np.abs(previous_coefficients))
        ):
            break
        adjusted_residuals = (y - X @ coefficients) * adjustment
        scale = np.median(np.sort(np.abs(adjusted_residuals))[number_of_coefficients - 1 :]) / 0.6745
        u = adjusted_residuals / (max(scale, tiny_scale) * tune)
        weights = (np.abs(u) < 1) * (1 - u**2) ** 2
        previous_coefficients = coefficients
        sqrt_weights = np.sqrt(weights)
        coefficients = np.linalg.lstsq(X * sqrt_weights[:, np.newaxis], y * sqrt_weights, rcond=None)[0]
    return coefficients


def biexponential(x: np.ndarray, a: float, b: float, c: float, d: float) -> np.ndarray:
    """Return a * exp(b * x) + c * exp(d * x), the "exp2" model of MATLAB's fit."""
    return a * np.exp(b * x) + c * np.exp(d * x)


def get_biexponential_start_points(x: np.ndarray, y: np.ndarray) -> list[list[float]]:
    """Find start points for the bi-exponential fit by a grid search over the two rates.

    For each pair of rates of BIEXPONENTIAL_RATES the model is linear in the amplitudes, which are fitted by least
    squares on every 10th sample. The start points are the pairs with the smallest error within each band of
    START_POINT_RATE_BANDS (by the larger absolute rate), so that slow and fast curves are both tried.

    Parameters
    ----------
    x : np.ndarray
        Sample numbers of the fitted samples.
    y : np.ndarray
        Fitted signal.

    Returns
    -------
    list[list[float]]
        One start point [a, b, c, d] per band that has a candidate.
    """
    x_coarse, y_coarse = x[::10], y[::10]
    best_per_band = {}
    for i, b in enumerate(BIEXPONENTIAL_RATES):
        for d in BIEXPONENTIAL_RATES[i + 1 :]:
            with np.errstate(over="ignore"):
                design = np.column_stack([np.exp(b * x_coarse), np.exp(d * x_coarse)])
            if not np.all(np.isfinite(design)):
                continue
            amplitudes = np.linalg.lstsq(design, y_coarse, rcond=None)[0]
            error = np.sum((design @ amplitudes - y_coarse) ** 2)
            band = np.searchsorted(START_POINT_RATE_BANDS, max(abs(b), abs(d)), side="left")
            if band not in best_per_band or error < best_per_band[band][0]:
                best_per_band[band] = (error, [amplitudes[0], b, amplitudes[1], d])
    return [start_point for _, start_point in best_per_band.values()]


def calculate_dff_with_biexponential_fit(
    calcium_signal: np.ndarray,
    isosbestic_signal: np.ndarray,
    sampling_rate: float = PROCESSED_RATE,
    exclude_first_seconds: float = 1.0,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Calculate dF/F using a bi-exponential fit to the isosbestic signal.

    The baseline is fitted in two steps, as in the lab's code:
    1. Fit a bi-exponential function (biexponential) by least squares to the isosbestic (405 nm) signal, leaving
       out the first second. Samples are numbered from 1, as in MATLAB.
    2. Scale the fitted curve to the calcium (465 nm) signal by robust linear regression with an intercept
       (robustfit), on all samples.

    dF/F is 100 * (calcium - baseline) / baseline. The bi-exponential fit is refined from several start points
    (get_biexponential_start_points). A fit is kept only if its scaling slope is positive and its baseline stays
    above zero; of those, the one with the smallest squared error is used. See the module docstring for how this
    differs from the lab's MATLAB code.

    Parameters
    ----------
    calcium_signal : np.ndarray
        465 nm calcium-sensitive signal, shape (number of samples,).
    isosbestic_signal : np.ndarray
        405 nm isosbestic control signal, shape (number of samples,).
    sampling_rate : float, optional
        Sampling rate of both signals, in Hz (default is 100).
    exclude_first_seconds : float, optional
        Seconds at the start of the recording left out of the bi-exponential fit (default is 1).

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
        If the two signals do not have the same length, or if no bi-exponential fit gives a positive slope and a
        baseline above zero.
    """
    if len(calcium_signal) != len(isosbestic_signal):
        raise ValueError(f"Signal length mismatch: calcium={len(calcium_signal)}, isosbestic={len(isosbestic_signal)}")

    x = np.arange(1, len(isosbestic_signal) + 1, dtype=float)
    fitted = x > np.ceil(exclude_first_seconds * sampling_rate)

    best = None
    for start_point in get_biexponential_start_points(x[fitted], isosbestic_signal[fitted]):
        try:
            with warnings.catch_warnings():
                # the covariance of the parameters is not used; it cannot be estimated for a perfect fit
                warnings.simplefilter("ignore", optimize.OptimizeWarning)
                parameters, _ = optimize.curve_fit(
                    biexponential, x[fitted], isosbestic_signal[fitted], p0=start_point, maxfev=10000
                )
        except RuntimeError:  # no convergence from this start point
            continue
        with np.errstate(over="ignore"):
            isosbestic_fit = biexponential(x, *parameters)
        if not np.all(np.isfinite(isosbestic_fit)):
            continue
        # as in the lab's code, the scaling uses all samples, including those left out of the bi-exponential fit
        intercept, slope = robustfit(isosbestic_fit, calcium_signal)
        fitted_baseline = intercept + slope * isosbestic_fit
        if slope <= 0 or np.min(fitted_baseline) <= 0:
            continue
        error = np.sum((isosbestic_fit - isosbestic_signal)[fitted] ** 2)
        if best is None or error < best[0]:
            best = (error, isosbestic_fit, fitted_baseline, slope, intercept)
    if best is None:
        raise ValueError("No bi-exponential fit of the isosbestic signal gives a positive slope and baseline.")
    _, isosbestic_fit, fitted_baseline, slope, intercept = best

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
        "Gc", "af" and "dF" at 100 Hz, and, as FP.af_fit and FP.lin_fit of the lab's files, the bi-exponential fit
        of the isosbestic signal ("af_fit") and the baseline of dF/F ("lin_fit") at 100 Hz.
    """
    processed = dict(
        Gc_raw=demodulate(raw_signal, sampling_frequency, calcium_signal_in_hz),
        af_raw=demodulate(raw_signal, sampling_frequency, isosbestic_control_in_hz),
    )
    processed["Gc"] = resample(processed["Gc_raw"], sampling_frequency)
    processed["af"] = resample(processed["af_raw"], sampling_frequency)
    processed["dF"], fit_results = calculate_dff_with_biexponential_fit(processed["Gc"], processed["af"])
    processed["af_fit"] = fit_results["isosbestic_fit"]
    processed["lin_fit"] = fit_results["fitted_baseline"]
    return processed
