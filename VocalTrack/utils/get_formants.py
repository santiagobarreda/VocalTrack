"""
Formant estimation utilities for speech/audio analysis.

This module provides a fast, dependency-light method for estimating the first three
formant frequencies (F1, F2, F3) from an audio signal, using a native LPC-based approach.
"""

from typing import Dict
import numpy as np
import logging

# Optional Parselmouth import - keep it local to this module so callers don't need it
try:
    import parselmouth
    _HAS_PARSELMOUTH = True
except Exception:
    parselmouth = None
    _HAS_PARSELMOUTH = False

logger = logging.getLogger(__name__)


def get_formants(signal, sample_rate, method='native', **kwargs):
    """
    High-level dispatcher for formant extraction.
    """
    if method == 'native':
        kwargs.pop('parselmouth_sound', None)
        return get_formants_native(signal, sample_rate, **kwargs)
    elif method == 'wlp':
        kwargs.pop('parselmouth_sound', None)
        return get_formants_wlp(signal, sample_rate, **kwargs)
    elif method == 'parselmouth':
        return get_formants_parselmouth(signal, sample_rate, **kwargs)
    elif method == 'custom':
        kwargs.pop('parselmouth_sound', None)
        return get_formants_custom(signal, sample_rate, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")
    

def _levinson_durbin(r: np.ndarray, order: int) -> tuple:
    """
    Solve for LPC coefficients using the Levinson-Durbin recursion.
    Optimized using vectorized NumPy array operations.
    """
    a = np.zeros(order + 1, dtype=np.float64)
    e = r[0]
    if e == 0:
        return a, e
    a[0] = 1.0
    for i in range(1, order + 1):
        # Vectorized accumulation using dot product
        acc = float(np.dot(a[1:i], r[i-1:0:-1]))
        k = -(r[i] + acc) / e
        a_prev = a.copy()
        a[i] = k
        # Vectorized update of coefficients
        a[1:i] = a_prev[1:i] + k * a_prev[i-1:0:-1]
        e *= (1.0 - k * k)
        if e <= 0:
            break
    return a, e


def get_formants_native(signal: np.ndarray,
                  sample_rate: int,
                  max_formant: int = 5000,
                  n_formants_praat: float = 5.5,
                  robust: bool = False,
                  window_length: float = 0.05,
                  time_step: float = 0.01,
                  pre_emphasis_hz: float = 50.0) -> Dict:
    """
    Estimate the first three formant frequencies (F1, F2, F3) from an audio signal
    using a native LPC-based approach.

    Parameters
    ----------
    signal : np.ndarray
        The input audio signal (1D array, int16 or float).
    sample_rate : int
        The sampling rate of the signal in Hz.
    max_formant : int, optional
        Maximum frequency (Hz) to consider for formant search (default: 5000).
    n_formants_praat : float, optional
        Number of formants to search for in LPC analysis (default: 5.5).
        This corresponds to `2 * order` for the LPC analysis.
    robust : bool, optional
        Ignored for native method. For API compatibility only (default: False).
    window_length : float, optional
        Ignored for native method. For API compatibility only (default: 0.05).
    time_step : float, optional
        Ignored for native method. For API compatibility only (default: 0.01).
    pre_emphasis_hz : float, optional
        Ignored for native method. For API compatibility only (default: 50.0).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'method': str indicating which method was used ('native')
    """

    # Handle empty or invalid input signal
    if signal is None or signal.size == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'native'}

    # Normalize signal to float64 in range [-1, 1] for all methods
    if signal.dtype == np.int16:
        sig = signal.astype(np.float64) / 32768.0
    else:
        sig = signal.astype(np.float64)

    # Validate max_formant against Nyquist frequency (sample_rate / 2)
    # Clamp max_formant to Nyquist if needed
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
        logger.warning(f"max_formant ({max_formant} Hz) exceeds Nyquist frequency ({nyquist} Hz). Clamping to Nyquist.")
        max_formant = int(nyquist)

    # === Native LPC-based formant estimation ===
    # Apply pre-emphasis filter to boost high frequencies (improves formant detection)
    pre_emph = 0.97
    if sig.size > 1:
        sig = np.append(sig[0], sig[1:] - pre_emph * sig[:-1])

    if len(sig) < 20:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'native'}

    # Trying to copy Praat's Gaussian Window. Praat defines the physical window (N)
    # as exactly twice the effective window length (T)
    # Praat's specific Gaussian formula: exp(-12 * (t/T)^2)
    N = len(sig)
    n = np.arange(N)
    center = (N - 1) / 2.0
    T = N / 2.0
    gauss = np.exp(-12.0 * ((n - center) / T) ** 2)
    windowed = sig * gauss

    # Calculate LPC order: 2 * n_formants_praat (e.g., 5.5 → order=11 coefficients)
    # Higher order allows finding more formants, which improves accuracy of F1-F3
    # Even though we search for ~5-6 formants, we only return the lowest 3
    order = int(2 * n_formants_praat)

    # Compute autocorrelation of windowed signal
    autocorr = np.correlate(windowed, windowed, mode='full')
    autocorr = autocorr[autocorr.size // 2:]

    # Check if we have enough autocorrelation values for the requested order
    if autocorr.size < order + 1:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'native'}

    # Solve for LPC coefficients using Levinson-Durbin algorithm
    a, e = _levinson_durbin(autocorr, order)

    # Find roots of LPC polynomial (poles of vocal tract filter)
    roots = np.roots(a)
    # Keep only roots with positive imaginary part (upper half of z-plane)
    roots = roots[np.imag(roots) > 0]

    # Convert complex roots to formant frequencies and bandwidths
    formant_freqs = []
    bandwidths = []
    for r in roots:
        ang = np.arctan2(np.imag(r), np.real(r))
        freq = ang * sample_rate / (2.0 * np.pi)
        bw = -0.5 * (sample_rate / (2.0 * np.pi)) * np.log(np.abs(r))
        # Only keep plausible formants
        if freq > 50 and freq <= max_formant and bw > 0 and bw < 400:
            formant_freqs.append(freq)
            bandwidths.append(bw)

    if len(formant_freqs) == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'native'}

    # Sort and return lowest 3 formants
    idx = np.argsort(formant_freqs)
    formant_freqs = np.array(formant_freqs)[idx]
    bandwidths = np.array(bandwidths)[idx]
    out_formants = np.zeros(3)
    out_bandwidths = np.zeros(3)
    take = min(3, len(formant_freqs))
    out_formants[:take] = formant_freqs[:take]
    out_bandwidths[:take] = bandwidths[:take]
    return {'formants': out_formants, 'bandwidths': out_bandwidths, 'method': 'native'}



