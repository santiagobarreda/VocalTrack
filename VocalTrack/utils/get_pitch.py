"""
Lightweight pitch (f0) and voicing estimator for speech/audio analysis.

This module provides fast, dependency-light methods for estimating the fundamental
frequency (f0) and voicing from an audio signal: a window-corrected autocorrelation method
('autocorrelation') and YIN ('yin'), plus Praat via Parselmouth ('parselmouth').
The main entry point is `get_pitch`, which returns a dictionary with f0, voicing, 
confidence, and RMS level.
"""

from typing import Dict
import functools
import logging
import math
import numpy as np
from .. import config

logger = logging.getLogger(__name__)


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
        method = config.ANALYSIS_CONFIG.get('pitch_method', 'autocorrelation')
    method = config.current_method_name('pitch_method', method)

    if method == 'parselmouth':
        return get_pitch_parselmouth(signal, sample_rate, **kwargs)
    elif method == 'autocorrelation':
        kwargs.pop('parselmouth_sound', None)
        return get_pitch_autocorrelation(signal, sample_rate, **kwargs)
    elif method == 'yin':
        kwargs.pop('parselmouth_sound', None)
        return get_pitch_yin(signal, sample_rate, **kwargs)
    elif method == 'custom':
        kwargs.pop('parselmouth_sound', None)
        return get_pitch_custom(signal, sample_rate, **kwargs)
    else:
        raise ValueError(f"Unknown pitch method: {method}")


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


# Preference for shorter lags, per octave of lag (Boersma 1993's "octave cost"). Once the window
# is corrected for, the autocorrelation at 2x and 3x the period is about as high as at the period
# itself; this breaks the tie in favour of the true period. Praat's default is 0.01, but Praat
# also tracks the best path across frames; single-frame estimation needs a larger value.
OCTAVE_COST = 0.05
# Lags at which the window's own autocorrelation has fallen below this fraction of its lag-0 value
# are not searched: dividing by it there amplifies noise more than it corrects the window.
_MIN_WINDOW_AUTOCORR = 0.1
_warned_min_f0 = set()  # (window length, sample rate, min_f0) combinations already warned about


def _autocorr_pitch(signal: np.ndarray, sample_rate: int, min_f0: float, max_f0: float):
    """
    Estimate pitch with the windowed autocorrelation method of Boersma (1993), as in Praat's
    "To Pitch (ac)": the signal's autocorrelation is divided by the autocorrelation of the
    (Hanning) analysis window, so peaks at long lags (low f0) are not suppressed by the window.
    Peak lags and heights are refined by parabolic interpolation.

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (float, 1D array), not yet windowed.
    sample_rate : int
        Sampling rate in Hz.
    min_f0 : float
        Minimum f0 to search (Hz).
    max_f0 : float
        Maximum f0 to search (Hz).

    Returns
    -------
    tuple
        (f0, confidence):
            f0 : float or None
                Estimated f0 in Hz, or None if no autocorrelation peak falls in the f0 range.
            confidence : float
                Height of the chosen window-corrected autocorrelation peak (0..1).
    """
    x = signal.astype(np.float64)
    N = x.size
    if N < 4:
        return None, 0.0

    # Remove the DC offset before windowing, then apply a Hanning window
    window, wac, max_usable_lag = _hanning_window(N)
    xw = (x - np.mean(x)) * window

    # Autocorrelation of the windowed signal, normalised to 1 at lag 0
    ac = np.correlate(xw, xw, mode='full')[N - 1:]
    if ac[0] <= 0:
        return None, 0.0
    # Divide by the window's own normalised autocorrelation (the window correction)
    r = (ac / ac[0]) / np.maximum(wac, _MIN_WINDOW_AUTOCORR)

    # Lag search range from the f0 range, limited to lags the window supports
    min_lag = max(1, int(math.floor(sample_rate / max_f0))) if max_f0 > 0 else 1
    max_lag_requested = int(math.ceil(sample_rate / min_f0)) if min_f0 > 0 else N - 2
    max_lag = min(max_lag_requested, max_usable_lag, N - 2)
    if max_lag < max_lag_requested:
        key = (N, sample_rate, min_f0)
        if key not in _warned_min_f0:
            _warned_min_f0.add(key)
            logger.warning(f"Analysis window ({1000.0 * N / sample_rate:.0f} ms) is too short for min f0 "
                           f"{min_f0} Hz; the lowest f0 that can be tracked is {sample_rate / max_lag:.1f} Hz. "
                           f"Use a longer window (Window Length in Analysis Settings) to track lower voices.")
    if max_lag <= min_lag:
        return None, 0.0

    # Candidates: local maxima of r within the lag range
    lags = np.arange(min_lag, max_lag + 1)
    left, peak, right = r[lags - 1], r[lags], r[lags + 1]
    is_peak = (peak > 0) & (peak >= left) & (peak >= right)
    if not np.any(is_peak):
        return None, 0.0
    lags, left, peak, right = lags[is_peak], left[is_peak], peak[is_peak], right[is_peak]

    # Parabolic interpolation of each peak's lag and height
    curvature = left - 2.0 * peak + right
    offset = np.zeros_like(peak)
    curved = curvature < 0
    offset[curved] = 0.5 * (left[curved] - right[curved]) / curvature[curved]
    true_lag = lags + offset
    height = peak - 0.25 * (left - right) * offset
    f0 = sample_rate / true_lag
    in_range = (f0 >= min_f0) & (f0 <= max_f0)
    if not np.any(in_range):
        return None, 0.0
    true_lag, height, f0 = true_lag[in_range], height[in_range], f0[in_range]

    # Octave cost: prefer the shortest lag among near-equal peaks
    strength = height - OCTAVE_COST * np.log2(min_f0 * true_lag / sample_rate) if min_f0 > 0 else height
    best = int(np.argmax(strength))
    return float(f0[best]), float(min(max(height[best], 0.0), 1.0))


