"""
Spectral analysis utilities for speech/audio analysis.

This module provides a function `get_spectrum` that computes a single
spectrum from a short audio buffer and returns frequency bins and raw dB magnitudes.
Gain, dynamic range and colour mapping are applied by the visualizers.
"""

from typing import Dict
import numpy as np


def get_spectrum(audio_chunk: np.ndarray,
                   sample_rate: int,
                   max_freq: int,
                   window_samples: int,
                   nfft: int,
                   pre_emphasis: float = 0.97) -> Dict:
    """
    Compute the magnitude spectrum (dB) of a short audio chunk.

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

    Returns
    -------
    dict
        Dictionary with keys:
        - 'frequencies': 1D np.ndarray of bin center frequencies (Hz)
        - 'magnitude_db': 1D np.ndarray of dB values (not clipped)
    """
    empty = {'frequencies': np.array([]), 'magnitude_db': np.array([])}
    if audio_chunk is None:
        return empty

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
        return empty

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

    # Zero-pad from end of signal to nfft length (or signal length if larger)
    actual_nfft = max(nfft, len(windowed))
    signal = np.zeros(actual_nfft, dtype=np.float32)
    signal[:len(windowed)] = windowed

    # Compute real FFT (DTFT approximation)
    fft_result = np.fft.rfft(signal, n=actual_nfft)
    magnitude = np.abs(fft_result)
    frequencies = np.fft.rfftfreq(actual_nfft, 1.0 / sample_rate)
    # Limit to max_freq
    freq_mask = frequencies <= max_freq
    frequencies = frequencies[freq_mask]
    magnitude = magnitude[freq_mask]
    # Convert magnitude to dB relative to a bin magnitude of 1.0. This is a relative scale for
    # display: it depends on the window length and FFT size, so it is not calibrated to dBFS.
    magnitude_db = 20 * np.log10(magnitude + 1e-10)

    # Gain, dynamic-range clipping and colour mapping are NOT applied here. The visualizers
    # (LiveSpectrogram.render_spectrogram_column, LiveSpectrum) apply them, so gain can be
    # adjusted in real time and quiet frames stay quiet.
    return {'frequencies': frequencies, 'magnitude_db': magnitude_db}
