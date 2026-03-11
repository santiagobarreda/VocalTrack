"""Configuration settings for VocalTrack application."""

# Performance and Logging
PERFORMANCE_CONFIG = {
    'logging_level': 30,  # logging.WARNING - use 10 for DEBUG, 20 for INFO
}

# Export Settings
EXPORT_CONFIG = {
    'save_recordings': False,  # Enable/disable saving recordings (off by default)
    'save_wav': True,  # Save audio as WAV (when save_recordings is True)
    'save_csv': True,  # Save timestamped CSV with formants (when save_recordings is True)
    'output_dir': 'recordings',  # Output directory for files
}

# Audio Processing
AUDIO_CONFIG = {
    'sample_rate': 10000,  # Auto-calculated as 2 × max_formant (Nyquist theorem: 5000 Hz × 2 = 10000 Hz)
    'chunk_ms': 20,  # Duration of each chunk in milliseconds
    'number_of_chunks': 3,  # Number of chunks to stitch together for analysis window
    'min_rms_db': -50.0  # Minimum RMS amplitude in dB for analysis
}

# GUI - LiveVowel
LIVEVOWEL_CONFIG = {
    'gui_size': (800.0, 600.0),
    'f1_range': (200.0, 1200.0),
    'f2_range': (500.0, 2700.0),
    'fps': 60,
    'show_vowel_template': False,  # Show vowel template overlay
    'display_mode': 'single',  # Visualization mode: 'single', 'track', or 'all'
    'freq_scale': 'log',  # Frequency axis scale: 'log' or 'linear'
}

# GUI - LivePitch
LIVEPITCH_CONFIG = {
    'gui_width': 850,
    'gui_height': 500,
    'min_f0': 75,
    'max_f0': 500,
    'fps': 60,
    'display_seconds': 5.0,
    'pitch_plot_mode': 'fixed',  # 'fixed' or 'continuous'
    'pitch_display_seconds': 5.0,  # Display window width in seconds
    'freq_scale': 'log',  # Frequency axis scale: 'log' or 'linear'
}

# GUI - LiveSpectrogram
LIVESPECTROGRAM_CONFIG = {
    'gui_width': 1200,  # Display window width in pixels (typical: 1200 for widescreen)
    'gui_height': 600,  # Display window height in pixels; larger height = finer frequency resolution
    'max_freq': 5000,  # Maximum frequency to display in Hz; limits X-axis range (avoids aliasing above 5kHz for 10kHz sample rate)
    'display_seconds': 3.0,  # Time window duration in seconds; controls horizontal scroll speed (5s typical for real-time response)
    'colormap': 'plasma',  # Matplotlib colormap name for magnitude-to-color mapping; 'plasma' is perceptually uniform
    'dynamic_range': 40,  # Dynamic range in dB for spectrogram amplitude display; controls contrast (smaller=more detail, larger=more contrast)
    'fps': 60,  # Frame rate for display refresh (30 fps is UI-responsive but lower CPU than 60)
    'chunk_ms': 6.0,                 # Duration of each audio chunk in ms
    'number_of_chunks': 1,            # Number of chunks to form a complete analysis window (15ms * 3 = 45ms window)
    'padding_length_ms': 20.0,  # Zero-padding length in milliseconds for frequency resolution enhancement (typical: 20ms)
}

# GUI - LiveSpectrum
LIVESPECTRUM_CONFIG = {
    'gui_width': 1200,  # Display window width in pixels
    'gui_height': 600,  # Display window height in pixels
    'max_freq': 5000,  # Maximum frequency to display in Hz
    'dynamic_range': 40,  # Dynamic range in dB for amplitude display
    'fps': 60,  # Frame rate for display refresh
    'chunk_ms': 15.0,  # Duration of each audio chunk in ms
    'number_of_chunks': 3,  # Number of chunks to form complete analysis window (15ms * 3 = 45ms)
    'padding_length_ms': 20.0,  # Zero-padding length in milliseconds for frequency resolution enhancement
    'smoothing': 0.7,  # Exponential smoothing parameter (0=no smoothing, 1=full smoothing)
}

# Analysis
ANALYSIS_CONFIG = {
    'n_formants': 5.5,
    'robust_formants': False,
    'max_formant': 5000,
    'window_length': 0.06,  # Calculated from chunk_ms=20 × number_of_chunks=3 = 60ms = 0.06s
    'time_step': 0.020,  # Calculated from chunk_ms=20
    'pre_emphasis_coeff': 0.97,
    'pre_emphasis_hz': 50,
    'min_f0': 60,  # Minimum f0 for analysis
    'max_f0': 500,  # Maximum f0 for analysis
    'min_confidence': 0.2,  # Minimum confidence threshold for accepting pitch estimates
    'min_rms_db': -60.0,  # Minimum RMS amplitude in dB for analysis
    'formant_method': 'native',  # Formant analysis method: 'native', 'parselmouth', or 'custom'
    'pitch_method': 'native',  # Pitch analysis method: 'native', 'parselmouth', or 'custom'
}

# Smoother
SMOOTHER_CONFIG = {
    'memory_n': 3,
    'stability_threshold': 0.15,  # Updated for tighter tracking with 1-Euro filter
    'skip_tolerance': 2,  # frames to skip before resetting track
    'hold_unvoiced': True,  # GitHub baseline (was False - broke tracks on voicing drops)
    # 1-Euro filter parameters for adaptive smoothing
    'euro_min_cutoff': 0.05,  # Baseline cutoff frequency (Hz) - lower = smoother
    'euro_beta': 1.5,  # Responsiveness to velocity - higher = more adaptive
    'euro_dcutoff': 0.5,  # Cutoff for velocity smoothing - lower = smoother velocity
    'velocity_power': 1.5,  # Exponent for non-linear velocity influence (>1 = snap to fast changes)
}

# Colors (RGB)
COLORS = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'blue': (0, 0, 255),
    'grey': (50, 50, 50),
}