@functools.lru_cache(maxsize=8)
def _hanning_window(N):
    """
    Hanning window of length N, its autocorrelation normalised to 1 at lag 0, and the longest
    lag at which that autocorrelation is still usable for the window correction.
    """
    n = np.arange(N)
    window = 0.5 - 0.5 * np.cos(2.0 * np.pi * (n + 0.5) / N)
    wac = np.correlate(window, window, mode='full')[N - 1:]
    wac = wac / wac[0]
    max_usable_lag = int(np.nonzero(wac >= _MIN_WINDOW_AUTOCORR)[0][-1])
    window.flags.writeable = False
    wac.flags.writeable = False
    return window, wac, max_usable_lag


def get_pitch_autocorrelation(signal: np.ndarray,
               sample_rate: int,
               min_f0: int = 75,
               max_f0: int = 500,
               min_rms_db: float = -60.0,
               min_confidence: float = 0.45) -> Dict:
    """
    Estimate pitch (f0) and voicing for a short audio signal window using a built-in
    window-corrected autocorrelation method (Boersma 1993; see _autocorr_pitch).

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (1D numpy array, int16 or float).
    sample_rate : int
        Sampling frequency in Hz.
    min_f0 : int, optional
        Minimum f0 to search (Hz, default: 75). The window must be long enough for this;
        it must hold about 1.8 periods of min_f0 (a 50 ms window reaches down to about 36 Hz).
    max_f0 : int, optional
        Maximum f0 to search (Hz, default: 500).
    min_rms_db : float, optional
        Minimum RMS dB threshold for voiced decision (default: -60.0).
    min_confidence : float, optional
        Minimum window-corrected autocorrelation peak for a voiced frame (default: 0.45,
        Praat's voicing threshold).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'f0': float or None, estimated f0 in Hz (None if unvoiced)
        - 'voiced': bool, True if voiced
        - 'confidence': float, window-corrected autocorrelation peak height (0..1)
        - 'rms_db': float, RMS level in dBFS
    """
    # Handle empty or invalid signal: return unvoiced result
    if signal is None or signal.size == 0:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': -999.0, 'method_used': 'autocorrelation'}

    # Normalize signal to float32 in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float32) / 32768.0
    else:
        sig = signal.astype(np.float32)

    # Calculate RMS level in decibels for voicing gate
    rms_db = _rms_db(sig)
    # If signal is too quiet, classify as unvoiced (no pitch)
    if rms_db < min_rms_db:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': rms_db, 'method_used': 'autocorrelation'}

    # Estimate pitch with the window-corrected autocorrelation method (windowing happens inside)
    f0, conf = _autocorr_pitch(sig, sample_rate, min_f0, max_f0)
    # Classify as voiced if pitch was found and confidence exceeds threshold
    voiced = (f0 is not None) and (conf > min_confidence)
    if not voiced:
        f0 = None

    return {'f0': f0, 'voiced': bool(voiced), 'confidence': conf, 'rms_db': rms_db, 'method_used': 'autocorrelation'}


