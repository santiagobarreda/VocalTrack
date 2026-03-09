"""
Spectral analysis utilities for speech/audio analysis.

This module provides a function `get_spectrum` that computes a single 
spectrum from a short audio buffer. It returns frequency bins, dB magnitudes 
(clipped by dynamic range), and a normalized uint8 array suitable for colormap 
mapping. The logic is separated from GUI rendering for modularity.
"""

from typing import Dict
import numpy as np


def get_spectrum(audio_chunk: np.ndarray,
                   sample_rate: int,
                   max_freq: int,
                   window_samples: int,
                   nfft: int,
                   pre_emphasis: float = 0.97,
                   dynamic_range: float = 70.0,
                   gain_db: float = 40.0) -> Dict:
    """
    Compute the spectrum and normalized magnitude column for a short audio chunk.

    Parameters
    ----------
    audio_chunk : np.ndarray
        Audio samples (int16 or float32), 1D array.
    sample_rate : int
        Sample rate in Hz.
    max_freq : int
        Maximum frequency to return in Hz.
    window_samples : int
        Number of samples in the analysis window (e.g., 5ms window).
    nfft : int
        FFT length (window_samples + zero padding).
    pre_emphasis : float, optional
        Pre-emphasis coefficient (default: 0.97, set 0 to disable).
    dynamic_range : float, optional
        dB range for clipping (default: 70 dB).
    gain_db : float, optional
        Additive gain in dB for normalization/visualization (default: +40).

    Returns
    -------
    dict
        Dictionary with keys:
        - 'frequencies': 1D np.ndarray of bin center frequencies (Hz)
        - 'magnitude_db': 1D np.ndarray of clipped dB values
        - 'magnitude_normalized': 1D uint8 array (0-255) for colormap lookup
        - 'max_db': float, maximum dB found in this frame
    """
    if audio_chunk is None:
        return {'frequencies': np.array([]), 'magnitude_db': np.array([]), 'magnitude_normalized': np.array([], dtype=np.uint8), 'max_db': 0.0}

    # Convert to float32 in range [-1, 1]
    if audio_chunk.dtype == np.int16:
        audio_float = audio_chunk.astype(np.float32) / 32768.0
    else:
        audio_float = audio_chunk.astype(np.float32)

    # Pre-emphasis (simple high-pass filter to boost high frequencies)
    if pre_emphasis > 0 and len(audio_float) > 1:
        emphasized = np.append(audio_float[0], audio_float[1:] - pre_emphasis * audio_float[:-1])
    else:
        emphasized = audio_float

    # Remove DC component (subtract mean)
    emphasized = emphasized - np.mean(emphasized)

    # Use only the requested window samples (truncate if longer)
    window = emphasized[:window_samples]
    if len(window) == 0:
        return {'frequencies': np.array([]), 'magnitude_db': np.array([]), 'magnitude_normalized': np.array([], dtype=np.uint8), 'max_db': 0.0}

    # Apply Gaussian window to reduce spectral leakage
    # Gaussian window provides good frequency resolution with minimal side lobes
    std = len(window) / 7.0
    n = np.arange(len(window))
    center = (len(window) - 1) / 2.0
    gaussian_window = np.exp(-0.5 * ((n - center) / std) ** 2)
    # Normalize window to preserve signal amplitude
    window_mean = np.mean(gaussian_window)
    gaussian_window_normalized = gaussian_window / window_mean
    windowed = window * gaussian_window_normalized

    # Zero-pad from end of signal to nfft length
    signal = np.zeros(nfft, dtype=np.float32)
    signal[:len(windowed)] = windowed

    # Compute real FFT (DTFT approximation)
    fft_result = np.fft.rfft(signal, n=nfft)
    magnitude = np.abs(fft_result)
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    # Limit to max_freq
    freq_mask = frequencies <= max_freq
    frequencies = frequencies[freq_mask]
    magnitude = magnitude[freq_mask]
    # Convert magnitude to dB (reference: 1.0 amplitude = 0 dB)
    # This gives approximately -96 to 0 dB for 16-bit audio
    magnitude_db = 20 * np.log10(magnitude + 1e-10)

    # NOTE: gain, dynamic_range clipping, and color normalization are NOT applied here.
    # They are applied by the renderer (LiveSpectrogram.render_spectrogram_column) where
    # gain can be adjusted in real-time and all spectrum processing is centralized.
    # This preserves raw dB values so quiet frames stay quiet without artificial normalization.
    # I used to do it in here and it caused constant bugs. 
    
    # Return raw magnitude for diagnostics
    if magnitude_db.size > 0:
        max_db = float(np.max(magnitude_db))
    else:
        max_db = 0.0
    # Empty normalized array (not used; rendering happens in LiveSpectrogram)
    magnitude_normalized = np.array([], dtype=np.uint8)

    return {
        'frequencies': frequencies,
        'magnitude_db': magnitude_db,
        'magnitude_normalized': magnitude_normalized,
        'max_db': max_db,
    }
