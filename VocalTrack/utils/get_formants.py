"""
Formant estimation utilities for speech/audio analysis.

This module estimates the first three formant frequencies (F1, F2, F3) from an audio signal
with the built-in LPC and WLP methods, Praat (through Parselmouth), or a user-written method.
The main entry point is `get_formants`.
"""

from typing import Dict
import numpy as np
import logging
from .. import config

# Optional Parselmouth import - keep it local to this module so callers don't need it
try:
    import parselmouth
    _HAS_PARSELMOUTH = True
except Exception:
    parselmouth = None
    _HAS_PARSELMOUTH = False

logger = logging.getLogger(__name__)


def get_formants(signal, sample_rate, method='lpc', **kwargs):
    """
    High-level dispatcher for formant extraction.
    """
    method = config.current_method_name('formant_method', method)
    if method != 'parselmouth':
        # Only the Parselmouth backend uses these: the LPC methods always return their LPC
        # polynomial, and there is no Praat Sound to reuse
        kwargs.pop('parselmouth_sound', None)
        kwargs.pop('return_lpc', None)
    if method == 'lpc':
        return get_formants_lpc(signal, sample_rate, **kwargs)
    elif method == 'wlp':
        return get_formants_wlp(signal, sample_rate, **kwargs)
    elif method == 'parselmouth':
        return get_formants_parselmouth(signal, sample_rate, **kwargs)
    elif method == 'custom':
        return get_formants_custom(signal, sample_rate, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")
    

def _resample_for_max_formant(sig: np.ndarray, sample_rate: float, max_formant: float) -> tuple:
    """
    Resample a signal to 2 x max_formant, as Praat does before formant analysis, so that the
    LPC models only the 0..max_formant band. Only downsampling is done (content above the
    input Nyquist frequency cannot be recovered). Uses FFT truncation, which low-pass filters
    and resamples in one step; this is cheap for a single short analysis window.

    Returns
    -------
    tuple
        (resampled signal, its exact sample rate). Unchanged if already at or below the target.
    """
    target_rate = 2.0 * float(max_formant)
    if sample_rate <= target_rate * 1.001 or sig.size < 2:
        return sig, sample_rate
    n_out = int(round(sig.size * target_rate / sample_rate))
    if n_out < 20:
        return sig, sample_rate
    spectrum = np.fft.rfft(sig)
    resampled = np.fft.irfft(spectrum[:n_out // 2 + 1], n_out) * (n_out / sig.size)
    # Exact rate after rounding the sample count
    return resampled, sample_rate * n_out / sig.size


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


def get_formants_lpc(signal: np.ndarray,
                  sample_rate: int,
                  max_formant: int = 5000,
                  n_formants_praat: float = 5.5,
                  robust: bool = False,
                  window_length: float = 0.05,
                  time_step: float = 0.01,
                  pre_emphasis_hz: float = 50.0) -> Dict:
    """
    Estimate the first three formant frequencies (F1, F2, F3) from an audio signal
    using a built-in LPC-based approach.

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
        The LPC order is 2 x this value, rounded down (5.5 -> order 11).
    robust : bool, optional
        Ignored for the LPC method. For API compatibility only (default: False).
    window_length : float, optional
        Ignored for the LPC method. For API compatibility only (default: 0.05).
    time_step : float, optional
        Ignored for the LPC method. For API compatibility only (default: 0.01).
    pre_emphasis_hz : float, optional
        Ignored for the LPC method. For API compatibility only (default: 50.0).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'method': str indicating which method was used ('lpc')
    """

    # Handle empty or invalid input signal
    if signal is None or signal.size == 0:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'lpc', 'lpc_a': None, 'lpc_e': 0.0, 'lpc_order': 0}

    # Normalize signal to float64 in range [-1, 1] for all methods
    if signal.dtype == np.int16:
        sig = signal.astype(np.float64) / 32768.0
    else:
        sig = signal.astype(np.float64)

    # Validate max_formant against Nyquist frequency (sample_rate / 2)
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
        max_formant = int(nyquist)

    # Analyze the 0..max_formant band only, at 2 x max_formant (no-op if already at that rate)
    sig, sample_rate = _resample_for_max_formant(sig, sample_rate, max_formant)

    # === Native LPC-based formant estimation ===
    # Apply pre-emphasis filter to boost high frequencies (improves formant detection)
    pre_emph = 0.97
    if sig.size > 1:
        sig = np.append(sig[0], sig[1:] - pre_emph * sig[:-1])

    if len(sig) < 20:
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'lpc', 'lpc_a': None, 'lpc_e': 0.0, 'lpc_order': 0}

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
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'lpc', 'lpc_a': None, 'lpc_e': 0.0, 'lpc_order': 0}

    # Solve for LPC coefficients using Levinson-Durbin algorithm
    a, e = _levinson_durbin(autocorr, order)

    result = _formants_from_polynomial(a, sample_rate, max_formant)
    result.update({'method': 'lpc', 'lpc_a': a, 'lpc_e': e, 'lpc_order': order, 'lpc_sample_rate': sample_rate})
    return result


