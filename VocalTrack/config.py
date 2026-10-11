"""Configuration settings for VocalTrack application."""

# Performance and Logging
PERFORMANCE_CONFIG = {
    'logging_level': 30,  # logging.WARNING - use 10 for DEBUG, 20 for INFO
}

# Export and Data Settings
EXPORT_CONFIG = {
    'data_dir': '.',  # Subject/data directory for project files (settings, templates, recordings)
    'save_csv': True,  # Save timestamped CSV data (formants / pitch)
    'save_original_audio': True,  # Save the device-rate/original audio stream as WAV
    'save_downsampled_audio': False,  # Save the analysis-rate/downsampled audio stream as WAV
    'output_dir': 'recordings',  # Output subdirectory for recordings (relative to data_dir)
}

# Audio Processing
AUDIO_CONFIG = {
    'sample_rate': 10000,  # Auto-calculated as 2 × max_formant (Nyquist theorem: 5000 Hz × 2 = 10000 Hz)
    'window_ms': 50,  # Analysis window length in milliseconds (LiveVowel and LivePitch)
    'min_rms_db': -60.0  # Minimum RMS amplitude in dB for analysis
}


def chunk_ms_for_fps(fps):
    """Audio chunk duration (ms) for a display refresh rate: one chunk, and so one analysis, per
    display frame. The chunk is the time step between analyses."""
    return 1000.0 / max(float(fps), 1.0)

# GUI - LiveVowel
LIVEVOWEL_CONFIG = {
    'gui_size': (900.0, 650.0),
    'f1_range': (200.0, 1200.0),
    'f2_range': (500.0, 3000.0),
    'fps': 60,
    'show_vowel_template': False,  # Show vowel template overlay
    'template_file': 'IPA_all_vowels.json',  # Vowel template in templates/ ('None' = no template)
    'display_mode': 'single',  # Visualization mode: 'single', 'track', or 'all'
    'freq_scale': 'log',  # Frequency axis scale: 'log' or 'linear'
}

# GUI - LivePitch
LIVEPITCH_CONFIG = {
    'gui_width': 1200,
    'gui_height': 650,
    'min_f0': 75,
    'max_f0': 500,
    'fps': 60,
    'pitch_plot_mode': 'fixed',  # 'fixed' or 'continuous'
    'pitch_display_seconds': 5.0,  # Display window width in seconds
    'freq_scale': 'log',  # Frequency axis scale: 'log' or 'linear'
}

# GUI - LiveSpectrogram
LIVESPECTROGRAM_CONFIG = {
    'gui_width': 1200,  # Display window width in pixels (typical: 1200 for widescreen)
    'gui_height': 650,  # Display window height in pixels; larger height = finer frequency resolution
    'max_freq': 5000,  # Maximum frequency to display in Hz; limits X-axis range (avoids aliasing above 5kHz for 10kHz sample rate)
    'display_seconds': 3.0,  # Time window duration in seconds; controls horizontal scroll speed (5s typical for real-time response)
    'colormap': 'plasma',  # Matplotlib colormap name for magnitude-to-color mapping; 'plasma' is perceptually uniform
    'dynamic_range': 40,  # Dynamic range in dB for spectrogram amplitude display; controls contrast (smaller=more detail, larger=more contrast)
    'gain_db': 0.0,  # Default gain in dB for spectrogram display brightness
    'fps': 60,  # Frame rate for display refresh (30 fps is UI-responsive but lower CPU than 60)
    'window_ms': 6.0,  # Analysis window length in ms (short = wide-band, long = narrow-band)
    'time_step_ms': 6.0,  # Time between analyses in ms: each analysis is drawn as one column
    'padding_length_ms': 20.0,  # Zero-padding length in milliseconds for frequency resolution enhancement (typical: 20ms)
}

# GUI - LiveSpectrum
LIVESPECTRUM_CONFIG = {
    'gui_width': 1200,  # Display window width in pixels
    'gui_height': 650,  # Display window height in pixels
    'max_freq': 8000,  # Maximum frequency to display in Hz; also the highest max formant reachable with [ / ]
    'dynamic_range': 70,  # Dynamic range in dB for amplitude display
    'gain_offset_db': -30.0,  # Default gain offset in dB
    'fps': 60,  # Frame rate for display refresh; one spectrum is analyzed per frame
    'window_ms': 50.0,  # Analysis window length in ms
    'padding_length_ms': 20.0,  # Zero-padding length in milliseconds for frequency resolution enhancement
    'smoothing': 0.7,  # Response factor alpha (1=no smoothing/instantaneous, 0=maximum smoothing/frozen)
}

