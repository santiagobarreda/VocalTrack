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
        return get_formants_native(signal, sample_rate, **kwargs)
    elif method == 'parselmouth':
        return get_formants_parselmouth(signal, sample_rate, **kwargs)
    elif method == 'custom':
        return get_formants_custom(signal, sample_rate, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")
    

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

    # Levinson-Durbin recursion for LPC coefficients
    def levinson(r, order):
        a = np.zeros(order + 1, dtype=np.float64)
        e = r[0]
        if e == 0:
            return a, e
        a[0] = 1.0
        for i in range(1, order + 1):
            acc = 0.0
            for j in range(1, i):
                acc += a[j] * r[i - j]
            k = -(r[i] + acc) / e
            a_prev = a.copy()
            a[i] = k
            for j in range(1, i):
                a[j] = a_prev[j] + k * a_prev[i - j]
            e *= (1.0 - k * k)
            if e <= 0:
                break
        return a, e

    # Check if we have enough autocorrelation values for the requested order
    if autocorr.size < order + 1:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'native'}

    # Solve for LPC coefficients using Levinson-Durbin algorithm
    a, e = levinson(autocorr, order)

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
                  n_formants_praat: float = 5.5) -> Dict:
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
        snd = parselmouth.Sound(sig, sampling_frequency=sample_rate)
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

   