# Poles wider than this are not counted as formants. Earlier versions computed bandwidths at a
# quarter of their true value and applied a 400 Hz limit, which is a true limit of 1600 Hz; this
# keeps that behaviour (Praat applies no bandwidth limit at all).
MAX_FORMANT_BANDWIDTH = 1600.0


def _formants_from_polynomial(poly, sample_rate, max_formant):
    """
    Convert a prediction polynomial [1, a1, ..., ap] to formants: each complex pole pair in
    the upper half plane gives a frequency and a bandwidth. Poles outside the unit circle
    (possible for WLP, never for Levinson-Durbin LPC) are reflected inside it first, which
    keeps their frequency. Returns the three lowest plausible formants.
    """
    roots = np.roots(poly)
    outside = np.abs(roots) > 1.0
    roots[outside] = 1.0 / np.conj(roots[outside])
    roots = roots[np.imag(roots) > 0]

    freqs = np.arctan2(np.imag(roots), np.real(roots)) * sample_rate / (2.0 * np.pi)
    bandwidths = -(sample_rate / np.pi) * np.log(np.abs(roots))
    keep = (freqs > 50) & (freqs <= max_formant) & (bandwidths > 0) & (bandwidths < MAX_FORMANT_BANDWIDTH)
    order = np.argsort(freqs[keep])
    freqs, bandwidths = freqs[keep][order], bandwidths[keep][order]

    out_formants = np.zeros(3)
    out_bandwidths = np.zeros(3)
    take = min(3, freqs.size)
    out_formants[:take] = freqs[:take]
    out_bandwidths[:take] = bandwidths[:take]
    return {'formants': out_formants, 'bandwidths': out_bandwidths, 'all_formants': freqs}



# Formant estimation with Praat (through Parselmouth)

