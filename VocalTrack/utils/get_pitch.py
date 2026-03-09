"""
Lightweight pitch (f0) and voicing estimator for speech/audio analysis.

This module provides a fast, dependency-light method for estimating the fundamental 
frequency (f0) and voicing from an audio signal, using an autocorrelation method.
The main entry point is `get_pitch`, which returns a dictionary with f0, voicing, 
confidence, and RMS level.
"""

from typing import Dict
import numpy as np
from .. import config


# Optional Parselmouth import kept local to this module
try:
    import parselmouth
    _HAS_PARSELMOUTH = True
except Exception:
    parselmouth = None
    _HAS_PARSELMOUTH = False

def get_pitch(signal, sample_rate, method=None, **kwargs):
    """
    Thin dispatcher to keep the UI code clean while preserving 
    standalone function readability.
    """
    if method is None:
        method = config.ANALYSIS_CONFIG.get('pitch_method', 'native')
        
    if method == 'parselmouth':
        return get_pitch_parselmouth(signal, sample_rate, **kwargs)
    elif method == 'custom':
        return get_pitch_custom(signal, sample_rate, **kwargs)
    else:
        return get_pitch_native(signal, sample_rate, **kwargs)


def _rms_db(signal: np.ndarray) -> float:
    """
    Compute RMS level in dBF (-96 to 0 dB), assuming input is float in [-1, 1].

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (float, range [-1, 1]).

    Returns
    -------
    float
        RMS level in dBFS. Returns -999.0 for empty or silent signals.
    """
    if signal.size == 0:
        return -999.0
    rms = np.sqrt(np.mean(signal.astype(np.float64) ** 2))
    if rms <= 1e-12:
        return -999.0
    return 20.0 * np.log10(rms)