# Analysis
ANALYSIS_CONFIG = {
    'n_formants': 5.5,
    'robust_formants': False,
    'max_formant': 5000,
    'window_length': 0.05,  # Analysis window in seconds: window_ms / 1000
    'time_step': 1.0 / 60,  # Time between analyses in seconds: one display frame (set by each visualizer from its fps)
    'pre_emphasis_coeff': 0.97,
    'pre_emphasis_hz': 50,
    'min_f0': 60,  # Minimum f0 for analysis
    'max_f0': 500,  # Maximum f0 for analysis
    'min_confidence': 0.45,  # Minimum window-corrected autocorrelation peak for a voiced frame (Praat's voicing threshold)
    'min_rms_db': -60.0,  # Minimum RMS amplitude in dB for analysis
    'formant_method': 'lpc',  # Formant analysis method: 'lpc', 'wlp', 'parselmouth', or 'custom'
    'pitch_method': 'autocorrelation',  # Pitch analysis method: 'autocorrelation', 'yin', 'parselmouth', or 'custom'
}

# Earlier versions called both built-in methods 'native'. Settings files saved then still contain
# that name, so it is translated to the current one wherever a method name is read.
LEGACY_METHOD_NAMES = {
    'formant_method': {'native': 'lpc'},
    'pitch_method': {'native': 'autocorrelation'},
}


def current_method_name(setting, method):
    """Return the current name for a formant_method/pitch_method value (translating old names)."""
    return LEGACY_METHOD_NAMES.get(setting, {}).get(method, method)


def update_method_names(settings):
    """Translate old method names in a settings dict (e.g. loaded from a settings file) in place."""
    if settings:
        for setting in LEGACY_METHOD_NAMES:
            if setting in settings:
                settings[setting] = current_method_name(setting, settings[setting])
    return settings


# Earlier versions set each analysis window as chunk_ms x number_of_chunks. Settings files saved
# then are converted to a window length in ms wherever they are loaded. The values are the
# defaults those versions used for a key missing from the file.
LEGACY_CHUNK_DEFAULTS = {
    'analysis': (20, 3),
    'spectrum': (15.0, 3),
    'spectrogram': (6.0, 1),
}


def update_window_settings(settings):
    """Convert chunk-based window settings in a loaded settings dict to window_ms, in place.
    The spectrogram's chunk also becomes its time_step_ms; in the other modes the time step
    now follows the display refresh rate."""
    for section, (default_chunk, default_n) in LEGACY_CHUNK_DEFAULTS.items():
        saved = settings.get(section) if isinstance(settings, dict) else None
        if not isinstance(saved, dict) or not ('chunk_ms' in saved or 'number_of_chunks' in saved):
            continue
        chunk_ms = saved.pop('chunk_ms', default_chunk)
        number_of_chunks = saved.pop('number_of_chunks', default_n)
        saved.setdefault('window_ms', chunk_ms * number_of_chunks)
        if section == 'spectrogram':
            saved.setdefault('time_step_ms', chunk_ms)
    return settings

# Smoother
SMOOTHER_CONFIG = {
    'memory_n': 3,
    'stability_threshold': 0.15,  # Updated for tighter tracking with 1-Euro filter
    'skip_tolerance': 2,  # frames to skip before resetting track
    # 1-Euro filter parameters for adaptive smoothing
    'use_euro_filter': True,  # Enable/disable 1-Euro temporal smoothing of formants and pitch
    'euro_min_cutoff': 0.05,  # Baseline cutoff frequency (Hz) - lower = smoother
    'euro_beta': 1.5,  # Responsiveness to velocity - higher = more adaptive
    'euro_dcutoff': 0.5,  # Cutoff for velocity smoothing - lower = smoother velocity
    'velocity_power': 1.5,  # Exponent for non-linear velocity influence (>1 = snap to fast changes)
}

# Colors (RGB)
COLORS = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}

# Save deep copies of initial/factory defaults for "Defaults" button reversion
import copy
FACTORY_AUDIO_CONFIG = copy.deepcopy(AUDIO_CONFIG)
FACTORY_ANALYSIS_CONFIG = copy.deepcopy(ANALYSIS_CONFIG)
FACTORY_LIVEVOWEL_CONFIG = copy.deepcopy(LIVEVOWEL_CONFIG)
FACTORY_LIVEPITCH_CONFIG = copy.deepcopy(LIVEPITCH_CONFIG)
FACTORY_LIVESPECTROGRAM_CONFIG = copy.deepcopy(LIVESPECTROGRAM_CONFIG)
FACTORY_LIVESPECTRUM_CONFIG = copy.deepcopy(LIVESPECTRUM_CONFIG)
FACTORY_SMOOTHER_CONFIG = copy.deepcopy(SMOOTHER_CONFIG)
FACTORY_EXPORT_CONFIG = copy.deepcopy(EXPORT_CONFIG)