"""
Formant estimation utilities for speech/audio analysis using Parselmouth.
"""

def get_formants_parselmouth(signal: np.ndarray,
                  sample_rate: int,
                  max_formant: int = 5000,
                  robust: bool = False,
                  window_length: float = 0.05,
                  time_step: float = 0.01,
                  pre_emphasis_hz: float = 50.0,
                  n_formants_praat: float = 5.5,
                  parselmouth_sound=None) -> Dict:
    """
    Estimate the first three formant frequencies (F1, F2, F3) from an audio signal
    using Parselmouth/Praat.

    Parameters
    ----------
    signal : np.ndarray
        The input audio signal (1D array, int16 or float).
    sample_rate : int
        The sampling rate of the signal in Hz.
    max_formant : int, optional
        Maximum frequency (Hz) to consider for formant search (default: 5000).
    method : str or callable, optional
        This parameter is ignored. Kept for API compatibility.
    custom_func : callable, optional
        This parameter is ignored. Kept for API compatibility.
    robust : bool, optional
        Use robust formant estimation in Parselmouth (default: False).
    window_length : float, optional
        Analysis window length in seconds for Parselmouth (default: 0.05).
    time_step : float, optional
        Time step in seconds for Parselmouth (default: 0.01).
    pre_emphasis_hz : float, optional
        Pre-emphasis cutoff frequency for Parselmouth (default: 50.0).
    n_formants_praat : float, optional
        Number of formants to search for in Parselmouth (default: 5.5).
    parselmouth_sound : parselmouth.Sound, optional
        Pre-allocated Parselmouth Sound object to reuse.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'method': str, always 'parselmouth'.
    """

    # Handle empty or invalid input signal
    if signal is None or signal.size == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'parselmouth'}

    if not _HAS_PARSELMOUTH:
        logger.warning("Parselmouth library not found. Cannot perform formant tracking.")
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'parselmouth'}

    # Normalize signal to float64 in range [-1, 1] for all methods
    if signal.dtype == np.int16:
        sig = signal.astype(np.float64) / 32768.0
    else:
        sig = signal.astype(np.float64)

    # Validate max_formant against Nyquist frequency (sample_rate / 2)
    # Clamp max_formant to Nyquist if needed
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
        logger.warning(f"max_formant ({max_formant} Hz) exceeds Nyquist frequency ({nyquist} Hz). Clamping to Nyquist.")
        max_formant = int(nyquist)

    # Use Parselmouth/Praat for formant tracking
    try:
        snd = parselmouth_sound if parselmouth_sound is not None else parselmouth.Sound(sig, sampling_frequency=sample_rate)
        praat_n_formants = n_formants_praat
        if robust:
            formant_obj = parselmouth.praat.call(
                snd, 'To Formant (robust)', time_step, praat_n_formants, max_formant, window_length, 24, 1.5, 5, 1e-6)
        else:
            formant_obj = parselmouth.praat.call(
                snd, 'To Formant (burg)', time_step, praat_n_formants, max_formant, window_length, pre_emphasis_hz)
        n_frames = formant_obj.get_number_of_frames()
        t = formant_obj.get_time_from_frame_number(n_frames if n_frames > 0 else 1)
        fvals = np.zeros(3)
        bws = np.zeros(3)
        for i in range(1, 4):
            try:
                val = parselmouth.praat.call(formant_obj, 'Get value at time', i, t, 'Hertz', 'Linear')
                fvals[i - 1] = float(val) if val is not None else 0.0
            except Exception:
                fvals[i - 1] = 0.0
        return {'formants': fvals, 'bandwidths': bws, 'method': 'parselmouth'}
    except Exception as e:
        logger.warning(f"Parselmouth formant extraction failed: {e}.")
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'parselmouth'}