def get_formants_parselmouth(signal: np.ndarray,
                  sample_rate: int,
                  max_formant: int = 5000,
                  robust: bool = False,
                  window_length: float = 0.05,
                  time_step: float = 0.01,
                  pre_emphasis_hz: float = 50.0,
                  n_formants_praat: float = 5.5,
                  parselmouth_sound=None,
                  return_lpc: bool = False) -> Dict:
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
    return_lpc : bool, optional
        Also return Praat's LPC polynomial for the frame (for the LPC envelope in LiveSpectrum).
        Computed as Praat's "To Formant (burg)" does it: resampled to 2 x max_formant, Burg LPC of
        order 2 x n_formants_praat with the same window, time step and pre-emphasis, so its roots
        closely match the formants returned (it is a separate analysis, so they are not identical,
        especially for the highest formants). Off by default, since it costs a second analysis.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'formants': np.ndarray of estimated formant frequencies (Hz, shape (3,))
        - 'bandwidths': np.ndarray of estimated formant bandwidths (Hz, shape (3,))
        - 'all_formants': np.ndarray of all formants Praat found in the frame (Hz)
        - 'method': str, always 'parselmouth'.
        - with return_lpc: 'lpc_a', 'lpc_e', 'lpc_order', 'lpc_sample_rate' (as for the LPC method;
          'lpc_e' is 1.0, since the envelope is aligned to the spectrum for display anyway)
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
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
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
        frame = n_frames if n_frames > 0 else 1
        t = formant_obj.get_time_from_frame_number(frame)
        fvals = np.zeros(3)
        bws = np.zeros(3)
        for i in range(1, 4):
            try:
                val = parselmouth.praat.call(formant_obj, 'Get value at time', i, t, 'Hertz', 'Linear')
                fvals[i - 1] = float(val) if val is not None else 0.0
            except Exception:
                fvals[i - 1] = 0.0
        result = {'formants': fvals, 'bandwidths': bws, 'method': 'parselmouth'}

        # All formants Praat found in the frame (F4, F5, ... for the LiveSpectrum markers)
        try:
            n_found = int(parselmouth.praat.call(formant_obj, 'Get number of formants', frame))
            all_f = [parselmouth.praat.call(formant_obj, 'Get value at time', i, t, 'Hertz', 'Linear')
                     for i in range(1, n_found + 1)]
            result['all_formants'] = np.array([f for f in all_f if f is not None and not np.isnan(f)])
        except Exception:
            pass

        if return_lpc:
            try:
                order = int(2 * n_formants_praat)
                lpc_rate = 2.0 * max_formant
                lpc_snd = snd if abs(snd.sampling_frequency - lpc_rate) < 1e-6 else \
                    parselmouth.praat.call(snd, 'Resample', lpc_rate, 50)
                lpc_obj = parselmouth.praat.call(lpc_snd, 'To LPC (burg)', order, window_length, time_step, pre_emphasis_hz)
                coefs = parselmouth.praat.call(lpc_obj, 'Down to Matrix (lpc)').values
                if coefs.size:
                    # Same frame as the formants (the last one); polynomial [1, a1, ..., ap]
                    result.update({'lpc_a': np.concatenate([[1.0], coefs[:, -1]]), 'lpc_e': 1.0,
                                   'lpc_order': order, 'lpc_sample_rate': lpc_rate})
            except Exception as e:
                logger.debug(f"Parselmouth LPC extraction failed: {e}")
        return result
    except Exception as e:
        logger.warning(f"Parselmouth formant extraction failed: {e}.")
        return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'parselmouth'}