def _autocorr_pitch(signal: np.ndarray, sample_rate: int, min_f0: int, max_f0: int, min_confidence: float = 0.2):
    """
    Estimate pitch using autocorrelation method.

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (float, 1D array).
    sample_rate : int
        Sampling rate in Hz.
    min_f0 : int
        Minimum f0 to search (Hz).
    max_f0 : int
        Maximum f0 to search (Hz).
    min_confidence : float, optional
        Minimum confidence threshold for accepting a pitch estimate (default: 0.2).

    Returns
    -------
    tuple
        (f0, confidence):
            f0 : float or None
                Estimated f0 in Hz, or None if unvoiced or below confidence threshold.
            confidence : float
                Normalized confidence (0..1).
    """
    x = signal.astype(np.float64)
    if x.size < 3:
        return None, 0.0
    # Remove DC offset
    x = x - np.mean(x)
    # Compute autocorrelation using numpy (no scipy needed)
    ac = np.correlate(x, x, mode='full')
    ac = ac[ac.size // 2:]
    if np.all(ac == 0):
        return None, 0.0
    # Convert f0 bounds to lag bounds
    max_lag = int(sample_rate / min_f0) if min_f0 > 0 else len(ac) - 1
    min_lag = int(sample_rate / max_f0) if max_f0 > 0 else 1
    min_lag = max(1, min_lag)
    max_lag = min(len(ac) - 1, max_lag)
    if max_lag <= min_lag:
        return None, 0.0
    search = ac[min_lag:max_lag + 1]
    peak = np.argmax(search) + min_lag
    peak_value = ac[peak]
    # Confidence: normalized peak relative to lag0
    conf = float(peak_value / (ac[0] + 1e-12))
    if conf < min_confidence:
        return None, conf
    f0 = sample_rate / peak
    return f0, float(conf)


def get_pitch_native(signal: np.ndarray,
               sample_rate: int,
               min_f0: int = 75,
               max_f0: int = 500,
               min_rms_db: float = -60.0,
               min_confidence: float = 0.2) -> Dict:
    """
    Estimate pitch (f0) and voicing for a short audio signal window using a native
    autocorrelation method.

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (1D numpy array, int16 or float).
    sample_rate : int
        Sampling frequency in Hz.
    min_f0 : int, optional
        Minimum f0 to search (Hz, default: 75).
    max_f0 : int, optional
        Maximum f0 to search (Hz, default: 500).
    min_rms_db : float, optional
        Minimum RMS dB threshold for voiced decision (default: -60.0).
    min_confidence : float, optional
        Minimum confidence threshold for accepting a pitch estimate (default: 0.2).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'f0': float or None, estimated f0 in Hz (None if unvoiced)
        - 'voiced': bool, True if voiced
        - 'confidence': float, normalized confidence (0..1)
        - 'rms_db': float, RMS level in dBFS
    """
    # Handle empty or invalid signal: return unvoiced result
    if signal is None or signal.size == 0:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': -999.0, 'method_used': 'native'}

    # Normalize signal to float32 in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float32) / 32768.0
    else:
        sig = signal.astype(np.float32)

    # Calculate RMS level in decibels for voicing gate
    rms_db = _rms_db(sig)
    # If signal is too quiet, classify as unvoiced (no pitch)
    if rms_db < min_rms_db:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': rms_db, 'method_used': 'native'}

    # Apply Gaussian window to reduce edge effects before autocorrelation
    N = len(sig)
    if N > 0:
        # copy of Praat's Gaussian Window. Praat defines the physical window (N) 
        # as exactly twice the effective window length (T)
        n = np.arange(N)
        center = (N - 1) / 2.0
        T = N / 2.0 
        gauss = np.exp(-12.0 * ((n - center) / T) ** 2)
        sig_windowed = sig * gauss
    else:
        sig_windowed = sig

    # Estimate pitch using native autocorrelation method
    f0, conf = _autocorr_pitch(sig_windowed, sample_rate, min_f0, max_f0, min_confidence=min_confidence)
    # Classify as voiced if pitch was found and confidence exceeds threshold
    voiced = (f0 is not None) and (conf > min_confidence)

    return {'f0': f0, 'voiced': bool(voiced), 'confidence': conf, 'rms_db': rms_db, 'method_used': 'native'}


def get_pitch_parselmouth(signal: np.ndarray,
               sample_rate: int,
               min_f0: int = 75,
               max_f0: int = 500,
               min_rms_db: float = -60.0,
               min_confidence: float = 0.2) -> Dict:
    """
    Estimate pitch (f0) and voicing for a short audio signal window using Parselmouth.

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (1D numpy array, int16 or float).
    sample_rate : int
        Sampling frequency in Hz.
    min_f0 : int, optional
        Minimum f0 to search (Hz, default: 75).
    max_f0 : int, optional
        Maximum f0 to search (Hz, default: 500).
    min_rms_db : float, optional
        Minimum RMS dB threshold for voiced decision (default: -60.0).
    min_confidence : float, optional
        MUnused, for API consistency.
    Returns
    -------
    dict
        Dictionary with keys:
        - 'f0': float or None, estimated f0 in Hz (None if unvoiced)
        - 'voiced': bool, True if voiced
        - 'confidence': float, normalized confidence (0..1)
        - 'rms_db': float, RMS level in dBFS
    """
    
    # Handle empty or invalid signal: return unvoiced result
    if signal is None or signal.size == 0:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': -999.0, 'method_used': 'parselmouth'}

    # Normalize signal to float32 in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float32) / 32768.0
    else:
        sig = signal.astype(np.float32)

    # Calculate RMS level in decibels for voicing gate
    rms_db = _rms_db(sig)

    # If signal is too quiet, classify as unvoiced (no pitch)
    if rms_db < min_rms_db:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': rms_db, 'method_used': 'parselmouth'}

    # Use Parselmouth/Praat for pitch tracking
    try:
        snd = parselmouth.Sound(sig, sampling_frequency=sample_rate)
        pitch_obj = snd.to_pitch_ac(time_step=0.01, pitch_floor=min_f0, pitch_ceiling=max_f0)
        mean_f0 = parselmouth.praat.call(pitch_obj, 'Get mean', 0, 0, 'Hertz')

        # In Parselmouth, a mean_f0 of 0 or None from 'Get mean' indicates unvoiced.
        # Confidence is not directly provided for the mean f0, so we set it to 1.0 for voiced, 0.0 for unvoiced.
        is_voiced = mean_f0 is not None and mean_f0 > 0
        
        f0_val = float(mean_f0) if is_voiced else None
        confidence = 1.0 if is_voiced else 0.0

        return {'f0': f0_val, 'voiced': is_voiced, 'confidence': confidence, 'rms_db': rms_db, 'method_used': 'parselmouth'}

    except Exception:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': rms_db, 'method_used': 'parselmouth'}


def get_pitch_custom(signal: np.ndarray,
               sample_rate: int,
               min_f0: int = 75,
               max_f0: int = 500,
               min_rms_db: float = -60.0,
               min_confidence: float = 0.2) -> Dict:
    """
    Estimate pitch (f0) and voicing for a short audio signal window using a native
    autocorrelation method.

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (1D numpy array, int16 or float).
    sample_rate : int
        Sampling frequency in Hz.
    min_f0 : int, optional
        Minimum f0 to search (Hz, default: 75).
    max_f0 : int, optional
        Maximum f0 to search (Hz, default: 500).
    min_rms_db : float, optional
        Minimum RMS dB threshold for voiced decision (default: -60.0).
    min_confidence : float, optional
        Minimum confidence threshold for accepting a pitch estimate (default: 0.2).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'f0': float or None, estimated f0 in Hz (None if unvoiced)
        - 'voiced': bool, True if voiced
        - 'confidence': float, normalized confidence (0..1)
        - 'rms_db': float, RMS level in dBFS
    """

    # Your custom pitch tracking function here
    return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': 0.0, 'method_used': 'native'}


