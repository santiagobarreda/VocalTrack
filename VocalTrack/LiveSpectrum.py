
# Logging for status and debug messages
import logging
# Numpy for numerical operations and signal processing
import numpy as np
# Pygame for real-time graphics rendering
import pygame

# Import base visualizer and audio processing utilities
from .BaseAudioVisualizer import BaseAudioVisualizer, fit_to_desktop
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from .utils.get_formants import get_formants
from . import config

# Logger for this module
logger = logging.getLogger(__name__)


class LiveSpectrum(BaseAudioVisualizer):
    """
    Real-time frequency spectrum visualizer with a continuous line plot.

    This class displays the power spectrum of live audio input in real time. Each frame, it
    takes all available sound objects from the queue, blends each one into a running
    (exponentially smoothed) spectrum, and updates the display as a static (non-scrolling)
    spectrum. An optional overlay (Ctrl/Cmd+L) adds the spectral envelope and the formant
    estimates of the selected formant method.
    """

    # Lowest max formant reachable with the [ key (Hz); the highest is max_freq
    MIN_MAX_FORMANT = 3000.0
    # Change in max formant per [ or ] press (Hz)
    MAX_FORMANT_STEP = 50.0
    # Plot area margins in pixels (left, right, top, bottom): room for axis labels and the title
    PLOT_MARGINS = (60, 20, 40, 60)

    def __init__(self,
                 gui_width=None,
                 gui_height=None,
                 max_freq=None,
                 dynamic_range=None,
                 spec_config=None,
                 audio_config=None,
                 analysis_config=None,
                 input_device_index=None,
                 input_device_name=None):
        """
        Initialize the LiveSpectrum visualizer with optional configuration overrides.

        Args:
            gui_width (int, optional): Window width in pixels. Overrides config default.
            gui_height (int, optional): Window height in pixels. Overrides config default.
            max_freq (int, optional): Maximum frequency to display in Hz. Overrides config.
            dynamic_range (int, optional): dB range for spectrum display. Overrides config.
            spec_config (dict, optional): Spectrum config dict. Uses config.LIVESPECTRUM_CONFIG if None.
            audio_config (dict, optional): Audio config dict. Uses config.AUDIO_CONFIG if None.
            analysis_config (dict, optional): Analysis config dict. Uses config.ANALYSIS_CONFIG if None.
            input_device_index (int, optional): Audio input device index for QtMultimedia selection.

        Note:
            Sample rate is set automatically from max_formant (sample_rate = 2 × max_formant).
        """
        
        # Load or copy configuration dictionaries
        self.spec_config = spec_config or config.LIVESPECTRUM_CONFIG.copy()
        self.audio_config = audio_config or config.AUDIO_CONFIG.copy()
        self.analysis_config = analysis_config or config.ANALYSIS_CONFIG.copy()

        # Store audio device selection for AudioProcessor (the name takes priority over the index)
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name

        # Apply parameter overrides to spectrum config
        if gui_width is not None:
            self.spec_config['gui_width'] = gui_width
        if gui_height is not None:
            self.spec_config['gui_height'] = gui_height
        if max_freq is not None:
            self.spec_config['max_freq'] = max_freq
        if dynamic_range is not None:
            self.spec_config['dynamic_range'] = dynamic_range

        # FFT and display parameters
        self.window_ms = self.spec_config.get('window_ms', 50.0)
        self.max_freq = self.spec_config.get('max_freq', 5000)
        self.dynamic_range = self.spec_config.get('dynamic_range', 40)
        self.fps = self.spec_config.get('fps', 60)
        # One spectrum per display frame: the audio chunk (the analysis time step) is one frame long
        self.chunk_ms = config.chunk_ms_for_fps(self.fps)
        self.audio_config['chunk_ms'] = self.chunk_ms
        self.smoothing = self.spec_config.get('smoothing', 0.7)

        # Get max_formant and n_formants from global analysis_config options
        self.max_formant = float(self.analysis_config.get('max_formant', config.ANALYSIS_CONFIG.get('max_formant', 5000.0)))
        self.n_formants = float(self.analysis_config.get('n_formants', config.ANALYSIS_CONFIG.get('n_formants', 5.5)))

        # Audio stream rate is 2 x max_freq (Spectrum Settings), so the spectrum covers 0..max_freq.
        # Each LPC window is resampled down to 2 x the current max formant (as Praat does), so max
        # formant can change live with [ / ] without restarting the stream, up to max_freq.
        sample_rate = 2 * int(self.max_freq)
        self.analysis_config['analysis_sample_rate'] = sample_rate
        # Max formant range for [ / ]: the LPC can only be resampled down, so max_freq is the ceiling
        self.max_formant_ceiling = float(self.max_freq)
        self.max_formant_floor = min(self.MIN_MAX_FORMANT, self.max_formant_ceiling)
        # Set when the user changes max formant with [ / ]; only then is it copied back to Analysis Settings
        self.max_formant_changed = False
        # Max formant from Analysis Settings, if it had to be lowered to the ceiling (reported on screen)
        self.max_formant_requested = None
        if self.max_formant > self.max_formant_ceiling:
            logger.warning(f"Max formant {self.max_formant:.0f} Hz is above max frequency; LPC limited to {self.max_formant_ceiling:.0f} Hz")
            self.max_formant_requested = self.max_formant
            self.max_formant = self.max_formant_ceiling

        # Calculate FFT size (NFFT) based on window and padding
        window_samples = max(round(self.window_ms * sample_rate / 1000), 1)  # Same formula as AudioProcessor
        padding_length_ms = self.spec_config.get('padding_length_ms', 20.0)
        zero_pad_samples = int(round((padding_length_ms / 1000.0) * sample_rate))
        nfft = window_samples + zero_pad_samples

        # Configure analysis in analysis_config
        self.analysis_config['compute_spectrum'] = True  # Enable FFT spectrum in Sound objects
        self.analysis_config['spectrum_nfft'] = nfft  # FFT size
        self.analysis_config['max_freq'] = int(self.max_freq)  # Fixed FFT frequency limit
        self.analysis_config['formants'] = False  # LPC formant tracking runs only while the LPC overlay is on (Ctrl/Cmd+L)
        self.analysis_config['lpc_envelope'] = True  # Return the LPC polynomial with every backend (Parselmouth too)
        self.analysis_config['pitch'] = False  # Pitch tracking not needed for spectrum
        self.analysis_config['max_formant'] = int(self.max_formant)
        self.analysis_config['n_formants'] = self.n_formants
        self.analysis_config['window_length'] = float(self.analysis_config.get('window_length', config.ANALYSIS_CONFIG.get('window_length', 0.05)))
        self.analysis_config['time_step'] = self.chunk_ms / 1000.0
        
        # Prepare config for base class
        base_config = {
            'audio_config': self.audio_config,
            'analysis_config': self.analysis_config,
        }

        # Initialize parent class (sets up pygame, screen, etc.)
        # Shrink the window (same aspect ratio) if it does not fit on this screen
        gui_size = fit_to_desktop(self.spec_config.get('gui_width', 1200), self.spec_config.get('gui_height', 600))
        self.spec_config['gui_width'], self.spec_config['gui_height'] = gui_size
        super().__init__(
            app_title="Live Spectrum",
            config=base_config,
            gui_width=gui_size[0],
            gui_height=gui_size[1],
            input_device_index=input_device_index
        )
        self.target_fps = self.fps

        # The Analysis Settings max formant is above what LiveSpectrum can analyze: say so, since the
        # LPC overlay then does not match what LiveVowel uses
        if self.max_formant_requested is not None:
            self.show_notification(
                f"Max formant {self.max_formant_requested:.0f} Hz limited to {self.max_formant_ceiling:.0f} Hz: "
                f"raise Max Frequency in Spectrum Settings",
                duration_ms=6000
            )

        # Create audio processor for background audio capture
        self.audio_processor = AudioProcessor(
            chunk_ms=self.chunk_ms,
            window_ms=self.window_ms,
            analysis_config=self.analysis_config,
            input_device_index=input_device_index,
            input_device_name=input_device_name
        )

        # Spectrum display state
        self.current_spectrum_db = None  # Averaged spectrum for drawing
        self.current_frequencies = None  # Frequency bins for spectrum
        self.sounds_processed_this_frame = 0  # Number of sounds processed this frame
        self.gain_offset_db = float(self.spec_config.get('gain_offset_db', 0.0))  # Gain offset in dB (adjustable with +/-)

        # Recording and pause state management
        self.paused = False
        self.recording = True
        self.file_tag = 'spectrum'  # Used in exported file names
        self.session_name = self.new_recording_name()
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.original_recording_sample_rate = self.audio_config.get('sample_rate', 10000)
        self.downsampled_recording_sample_rate = self.audio_config.get('sample_rate', 10000)

        # Formant arrow markers (F1-F5) for tracking calibration (keys 1-5 + Click)
        self.formant_markers = {}  # {1: freq_hz, ..., 5: freq_hz}
        self.FORMANT_COLORS = {
            1: (230, 45, 45),    # F1: Red / Coral
            2: (30, 140, 255),   # F2: Cyan / Royal Blue
            3: (35, 185, 75),    # F3: Emerald Green
            4: (190, 45, 190),   # F4: Magenta / Purple
            5: (230, 150, 20),   # F5: Gold / Amber
        }

        # LPC spectral envelope overlay (Ctrl+L) for diagnosing vowel formant tracking
        self.show_lpc_spectrum = False
        self.current_lpc_spectrum_db = None
        self.last_audio_samples = None
        self.last_lpc_a = None
        self.last_lpc_e = None
        self.last_lpc_rate = None  # Sample rate the LPC was computed at (2 x max formant)
        self.last_sound_formants = None
        self.current_formants = None

        # Saved spectrum snapshots (Ctrl+S) for overlaying and comparing vowel tokens
        self.saved_spectra = []
        self.SAVED_SPECTRA_PALETTE = [
            (235, 110, 40),   # Orange
            (160, 60, 220),   # Violet
            (35, 175, 120),   # Teal green
            (220, 170, 20),   # Gold
            (220, 50, 110),   # Rose pink
            (0, 185, 215),    # Light cyan
            (130, 130, 235),  # Lavender
            (185, 125, 60),   # Ochre
        ]

        # Initialize default fonts to avoid recreating them on every frame (heavy OS lookup)
        self.font_14 = pygame.font.SysFont('Arial', 14)
        self.font_18_bold = pygame.font.SysFont('Arial', 18, bold=True)
        self.badge_font = self.font_14

        # Cached surfaces
        self.grid_surface = None
        self.axes_surface = None

        # Start the main event loop (blocking)
        self.run()

    def run(self):
        """
        Main event loop for real-time spectrum rendering.

        Runs at the configured frame rate (default 60 fps), performing:
            1. Handling user keyboard and mouse input
            2. Smoothing the power spectra of all sounds waiting in the queue
            3. Drawing the spectrum line plot, overlays, and grid
            4. Updating the pygame display

        The loop continues until the user presses ESC or closes the window.
        """
        # Start audio capture thread
        self.audio_processor.start()
        self.audio_processor.start_recording(
            record_original=bool(config.EXPORT_CONFIG.get('save_original_audio', True)),
            record_downsampled=bool(config.EXPORT_CONFIG.get('save_downsampled_audio', False))
        )
        self.original_recording_sample_rate = self.audio_processor.get_original_recording_sample_rate()
        self.downsampled_recording_sample_rate = self.audio_processor.get_downsampled_recording_sample_rate()
        # Log start message
        logger.info("LiveSpectrum started")

        try:
            while self.keep_running:
                # Limit frame rate to configured FPS (default 60) to prevent excessive CPU usage
                self.clock.tick(self.fps)

                # Get and parse pending pygame events, then handle them
                self.events = pygame.event.get()
                self.event_holder = EventHolder(self.events)
                self.main_events()

                # Smooth the spectra (and LPC envelope) of all sounds waiting in the queue
                self.collect_and_average_spectrum()

                # The audio device dropped out: the recording ended there, so export it and pause
                if self.recording and self.check_recording_interrupted() is not None:
                    self._pause_recording()

                # Draw the frame: background, grid and axes, spectra, markers, then overlays
                self.screen.fill(config.COLORS['white'])
                self.draw_background()
                self.draw_saved_spectra()
                if self.current_spectrum_db is not None and self.current_frequencies is not None:
                    self.draw_spectrum_line()
                if self.show_lpc_spectrum:
                    self.draw_lpc_spectrum_line()
                self.draw_formant_markers()
                self.draw_inspect_overlay()
                self.draw_status_indicators()
                if self.show_help:
                    self.draw_help_overlay()
                self.draw_performance_overlay()
                self.draw_notification()

                pygame.display.flip()
        finally:
            # Always execute cleanup code, even if exception occurs
            self.shutdown()

    def draw_background(self):
        """Draw the cached grid (if enabled, Ctrl/Cmd+G) and the axes, labels, and title."""
        if self.show_grid:
            if self.grid_surface is None:
                self.create_grid_surface()
            self.screen.blit(self.grid_surface, (0, 0))
        if self.axes_surface is None:
            self.create_axes_surface()
        self.screen.blit(self.axes_surface, (0, 0))

    def inspect_lines(self, x, y):
        """Inspection card: frequency, spectrum and LPC levels, and cursor level at the probe."""
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        left_m, right_m, top_m, bottom_m = self.PLOT_MARGINS
        plot_w = max(1, screen_w - left_m - right_m)
        plot_h = max(1, screen_h - top_m - bottom_m)

        freq_hz = max(0.0, min(1.0, (x - left_m) / plot_w)) * self.max_freq
        y_ratio = max(0.0, min(1.0, (screen_h - bottom_m - y) / plot_h))
        cursor_db = -self.dynamic_range + y_ratio * self.dynamic_range

        lines = [("Frequency", f"{int(round(freq_hz))} Hz", (0, 220, 255))]
        if self.current_frequencies is not None and self.current_spectrum_db is not None:
            curve_db = float(np.interp(freq_hz, self.current_frequencies, self.current_spectrum_db)) + self.gain_offset_db
            lines.append(("Spectrum Power", f"{curve_db:.1f} dB", (100, 255, 120)))
        if self.show_lpc_spectrum and self.current_frequencies is not None and self.current_lpc_spectrum_db is not None:
            lpc_val = float(np.interp(freq_hz, self.current_frequencies, self.current_lpc_spectrum_db)) + self.gain_offset_db
            if not np.isnan(lpc_val):  # NaN above max formant, where the LPC is not defined
                lines.append(("LPC Envelope", f"{lpc_val:.1f} dB", (255, 110, 110)))
        # The detected formant (as marked by the triangles) within 180 Hz of the probe, with its
        # level on the LPC envelope
        formants = self.current_formants if self.current_formants is not None else self.last_sound_formants
        if (self.show_lpc_spectrum and formants is not None and self.current_frequencies is not None
                and self.current_lpc_spectrum_db is not None):
            for f_idx, f_est in enumerate(formants, start=1):
                if abs(f_est - freq_hz) <= 180.0:
                    p_est = float(np.interp(f_est, self.current_frequencies, self.current_lpc_spectrum_db)) + self.gain_offset_db
                    level = "" if np.isnan(p_est) else f" ({p_est:.1f} dB)"
                    color = self.FORMANT_COLORS.get(f_idx, (255, 160, 160))
                    lines.append((f"Formant F{f_idx}", f"{int(round(f_est))} Hz{level}", color))
                    break
        lines.append(("Cursor Level", f"{cursor_db:.1f} dB", (200, 200, 200)))
        return lines

    def collect_and_average_spectrum(self):
        """
        Applies exponential smoothing to every sound object in the queue sequentially, so the
        smoothing does not depend on how many of them arrive in one display frame.
        """
        self.sounds_processed_this_frame = 0
        alpha = self.smoothing  # e.g., 0.7

        # Take every sound waiting in the queue. While paused they are discarded, so no backlog builds up
        sounds = self.take_analyzed_sounds()
        if self.paused:
            return

        # 1. Process them in order
        for sound in sounds:
            if sound.spectrum_magnitude_db is None:
                continue
            new_data = sound.spectrum_magnitude_db

            # Store latest audio samples & LPC coefficients from worker thread
            if sound.samples is not None:
                self.last_audio_samples = sound.samples
            if sound.lpc_a is not None and sound.lpc_e is not None:
                self.last_lpc_a = sound.lpc_a
                self.last_lpc_e = sound.lpc_e
                self.last_lpc_rate = sound.lpc_sample_rate

            # Collect exact LPC formant estimates from Sound object (identical to LiveVowel pipeline)
            new_formants = []
            if hasattr(sound, 'formants') and sound.formants:
                new_formants = [float(f) for f in sound.formants if f > 50]
            elif getattr(sound, 'f1', 0) > 0:
                new_formants = [float(f) for f in [sound.f1, sound.f2, sound.f3] if f > 50]

            if new_formants:
                self.last_sound_formants = new_formants
                new_f_arr = np.array(new_formants, dtype=np.float64)
                if self.current_formants is None or len(self.current_formants) != len(new_f_arr):
                    self.current_formants = new_f_arr
                else:
                    self.current_formants = (alpha * new_f_arr) + ((1.0 - alpha) * self.current_formants)

            # If this is the very first sound ever or shape changed, initialize
            if self.current_spectrum_db is None or self.current_spectrum_db.shape != new_data.shape:
                self.current_spectrum_db = new_data
            else:
                # SEQUENTIAL EXPONENTIAL SMOOTHING
                # Every new chunk updates the 'running' state
                self.current_spectrum_db = (alpha * new_data) + ((1 - alpha) * self.current_spectrum_db)

            # Update frequency axis if provided
            if sound.spectrum_frequencies is not None:
                self.current_frequencies = sound.spectrum_frequencies

            self.sounds_processed_this_frame += 1

        # 2. Evaluate and smooth LPC spectral envelope from background worker coefficients
        if self.show_lpc_spectrum and self.last_lpc_a is not None and self.current_frequencies is not None and self.sounds_processed_this_frame > 0:
            lpc_data = self.evaluate_lpc_filter(self.last_lpc_a, self.last_lpc_e, self.current_frequencies, self.last_lpc_rate)
            if lpc_data is not None:
                # Restart smoothing if the envelope's frequency range changed (max formant adjusted)
                if (self.current_lpc_spectrum_db is None or self.current_lpc_spectrum_db.shape != lpc_data.shape
                        or not np.array_equal(np.isnan(self.current_lpc_spectrum_db), np.isnan(lpc_data))):
                    self.current_lpc_spectrum_db = lpc_data
                else:
                    self.current_lpc_spectrum_db = (alpha * lpc_data) + ((1.0 - alpha) * self.current_lpc_spectrum_db)


    def draw_spectrum_line(self):
        """
        Draw the spectrum as a continuous line plot with a fixed dB scale.

        The power spectrum is displayed in dB (20*log10 of FFT magnitude).
        The Y-axis is fixed: 0 dB at the top, -dynamic_range dB at the bottom.
        The gain offset (adjustable with +/-) shifts all spectrum values for visibility.
        The frequency axis is linear in pixels.
        """
        # Safety check: require both spectrum and frequencies to be valid
        if self.current_spectrum_db is None or self.current_frequencies is None:
            return
        
        # Ensure we have proper 1D arrays
        spectrum = np.atleast_1d(self.current_spectrum_db)
        frequencies = np.atleast_1d(self.current_frequencies)
        
        # Check that we have matching data
        if len(spectrum) == 0 or len(frequencies) == 0 or len(spectrum) != len(frequencies):
            return
        
        # Apply gain offset to spectrum values and convert to screen coordinates
        points = self._spectrum_points(frequencies, spectrum + self.gain_offset_db)

        # Draw the continuous spectrum line in a single C-level call
        if points and len(points) > 1:
            # Arguments: surface, color, closed (False = don't connect end to start), points list, width
            pygame.draw.lines(self.screen, (0, 150, 255), False, points, 4)

    def _spectrum_points(self, frequencies, spectrum_db):
        """
        Screen points for a spectrum line: frequency on a linear axis from 0 to max_freq, and dB
        (gain already applied) clipped to the fixed axis from 0 dB (top) to -dynamic_range (bottom).
        """
        left, right, top, bottom = self.PLOT_MARGINS
        screen_width, screen_height = self.screen.get_width(), self.screen.get_height()
        plot_width = max(1, screen_width - left - right)
        plot_height = max(1, screen_height - top - bottom)
        x_pixels = (left + np.asarray(frequencies, dtype=np.float64) / float(self.max_freq) * plot_width).astype(np.int32)
        y_axis_min = -float(self.dynamic_range)
        level = (np.clip(np.asarray(spectrum_db, dtype=np.float64), y_axis_min, 0.0) - y_axis_min) / -y_axis_min
        y_pixels = (screen_height - bottom - level * plot_height).astype(np.int32)
        return list(zip(x_pixels.tolist(), y_pixels.tolist()))

    def draw_saved_spectra(self):
        """Draw all saved frozen spectrum overlays in their distinct assigned colors."""
        if not self.saved_spectra:
            return

        for snap in self.saved_spectra:
            spectrum = snap.get('spectrum_db')
            frequencies = snap.get('frequencies')
            if spectrum is None or frequencies is None or len(spectrum) == 0 or len(frequencies) == 0 or len(spectrum) != len(frequencies):
                continue

            points = self._spectrum_points(frequencies, spectrum + snap.get('gain_offset_db', self.gain_offset_db))
            if len(points) > 1:
                pygame.draw.lines(self.screen, snap.get('color', (200, 100, 50)), False, points, 2)

    def draw_formant_markers(self):
        """Draw colored arrow markers and vertical guidelines at user-designated formant frequencies (F1-F4)."""
        if not self.formant_markers:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        left_margin, right_margin, top_margin, bottom_margin = self.PLOT_MARGINS
        plot_width = max(1, screen_width - left_margin - right_margin)

        # Create alpha surface for vertical guidelines
        guide_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)

        for f_idx in sorted(self.formant_markers.keys()):
            freq_hz = self.formant_markers[f_idx]
            color = self.FORMANT_COLORS.get(f_idx, (0, 150, 255))
            x = int(round(left_margin + (freq_hz / float(self.max_freq)) * plot_width))
            x = max(left_margin, min(screen_width - right_margin, x))

            # 1. Subtle vertical guideline down the entire spectrum plot
            line_color = (color[0], color[1], color[2], 130)
            pygame.draw.line(guide_surface, line_color, (x, top_margin), (x, screen_height - bottom_margin), 1)

            # 2. Downward-pointing arrow triangle at top margin
            arrow_tip = (x, top_margin + 16)
            arrow_left = (x - 7, top_margin)
            arrow_right = (x + 7, top_margin)
            arrow_points = [arrow_tip, arrow_left, arrow_right]
            
            pygame.draw.polygon(self.screen, color, arrow_points)
            pygame.draw.polygon(self.screen, (30, 30, 30), arrow_points, 1)

            # 3. Formant pill badge (e.g., "F1: 520Hz") above the arrow
            label_text = f"F{f_idx}: {int(round(freq_hz))}Hz"
            font = getattr(self, 'font_14', None) or pygame.font.SysFont('Arial', 14, bold=True)
            text_surf = font.render(label_text, True, (255, 255, 255))
            
            badge_w = text_surf.get_width() + 10
            badge_h = text_surf.get_height() + 4
            badge_x = x - badge_w // 2
            badge_y = top_margin - badge_h - 2
            
            if badge_x < 10:
                badge_x = 10
            elif badge_x + badge_w > screen_width - 10:
                badge_x = screen_width - 10 - badge_w
            
            badge_surf = pygame.Surface((badge_w, badge_h), pygame.SRCALPHA)
            pygame.draw.rect(badge_surf, (color[0], color[1], color[2], 240), (0, 0, badge_w, badge_h), border_radius=4)
            pygame.draw.rect(badge_surf, (30, 30, 30, 180), (0, 0, badge_w, badge_h), 1, border_radius=4)
            badge_surf.blit(text_surf, (5, 2))
            self.screen.blit(badge_surf, (badge_x, badge_y))

        self.screen.blit(guide_surface, (0, 0))

    def evaluate_lpc_filter(self, lpc_a, lpc_e, target_frequencies, lpc_rate=None):
        """
        Evaluate the frequency response H(f) = sqrt(e) / |A(f)| of the LPC filter
        computed by the background analysis worker thread during formant tracking.

        The LPC is computed at lpc_rate (2 x max formant), so it only describes 0..max formant.
        Frequencies above that are returned as NaN and not drawn.
        """
        if lpc_a is None or target_frequencies is None or len(target_frequencies) == 0:
            return None

        sample_rate = float(lpc_rate or self.audio_processor.sample_rate)
        n_fft = max(512, (len(target_frequencies) - 1) * 2)
        A_fft = np.fft.rfft(lpc_a, n=n_fft)
        H_mag = np.sqrt(max(float(lpc_e if lpc_e is not None else 1.0), 1e-12)) / (np.abs(A_fft) + 1e-12)
        fft_freqs = np.linspace(0.0, sample_rate / 2.0, len(H_mag))

        target_f = np.asarray(target_frequencies, dtype=np.float64)
        lpc_curve = np.interp(target_f, fft_freqs, H_mag)
        lpc_db = 20.0 * np.log10(np.maximum(lpc_curve, 1e-12))
        in_band = target_f <= sample_rate / 2.0
        lpc_db[~in_band] = np.nan

        # Vertically align LPC curve to hug FFT harmonic peaks (within the LPC's band)
        if self.current_spectrum_db is not None and len(self.current_spectrum_db) == len(lpc_db) and np.any(in_band):
            fft_peak = float(np.percentile(self.current_spectrum_db[in_band], 95))
            lpc_peak = float(np.percentile(lpc_db[in_band], 95))
            lpc_db = lpc_db + (fft_peak - lpc_peak)

        return lpc_db

    def compute_lpc_spectrum(self, samples, target_frequencies):
        """
        Extract formants and LPC filter on demand using the shared get_formants pipeline
        and evaluate its frequency response curve.
        """
        if samples is None or len(samples) < 40 or target_frequencies is None or len(target_frequencies) == 0:
            return None

        sample_rate = int(self.audio_processor.sample_rate)
        max_formant = int(self.max_formant)
        # Same backend and settings as the analysis thread, so this curve matches the ones that follow
        # (a backend without an LPC polynomial, e.g. 'custom', gives no curve rather than a stale one)
        try:
            ff = get_formants(
                samples,
                sample_rate=sample_rate,
                method=self.analysis_config.get('formant_method', 'lpc'),
                max_formant=max_formant,
                n_formants_praat=self.n_formants,
                window_length=self.analysis_config.get('window_length', 0.05),
                time_step=self.analysis_config.get('time_step', 0.01),
                pre_emphasis_hz=self.analysis_config.get('pre_emphasis_hz', 50.0),
                return_lpc=True
            )
        except Exception as e:
            # A formant method that fails (e.g. a custom one) must not close the window. As in the
            # analysis thread, log each distinct error once
            if str(e) != getattr(self, '_last_overlay_error', None):
                self._last_overlay_error = str(e)
                logger.error(f"Formant analysis for the overlay failed: {e}")
            return None
        # Formants of this window, for the peak markers until the analysis thread delivers new ones
        all_f = ff.get('all_formants')
        if all_f is None or len(all_f) == 0:
            all_f = ff.get('formants', [])
        formants = [float(f) for f in all_f if f and not np.isnan(f) and f > 50]
        if formants:
            self.last_sound_formants = formants
            self.current_formants = np.array(formants, dtype=np.float64)
        lpc_a = ff.get('lpc_a', None)
        lpc_e = ff.get('lpc_e', None)
        if lpc_a is not None and lpc_e is not None:
            self.last_lpc_a = lpc_a
            self.last_lpc_e = lpc_e
            self.last_lpc_rate = ff.get('lpc_sample_rate', sample_rate)
            return self.evaluate_lpc_filter(lpc_a, lpc_e, target_frequencies, self.last_lpc_rate)
        return None

    def draw_lpc_spectrum_line(self):
        """
        Draw the LPC spectral envelope curve as a high-contrast smooth overlay line.
        """
        if not self.show_lpc_spectrum or self.current_lpc_spectrum_db is None or self.current_frequencies is None:
            return

        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        left_margin, right_margin, top_margin, bottom_margin = self.PLOT_MARGINS
        plot_width = max(1, screen_width - left_margin - right_margin)
        plot_height = max(1, screen_height - top_margin - bottom_margin)

        lpc_db = np.atleast_1d(self.current_lpc_spectrum_db)
        freqs = np.atleast_1d(self.current_frequencies)

        # Filter frequencies up to max_freq, and to the LPC's band (NaN above max formant)
        mask = (freqs <= self.max_freq) & ~np.isnan(lpc_db)
        freq_subset = freqs[mask]
        lpc_subset = lpc_db[mask]
        if len(freq_subset) < 2 or len(lpc_subset) < 2:
            return

        lpc_with_gain = lpc_subset + self.gain_offset_db
        y_axis_max = 0.0
        y_axis_min = -float(self.dynamic_range)
        points = self._spectrum_points(freq_subset, lpc_with_gain)
        if len(points) > 1:
            # Draw bold high-contrast coral/red curve (width 3)
            pygame.draw.lines(self.screen, (240, 50, 50), False, points, 3)

        # Draw Exact LPC Formant Estimates from Sound object (calibrated identically to LiveVowel)
        display_formants = self.current_formants if self.current_formants is not None else self.last_sound_formants
        if display_formants is not None and len(display_formants) > 0:
            for f_idx, f_val in enumerate(display_formants, start=1):
                f_hz = float(f_val)
                if f_hz <= 50.0 or f_hz > float(self.max_freq):
                    continue
                f_norm = f_hz / float(self.max_freq)
                x = int(round(left_margin + f_norm * plot_width))
                x = max(left_margin, min(screen_width - right_margin, x))

                # Interpolate power on the LPC envelope at this exact formant frequency
                p_db = float(np.interp(f_hz, freq_subset, lpc_with_gain))
                p_clamped = np.clip(p_db, y_axis_min, y_axis_max)
                p_norm = (p_clamped - y_axis_min) / (y_axis_max - y_axis_min)
                y = int(round(float(screen_height) - float(bottom_margin) - p_norm * float(plot_height)))
                y = max(top_margin, min(screen_height - bottom_margin, y))

                # Color-code by formant index matching standard palette
                color = self.FORMANT_COLORS.get(f_idx, (220, 100, 100))

                # Draw crisp downward-pointing triangle whose tip rests at (x, y)
                tri_w = 6
                tri_h = 10
                pt_tip = (x, y)
                pt_left = (x - tri_w, y - tri_h)
                pt_right = (x + tri_w, y - tri_h)

                pygame.draw.polygon(self.screen, color, [pt_tip, pt_left, pt_right])
                pygame.draw.polygon(self.screen, (20, 20, 20), [pt_tip, pt_left, pt_right], 1)

                # Formant badge text: "F1", "F2", etc.
                label_str = f"F{f_idx}"
                lbl_surf = self.font_14.render(label_str, True, (20, 20, 20))
                lbl_rect = lbl_surf.get_rect(center=(x, y - tri_h - 9))

                # High contrast pill background
                bg_pill = lbl_rect.inflate(6, 3)
                pygame.draw.rect(self.screen, (255, 255, 255), bg_pill, border_radius=3)
                pygame.draw.rect(self.screen, color, bg_pill, 1, border_radius=3)
                self.screen.blit(lbl_surf, lbl_rect)

    def create_axes_surface(self):
        """Create cached background surface for axes, labels, and title."""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        
        self.axes_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.axes_surface.fill((0, 0, 0, 0))
        
        left_margin, right_margin, top_margin, bottom_margin = self.PLOT_MARGINS
        
        plot_width = screen_width - left_margin - right_margin
        plot_height = screen_height - top_margin - bottom_margin
        
        # Draw axes
        # Left axis (Y-axis for magnitude)
        pygame.draw.line(self.axes_surface, (0, 0, 0), 
                         (left_margin, top_margin), 
                         (left_margin, screen_height - bottom_margin), 2)
        
        # Bottom axis (X-axis for frequency)
        pygame.draw.line(self.axes_surface, (0, 0, 0),
                         (left_margin, screen_height - bottom_margin),
                         (screen_width - right_margin, screen_height - bottom_margin), 2)

        # Draw frequency axis labels
        font = self.font_14
        freq_labels = [0, self.max_freq // 4, self.max_freq // 2, 3 * self.max_freq // 4, self.max_freq]
        for freq in freq_labels:
            x_pixel = left_margin + (freq / self.max_freq) * plot_width
            label_text = font.render(f"{freq}", True, (50, 50, 50))
            text_rect = label_text.get_rect(center=(x_pixel, screen_height - bottom_margin + 25))
            self.axes_surface.blit(label_text, text_rect)

        # Draw magnitude axis labels (dB)
        db_labels = [0, -self.dynamic_range // 3, -2 * self.dynamic_range // 3, -self.dynamic_range]
        for db_val in db_labels:
            mag_normalized = (db_val - (-self.dynamic_range)) / (0.0 - (-self.dynamic_range))
            y_pixel = screen_height - bottom_margin - mag_normalized * plot_height
            label_text = font.render(f"{int(db_val)} dB", True, (50, 50, 50))
            text_rect = label_text.get_rect(right=(left_margin - 10), centery=y_pixel)
            self.axes_surface.blit(label_text, text_rect)

        # Draw title
        title_font = self.font_18_bold
        title = title_font.render("Frequency Spectrum", True, (0, 0, 0))
        title_rect = title.get_rect(topleft=(20, 10))
        self.axes_surface.blit(title, title_rect)
        
        # Convert surface to match screen pixel format for optimized CPU blitting
        self.axes_surface = self.axes_surface.convert_alpha()

    def create_grid_surface(self):
        """Create cached background surface for the grid lines."""
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        
        self.grid_surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        self.grid_surface.fill((0, 0, 0, 0))
        
        left_margin, right_margin, top_margin, bottom_margin = self.PLOT_MARGINS
        
        plot_width = screen_width - left_margin - right_margin
        plot_height = screen_height - top_margin - bottom_margin
        
        grid_color = (200, 200, 200)
        
        # Draw vertical grid lines for frequency
        num_freq_lines = 4
        for i in range(1, num_freq_lines):
            x_pos = left_margin + (i / num_freq_lines) * plot_width
            pygame.draw.line(self.grid_surface, grid_color, 
                           (x_pos, top_margin),
                           (x_pos, screen_height - bottom_margin), 1)
        
        # Draw horizontal grid lines for magnitude
        num_mag_lines = 4
        for i in range(1, num_mag_lines):
            y_pos = top_margin + (i / num_mag_lines) * plot_height
            pygame.draw.line(self.grid_surface, grid_color,
                           (left_margin, y_pos),
                           (screen_width - right_margin, y_pos), 1)
            
        # Convert surface to match screen pixel format for optimized CPU blitting
        self.grid_surface = self.grid_surface.convert_alpha()

    def draw_help_overlay(self):
        """
        Display help text overlay with keyboard shortcuts for user interaction.
        """
        help_text = [
            "KEYBOARD SHORTCUTS:",
            "Space: Start / Stop recording (live / freeze)",
            "Shift + Click: Probe Frequency, Power & LPC (while paused)",
            "1-5 + Click: Place F1, F2, F3, F4, F5 formant arrow markers",
            "Ctrl/Cmd+L: Toggle LPC spectral envelope overlay",
            "[ / ]: Adjust Max Formant Frequency (±50 Hz)",
            "Ctrl/Cmd+S: Save current frozen spectrum snapshot",
            "Backspace: Undo last saved spectrum / marker",
            "Delete: Clear saved spectra and markers",
            "Right Click: Clear formant markers",
            "+/-: Adjust Gain",
            "Ctrl/Cmd+G: Toggle Grid",
            "Ctrl/Cmd+P: Toggle Performance Monitor",
            "Ctrl/Cmd+?: Toggle Help",
            "ESC: Quit"
        ]
        
        font = self.font_14
        line_height = 24
        start_y = 70
        bg_color = (240, 240, 240)
        text_color = (50, 50, 50)
        
        # Draw background box
        max_text_width = max(len(line) for line in help_text)
        box_width = max_text_width * 8 + 20
        box_height = len(help_text) * line_height + 20
        bg_rect = pygame.Rect(20, start_y - 10, box_width, box_height)
        pygame.draw.rect(self.screen, bg_color, bg_rect)
        pygame.draw.rect(self.screen, (150, 150, 150), bg_rect, 2)
        
        # Draw text
        for i, line in enumerate(help_text):
            text_surface = font.render(line, True, text_color)
            self.screen.blit(text_surface, (30, start_y + i * line_height))

    def main_events(self):
        """
        Process GUI events: shared controls (quit, grid, help, Space, Shift + click probe,
        Backspace/Delete), window resize, gain, and the LiveSpectrum tools (LPC overlay, max
        formant, spectrum snapshots, formant markers).
        """
        eh = self.event_holder
        # Handle base events (quit, grid/help toggle, Backspace/Delete)
        self.handle_base_events(eh)

        # Handle window resize events
        if eh.resize is not None:
            self.spec_config['gui_width'] = eh.resize.w
            self.spec_config['gui_height'] = eh.resize.h
            self.screen = pygame.display.set_mode((self.spec_config['gui_width'], self.spec_config['gui_height']), pygame.RESIZABLE)
            # Recreate cached surfaces
            self.grid_surface = None
            self.axes_surface = None

        # Gain adjustment with +/- keys (3 dB per press)
        if eh.plus_equals:
            self.gain_offset_db += 3.0
            logger.info(f"Gain increased to {self.gain_offset_db} dB")
        if eh.minus_underscore:
            self.gain_offset_db -= 3.0
            logger.info(f"Gain decreased to {self.gain_offset_db} dB")

        # Space: freeze (pause recording) / resume live display and recording
        self.handle_space_toggle(eh)
        # Shift + click inspection probe (only when the display is frozen)
        self.update_inspect_probe(eh)

        # Ctrl/Cmd+L: LPC spectral envelope overlay
        if eh.ctrl_l:
            self._toggle_lpc_overlay()

        # [ / ] (or Ctrl+[ / Ctrl+], Ctrl+Down / Ctrl+Up): max formant -/+ 50 Hz
        if eh.bracket_left or eh.ctrl_bracket_left:
            self._change_max_formant(-self.MAX_FORMANT_STEP)
        if eh.bracket_right or eh.ctrl_bracket_right:
            self._change_max_formant(+self.MAX_FORMANT_STEP)

        # Ctrl/Cmd+S: save the current spectrum as an overlay
        if eh.ctrl_s:
            self._save_snapshot()

        # Number keys 1-5 (+ click): formant arrow markers
        self._handle_formant_markers(eh)

        # BACKSPACE / DELETE are dispatched by handle_base_events() to _handle_backspace / _handle_delete

        # Right click: clear formant markers
        if eh.right_click_down is not None and self.formant_markers:
            self.formant_markers = {}
            self.show_notification("Cleared formant markers", duration_ms=1500)

    def _toggle_lpc_overlay(self):
        """Show or hide the LPC spectral envelope and formant peak markers."""
        self.show_lpc_spectrum = not self.show_lpc_spectrum
        # The analysis thread runs LPC formant tracking only while the overlay is shown
        self.analysis_config['formants'] = self.show_lpc_spectrum
        self.audio_processor.analysis_config['formants'] = self.show_lpc_spectrum
        if not self.show_lpc_spectrum:
            # Forget the last analysis, so nothing stale is drawn when the overlay is shown again
            self.last_lpc_a = None
            self.current_lpc_spectrum_db = None
            self.current_formants = None
            self.last_sound_formants = None
        elif self.last_audio_samples is not None and self.current_frequencies is not None:
            self.current_lpc_spectrum_db = self.compute_lpc_spectrum(self.last_audio_samples, self.current_frequencies)
        state_str = "ON" if self.show_lpc_spectrum else "OFF"
        self.show_notification(
            f"LPC Envelope: {state_str} (Max Formant: {int(self.max_formant)} Hz, [ / ] to adjust)",
            duration_ms=2500,
            bg_color=(255, 235, 235) if self.show_lpc_spectrum else (240, 240, 240),
            border_color=(240, 60, 60) if self.show_lpc_spectrum else (120, 120, 120)
        )
        logger.info(f"LPC spectral envelope toggled {state_str}")

    def _change_max_formant(self, step_hz):
        """
        Change the max formant by step_hz, within [max_formant_floor, max_formant_ceiling]. It takes
        effect immediately in the analysis; the launcher copies it to Analysis Settings when
        LiveSpectrum closes (via max_formant_changed), the single place that writes it to disk.

        On reaching (or pressing past) the ceiling, the Spectrum Settings max frequency, an alert
        says how to go higher; likewise at the floor.
        """
        new_value = min(self.max_formant_ceiling, max(self.max_formant_floor, self.max_formant + step_hz))
        if new_value != self.max_formant:
            self.max_formant = new_value
            self.max_formant_changed = True
            new_mf = int(self.max_formant)
            self.analysis_config['max_formant'] = new_mf
            self.audio_processor.analysis_config['max_formant'] = new_mf
            config.ANALYSIS_CONFIG['max_formant'] = new_mf
            if self.last_audio_samples is not None and self.current_frequencies is not None:
                self.current_lpc_spectrum_db = self.compute_lpc_spectrum(self.last_audio_samples, self.current_frequencies)
            logger.info(f"Max formant {'decreased' if step_hz < 0 else 'increased'} to {new_mf} Hz")

        if step_hz > 0 and self.max_formant >= self.max_formant_ceiling:
            self.show_notification(
                f"Maximum analysis frequency reached ({self.max_formant_ceiling:.0f} Hz): "
                f"raise Max Frequency in Spectrum Settings to go higher",
                duration_ms=4000
            )
        elif step_hz < 0 and self.max_formant <= self.max_formant_floor:
            self.show_notification(f"Minimum max formant reached ({self.max_formant_floor:.0f} Hz)", duration_ms=2500)
        else:
            self.show_notification(
                f"Max Formant: {int(self.max_formant)} Hz (Adult Male: 5000, Female: 5500, Child: 6500+)",
                duration_ms=2000,
                bg_color=(240, 245, 255),
                border_color=(0, 120, 220)
            )

    def _save_snapshot(self):
        """Keep a copy of the current (frozen or live) spectrum, drawn as a colored overlay."""
        if self.current_spectrum_db is None or self.current_frequencies is None:
            return
        color = self.SAVED_SPECTRA_PALETTE[len(self.saved_spectra) % len(self.SAVED_SPECTRA_PALETTE)]
        snapshot = {
            'spectrum_db': np.array(self.current_spectrum_db, copy=True),
            'frequencies': np.array(self.current_frequencies, copy=True),
            'gain_offset_db': self.gain_offset_db,
            'color': color,
            'id': len(self.saved_spectra) + 1
        }
        self.saved_spectra.append(snapshot)
        self.show_notification(
            f"Saved Spectrum #{snapshot['id']} ({len(self.saved_spectra)} total — Backspace: undo, Delete: clear)",
            duration_ms=2500,
            bg_color=(220, 255, 230),
            border_color=(0, 160, 60)
        )
        logger.info(f"Saved spectrum snapshot #{snapshot['id']} (total: {len(self.saved_spectra)})")

    def _handle_formant_markers(self, eh):
        """
        Place formant arrow marker F1-F5 at the mouse frequency: hold a number key 1-5 and left
        click (not with Shift, which probes), or press 1-5 while the mouse is over the plot.
        """
        screen_w = self.screen.get_width()
        left_m, right_m, _, _ = self.PLOT_MARGINS
        plot_w = max(1, screen_w - left_m - right_m)
        mouse_x = eh.mouse_pos[0]

        target_formant = None
        if eh.left_click_down is not None and eh.number_held is not None and not eh.shift_held:
            target_formant = eh.number_held
        elif eh.number_pressed is not None and left_m <= mouse_x <= screen_w - right_m:
            target_formant = eh.number_pressed
        if target_formant is None:
            return

        freq_hz = max(0.0, min(1.0, (mouse_x - left_m) / float(plot_w))) * self.max_freq
        self.formant_markers[target_formant] = freq_hz
        self.show_notification(
            f"Formant F{target_formant} marker set to {int(round(freq_hz))} Hz",
            duration_ms=2000,
            bg_color=(235, 245, 255),
            border_color=self.FORMANT_COLORS.get(target_formant, (0, 150, 255))
        )
        logger.info(f"Formant F{target_formant} marker set to {freq_hz:.1f} Hz")

    def _handle_backspace(self):
        """Backspace: undo the last saved spectrum, or the last formant marker if none are saved."""
        if self.saved_spectra:
            removed = self.saved_spectra.pop()
            self.show_notification(f"Removed Spectrum #{removed['id']} ({len(self.saved_spectra)} remaining)", duration_ms=1500)
        elif self.formant_markers:
            last_k = sorted(self.formant_markers.keys())[-1]
            del self.formant_markers[last_k]
            self.show_notification(f"Removed F{last_k} marker", duration_ms=1500)

    def _handle_delete(self):
        """Delete: clear all saved spectra and formant markers."""
        if self.saved_spectra or self.formant_markers:
            self.saved_spectra = []
            self.formant_markers = {}
            self.show_notification("Cleared all saved spectra and formant markers", duration_ms=1500)

    def status_badges(self):
        """[PAUSED] / [REC], plus the LPC overlay's max formant and the number of saved spectra."""
        badges = super().status_badges()
        if self.show_lpc_spectrum:
            badges.append((f"[LPC: {int(self.max_formant)}Hz]", (255, 185, 185)))
        if self.saved_spectra:
            badges.append((f"[Saved: {len(self.saved_spectra)}]", (180, 230, 255)))
        return badges

    def shutdown(self):
        """
        Clean up resources and close the application safely.

        Stops the audio processor, quits pygame, and logs shutdown status.
        """
        try:
            if self.recording:
                self._collect_recording()
            if self.original_audio_buffer or self.downsampled_audio_buffer:
                self.export_recording()
            # Save current settings (like gain and window dimensions) back to manager
            try:
                from . import settings_manager
                mgr = settings_manager.get_settings_manager()
                saved = mgr.get('spectrum', {})
                saved['gain_offset_db'] = self.gain_offset_db
                saved['gui_width'] = self.screen.get_width()
                saved['gui_height'] = self.screen.get_height()
                mgr.set('spectrum', saved)
                mgr.save()
                logger.info("LiveSpectrum settings saved successfully")
            except Exception as save_err:
                logger.error(f"Error saving LiveSpectrum settings: {save_err}")

            # Stop audio capture thread
            if self.audio_processor:
                self.audio_processor.stop()
            # Close Pygame
            pygame.quit()
            logger.info("LiveSpectrum shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
