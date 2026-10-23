import numpy as np
import pytest

from hnasko_lab_to_nwb.hadjas_2025.processing import (
    calculate_dff_with_biexponential_fit,
    demodulate,
    process_raw_signal,
    resample,
    robustfit,
)

SAMPLING_FREQUENCY = 6103.515625  # Fi1r rate of the RZ10x rigs


def get_modulated_signal(duration: float, calcium_amplitude: float, isosbestic_amplitude: float) -> np.ndarray:
    """Return a raw signal with the 465 nm LED at 330 Hz and the 405 nm LED at 210 Hz, as from 2024 on."""
    t = np.arange(int(duration * SAMPLING_FREQUENCY)) / SAMPLING_FREQUENCY
    return (
        1.0
        + calcium_amplitude * np.sin(2 * np.pi * 330.0 * t)
        + isosbestic_amplitude * np.sin(2 * np.pi * 210.0 * t + 0.3)
    )


@pytest.mark.parametrize("carrier_frequency, expected_amplitude", [(330.0, 2.0), (210.0, 0.5)])
def test_demodulate_gives_half_the_amplitude_of_the_carrier(carrier_frequency, expected_amplitude):
    raw_signal = get_modulated_signal(duration=20.0, calcium_amplitude=4.0, isosbestic_amplitude=1.0)

    demodulated = demodulate(raw_signal, SAMPLING_FREQUENCY, carrier_frequency)

    assert demodulated.shape == raw_signal.shape
    middle = slice(int(2 * SAMPLING_FREQUENCY), int(18 * SAMPLING_FREQUENCY))
    np.testing.assert_allclose(demodulated[middle], expected_amplitude, rtol=1e-3)


