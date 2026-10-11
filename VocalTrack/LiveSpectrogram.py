# json and importlib.resources load the bundled colormap tables, NumPy handles the array
# operations, and Pygame renders the display

import json
import logging
import numpy as np
import pygame
from importlib import resources

# Import BaseAudioVisualizer for audio stream handling and display management
# Import AudioProcessor for capturing and queuing audio chunks
# Import EventHolder for keyboard event detection
# Import config for default settings and COLORS

from .BaseAudioVisualizer import BaseAudioVisualizer, fit_to_desktop
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from . import config

# Create logger instance for this module
logger = logging.getLogger(__name__)

class LiveSpectrogram(BaseAudioVisualizer):
    """Real-time spectrogram visualization with scrolling display.
    
    This class generates a spectrogram from live audio input, displaying
    time-domain scrolling frequency content using the bundled colormap tables and pygame rendering.
    High-frequency content is boosted via pre-emphasis filtering for better visibility.
    Dynamic range and gain are user-adjustable for detail vs. contrast tradeoff.
    """

    @staticmethod
    def _load_colormap_table(colormap_name):
        """Load a 256-color RGB lookup table from packaged JSON files."""
        colormap_dir = resources.files("VocalTrack").joinpath("colormaps")
        preferred = colormap_dir.joinpath(f"{colormap_name}.json")
        fallback = colormap_dir.joinpath("plasma.json")
        colormap_file = preferred if preferred.is_file() else fallback
        with colormap_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return np.array(data["colors"], dtype=np.uint8)

    def __init__(self,
                 gui_width=None,
                 gui_height=None,
                 max_freq=None,
                 display_seconds=None,
                 colormap=None,
                 dynamic_range=None,
                 sample_rate=None,
                 spec_config=None,
                 audio_config=None,
                 analysis_config=None,
                 input_device_index=None,
                 input_device_name=None):
        """Initialize LiveSpectrogram with optional configuration override.
        
        Args:
            gui_width: Window width in pixels (overrides config default)
            gui_height: Window height in pixels (overrides config default)
            max_freq: Maximum frequency to display in Hz (overrides config)
            display_seconds: Time window to display in seconds (overrides config)
            colormap: Name of a bundled colormap (overrides config)
            dynamic_range: dB range for spectrogram display (overrides config)
            sample_rate: Audio sample rate in Hz (overrides config)
            spec_config: Full spectrogram config dict (if None, uses config.LIVESPECTROGRAM_CONFIG)
            audio_config: Full audio config dict (if None, uses config.AUDIO_CONFIG)
            analysis_config: Full analysis config dict (if None, uses config.ANALYSIS_CONFIG)
            input_device_index: Audio input device index for QtMultimedia device selection
        """
      
        # Load config dicts from parameters or use defaults from config module
        self.spec_config = spec_config or config.LIVESPECTROGRAM_CONFIG.copy()
        self.audio_config = audio_config or config.AUDIO_CONFIG.copy()
        self.analysis_config = analysis_config or config.ANALYSIS_CONFIG.copy()
        # Store audio device selection for AudioProcessor (the name takes priority over the index)
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name

        # Get FPS from config or default to 60 if not set
        self.fps = self.spec_config.get('fps', 60)

        # Apply individual parameter overrides to spec_config if provided
        if gui_width is not None:
            self.spec_config['gui_width'] = gui_width
        # Override display height if specified
        if gui_height is not None:
            self.spec_config['gui_height'] = gui_height
        # Override maximum display frequency if specified
        if max_freq is not None:
            self.spec_config['max_freq'] = max_freq
        # Override time window duration if specified
        if display_seconds is not None:
            self.spec_config['display_seconds'] = display_seconds
        # Override colormap name if specified
        if colormap is not None:
            self.spec_config['colormap'] = colormap
        # Override dynamic range in dB if specified
        if dynamic_range is not None:
            self.spec_config['dynamic_range'] = dynamic_range
        # Override sample rate if specified
        if sample_rate is not None:
            self.audio_config['sample_rate'] = sample_rate

        # Window length and time step from the spectrogram config. The audio chunk is one time step:
        # each chunk gives one analysis, drawn as one column (so the step can be shorter than a frame)
        window_length_ms = self.spec_config.get('window_ms', 6.0)
        chunk_ms = self.spec_config.get('time_step_ms', 6.0)
        self.chunk_ms = chunk_ms
        self.audio_config['chunk_ms'] = chunk_ms
        self.audio_config['window_ms'] = window_length_ms
        # Only the spectrum is computed in this mode, so the audio buffer need be no longer than its window
        self.analysis_config['window_length'] = window_length_ms / 1000.0

        # Shrink the window (same aspect ratio) if it does not fit on this screen
        self.spec_config['gui_width'], self.spec_config['gui_height'] = fit_to_desktop(
            self.spec_config['gui_width'], self.spec_config['gui_height'])

        # Initialize base class with audio configuration and title
        super().__init__(
            app_title="Live Spectrogram",
            config={
                'audio_config': self.audio_config,
                'analysis_config': self.analysis_config,
            },
            gui_width=self.spec_config['gui_width'],
            gui_height=self.spec_config['gui_height'],
            input_device_index=input_device_index
        )
        self.target_fps = self.fps
        
        # Store GUI dimensions from config for easy reference
        self.GUI_WIDTH = self.spec_config['gui_width']
        # Store GUI height for frequency axis scaling
        self.GUI_HEIGHT = self.spec_config['gui_height']
        # Store maximum frequency to limit spectrogram display (avoid aliasing artifacts)
        self.max_freq = self.spec_config['max_freq']
        # Store time window duration for horizontal scrolling calculation
        self.display_seconds = self.spec_config['display_seconds']
        # Store the name of the bundled colormap (e.g., 'plasma', 'viridis')
        self.colormap_name = self.spec_config['colormap']
        # Store dynamic range in dB for frequency axis amplitude clipping (controls contrast)
        self.dynamic_range = self.spec_config['dynamic_range']
        # Store gain in dB for amplitude scaling (controls overall brightness)
        self.gain_db = float(self.spec_config.get('gain_db', 0.0))
        
        # Update sample_rate based on max_freq (Nyquist: need 2× max frequency)
        # This overwrites any sample rate from audio_config to ensure correct sampling
        self.audio_config['sample_rate'] = 2 * self.max_freq
        self.sample_rate = self.audio_config['sample_rate']

        # Disable heavy math that the spectrum visualizer doesn't need
        self.analysis_config['formants'] = False
        self.analysis_config['pitch'] = False
        
        # FFT Analysis Parameters: window size from the window length setting
        self.window_length = window_length_ms / 1000.0  # For reference
        
        # Calculate total window size in samples.
        self.window_samples = max(round(window_length_ms * self.sample_rate / 1000), 1)  # Same formula as AudioProcessor

        # FFT size configuration: append configurable zero padding for smoothness
        # Zero padding increases visual smoothness without changing time resolution
        padding_length_ms = self.spec_config.get('padding_length_ms', 20.0)
        zero_pad_samples = int(round((padding_length_ms / 1000.0) * self.sample_rate))
        # Total FFT size is window_samples + zero padding
        self.nfft = self.window_samples + zero_pad_samples
        
        # Load a local 256-entry RGB lookup table for this colormap.
        self.colormap_table = self._load_colormap_table(self.colormap_name)
        
        # Create pygame surface for scrolling spectrogram display
        # This surface holds the entire spectrogram history visible on screen
        self.spec_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT)).convert()
        # Initialize display with black background to avoid artifacts
        self.spec_surface.fill((0, 0, 0))
        
        # Calculate pixels per second: how many pixels to scroll per second of audio
        self.pixels_per_second = self.GUI_WIDTH / self.display_seconds
        
        # Column width in pixels: A new spectrum is generated for each audio CHUNK.
        # So, the time between columns is chunk_ms.
        time_per_column = chunk_ms / 1000.0  # Convert ms to seconds
        self.column_width = int(round(self.pixels_per_second * time_per_column))
        # Ensure at least 1 pixel width
        self.column_width = max(self.column_width, 1)
        self._update_visible_seconds()

        # Pre-calculate frequency-to-pixel Y coordinate index mapping to save CPU on every frame
        num_bins = self.nfft // 2 + 1
        self.y_indices = (np.arange(self.GUI_HEIGHT) / self.GUI_HEIGHT * num_bins).astype(np.int32)
        
        # Rolling buffer of spectral magnitude (dB) across screen columns for Shift+Click inspection
        self.spec_db_buffer = np.full((self.GUI_WIDTH, num_bins), -120.0, dtype=np.float32)

        # Recording and pause state management
        self.keep_running = True  # Main loop control flag
        self.paused = False       # Freeze/pause display toggle flag
        self.recording = True     # Recording is active when running live
        self.file_tag = 'spectrogram'  # Used in exported file names
        # Create unique session name for exported files (includes timestamp)
        self.session_name = self.new_recording_name()
        # Buffers to accumulate audio samples when recording is enabled
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.original_recording_sample_rate = self.audio_config['sample_rate']
        self.downsampled_recording_sample_rate = self.audio_config['sample_rate']
        
        # Pre-define colors as RGB tuples from config for faster access
        self.WHITE = config.COLORS['white']
        # Define black for clearing and background rendering
        self.BLACK = config.COLORS['black']

        # Initialize default fonts to avoid recreating them on every frame (heavy OS lookup)
        self.font_16 = pygame.font.SysFont('Arial', 16)
        self.font_14 = pygame.font.SysFont('Arial', 14)
        self.font_24_bold = pygame.font.SysFont('Arial', 24, bold=True)
        self.font_18 = pygame.font.SysFont('Arial', 18)
        self.font_20 = pygame.font.SysFont('Arial', 20)
        self.badge_font = self.font_16
        self.badge_padding = (10, 6)

        # Enable spectrum computation in Sound objects (raw magnitude in dB, no processing)
        self.analysis_config['compute_spectrum'] = True
        self.analysis_config['spectrum_nfft'] = self.nfft
               
        # CRITICAL: Set max_formant in analysis_config to match spectrogram max_freq
        # This ensures AudioProcessor uses correct sample rate (2 × max_freq)
        # Without this, sample rate would be based on formant analysis max_formant (5000 Hz)
        # but we need it based on spectrogram display range to avoid aliasing
        self.analysis_config['max_formant'] = self.max_freq
        
        # Initialize AudioProcessor to capture live audio from input device
        self.audio_processor = AudioProcessor(
            chunk_ms=self.audio_config.get('chunk_ms'),
            window_ms=self.audio_config.get('window_ms'),
            # Pass analysis config to disable formants internally
            analysis_config=self.analysis_config,
            # Specify input device (None uses default device; the name takes priority over the index)
            input_device_index=self.input_device_index,
            input_device_name=self.input_device_name
        )
        # Start audio capture thread (runs in background, fills queue with chunks)
        self.audio_processor.start()
        self.audio_processor.start_recording(
            record_original=bool(config.EXPORT_CONFIG.get('save_original_audio', True)),
            record_downsampled=bool(config.EXPORT_CONFIG.get('save_downsampled_audio', False))
        )
        self.original_recording_sample_rate = self.audio_processor.get_original_recording_sample_rate()
        self.downsampled_recording_sample_rate = self.audio_processor.get_downsampled_recording_sample_rate()
        
        # Log initialization completion
        logger.info("LiveSpectrogram initialized")
        # Start the main event loop (blocking call)
        self.run()

    def _update_visible_seconds(self):
        """Compute the time span actually shown on screen.

        Each chunk is drawn as a whole number of pixels, so the visible span can differ from
        display_seconds (e.g. 2.4 px per column rounds to 2, showing 3.6 s instead of 3.0 s).
        The time axis and inspection probe use this value so labels match the image.
        """
        self.visible_seconds = self.GUI_WIDTH / float(self.column_width) * (self.chunk_ms / 1000.0)

    def render_spectrogram_column(self, spectrum_db, width):
        """Render a spectrogram column with the given spectrum and pixel width.
        
        Args:
            spectrum_db: 1D array of magnitude values in dB
            width: Width in pixels for this column (width = num_chunks * column_width)
        """
        if spectrum_db is None or spectrum_db.size == 0:
            return

        # Apply gain, clip to dynamic range, and normalize for display
        # spectrum_db contains raw magnitude values in dB (approximately -96 to 0 dB for 16-bit audio)
        magnitude_db_with_gain = spectrum_db + self.gain_db
        # Reference level is fixed at 0 dB (full scale)
        # Clip to keep only the top dynamic_range dB of the signal
        reference_db = 0.0
        magnitude_db_clipped = np.clip(magnitude_db_with_gain, reference_db - self.dynamic_range, reference_db)
        
        # Normalize clipped range to 0-255 uint8 for colormap
        # Signals at (reference_db - dynamic_range) map to 0 (black)
        # Signals at reference_db (0 dB) map to 255 (brightest color)
        # Gain shifts the signal upward, allowing previously-dark samples to reach brighter colors
        magnitude_normalized = (magnitude_db_clipped - (reference_db - self.dynamic_range)) / max(1e-12, self.dynamic_range) * 255.0
        magnitude_normalized = np.clip(magnitude_normalized, 0, 255).astype(np.uint8)
        
        # Flip so low freq is at bottom (frequencies are already ordered low to high)
        magnitude_normalized = np.flipud(magnitude_normalized)

        # Map normalized magnitudes to RGB colors via local lookup table.
        colors = self.colormap_table[magnitude_normalized]

        # Map y-coordinate to spectral index using pre-calculated mapping
        column_colors = colors[self.y_indices, :3]  # shape (GUI_HEIGHT, 3)

        # Create 2D array of shape (width, GUI_HEIGHT, 3) representing the column
        # Pygame's surfarray expects (X, Y) layout: (width, height, 3)
        column_rgb = np.repeat(column_colors[np.newaxis, :, :], width, axis=0)

        # Create column surface directly from numpy array (much faster than drawing lines in a loop)
        column_surface = pygame.surfarray.make_surface(column_rgb)

        # Scroll existing spectrogram left and blit new column at right edge
        self.spec_surface.scroll(-width, 0)
        pygame.draw.rect(self.spec_surface, self.BLACK, (self.GUI_WIDTH - width, 0, width, self.GUI_HEIGHT))
        self.spec_surface.blit(column_surface, (self.GUI_WIDTH - width, 0))

        # Also scroll and update rolling dB buffer for Shift+Click inspection
        if hasattr(self, 'spec_db_buffer') and self.spec_db_buffer is not None:
            self.spec_db_buffer = np.roll(self.spec_db_buffer, -width, axis=0)
            self.spec_db_buffer[-width:, :] = spectrum_db

    def draw_frequency_grid(self):
        """Draw frequency grid lines and labels for spectrogram axes.
        
        Renders horizontal lines at 1 kHz intervals and adds frequency labels
        on the left side for reference. Makes it easy to estimate frequencies by sight.
        """
        # Use cached font to avoid expensive OS lookups
        font = self.font_16
        
        # Draw horizontal grid lines every 1000 Hz (1 kHz)
        # This provides visual reference grid across entire spectrogram
        for freq in range(1000, int(self.max_freq), 1000):
            # Calculate y-pixel position: map frequency to GUI height
            # Frequency 0 Hz → bottom; max_freq → top
            y_pos = self.GUI_HEIGHT - int((freq / self.max_freq) * self.GUI_HEIGHT)
            # Draw horizontal line across entire width in dim gray (100,100,100)
            pygame.draw.line(self.screen, (100, 100, 100), (0, y_pos), (self.GUI_WIDTH, y_pos), 1)
            
            # Render frequency label (e.g., "1000 Hz", "2000 Hz")
            label = font.render(f'{freq} Hz', True, self.WHITE)
            # Position label on left side, slightly above the grid line for clarity
            self.screen.blit(label, (5, y_pos - 10))

    def draw_time_grid(self):
        """Draw vertical time grid lines and labels for spectrogram time axis.
        
        Dynamically calculates interval to always show 4-5 grid lines regardless
        of display_seconds setting. Adds time labels at the bottom for reference.
        """
        # Use cached font to avoid expensive OS lookups
        font = self.font_14
        
        # Calculate appropriate time interval to always show 4-5 grid lines
        # Target: 4-5 lines, so interval = display_seconds / 4.5
        target_lines = 4.5
        raw_interval = self.visible_seconds / target_lines
        
        # Round to nice numbers: 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, etc.
        nice_intervals = [0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
        # Find the closest nice interval
        interval = min(nice_intervals, key=lambda x: abs(x - raw_interval))
        
        # Draw vertical grid lines at calculated intervals
        current = interval
        while current < self.visible_seconds:
            # Calculate x-pixel position: map time to GUI width
            # Time 0s → left edge; visible_seconds → right edge
            x_pos = int((current / self.visible_seconds) * self.GUI_WIDTH)
            # Draw vertical line from top to bottom in dim gray
            pygame.draw.line(self.screen, (100, 100, 100), (x_pos, 0), (x_pos, self.GUI_HEIGHT), 1)
            
            # Render time label with appropriate precision
            if interval < 1.0:
                label_text = f'{current:.1f}s'
            else:
                label_text = f'{int(current)}s'
            label = font.render(label_text, True, self.WHITE)
            # Position label at bottom, centered on the grid line
            label_x = x_pos - label.get_width() // 2
            label_y = self.GUI_HEIGHT - 20
            self.screen.blit(label, (label_x, label_y))
            
            current += interval

    def draw_help_overlay(self):
        """Draw help overlay showing all keyboard controls.
        
        Displays a semi-transparent panel in the center of the screen
        listing all available keyboard shortcuts and their functions.
        """
        # Create semi-transparent overlay background
        overlay_width = 500
        overlay_height = 380
        overlay_x = (self.GUI_WIDTH - overlay_width) // 2
        overlay_y = (self.GUI_HEIGHT - overlay_height) // 2
        
        # Create surface with per-pixel alpha for transparency
        overlay_surface = pygame.Surface((overlay_width, overlay_height), pygame.SRCALPHA)
        # Fill with semi-transparent black (RGBA: 0, 0, 0, 220)
        overlay_surface.fill((0, 0, 0, 220))
        
        # Draw border around overlay
        pygame.draw.rect(overlay_surface, (200, 200, 200), (0, 0, overlay_width, overlay_height), 2)
        
        # Use cached fonts to avoid expensive OS lookups
        title_font = self.font_24_bold
        text_font = self.font_18
        
        # Draw title
        title = title_font.render('Keyboard Controls', True, (255, 255, 255))
        title_rect = title.get_rect(centerx=overlay_width // 2, top=15)
        overlay_surface.blit(title, title_rect)
        
        # Define help text lines (key: description)
        help_lines = [
            ('Ctrl/Cmd+?', 'Toggle this help overlay'),
            ('Ctrl/Cmd+P', 'Toggle performance overlay'),
            ('Ctrl/Cmd+G', 'Toggle frequency / time grid'),
            ('Space', 'Start / Stop recording (live / freeze)'),
            ('Shift + Click', 'Probe Time, Frequency & Power (while paused)'),
            ('ESC', 'Quit application'),
            ('', ''),  # Blank line for spacing
            ('+  / -', 'Decrease / Increase dynamic range'),
            ('Ctrl/Cmd+ / Ctrl/Cmd-', 'Increase / Decrease gain'),
        ]
        
        # Draw help text lines
        y_offset = 60
        line_height = 30
        for key, description in help_lines:
            if key:  # Skip blank lines for key column
                # Render key name in yellow
                key_text = text_font.render(key, True, (255, 255, 100))
                overlay_surface.blit(key_text, (30, y_offset))
                
                # Render description in white
                desc_text = text_font.render(description, True, (255, 255, 255))
                overlay_surface.blit(desc_text, (200, y_offset))
            
            y_offset += line_height
        
        # Use cached font to avoid expensive OS lookups
        footer_font = self.font_16
        footer_y = overlay_height - 50
        
        settings_text = footer_font.render(
            f'Current: Dynamic Range = {self.dynamic_range} dB  |  Gain = {self.gain_db} dB',
            True, (180, 180, 180)
        )
        settings_rect = settings_text.get_rect(centerx=overlay_width // 2, top=footer_y)
        overlay_surface.blit(settings_text, settings_rect)
        
        # Blit overlay to main screen
        self.screen.blit(overlay_surface, (overlay_x, overlay_y))

    def main_events(self):
        """Handle pygame events including user keyboard input and window resize.
        
        Processes quit signals, dynamic range adjustment (+/- keys),
        gain adjustment (Ctrl+/Ctrl-), help overlay toggle (Ctrl+?),
        and window resize events. Updates display state accordingly.
        """
        # Call base class event handler to handle global visualizer controls (Ctrl+G, Ctrl+H, Ctrl+P, ESC, Backspace, Delete)
        if not self.handle_base_events(self.event_holder):
            return
        
        # Handle window resize events
        if self.event_holder.resize is not None:
           # Update window size
                self.GUI_WIDTH = self.event_holder.resize.w
                self.GUI_HEIGHT = self.event_holder.resize.h
                # Update config so dimensions can be persisted
                self.spec_config['gui_width'] = self.GUI_WIDTH
                self.spec_config['gui_height'] = self.GUI_HEIGHT
                # Recreate screen with new dimensions
                self.screen = pygame.display.set_mode((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.RESIZABLE)
                # Recreate spectrogram surface with new dimensions
                old_surface = self.spec_surface
                self.spec_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT)).convert()
                self.spec_surface.fill((0, 0, 0))
                # Copy old spectrogram data, scaled to fit new dimensions
                if old_surface:
                    # Scale old surface to new size
                    scaled = pygame.transform.scale(old_surface, (self.GUI_WIDTH, self.GUI_HEIGHT))
                    self.spec_surface.blit(scaled, (0, 0))
                # Recreate/resample spec_db_buffer for new width
                num_bins = self.nfft // 2 + 1
                old_db_buf = getattr(self, 'spec_db_buffer', None)
                self.spec_db_buffer = np.full((self.GUI_WIDTH, num_bins), -120.0, dtype=np.float32)
                if old_db_buf is not None and old_db_buf.shape[0] > 0:
                    indices = np.linspace(0, old_db_buf.shape[0] - 1, self.GUI_WIDTH).astype(int)
                    self.spec_db_buffer = old_db_buf[indices, :]
                # Recalculate pixels per second for new width
                self.pixels_per_second = self.GUI_WIDTH / self.display_seconds
                # Recalculate column width for new dimensions using the actual chunk duration
                time_per_column = self.chunk_ms / 1000.0
                self.column_width = int(round(self.pixels_per_second * time_per_column))
                self.column_width = max(self.column_width, 1)
                self._update_visible_seconds()
                # Recalculate pre-calculated y_indices for the new height
                self.y_indices = (np.arange(self.GUI_HEIGHT) / self.GUI_HEIGHT * num_bins).astype(np.int32)
        
        # DYNAMIC RANGE ADJUSTMENT WITH +/- KEYS
        # + key reduces dynamic range (fewer dB displayed = more detail, less contrast)
        if self.event_holder.plus_equals:
            # Decrease dynamic range by 5 dB each press (minimum 10 dB to avoid zoom-in too much)
            self.dynamic_range = max(self.dynamic_range - 5, 10)
            # Log the new dynamic range setting to console for user feedback
            logger.info(f"Dynamic range: {self.dynamic_range} dB")
        # - key increases dynamic range (more dB displayed = less detail, more contrast)
        elif self.event_holder.minus_underscore:
            # Increase dynamic range by 5 dB each press (maximum 120 dB for reasonable display)
            self.dynamic_range = min(self.dynamic_range + 5, 120)
            # Log the new dynamic range setting to console for user feedback
            logger.info(f"Dynamic range: {self.dynamic_range} dB")
        
        # GAIN ADJUSTMENT WITH CTRL+/CTRL-
        # Ctrl+Plus increases gain (makes display brighter overall)
        if self.event_holder.ctrl_plus:
            # Increase gain by 5 dB each press (maximum 80 dB for reasonable display)
            self.gain_db = min(self.gain_db + 5, 80)
            # Log the new gain setting to console for user feedback
            logger.info(f"Gain: {self.gain_db} dB")
        # Ctrl+Minus decreases gain (makes display darker overall)
        elif self.event_holder.ctrl_minus:
            # Decrease gain by 5 dB each press (minimum 0 dB to avoid invisible display)
            self.gain_db = max(self.gain_db - 5, 0)
            # Log the new gain setting to console for user feedback
            logger.info(f"Gain: {self.gain_db} dB")

        # Space: freeze (pause recording) / resume live display and recording
        self.handle_space_toggle(self.event_holder)

        # Shift + click inspection probe (only when the display is frozen)
        self.update_inspect_probe(self.event_holder)

    def process_audio(self):
        """Draw a spectrogram column for each analyzed sound waiting in the queue. While frozen,
        discard them instead so no backlog builds up."""
        for sound in self.take_analyzed_sounds():
            if not self.paused and sound.spectrum_magnitude_db is not None:
                self.render_spectrogram_column(sound.spectrum_magnitude_db, self.column_width)

        # The audio device dropped out: the recording ended there, so export it and pause
        if self.recording and self.check_recording_interrupted() is not None:
            self._pause_recording()

    def inspect_lines(self, x, y):
        """Inspection card: time, frequency, and power at the probe (the display is frozen)."""
        ix = max(0, min(self.GUI_WIDTH - 1, int(x)))
        iy = max(0, min(self.GUI_HEIGHT - 1, int(y)))
        freq = max(0.0, min(self.max_freq, (1.0 - iy / float(self.GUI_HEIGHT)) * self.max_freq))
        t_val = (ix / float(self.GUI_WIDTH)) * self.visible_seconds
        lines = [
            ("Time", f"{t_val:.2f} s", (255, 255, 255)),
            ("Frequency", f"{int(round(freq))} Hz", (0, 220, 255)),
        ]
        if getattr(self, 'spec_db_buffer', None) is not None:
            num_bins = self.spec_db_buffer.shape[1]
            freq_ratio = max(0.0, min(1.0, 1.0 - (iy / float(self.GUI_HEIGHT))))
            bin_idx = max(0, min(num_bins - 1, int(round(freq_ratio * (num_bins - 1)))))
            raw_db = float(self.spec_db_buffer[ix, bin_idx])
            if raw_db > -200.0:
                lines.append(("Power", f"{raw_db + self.gain_db:.1f} dB", (100, 255, 120)))
        return lines

    def draw_dynamic_range_indicator(self):
        """Draw the dynamic range indicator in the top-left corner if not at default value.
        Shows the current dynamic range setting when it differs from the default.
        """
        if self.dynamic_range != self.spec_config['dynamic_range']:
            y_pos = 10
            font = self.font_20
            dr_text = font.render(f'Dynamic Range: {self.dynamic_range} dB', True, (255, 255, 255))
            text_rect = dr_text.get_rect(topleft=(10, y_pos))
            bg_rect = text_rect.inflate(10, 6)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (100, 100, 100), bg_rect, 1)
            self.screen.blit(dr_text, (10, y_pos))

    def draw_gain_indicator(self):
        """Draw the gain indicator below the dynamic range indicator if not at default value (40 dB).
        Shows the current gain setting when it differs from the default.
        """
        if self.gain_db != 0.0:
            # Find y position below dynamic range indicator
            y_pos = 10
            if self.dynamic_range != self.spec_config['dynamic_range']:
                y_pos += 35
            font = self.font_20
            gain_text = font.render(f'Gain: {self.gain_db} dB', True, (255, 255, 255))
            text_rect = gain_text.get_rect(topleft=(10, y_pos))
            bg_rect = text_rect.inflate(10, 6)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (100, 100, 100), bg_rect, 1)
            self.screen.blit(gain_text, (10, y_pos))

    def run(self):
        """Main event loop for real-time spectrogram rendering.
        
        This 60 fps loop continuously:
        1. Handles user keyboard and mouse input
        2. Draws a spectrogram column for each analyzed sound in the queue
        3. Draws the spectrogram, grids, indicators, and overlays
        4. Updates the pygame display
        
        The loop runs until user presses ESC/closes window.
        """
        try:
            while self.keep_running:
                # Limit frame rate to configured FPS for consistent CPU usage and smooth display
                self.clock.tick(self.fps)

                # Get and parse events first to keep the window responsive under load.
                self.events = pygame.event.get()
                self.event_holder = EventHolder(self.events)
                self.main_events()
                if not self.keep_running:
                    break

                # Add a spectrogram column for every analyzed sound waiting in the queue
                self.process_audio()

                # Draw the frame: spectrogram, grids, indicators, then overlays
                self.screen.fill(self.BLACK)
                self.screen.blit(self.spec_surface, (0, 0))
                if self.show_grid:  # Ctrl/Cmd+G
                    self.draw_frequency_grid()
                    self.draw_time_grid()
                self.draw_dynamic_range_indicator()
                self.draw_gain_indicator()
                self.draw_status_indicators()
                self.draw_inspect_overlay()
                if self.show_help:
                    self.draw_help_overlay()
                self.draw_performance_overlay()
                self.draw_notification()

                pygame.display.flip()
        finally:
            self.shutdown()

    def shutdown(self):
        """Export the recorded audio, save the display settings, and close the window."""
        try:
            if self.recording:
                self._collect_recording()
            if self.original_audio_buffer or self.downsampled_audio_buffer:
                self.export_recording()
            from . import settings_manager
            mgr = settings_manager.get_settings_manager()
            saved = mgr.get('spectrogram', {})
            saved['gain_db'] = self.gain_db
            saved['gui_width'] = self.screen.get_width()
            saved['gui_height'] = self.screen.get_height()
            mgr.set('spectrogram', saved)
            mgr.save()
            logger.info("LiveSpectrogram settings saved successfully")
        except Exception as save_err:
            logger.error(f"Error saving LiveSpectrogram settings: {save_err}")

        if self.audio_processor:
            self.audio_processor.stop()
        pygame.quit()
