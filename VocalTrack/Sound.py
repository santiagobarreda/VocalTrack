
# Import numpy for numerical array operations
import numpy as np
import logging

# Import utilities for pitch, formant, and spectrum estimation
from .utils.get_pitch import get_pitch  # Standardized pitch/voicing estimator
from .utils.get_formants import get_formants  # Centralized formant extraction
from .utils.get_spectrum import get_spectrum  # Power spectrum calculation

logger = logging.getLogger(__name__)
_warned_parselmouth = False  # Parselmouth setup failure has been logged


class Sound:
    """
    Analyze pitch, voicing, formants, and spectrum from an audio signal chunk.

    This class provides a unified interface for extracting pitch (f0), voicing,
    and the first three formant frequencies (F1, F2, F3) from a short audio segment.
    It uses centralized utility functions for all signal processing, and can optionally
    compute a power spectrum for visualization. The class is agnostic to the backend
    (e.g., Parselmouth/Praat, custom, or built-in) used by the utilities. Any method selection
    (e.g. lpc/autocorrelation/yin/parselmouth/custom) is handled inside the utility functions.

    A Sound keeps the audio it was computed from (`samples`). While recording, AudioProcessor also
    stamps it with `recording_time`, the center of its analysis window in seconds from the start of
    the recording, so the same audio can be found again in the exported WAV file. The visualizers
    keep that time (not the audio) with each point they plot.

    """
    
    def __init__(self,
                 samples=None,
                 sample_rate=10000,
                 n_formants=5.5,
                 formants=True,
                 pitch=True,
                 robust_formants=False,
                 max_formant=None,
                 window_length=0.05,
                 time_step=0.01,
                 pre_emphasis_coeff=0.97,
                 pre_emphasis_hz=50,
                 min_f0=60,
                 max_f0=500,
                 min_confidence=0.45,
                 min_rms_db=None,
                 formant_method='lpc',
                 pitch_method='autocorrelation',
                 compute_spectrum=False,
                 spectrum_nfft=512,
                 max_freq=None,
                 **kwargs):
        """
        Initialize Sound object and optionally perform analysis on provided samples.

        If samples are provided, pitch, voicing, formants, and spectrum (if requested)
        are extracted immediately. Otherwise, the object is initialized with default values.

        Args:
            samples (np.ndarray, optional): Audio samples. Defaults to None.
            sample_rate (int, optional): Sample rate in Hz. Defaults to 10000.
            n_formants (float, optional): Number of formants (LPC order for Praat). Defaults to 5.5.
            formants (bool, optional): Estimate formants. Defaults to True.
            pitch (bool, optional): Estimate pitch. Defaults to True.
            robust_formants (bool, optional): Use robust method. Defaults to False.
            max_formant (float, optional): Maximum formant frequency (Hz). Defaults to Nyquist.
            max_freq (float, optional): Maximum frequency limit for FFT spectrum. Defaults to Nyquist.
            window_length (float, optional): Analysis window length (s). Defaults to 0.05.
            time_step (float, optional): Time step between analyses (s). Defaults to 0.01.
            pre_emphasis_coeff (float, optional): Pre-emphasis filter coefficient. Defaults to 0.97.
            pre_emphasis_hz (float, optional): Pre-emphasis cutoff frequency (Hz). Defaults to 50.
            min_f0 (int, optional): Minimum f0 for pitch/voicing detection. Defaults to 60.
            max_f0 (int, optional): Maximum f0 for pitch/voicing detection. Defaults to 500.
            min_confidence (float, optional): Minimum confidence threshold for accepting pitch estimates. Defaults to 0.45.
            min_rms_db (float, optional): Minimum RMS amplitude in dB for analysis. Defaults to None.
            compute_spectrum (bool, optional): Whether to compute power spectrum. Defaults to False.
            spectrum_nfft (int, optional): FFT size for spectrum. Defaults to 512.
        """
        # Store the audio samples (raw waveform data)
        self.samples = samples

        # Store sample rate (samples per second, typically 10000 Hz)
        self.sample_rate = sample_rate
        # Set max formant: if not provided, use Nyquist frequency (half the sample rate)
        self.max_formant = max_formant if max_formant is not None else (self.sample_rate / 2)
        # Set max frequency for spectrum: if not provided, use Nyquist
        self.max_freq = max_freq if max_freq is not None else (self.sample_rate / 2)
        # Number of formants to track (LPC order for Praat; 5.5 is common for adult speech)
        self.n_formants = n_formants
        # Analysis window length in seconds (default 0.05 = 50ms)
        self.window_length = window_length
        # Time step between consecutive analyses in seconds (default 0.01 = 10ms)
        self.time_step = time_step
        # Pre-emphasis coefficient for high-frequency boost (0.97 is standard)
        self.pre_emphasis_coeff = pre_emphasis_coeff
        # Pre-emphasis frequency cutoff in Hz (50 Hz is standard)
        self.pre_emphasis_hz = pre_emphasis_hz
        # Minimum fundamental frequency for pitch tracking (Hz)
        self.min_f0 = min_f0
        # Maximum fundamental frequency for pitch tracking (Hz)
        self.max_f0 = max_f0
        # Minimum confidence threshold for accepting pitch estimates
        self.min_confidence = min_confidence
        # Minimum RMS amplitude in dB for analysis (None = no gating)
        self.min_rms_db = min_rms_db
        # Method selector for formant backend.
        self.formant_method = formant_method
        # Method selector for pitch backend.
        self.pitch_method = pitch_method

        # Spectrum calculation parameters
        self.compute_spectrum = compute_spectrum  # Whether to compute power spectrum
        self.spectrum_nfft = spectrum_nfft  # FFT size for spectrum
        self.spectrum_window_samples = kwargs.get('spectrum_window_samples', None)
        # Also return the LPC polynomial when the formant backend does not compute one anyway
        # (Parselmouth), for the LPC envelope in LiveSpectrum
        self.lpc_envelope = kwargs.get('lpc_envelope', False)

        # Analysis results - initialize all to 0 or None
        self.f0 = 0   # Fundamental frequency (pitch) in Hz
        self.f1 = 0   # First formant frequency in Hz
        self.f2 = 0   # Second formant frequency in Hz
        self.f3 = 0   # Third formant frequency in Hz
        self.voicing = 0  # Voicing status (0 = unvoiced, 1 = voiced)
        self.lpc_a = None  # LPC polynomial coefficients (from formant tracking)
        self.lpc_e = None  # LPC prediction residual error energy
        self.lpc_order = 0  # LPC order used in analysis
        self.lpc_sample_rate = None  # Sample rate the LPC coefficients correspond to
        self.recording_time = None      # Window center (s) relative to recording start, set by AudioProcessor

        # Spectrum analysis results (only computed if compute_spectrum=True)
        self.spectrum_frequencies = None  # Frequency bins for spectrum (Hz)
        self.spectrum_magnitude_db = None  # Magnitude in dB

        # Store whether to perform formant and pitch analysis
        self.formants = formants
        self.pitch = pitch
        self.robust_formants = robust_formants

        # If audio samples were provided, process them immediately
        if self.samples is not None:
            self.process()

    def process(self):
        """
        Extract audio features (pitch, formants, and power spectrum) from samples.

        Results are stored as attributes of the Sound object.
        """

        # --- Power spectrum computation (for spectrogram visualization) ---
        # This ALWAYS runs regardless of voicing - spectrograms need all frames
        if self.compute_spectrum:
            if self.spectrum_window_samples is not None and 0 < self.spectrum_window_samples < len(self.samples):
                spec_samples = self.samples[-self.spectrum_window_samples:]
            else:
                spec_samples = self.samples

            spectrum_result = get_spectrum(
                audio_chunk=spec_samples,
                sample_rate=self.sample_rate,
                max_freq=int(self.max_freq),  # Use max_freq as FFT frequency limit
                window_samples=len(spec_samples),
                nfft=self.spectrum_nfft,
                pre_emphasis=self.pre_emphasis_coeff
            )
            self.spectrum_frequencies = spectrum_result.get('frequencies')
            self.spectrum_magnitude_db = spectrum_result.get('magnitude_db')


        # --- Pitch, voicing, and formant/LPC estimation ---
        if self.pitch or self.formants:
            # Create a normalized copy of the samples in float64 range [-1, 1]
            if self.samples is not None and self.samples.size > 0:
                if self.samples.dtype == np.int16:
                    normalized_samples = self.samples.astype(np.float64) / 32768.0
                else:
                    normalized_samples = self.samples.copy().astype(np.float64)
            else:
                normalized_samples = np.array([])

            # Pre-allocate Parselmouth sound wrapper once if parselmouth is used for either pitch or formants
            pm_sound = None
            if (self.pitch_method == 'parselmouth' or self.formant_method == 'parselmouth') and normalized_samples.size > 0:
                try:
                    import parselmouth
                    pm_sound = parselmouth.Sound(normalized_samples.astype(np.float32), sampling_frequency=self.sample_rate)
                except Exception as pm_err:
                    # Warn once, not on every frame (e.g. parselmouth selected but not installed)
                    global _warned_parselmouth
                    if not _warned_parselmouth:
                        _warned_parselmouth = True
                        logger.warning(f"Failed to pre-allocate Parselmouth sound: {pm_err}")

            if self.pitch:
                pitch_res = get_pitch(
                    normalized_samples,
                    sample_rate=self.sample_rate,
                    method=self.pitch_method,
                    min_f0=self.min_f0,
                    max_f0=self.max_f0,
                    min_confidence=self.min_confidence,
                    min_rms_db=self.min_rms_db if self.min_rms_db is not None else -999.0,
                    parselmouth_sound=pm_sound
                )
                self.voicing = bool(pitch_res.get('voiced', False))
                f0val = pitch_res.get('f0')
                # Keep sub-Hz precision (the autocorrelation tracker interpolates between lags); 0 = unvoiced
                self.f0 = round(float(f0val), 2) if (f0val is not None and not np.isnan(f0val)) else 0
            else:
                self.voicing = True
                self.f0 = 0

            # --- Formant and LPC extraction ---
            if self.formants:
                # If pitch tracking is active and frame is unvoiced, skip formant extraction
                if self.pitch and not self.voicing:
                    return

                # n_formants_praat (e.g., 5.5) controls LPC order for formant search
                # Extracts formants (F1, F2, F3) and returns LPC filter polynomial
                ff = get_formants(
                    normalized_samples,
                    sample_rate=self.sample_rate,
                    method=self.formant_method,
                    max_formant=int(self.max_formant),
                    robust=self.robust_formants,
                    window_length=self.window_length,
                    time_step=self.time_step,
                    pre_emphasis_hz=self.pre_emphasis_hz,
                    n_formants_praat=self.n_formants,
                    parselmouth_sound=pm_sound,
                    return_lpc=self.lpc_envelope
                )
                # Pad to three values, so a method that finds fewer formants does not fail the frame
                farr = ff.get('formants')
                farr = (list(farr) if farr is not None else []) + [0, 0, 0]
                # Handle NaN values that can come from Parselmouth or other estimators
                self.f1, self.f2, self.f3 = [int(x) if (x and not np.isnan(x)) else 0 for x in farr[:3]]
                all_f = ff.get('all_formants')
                if all_f is not None and len(all_f) > 0:
                    self.formants = [float(x) for x in all_f if (x and not np.isnan(x))]
                else:
                    self.formants = [float(x) for x in [self.f1, self.f2, self.f3] if x > 0]
                self.lpc_a = ff.get('lpc_a', None)
                self.lpc_e = ff.get('lpc_e', None)
                self.lpc_order = ff.get('lpc_order', 0)
                # Rate the LPC was computed at (2 x max_formant when the window was resampled)
                self.lpc_sample_rate = ff.get('lpc_sample_rate', self.sample_rate)