def matlab_filtfilt(b: np.ndarray, a: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Filter forward and backward as MATLAB's filtfilt: odd reflection of 3 * (filter order) samples at each end."""
    from scipy import signal

    edge = 3 * (len(a) - 1)
    padded = np.concatenate([2 * x[0] - x[edge:0:-1], x, 2 * x[-1] - x[-2 : -edge - 2 : -1]])
    zi = signal.lfilter_zi(b, a)
    forward, _ = signal.lfilter(b, a, padded, zi=zi * padded[0])
    backward, _ = signal.lfilter(b, a, forward[::-1], zi=zi * forward[-1])
    return backward[::-1][edge:-edge]


def test_demodulate_pads_the_filter_as_matlab_filtfilt():
    from scipy import signal

    raw_signal = get_modulated_signal(duration=2.0, calcium_amplitude=4.0, isosbestic_amplitude=1.0)
    b, a = signal.butter(2, 6.0 / (SAMPLING_FREQUENCY / 2), "low")
    t = np.arange(len(raw_signal)) / SAMPLING_FREQUENCY
    expected = np.sqrt(
        matlab_filtfilt(b, a, raw_signal * np.sin(2 * np.pi * 330.0 * t)) ** 2
        + matlab_filtfilt(b, a, raw_signal * np.cos(2 * np.pi * 330.0 * t)) ** 2
    )

    np.testing.assert_allclose(demodulate(raw_signal, SAMPLING_FREQUENCY, 330.0), expected, rtol=1e-9)


def test_resample_uses_the_grids_of_matlab_griddedinterpolant():
    # sample i (from 1) of the demodulated signal is at i / fs; the resampled signal is at k / 100 (k from 1)
    number_of_samples = int(10.5 * SAMPLING_FREQUENCY)
    ramp = np.arange(1, number_of_samples + 1) / SAMPLING_FREQUENCY

    resampled = resample(ramp, SAMPLING_FREQUENCY)

    assert len(resampled) == int(np.floor(number_of_samples / SAMPLING_FREQUENCY * 100))
    np.testing.assert_allclose(resampled, np.arange(1, len(resampled) + 1) / 100.0, atol=1e-12)


def test_calculate_dff_gives_the_fraction_above_the_scaled_isosbestic_baseline():
    x = np.arange(60 * 100)
    isosbestic = 1.0 + 0.5 * np.exp(-x / 3000)
    response = np.zeros(len(x))
    response[3000:3050] = 0.1  # 0.5 s at 10 % above baseline
    calcium = 2.0 * isosbestic * (1 + response)

    dff, fit_results = calculate_dff_with_biexponential_fit(calcium, isosbestic)

    np.testing.assert_allclose(fit_results["isosbestic_fit"], isosbestic, rtol=1e-6)
    np.testing.assert_allclose(dff, 100 * response, atol=0.5)


def test_robustfit_ignores_outliers():
    rng = np.random.default_rng(0)
    x = np.linspace(0, 10, 1000)
    y = 1.0 + 2.0 * x + rng.normal(scale=0.01, size=len(x))
    y[::20] += 50.0  # 5 % outliers

    intercept, slope = robustfit(x, y)

    assert intercept == pytest.approx(1.0, abs=0.01)
    assert slope == pytest.approx(2.0, abs=0.01)


def test_calculate_dff_scales_the_baseline_with_an_intercept():
    # the lab's robustfit keeps the intercept; a fit through the origin would put the offset into dF/F
    x = np.arange(60 * 100)
    isosbestic = 1.0 + 0.5 * np.exp(-x / 3000)
    response = np.zeros(len(x))
    response[3000:3050] = 0.1
    baseline = 0.5 + 2.0 * isosbestic
    calcium = baseline * (1 + response)

    dff, fit_results = calculate_dff_with_biexponential_fit(calcium, isosbestic)

    np.testing.assert_allclose(fit_results["linear_coefficients"], [2.0, 0.5], rtol=1e-6)
    np.testing.assert_allclose(dff, 100 * response, atol=1e-6)


def test_calculate_dff_fits_a_slow_and_a_fast_exponential():
    # photobleaching with a 2 min and a 20 min component; samples numbered from 1 as in MATLAB
    x = np.arange(1, 10 * 60 * 100 + 1)
    isosbestic = 0.02 * np.exp(-x / 12_000) + 0.05 * np.exp(-x / 120_000)
    calcium = 0.001 + 1.5 * isosbestic

    dff, fit_results = calculate_dff_with_biexponential_fit(calcium, isosbestic)

    np.testing.assert_allclose(fit_results["isosbestic_fit"], isosbestic, rtol=1e-6)
    np.testing.assert_allclose(dff, 0.0, atol=1e-4)


def test_calculate_dff_raises_without_a_positive_scaling():
    # a calcium signal that falls as the isosbestic signal rises cannot be scaled with a positive slope
    x = np.arange(1, 60 * 100 + 1)
    isosbestic = 1.0 + 0.5 * np.exp(-x / 3000)
    calcium = 3.0 - isosbestic

    with pytest.raises(ValueError, match="No bi-exponential fit"):
        calculate_dff_with_biexponential_fit(calcium, isosbestic)


def test_process_raw_signal_returns_the_streams_of_the_lab_files():
    raw_signal = get_modulated_signal(duration=20.0, calcium_amplitude=4.0, isosbestic_amplitude=1.0)

    processed = process_raw_signal(
        raw_signal, SAMPLING_FREQUENCY, calcium_signal_in_hz=330.0, isosbestic_control_in_hz=210.0
    )

    assert list(processed) == ["Gc_raw", "af_raw", "Gc", "af", "dF", "af_fit", "lin_fit"]
    assert len(processed["Gc_raw"]) == len(processed["af_raw"]) == len(raw_signal)
    assert len(processed["Gc"]) == len(processed["af"]) == len(processed["dF"]) == len(processed["af_fit"])
    middle = slice(200, 1800)
    np.testing.assert_allclose(processed["Gc"][middle], 2.0, rtol=1e-3)
    np.testing.assert_allclose(processed["af"][middle], 0.5, rtol=1e-3)