# Your own formant estimation method

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
        The LPC order is 2 x this value, rounded down (5.5 -> order 11).
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

        Optional, for the overlay in LiveSpectrum (Ctrl/Cmd+L):
        - 'all_formants': np.ndarray of every formant found (Hz), for the F4 and F5 markers
        - 'lpc_a': prediction polynomial [1, a1, ..., ap]; the envelope drawn is 1 / |A(f)|
        - 'lpc_e': gain of the envelope (any positive number, e.g. 1.0: the curve is aligned to
          the spectrum for display)
        - 'lpc_sample_rate': sample rate (Hz) the polynomial applies to (default: sample_rate)
        Without 'lpc_a' and 'lpc_e' the overlay draws nothing for this method.
    """

    # YOUR METHOD IMPLEMENTATION HERE
    if not get_formants_custom._warned:
        logger.warning(
            "formant_method='custom' is selected but get_formants_custom() is an unimplemented "
            "placeholder - it always returns zeros. Implement it in utils/get_formants.py, or "
            "switch to 'lpc', 'wlp', or 'parselmouth' in Analysis Settings."
        )
        get_formants_custom._warned = True
    return {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'method': 'custom'}


get_formants_custom._warned = False


# Length of the short-time energy window for WLP weighting (the energy of this much signal just
# before each sample is that sample's weight)
STE_WINDOW_MS = 2.0


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
    using Weighted Linear Prediction (WLP) with Short-Time Energy (STE) weighting
    (Ma, Kamp & Willems 1993; applied to high-pitched vowels by Alku et al. 2013).

    Standard LPC weights the prediction error equally at every sample. WLP weights it by the
    energy of the STE_WINDOW_MS of signal preceding each sample. No glottal events are detected:
    a glottal excitation follows the decayed end of the previous cycle, so it (the least
    predictable part of the signal) gets a small weight, while the high-energy stretch after it,
    when the vocal tract rings freely, gets large weights. This makes it less prone than LPC to
    locking onto harmonics in high-pitched voices. Without a clear excitation-then-decay pattern
    the weights flatten and WLP approaches ordinary linear prediction.

    The frame is resampled to 2 x max_formant, pre-emphasized and Gaussian-windowed exactly
    as in the LPC method. The weighted normal equations are solved directly; unlike
    Levinson-Durbin LPC this can give poles outside the unit circle, which are reflected
    inside (keeping their frequency) rather than dropped.

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
        The WLP order is 2 x this value, rounded down (5.5 -> order 11).
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
        - 'all_formants': np.ndarray of all plausible formant frequencies (Hz)
        - 'method': str indicating WLP method was used ('wlp')
        - 'lpc_a', 'lpc_e', 'lpc_order', 'lpc_sample_rate': prediction polynomial, weighted
          mean squared residual, order, and the sample rate they apply to
    """
    empty = {'formants': np.zeros(3), 'bandwidths': np.zeros(3), 'all_formants': np.array([]), 'method': 'wlp',
             'lpc_a': None, 'lpc_e': 0.0, 'lpc_order': 0}
    # Handle empty or invalid input signal
    if signal is None or signal.size == 0:
        return empty

    # Normalize signal to float64 in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float64) / 32768.0
    else:
        sig = signal.astype(np.float64)

    # Validate max_formant against Nyquist frequency
    nyquist = sample_rate / 2.0
    if max_formant > nyquist:
        max_formant = int(nyquist)

    # Analyze the 0..max_formant band only, at 2 x max_formant (no-op if already at that rate)
    sig, sample_rate = _resample_for_max_formant(sig, sample_rate, max_formant)

    # Apply pre-emphasis filter to boost high frequencies
    pre_emph = 0.97
    if sig.size > 1:
        sig = np.append(sig[0], sig[1:] - pre_emph * sig[:-1])

    N = len(sig)
    order = int(2 * n_formants_praat)
    if N < order + 10:
        return empty

    # Taper the frame with the same Gaussian window as the LPC method
    n = np.arange(N)
    x = sig * np.exp(-12.0 * ((n - (N - 1) / 2.0) / (N / 2.0)) ** 2)

    # Predict every sample x[n], n = 0..N+order-1, from the `order` samples before it, with the
    # frame zero-padded on both sides (the autocorrelation-style formulation used by Ma et al.)
    padded = np.concatenate([np.zeros(order), x, np.zeros(order)])
    targets = np.arange(N + order) + order          # position of each predicted sample in `padded`
    Y = np.stack([padded[targets - k] for k in range(1, order + 1)], axis=1)
    y = padded[targets]

    # Short-time energy weight: the energy of the STE_WINDOW_MS of signal just before each
    # predicted sample (Ma, Kamp & Willems 1993). Low at the glottal excitations (after the
    # previous cycle has decayed), high in the stretch of free resonance that follows them
    M = max(1, int(round(STE_WINDOW_MS / 1000.0 * sample_rate)))
    energy = np.concatenate([[0.0], np.cumsum(np.concatenate([np.zeros(M), padded]) ** 2)])
    w = energy[targets + M] - energy[targets]       # sum of padded[t - M .. t - 1]
    if w.max() <= 0:
        return empty
    w = w + 1e-9 * w.max()                          # keep the normal equations well posed

    # Weighted least squares: minimise sum_n w[n] * (y[n] - Y[n] . a)^2
    Yw = Y * w[:, np.newaxis]
    try:
        coeffs = np.linalg.solve(Y.T @ Yw, Yw.T @ y)
    except np.linalg.LinAlgError:
        coeffs = np.linalg.lstsq(Y * np.sqrt(w)[:, np.newaxis], y * np.sqrt(w), rcond=None)[0]

    # Prediction polynomial A(z) = 1 - sum_k a_k z^-k, and the weighted mean squared residual
    poly = np.concatenate([[1.0], -coeffs])
    residual = y - Y @ coeffs
    lpc_e = float(np.sum(w * residual ** 2) / np.sum(w))

    result = _formants_from_polynomial(poly, sample_rate, max_formant)
    result.update({'method': 'wlp', 'lpc_a': poly, 'lpc_e': lpc_e, 'lpc_order': order, 'lpc_sample_rate': sample_rate})
    return result