# YIN absolute threshold on the cumulative mean normalized difference (de Cheveigne & Kawahara
# 2002 use 0.1): the first dip below it is taken as the period, which avoids octave-down errors
# from later dips of similar depth.
YIN_THRESHOLD = 0.1


def _yin_pitch(signal: np.ndarray, sample_rate: int, min_f0: float, max_f0: float):
    """
    Estimate pitch with YIN (de Cheveigne & Kawahara 2002): difference function, cumulative
    mean normalized difference, absolute threshold, and parabolic interpolation (steps 1-5
    of the paper; the best-local-estimate step 6 is not used, since each frame stands alone).

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (float, 1D array).
    sample_rate : int
        Sampling rate in Hz.
    min_f0 : float
        Minimum f0 to search (Hz).
    max_f0 : float
        Maximum f0 to search (Hz).

    Returns
    -------
    tuple
        (f0, confidence):
            f0 : float or None
                Estimated f0 in Hz, or None if no dip falls in the f0 range.
            confidence : float
                1 - aperiodicity, where aperiodicity is the normalized difference at the chosen
                dip (1 = perfectly periodic, 0 = no periodicity).
    """
    x = signal.astype(np.float64)
    x = x - np.mean(x)
    N = x.size

    # Lag range. The comparison window (N - max_lag samples) must be at least max_lag long,
    # i.e. hold at least one period of the lowest f0, so lags are capped at N // 2.
    min_lag = max(2, int(math.floor(sample_rate / max_f0))) if max_f0 > 0 else 2
    max_lag_requested = int(math.ceil(sample_rate / min_f0)) if min_f0 > 0 else N // 2
    max_lag = min(max_lag_requested, N // 2)
    if max_lag < max_lag_requested:
        key = ('yin', N, sample_rate, min_f0)
        if key not in _warned_min_f0:
            _warned_min_f0.add(key)
            logger.warning(f"Analysis window ({1000.0 * N / sample_rate:.0f} ms) is too short for min f0 "
                           f"{min_f0} Hz with YIN; the lowest f0 that can be tracked is {sample_rate / max_lag:.1f} Hz. "
                           f"Use a longer window (Window Length in Analysis Settings) to track lower voices.")
    if max_lag <= min_lag + 1:
        return None, 0.0

    # Step 2: difference function d(tau) = sum_{j<W} (x[j] - x[j + tau])^2 over a fixed window W,
    # computed as energy(x[0:W]) + energy(x[tau:tau+W]) - 2 * crosscorrelation, for tau = 0..max_lag+1
    W = N - (max_lag + 1)
    energy = np.concatenate([[0.0], np.cumsum(x * x)])
    taus = np.arange(max_lag + 2)
    shifted_energy = energy[taus + W] - energy[taus]
    cross = np.correlate(x[:W + max_lag + 1], x[:W], mode='valid')
    diff = np.maximum(energy[W] + shifted_energy - 2.0 * cross, 0.0)
    if energy[W] <= 0:
        return None, 0.0

    # Step 3: cumulative mean normalized difference d'(tau) = d(tau) * tau / sum_{j=1..tau} d(j)
    cmnd = np.ones_like(diff)
    running = np.cumsum(diff[1:])
    with np.errstate(divide='ignore', invalid='ignore'):
        cmnd[1:] = np.where(running > 0, diff[1:] * taus[1:] / running, 1.0)

    # Step 4: absolute threshold - the first lag in range below the threshold, followed down to
    # its local minimum; if none, the global minimum in range
    search = cmnd[min_lag:max_lag + 1]
    below = np.nonzero(search < YIN_THRESHOLD)[0]
    if below.size:
        tau = min_lag + int(below[0])
        while tau + 1 <= max_lag and cmnd[tau + 1] < cmnd[tau]:
            tau += 1
    else:
        tau = min_lag + int(np.argmin(search))

    # Step 5: parabolic interpolation around the dip
    left, mid, right = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
    curvature = left - 2.0 * mid + right
    offset = 0.5 * (left - right) / curvature if curvature > 0 else 0.0
    offset = max(-0.5, min(0.5, offset))
    true_lag = tau + offset
    aperiodicity = mid - 0.25 * (left - right) * offset

    f0 = sample_rate / true_lag
    if f0 < min_f0 or f0 > max_f0:
        return None, 0.0
    return float(f0), float(min(max(1.0 - aperiodicity, 0.0), 1.0))


def get_pitch_yin(signal: np.ndarray,
                  sample_rate: int,
                  min_f0: int = 75,
                  max_f0: int = 500,
                  min_rms_db: float = -60.0,
                  min_confidence: float = 0.45) -> Dict:
    """
    Estimate pitch (f0) and voicing for a short audio signal window using a built-in
    implementation of YIN (de Cheveigne & Kawahara 2002; see _yin_pitch).

    Parameters
    ----------
    signal : np.ndarray
        Input audio signal (1D numpy array, int16 or float).
    sample_rate : int
        Sampling frequency in Hz.
    min_f0 : int, optional
        Minimum f0 to search (Hz, default: 75). The window must hold 2 periods of min_f0
        (a 50 ms window reaches down to about 40 Hz).
    max_f0 : int, optional
        Maximum f0 to search (Hz, default: 500).
    min_rms_db : float, optional
        Minimum RMS dB threshold for voiced decision (default: -60.0).
    min_confidence : float, optional
        Minimum periodicity (1 - YIN aperiodicity) for a voiced frame (default: 0.45).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'f0': float or None, estimated f0 in Hz (None if unvoiced)
        - 'voiced': bool, True if voiced
        - 'confidence': float, 1 - YIN aperiodicity (0..1)
        - 'rms_db': float, RMS level in dBFS
    """
    if signal is None or signal.size == 0:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': -999.0, 'method_used': 'yin'}

    # Normalize signal to float in range [-1, 1]
    if signal.dtype == np.int16:
        sig = signal.astype(np.float32) / 32768.0
    else:
        sig = signal.astype(np.float32)

    rms_db = _rms_db(sig)
    if rms_db < min_rms_db:
        return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': rms_db, 'method_used': 'yin'}

    f0, conf = _yin_pitch(sig, sample_rate, min_f0, max_f0)
    voiced = (f0 is not None) and (conf > min_confidence)
    if not voiced:
        f0 = None

    return {'f0': f0, 'voiced': bool(voiced), 'confidence': conf, 'rms_db': rms_db, 'method_used': 'yin'}


def get_pitch_parselmouth(signal: np.ndarray,
               sample_rate: int,
               min_f0: int = 75,
               max_f0: int = 500,
               min_rms_db: float = -60.0,
               min_confidence: float = 0.2,
               parselmouth_sound=None) -> Dict:
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
        Unused, for API consistency.
    parselmouth_sound : parselmouth.Sound, optional
        Pre-allocated Parselmouth Sound object to reuse.
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
        snd = parselmouth_sound if parselmouth_sound is not None else parselmouth.Sound(sig, sampling_frequency=sample_rate)
        # Praat needs 3 periods of the pitch floor in the window and raises an error otherwise, which
        # would leave every frame unvoiced. Like the built-in methods, track what the window allows.
        pitch_floor = min_f0
        lowest_floor = 3.0 / snd.duration
        if pitch_floor < lowest_floor - 1e-6:
            pitch_floor = lowest_floor + 1e-6
            key = ('parselmouth', signal.size, sample_rate, min_f0)
            if key not in _warned_min_f0:
                _warned_min_f0.add(key)
                logger.warning(f"Analysis window ({1000.0 * snd.duration:.0f} ms) is too short for min f0 "
                               f"{min_f0} Hz with Parselmouth; the lowest f0 that can be tracked is {lowest_floor:.1f} Hz. "
                               f"Use a longer window (Window Length in Analysis Settings) to track lower voices.")
        pitch_obj = snd.to_pitch_ac(time_step=0.01, pitch_floor=pitch_floor, pitch_ceiling=max_f0)
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
    Placeholder for your own pitch (f0) and voicing estimator (pitch_method='custom').
    Not implemented: it always returns an unvoiced frame. Replace the body with your method,
    keeping the arguments and the returned dictionary keys.

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

    # YOUR METHOD IMPLEMENTATION HERE
    if not get_pitch_custom._warned:
        logger.warning(
            "pitch_method='custom' is selected but get_pitch_custom() is an unimplemented "
            "placeholder - every frame is unvoiced. Implement it in utils/get_pitch.py, or "
            "switch to 'autocorrelation', 'yin', or 'parselmouth' in Analysis Settings."
        )
        get_pitch_custom._warned = True
    return {'f0': None, 'voiced': False, 'confidence': 0.0, 'rms_db': 0.0, 'method_used': 'custom'}


get_pitch_custom._warned = False


