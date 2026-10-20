"""
Modular functions for reproducing Lotfi 2025 fiber photometry analysis.

This module provides functions to process fiber photometry data from NWB files,
following the analysis pipeline from the original MATLAB scripts.

Author: Catalyst Neuro
Date: 2025
"""

import numpy as np
import warnings
from scipy import optimize
from typing import Tuple, Dict


def calculate_dff_with_biexponential_fit(
    calcium_signal: np.ndarray,
    isosbestic_signal: np.ndarray,
    sampling_rate: float = 100.0,
    exclude_first_seconds: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Calculate dF/F using bi-exponential fit to isosbestic signal.

    This function implements the same baseline correction method as the MATLAB
    scripts, using a two-step fitting process:
    1. Fit bi-exponential function to isosbestic (405nm) signal
    2. Scale fitted baseline to match calcium (465nm) signal via robust linear regression

    Parameters
    ----------
    calcium_signal : np.ndarray
        465nm calcium-sensitive signal (GCaMP), shape (n_samples,)
    isosbestic_signal : np.ndarray
        405nm isosbestic control signal, shape (n_samples,)
    sampling_rate : float, optional
        Sampling rate in Hz, by default 100.0
    exclude_first_seconds : float, optional
        Seconds to exclude from start of recording for fitting, by default 1.0

    Returns
    -------
    dff : np.ndarray
        Baseline-corrected dF/F in percentage (%), shape (n_samples,)
    fit_results : dict
        Dictionary containing fitted baseline components:
        - 'fitted_baseline': Final fitted baseline used for dF/F
        - 'isosbestic_fit': Bi-exponential fit to isosbestic signal
        - 'linear_coefficients': Scaling coefficients (slope, intercept)

    Notes
    -----
    The bi-exponential model is: f(x) = a*exp(b*x) + c*exp(d*x)
    This captures photobleaching dynamics over the recording session.

    Examples
    --------
    >>> calcium = nwbfile.processing['ophys']['downsampled_calcium_signal'].data[:]
    >>> isosbestic = nwbfile.processing['ophys']['downsampled_isosbestic_signal'].data[:]
    >>> dff, fit_info = calculate_dff_with_biexponential_fit(calcium, isosbestic)
    """
    # Validate inputs
    if len(calcium_signal) != len(isosbestic_signal):
        raise ValueError(
            f"Signal length mismatch: calcium={len(calcium_signal)}, " f"isosbestic={len(isosbestic_signal)}"
        )

    n_samples = len(isosbestic_signal)
    time_points = np.arange(n_samples)

    # Determine indices to exclude from fitting
    exclude_indices = int(exclude_first_seconds * sampling_rate)
    include_mask = np.ones(n_samples, dtype=bool)
    include_mask[:exclude_indices] = False

    # Step 1: Bi-exponential fit to isosbestic signal
    # Define bi-exponential function
    def biexponential(x, a, b, c, d):
        return a * np.exp(b * x) + c * np.exp(d * x)

    # Initial parameter guess
    p0 = [
        isosbestic_signal[exclude_indices],  # a: initial amplitude
        -1e-5,  # b: decay rate 1
        isosbestic_signal[exclude_indices],  # c: initial amplitude 2
        -1e-6,  # d: decay rate 2
    ]

    try:
        # Fit bi-exponential to isosbestic signal (excluding initial period)
        popt, _ = optimize.curve_fit(
            biexponential,
            time_points[include_mask],
            isosbestic_signal[include_mask],
            p0=p0,
            maxfev=10000,
        )

        # Generate fitted isosbestic trace for all timepoints
        isosbestic_fit = biexponential(time_points, *popt)

    except (RuntimeError, ValueError) as e:
        warnings.warn(
            f"Bi-exponential fit failed: {e}. Using linear fit as fallback.",
            RuntimeWarning,
        )
        # Fallback to linear fit
        fit_coeffs = np.polyfit(
            time_points[include_mask],
            isosbestic_signal[include_mask],
            1,
        )
        isosbestic_fit = np.polyval(fit_coeffs, time_points)

    # Step 2: Robust linear regression to scale isosbestic fit to calcium signal
    # Using robust regression to minimize outlier influence
    try:
        from statsmodels.robust.robust_linear_model import RLM

        X = isosbestic_fit[include_mask].reshape(-1, 1)
        y = calcium_signal[include_mask]

        rlm_model = RLM(y, X)
        rlm_results = rlm_model.fit()

        slope = rlm_results.params[0]
        intercept = 0.0  # Forced through origin in MATLAB version

    except ImportError:
        # Fallback if statsmodels not available
        warnings.warn(
            "Statsmodels not available. Using standard linear regression.",
            RuntimeWarning,
        )
        slope, intercept = np.polyfit(
            isosbestic_fit[include_mask],
            calcium_signal[include_mask],
            1,
        )

    # Check for negative slope (indicates potential issue)
    if slope < 0:
        warnings.warn(
            f"Negative regression coefficient ({slope:.4f}). " "This may indicate signal quality issues.",
            RuntimeWarning,
        )

    # Calculate final fitted baseline
    fitted_baseline = slope * isosbestic_fit + intercept

    # Calculate dF/F as percentage
    dff = 100.0 * (calcium_signal - fitted_baseline) / fitted_baseline

    # Prepare output dictionary
    fit_results = {
        "fitted_baseline": fitted_baseline,
        "isosbestic_fit": isosbestic_fit,
        "linear_coefficients": np.array([slope, intercept]),
    }

    return dff, fit_results


def extract_trials_around_events(
    signal: np.ndarray,
    event_times: np.ndarray,
    sampling_rate: float = 100.0,
    baseline_duration: float = 5.0,
    post_event_duration: float = 10.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract signal segments aligned to event times.

    Parameters
    ----------
    signal : np.ndarray
        Continuous signal to extract trials from, shape (n_samples,)
    event_times : np.ndarray
        Event onset times in seconds, shape (n_events,)
    sampling_rate : float, optional
        Sampling rate in Hz, by default 100.0
    baseline_duration : float, optional
        Duration before event to include (seconds), by default 5.0
    post_event_duration : float, optional
        Duration after event to include (seconds), by default 10.0

    Returns
    -------
    trial_matrix : np.ndarray
        Trials × timepoints matrix, shape (n_events, n_timepoints)
    time_vector : np.ndarray
        Time vector relative to event onset (seconds), shape (n_timepoints,)

    Notes
    -----
    Trials that extend beyond signal boundaries are filled with NaN.

    Examples
    --------
    >>> dff = calculate_dff_with_biexponential_fit(calcium, isosbestic)[0]
    >>> stim_times = nwbfile.intervals['optogenetic_epochs_table']['start_time'][:]
    >>> trials, time_vec = extract_trials_around_events(dff, stim_times)
    """
    # Calculate window parameters
    pre_samples = int(baseline_duration * sampling_rate)
    post_samples = int(post_event_duration * sampling_rate)
    total_samples = pre_samples + post_samples + 1

    # Convert event times to sample indices
    event_indices = np.floor(event_times * sampling_rate).astype(int)
    n_events = len(event_indices)

    # Initialize trial matrix with NaN
    trial_matrix = np.full((n_events, total_samples), np.nan)

    # Extract each trial
    signal_length = len(signal)
    for i, event_idx in enumerate(event_indices):
        start_idx = event_idx - pre_samples
        end_idx = event_idx + post_samples + 1

        # Check boundaries
        if start_idx < 0 or end_idx > signal_length:
            warnings.warn(
                f"Trial {i} extends beyond signal boundaries. "
                f"Event at index {event_idx}, signal length {signal_length}. "
                "Filling with NaN.",
                RuntimeWarning,
            )
            # Calculate valid range
            valid_start = max(0, start_idx)
            valid_end = min(signal_length, end_idx)
            trial_start = max(0, -start_idx)
            trial_end = trial_start + (valid_end - valid_start)

            trial_matrix[i, trial_start:trial_end] = signal[valid_start:valid_end]
        else:
            trial_matrix[i, :] = signal[start_idx:end_idx]

    # Create time vector
    time_vector = np.arange(-baseline_duration, post_event_duration + 1 / sampling_rate, 1 / sampling_rate)
    # Ensure exact length match
    time_vector = time_vector[:total_samples]

    return trial_matrix, time_vector


def baseline_normalize_trials(
    trial_matrix: np.ndarray,
    time_vector: np.ndarray,
    baseline_window: Tuple[float, float] = (-1.0, 0.0),
) -> np.ndarray:
    """
    Normalize trials by subtracting baseline period mean.

    Parameters
    ----------
    trial_matrix : np.ndarray
        Matrix of trials, shape (n_trials, n_timepoints)
    time_vector : np.ndarray
        Time vector in seconds, shape (n_timepoints,)
    baseline_window : tuple of float, optional
        (start, end) of baseline period in seconds, by default (-1.0, 0.0)

    Returns
    -------
    normalized_trials : np.ndarray
        Baseline-normalized trials, shape (n_trials, n_timepoints)

    Notes
    -----
    For each trial, the mean of the baseline period is subtracted from
    the entire trial, making the baseline period centered at zero.

    Examples
    --------
    >>> trials, time_vec = extract_trials_around_events(dff, stim_times)
    >>> norm_trials = baseline_normalize_trials(trials, time_vec)
    """
    # Find baseline period indices
    baseline_mask = (time_vector >= baseline_window[0]) & (time_vector <= baseline_window[1])

    if not np.any(baseline_mask):
        raise ValueError(
            f"No timepoints found in baseline window {baseline_window}. "
            f"Time vector range: [{time_vector[0]:.2f}, {time_vector[-1]:.2f}]"
        )

    # Calculate baseline mean for each trial
    baseline_means = np.nanmean(trial_matrix[:, baseline_mask], axis=1, keepdims=True)

    # Subtract baseline from each trial
    normalized_trials = trial_matrix - baseline_means

    return normalized_trials


def calculate_summary_statistics(
    trial_matrix: np.ndarray,
    time_vector: np.ndarray,
    time_windows: Dict[str, Tuple[float, float]],
    sampling_rate: float = 100.0,
) -> Dict[str, np.ndarray]:
    """
    Calculate summary statistics for specified time windows.

    Parameters
    ----------
    trial_matrix : np.ndarray
        Matrix of trials, shape (n_trials, n_timepoints)
    time_vector : np.ndarray
        Time vector in seconds, shape (n_timepoints,)
    time_windows : dict
        Dictionary mapping window names to (start, end) tuples in seconds
        Example: {'during_stim': (0.0, 1.0), 'post_stim': (1.0, 2.0)}
    sampling_rate : float, optional
        Sampling rate in Hz, by default 100.0

    Returns
    -------
    statistics : dict
        Dictionary containing statistics for each window:
        - 'mean': Mean across trials, shape (n_windows,)
        - 'auc': Area under curve, shape (n_windows,)
        - 'peak': Peak value from mean trace, shape (n_windows,)
        - 'max_abs_dev': Maximum absolute deviation, shape (n_windows,)

    Examples
    --------
    >>> windows = {
    ...     'stim_0_250ms': (0.0, 0.25),
    ...     'post_stim_1s': (0.25, 1.25),
    ... }
    >>> stats = calculate_summary_statistics(norm_trials, time_vec, windows)
    """
    n_windows = len(time_windows)
    n_trials = trial_matrix.shape[0]

    # Initialize output arrays
    mean_values = np.full(n_windows, np.nan)
    auc_values = np.full(n_windows, np.nan)
    peak_values = np.full(n_windows, np.nan)
    max_abs_dev_values = np.full(n_windows, np.nan)

    # Process each time window
    for i, (window_name, (t_start, t_end)) in enumerate(time_windows.items()):
        # Find indices for this window
        window_mask = (time_vector >= t_start) & (time_vector <= t_end)

        if not np.any(window_mask):
            warnings.warn(
                f"No timepoints found in window '{window_name}' ({t_start}, {t_end})",
                RuntimeWarning,
            )
            continue

        # Extract data for this window
        window_data = trial_matrix[:, window_mask]

        # Calculate mean across all trials and timepoints
        mean_values[i] = np.nanmean(window_data)

        # Calculate AUC (area under curve) using trapezoidal integration
        # Average AUC across trials
        aucs = []
        for trial_idx in range(n_trials):
            trial_segment = window_data[trial_idx, :]
            if not np.all(np.isnan(trial_segment)):
                auc = np.trapezoid(trial_segment, dx=1 / sampling_rate)
                aucs.append(auc)

        if aucs:
            auc_values[i] = np.mean(aucs)

        # Calculate peak from mean trace
        mean_trace = np.nanmean(window_data, axis=0)
        if not np.all(np.isnan(mean_trace)):
            peak_values[i] = np.nanmax(mean_trace)

        # Calculate maximum absolute deviation from mean trace
        if not np.all(np.isnan(mean_trace)):
            abs_trace = np.abs(mean_trace)
            max_idx = np.nanargmax(abs_trace)
            max_abs_dev_values[i] = mean_trace[max_idx]

    statistics = {
        "mean": mean_values,
        "auc": auc_values,
        "peak": peak_values,
        "max_abs_dev": max_abs_dev_values,
    }

    return statistics


def get_standard_time_windows(
    stimulus_duration: float,
) -> Dict[str, Tuple[float, float]]:
    """
    Get standard time windows for analysis based on stimulus duration.

    Parameters
    ----------
    stimulus_duration : float
        Duration of stimulus in seconds (0.25, 1.0, or 4.0)

    Returns
    -------
    windows : dict
        Dictionary of time window names and (start, end) tuples

    Notes
    -----
    Windows are designed to capture:
    - Pre-stimulus baseline
    - During stimulus
    - Post-stimulus response
    - Late stimulus (for longer stimuli)

    Examples
    --------
    >>> windows_250ms = get_standard_time_windows(0.25)
    >>> windows_1s = get_standard_time_windows(1.0)
    >>> windows_4s = get_standard_time_windows(4.0)
    """
    # Common windows for all durations
    windows = {
        "baseline_1s": (-1.0, 0.0),
        "baseline_4s": (-4.0, 0.0),
        "pre_stim_250ms": (-0.25, 0.0),
    }

    # Duration-specific windows
    if stimulus_duration == 0.25:
        windows.update(
            {
                "during_stim": (0.0, 0.25),
                "post_stim_250ms": (0.25, 0.5),
                "post_stim_1s": (0.25, 1.25),
                "post_stim_2s": (0.25, 2.25),
            }
        )

    elif stimulus_duration == 1.0:
        windows.update(
            {
                "during_stim": (0.0, 1.0),
                "late_stim_250ms": (0.75, 1.0),
                "post_stim_1s": (1.0, 2.0),
                "post_stim_2s": (1.0, 3.0),
            }
        )

    elif stimulus_duration == 4.0:
        windows.update(
            {
                "during_stim": (0.0, 4.0),
                "late_stim_1s": (3.0, 4.0),
                "late_stim_250ms": (3.75, 4.0),
                "post_stim_1s": (4.0, 5.0),
                "post_stim_2s": (4.0, 6.0),
                "post_stim_4s": (4.0, 8.0),
            }
        )

    else:
        warnings.warn(
            f"Stimulus duration {stimulus_duration}s not standard. " "Using generic windows.",
            RuntimeWarning,
        )
        windows.update(
            {
                "during_stim": (0.0, stimulus_duration),
                "post_stim": (stimulus_duration, stimulus_duration + 1.0),
            }
        )

    return windows


def organize_by_stimulus_condition(
    nwbfile,
    dff: np.ndarray,
    sampling_rate: float = 100.0,
) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Organize trials by stimulus condition (duration or frequency).

    Parameters
    ----------
    nwbfile : NWBFile
        NWB file object containing optogenetic stimulation epochs
    dff : np.ndarray
        Continuous dF/F signal, shape (n_samples,)
    sampling_rate : float, optional
        Sampling rate in Hz, by default 100.0

    Returns
    -------
    organized_data : dict
        Nested dictionary organized by stimulus condition:
        {
            'Stim250ms': {
                'trials': trial_matrix,
                'time_vector': time_vector,
                'event_times': event_times,
                'normalized': normalized_trials,
            },
            ...
        }

    Examples
    --------
    >>> dff = calculate_dff_with_biexponential_fit(calcium, isosbestic)[0]
    >>> data_by_condition = organize_by_stimulus_condition(nwbfile, dff)
    >>> trials_250ms = data_by_condition['Stim250ms']['normalized']
    """
    # Get optogenetic epochs table
    epochs_df = nwbfile.intervals["optogenetic_epochs_table"].to_dataframe()

    # Identify unique conditions based on stimulus duration or frequency
    # Try to group by duration first
    epochs_df["duration"] = epochs_df["stop_time"] - epochs_df["start_time"]

    # Round durations to standard values
    duration_map = {
        0.25: "Stim250ms",
        1.0: "Stim1s",
        4.0: "Stim4s",
    }

    organized_data = {}

    for duration_val, condition_label in duration_map.items():
        # Find trials matching this duration (with small tolerance)
        mask = np.abs(epochs_df["duration"] - duration_val) < 0.05

        if not np.any(mask):
            continue

        # Extract event times for this condition
        event_times = epochs_df.loc[mask, "start_time"].values

        if len(event_times) == 0:
            continue

        # Extract trials
        trials, time_vec = extract_trials_around_events(
            dff,
            event_times,
            sampling_rate=sampling_rate,
        )

        # Normalize trials
        normalized = baseline_normalize_trials(trials, time_vec)

        # Store in organized structure
        organized_data[condition_label] = {
            "trials": trials,
            "time_vector": time_vec,
            "event_times": event_times,
            "normalized": normalized,
            "duration": duration_val,
        }

    return organized_data