"""
Your own formant estimation utilities for speech/audio analysis.

"""

def get_formants_custom(signal: np.ndarray,
                  sample_rate: int,
                  max_formant: int = 5000,
                  n_formants_praat: float = 5.5,
                  robust: bool = False,
                  window_length: float = 0.05,
                  time_step: float = 0.01,
                  pre_emphasis_hz: float = 50.0) -> Dict:
    """
    Estimate the first three formant frequencies (F1, F2, F3) from an audio signal
    using a custom approach.

    Parameters
    ----------
    signal : np.ndarray
        The input audio signal (1D array, int16 or float).
    sample_rate : int
        The sampling rate of the signal in Hz.
    max_formant : int, optional
        Maximum frequency (Hz) to consider for formant search (default: 5000).
    n_formants_praat : float, optional
        Number of formants to search for in LPC analysis (default: 5.5).
        This corresponds to `2 * order` for the LPC analysis.
    robust : bool, optional
        Use robust formant estimation if applicable (default: False).
    window_length : float, optional
        Analysis window length in seconds (default: 0.05).
    time_step : float, optional
        Time step in seconds (default: 0.01).
    pre_emphasis_hz : float, optional
        Pre-emphasis cutoff frequency (default: 50.0).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'method': str indicating which method was used ('custom')
    """

    # YOUR METHOD IMPLEMENTATION HERE 
    return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'custom'}


