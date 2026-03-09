
# Import numpy for numerical array operations
import numpy as np
# Import time for high-resolution analysis timestamping
import time

# Import utilities for pitch, formant, and spectrum estimation
from .utils.get_pitch import get_pitch  # Standardized pitch/voicing estimator
from .utils.get_formants import get_formants  # Centralized formant extraction
from .utils.get_spectrum import get_spectrum  # Power spectrum calculation


class Sound:
    """
    Analyze pitch, voicing, formants, and spectrum from an audio signal chunk.

    This class provides a unified interface for extracting pitch (f0), voicing,
    and the first three formant frequencies (F1, F2, F3) from a short audio segment.
    It uses centralized utility functions for all signal processing, and can optionally
    compute a power spectrum for visualization. The class is agnostic to the backend
    (e.g., Parselmouth/Praat, custom, or native) used by the utilities. Any method selection 
    (native/parselmouth/custom) is handled inside the utility functions. 
    
    """
    
    def __init__(self,
                 samples=None,
                 sample_rate=10000,
                 n_formants=5.5,
                 formants=True,
                 robust_formants=False,
                 max_formant=None,
                 window_length=0.05,
                 time_step=0.01,
                 pre_emphasis_coeff=0.97,
                 pre_emphasis_hz=50,
                 min_f0=75,
                 max_f0=300,
                 min_confidence=0.2,
                 min_rms_db=None,
                 compute_spectrum=False,
                 spectrum_nfft=512,
                 spectrum_dynamic_range=70.0,
                 spectrum_gain_db=40.0,
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
            robust_formants (bool, optional): Use robust method. Defaults to False.
            max_formant (float, optional): Maximum formant frequency (Hz). Defaults to Nyquist.
            window_length (float, optional): Analysis window length (s). Defaults to 0.05.
            time_step (float, optional): Time step between analyses (s). Defaults to 0.01.
            pre_emphasis_coeff (float, optional): Pre-emphasis filter coefficient. Defaults to 0.97.
            pre_emphasis_hz (float, optional): Pre-emphasis cutoff frequency (Hz). Defaults to 50.
            min_f0 (int, optional): Minimum f0 for pitch/voicing detection. Defaults to 75.
            max_f0 (int, optional): Maximum f0 for pitch/voicing detection. Defaults to 300.
            min_confidence (float, optional): Minimum confidence threshold for accepting pitch estimates. Defaults to 0.2.
            min_rms_db (float, optional): Minimum RMS amplitude in dB for analysis. Defaults to None.
            compute_spectrum (bool, optional): Whether to compute power spectrum. Defaults to False.
            spectrum_nfft (int, optional): FFT size for spectrum. Defaults to 512.
            spectrum_dynamic_range (float, optional): Dynamic range for spectrum in dB. Defaults to 70.0.
            spectrum_gain_db (float, optional): Gain in dB for spectrum. Defaults to 40.0.
        """
        # Store the audio samples (raw waveform data)
        self.samples = samples

        # Try to determine chunk size from samples length (for duration calculation)
        try:
            chunk_size = len(samples)  # Number of samples in the audio chunk
        except TypeError:
            # If samples is None or not iterable, set chunk size to 0
            chunk_size = 0

        # Store sample rate (samples per second, typically 10000 Hz)
        self.sample_rate = sample_rate
        # Set max formant: if not provided, use Nyquist frequency (half the sample rate)
        self.max_formant = max_formant if max_formant is not None else (self.sample_rate / 2)
        # Calculate duration in milliseconds from chunk size and sample rate
        self.duration = 1000 * chunk_size / sample_rate
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
        # Minimum fundamental frequency for pitch tracking (75 Hz for male voices)
        self.min_f0 = min_f0
        # Maximum fundamental frequency for pitch tracking (300 Hz covers most adult speech)
        self.max_f0 = max_f0
        # Minimum confidence threshold for accepting pitch estimates
        self.min_confidence = min_confidence
        # Minimum RMS amplitude in dB for analysis (None = no gating)
        self.min_rms_db = min_rms_db

        # Spectrum calculation parameters
        self.compute_spectrum = compute_spectrum  # Whether to compute power spectrum
        self.spectrum_nfft = spectrum_nfft  # FFT size for spectrum
        self.spectrum_dynamic_range = spectrum_dynamic_range  # Dynamic range in dB
        self.spectrum_gain_db = spectrum_gain_db  # Gain in dB for spectrum

        # Analysis results - initialize all to 0 or None
        self.f0 = 0   # Fundamental frequency (pitch) in Hz
        self.f1 = 0   # First formant frequency in Hz
        self.f2 = 0   # Second formant frequency in Hz
        self.f3 = 0   # Third formant frequency in Hz
        self.voicing = 0  # Voicing status (0 = unvoiced, 1 = voiced)
        self.analysis_timestamp = None  # Timestamp for when analysis finished (perf_counter seconds)
        self.capture_timestamp = None   # Timestamp for when the analysis window was captured (perf_counter seconds)

        # Spectrum analysis results (only computed if compute_spectrum=True)
        self.spectrum_frequencies = None  # Frequency bins for spectrum (Hz)
        self.spectrum_magnitude_db = None  # Magnitude in dB
        self.spectrum_magnitude_normalized = None  # Normalized magnitude (0-255 uint8)
        self.spectrum_max_db = None  # Maximum dB in this frame

        # Store whether to perform formant analysis
        self.formants = formants
        # Store whether to use robust formant estimation (slower but more accurate)
        self.robust_formants = robust_formants

        # If samples were provided, run the analysis immediately
        if self.samples is not None:
            self.process()

    def process(self):
        """
        Extract pitch, voicing, formants, and/or spectrum from audio samples.

        This method runs the full analysis pipeline on the current audio chunk:
        - Pitch and voicing are always estimated using the standardized utility.
        - Power spectrum is computed if requested (for spectrogram visualization).
        - Formant extraction is only performed on voiced frames (for efficiency).
        Results are stored as attributes of the Sound object.
        """

        # --- Power spectrum computation (for spectrogram visualization) ---
        # This ALWAYS runs regardless of voicing - spectrograms need all frames
        if self.compute_spectrum:
            spectrum_result = get_spectrum(
                audio_chunk=self.samples,
                sample_rate=self.sample_rate,
                max_freq=int(self.max_formant),  # Use max_formant as frequency limit
                window_samples=len(self.samples),
                nfft=self.spectrum_nfft,
                pre_emphasis=self.pre_emphasis_coeff,
                dynamic_range=self.spectrum_dynamic_range,
                gain_db=self.spectrum_gain_db
            )
            self.spectrum_frequencies = spectrum_result.get('frequencies')
            self.spectrum_magnitude_db = spectrum_result.get('magnitude_db')
            self.spectrum_magnitude_normalized = spectrum_result.get('magnitude_normalized')
            self.spectrum_max_db = spectrum_result.get('max_db')


        # --- Pitch and voicing estimation ---
        # Pitch is only estimate if spectrum is not, i.e., if we're not in spectrogram mode 
        # where we only care about the spectrum and not f0 and formants
        if not self.compute_spectrum:
            pitch_res = get_pitch(
                self.samples if self.samples is not None else np.array([]),
                sample_rate=self.sample_rate,
                min_f0=self.min_f0,
                max_f0=self.max_f0,
                min_confidence=self.min_confidence,
                min_rms_db=self.min_rms_db if self.min_rms_db is not None else -999.0
            )

            # Store voicing and f0 from standardized estimator
            self.voicing = bool(pitch_res.get('voiced', False))
            f0val = pitch_res.get('f0')
            self.f0 = int(f0val) if (f0val is not None and not np.isnan(f0val)) else 0            

            # --- Formant extraction (only on voiced frames) ---
            if not self.voicing:
                # If frame is unvoiced, skip formant extraction for efficiency
                self.analysis_timestamp = time.perf_counter()
                return

            if self.formants:
                # n_formants_praat (e.g., 5.5) controls LPC order for formant search
                # Always extract and return only the first 3 formants (F1, F2, F3)
                ff = get_formants(
                    self.samples,
                    sample_rate=self.sample_rate,
                    max_formant=int(self.max_formant),
                    robust=self.robust_formants,
                    window_length=self.window_length,
                    time_step=self.time_step,
                    pre_emphasis_hz=self.pre_emphasis_hz,
                    n_formants_praat=self.n_formants
                )
                farr = ff.get('formants', np.zeros(3))
                # Handle NaN values that can come from Parselmouth or other estimators
                self.f1, self.f2, self.f3 = [int(x) if (x and not np.isnan(x)) else 0 for x in farr[:3]]

            # Store analysis timestamp after all computations
            self.analysis_timestamp = time.perf_counter()