def get_formants_wlp(signal: np.ndarray,
                     sample_rate: int,
                     max_formant: int = 5000,
                     n_formants_praat: float = 5.5,
                     robust: bool = False,
                     window_length: float = 0.05,
                     time_step: float = 0.01,
                     pre_emphasis_hz: float = 50.0) -> Dict:
    """
    Estimate the first three formant frequencies (F1, F2, F3) from an audio signal
    using Weighted Linear Prediction (WLP) with Short-Time Energy (STE) weighting.

    Parameters
    ----------
    signal : np.ndarray
        The input audio signal (1D array, int16 or float).
    sample_rate : int
        The sampling rate of the signal in Hz.
    max_formant : int, optional
        Maximum frequency (Hz) to consider for formant search (default: 5000).
    n_formants_praat : float, optional
        Number of formants to search for in WLP analysis (default: 5.5).
        This corresponds to `2 * order` for the WLP analysis.
    robust : bool, optional
        Ignored for WLP method. For API compatibility only (default: False).
    window_length : float, optional
        Ignored for WLP method. For API compatibility only (default: 0.05).
    time_step : float, optional
        Ignored for WLP method. For API compatibility only (default: 0.01).
    pre_emphasis_hz : float, optional
        Ignored for WLP method. For API compatibility only (default: 50.0).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'method': str indicating WLP method was used ('wlp')
    """
    # Handle empty or invalid input signal
    if signal is None or signal.size == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'wlp'}

    # Normalize signal to float64 in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float64) / 32768.0
    else:
        sig = signal.astype(np.float64)

    # Validate max_formant against Nyquist frequency
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
        max_formant = int(nyquist)

    # Apply pre-emphasis filter to boost high frequencies
    pre_emph = 0.97
    if sig.size > 1:
        sig = np.append(sig[0], sig[1:] - pre_emph * sig[:-1])

    N = len(sig)
    order = int(2 * n_formants_praat)
    if N < order + 10:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'wlp'}

    # Apply Gaussian Window to window the pre-emphasized signal
    n = np.arange(N)
    center = (N - 1) / 2.0
    T = N / 2.0
    gauss = np.exp(-12.0 * ((n - center) / T) ** 2)
    windowed = sig * gauss

    # Calculate Short-Time Energy (STE) weight function
    # Compute squared samples
    squared = windowed ** 2
    # Moving average window of approx 1.5 ms for weight smoothing
    ste_win_len = max(3, int(round(sample_rate * 0.0015)))
    if ste_win_len % 2 == 0:
        ste_win_len += 1
    ste_window = np.ones(ste_win_len) / ste_win_len
    # Weights vector
    ste_weight = np.convolve(squared, ste_window, mode='same')
    # Prevent zero weight division issues by adding a tiny threshold based on max energy
    ste_weight = ste_weight + 1e-8 * np.max(ste_weight)

    # Formulate WLP matrix normal equations
    # We predict windowed[order:] using its lagged elements
    M = N - order
    x_target = windowed[order:]
    Y = np.zeros((M, order))
    for k in range(order):
        Y[:, k] = windowed[order - 1 - k : N - 1 - k]

    # Weights vector at prediction times
    w = ste_weight[order:]

    # Scale the columns of Y by weight vector w
    Y_weighted = Y * w[:, np.newaxis]

    # Solve the WLP normal equations: (Y^T * W * Y) a = Y^T * W * x_target
    C = np.dot(Y.T, Y_weighted)
    d = np.dot(Y_weighted.T, x_target)

    try:
        # Solve for WLP predictor coefficients
        coeffs = np.linalg.solve(C, d)
    except np.linalg.LinAlgError:
        # Fallback to pseudo-inverse if WLP matrix is singular or ill-conditioned
        try:
            coeffs = np.dot(np.linalg.pinv(C), d)
        except Exception:
            return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'wlp'}

    # Construct the polynomial: 1 - sum_{k=1}^order coeffs_k * z^-k
    poly = np.zeros(order + 1)
    poly[0] = 1.0
    poly[1:] = -coeffs

    # Find polynomial roots
    roots = np.roots(poly)
    # Filter roots to upper z-plane (imaginary part > 0)
    roots = roots[np.imag(roots) > 0]

    # Convert complex roots to frequencies and bandwidths
    formant_freqs = []
    bandwidths = []
    for r_val in roots:
        ang = np.arctan2(np.imag(r_val), np.real(r_val))
        freq = ang * sample_rate / (2.0 * np.pi)
        bw = -0.5 * (sample_rate / (2.0 * np.pi)) * np.log(np.abs(r_val))
        # Keep plausible formant candidates
        if freq > 50 and freq <= max_formant and bw > 0 and bw < 400:
            formant_freqs.append(freq)
            bandwidths.append(bw)

    if len(formant_freqs) == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'wlp'}

    # Sort formants by frequency and keep the lowest 3
    idx = np.argsort(formant_freqs)
    formant_freqs = np.array(formant_freqs)[idx]
    bandwidths = np.array(bandwidths)[idx]
    out_formants = np.zeros(3)
    out_bandwidths = np.zeros(3)
    take = min(3, len(formant_freqs))
    out_formants[:take] = formant_freqs[:take]
    out_bandwidths[:take] = bandwidths[:take]

    return {'formants': out_formants, 'bandwidths': out_bandwidths, 'method': 'wlp'}

   