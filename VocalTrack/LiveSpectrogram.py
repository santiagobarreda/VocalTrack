# Import logging module for status and debug messages
# NumPy for numerical array operations and signal processing
# Pygame for real-time graphics rendering
# ScalarMappable for mapping normalized data values to RGBA colors using colormaps
# Normalize for normalizing data to 0-1 range for colormap application
# Matplotlib for colormap access

import json
import logging
import numpy as np
import pygame
import queue
from importlib import resources

# Import BaseAudioVisualizer for audio stream handling and display management
# Import AudioProcessor for capturing and queuing audio chunks
# Import EventHolder for keyboard event detection
# Import config for default settings and COLORS

from .BaseAudioVisualizer import BaseAudioVisualizer
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from . import config, exporter

# Create logger instance for this module
logger = logging.getLogger(__name__)

class LiveSpectrogram(BaseAudioVisualizer):
    """Real-time spectrogram visualization with scrolling display.
    
    This class generates a spectrogram from live audio input, displaying
    time-domain scrolling frequency content using matplotlib colormaps and pygame rendering.
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
                 input_device_index=None):
        """Initialize LiveSpectrogram with optional configuration override.
        
        Args:
            gui_width: Window width in pixels (overrides config default)
            gui_height: Window height in pixels (overrides config default)
            max_freq: Maximum frequency to display in Hz (overrides config)
            display_seconds: Time window to display in seconds (overrides config)
            colormap: Matplotlib colormap name (overrides config)
            dynamic_range: dB range for spectrogram display (overrides config)
            sample_rate: Audio sample rate in Hz (overrides config)
            spec_config: Full spectrogram config dict (if None, uses config.LIVESPECTROGRAM_CONFIG)
            audio_config: Full audio config dict (if None, uses config.AUDIO_CONFIG)
            analysis_config: Full analysis config dict (if None, uses config.ANALYSIS_CONFIG)
            input_device_index: Audio input device index for portaudio device selection
        """
      
        # Load config dicts from parameters or use defaults from config module
        self.spec_config = spec_config or config.LIVESPECTROGRAM_CONFIG.copy()
        self.audio_config = audio_config or config.AUDIO_CONFIG.copy()
        self.analysis_config = analysis_config or config.ANALYSIS_CONFIG.copy()
        # Store audio device selection for AudioProcessor
        self.input_device_index = input_device_index

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
        # chunk_size parameter is deprecated and unused
        # Override sample rate if specified
        if sample_rate is not None:
            self.audio_config['sample_rate'] = sample_rate

        # Use chunk-based settings from spectrogram config for the analysis window
        chunk_ms = self.spec_config.get('chunk_ms', 15.0)
        number_of_chunks = self.spec_config.get('number_of_chunks', 3)
        self.audio_config['chunk_ms'] = chunk_ms
        self.audio_config['number_of_chunks'] = number_of_chunks

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
        
        # Store GUI dimensions from config for easy reference
        self.GUI_WIDTH = self.spec_config['gui_width']
        # Store GUI height for frequency axis scaling
        self.GUI_HEIGHT = self.spec_config['gui_height']
        # Store maximum frequency to limit spectrogram display (avoid aliasing artifacts)
        self.max_freq = self.spec_config['max_freq']
        # Store time window duration for horizontal scrolling calculation
        self.display_seconds = self.spec_config['display_seconds']
        # Store colormap name for matplotlib color mapping (e.g., 'plasma', 'viridis')
        self.colormap_name = self.spec_config['colormap']
        # Store dynamic range in dB for frequency axis amplitude clipping (controls contrast)
        self.dynamic_range = self.spec_config['dynamic_range']
        # Store gain in dB for amplitude scaling (controls overall brightness)
        self.gain_db = 0.0
        # Flag to toggle help overlay display
        self.show_help = False
        
        # Update sample_rate based on max_freq (Nyquist: need 2× max frequency)
        # This overwrites any sample rate from audio_config to ensure correct sampling
        self.audio_config['sample_rate'] = 2 * self.max_freq
        self.sample_rate = self.audio_config['sample_rate']

        # Disable heavy math that the spectrum visualizer doesn't need
        self.analysis_config['formants'] = False
        self.analysis_config['pitch'] = False
        
        # FFT Analysis Parameters: window size is determined by chunk size and number of chunks
        window_length_ms = chunk_ms * number_of_chunks
        self.window_length = window_length_ms / 1000.0  # For reference
        
        # Calculate total window size in samples.
        self.window_samples = int(round(window_length_ms / 1000.0 * self.sample_rate))
        self.window_samples = max(self.window_samples, 1)

        # FFT size configuration: append configurable zero padding for smoothness
        # Zero padding increases visual smoothness without changing time resolution
        padding_length_ms = self.spec_config.get('padding_length_ms', 20.0)
        zero_pad_samples = int(round((padding_length_ms / 1000.0) * self.sample_rate))
        # Total FFT size is window_samples + zero padding
        self.nfft = self.window_samples + zero_pad_samples
        
        # Pre-Emphasis Filter: boost high frequencies to compensate for speech spectral tilt
        # Alpha coefficient (0.97) is standard for speech; amplifies fricatives and /s/ sounds
        self.pre_emphasis = 0.97
        
        # Load a local 256-entry RGB lookup table for this colormap.
        self.colormap_table = self._load_colormap_table(self.colormap_name)
        
        # Create pygame surface for scrolling spectrogram display
        # This surface holds the entire spectrogram history visible on screen
        self.spec_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT))
        # Initialize display with black background to avoid artifacts
        self.spec_surface.fill((0, 0, 0))
        
        # Time tracking for calculating correct pixel positions during scrolling
        self.current_time = 0.0
        # Calculate pixels per second: how many pixels to scroll per second of audio
        self.pixels_per_second = self.GUI_WIDTH / self.display_seconds
        
        # Column width in pixels: A new spectrum is generated for each audio CHUNK.
        # So, the time between columns is chunk_ms.
        time_per_column = chunk_ms / 1000.0  # Convert ms to seconds
        self.column_width = int(round(self.pixels_per_second * time_per_column))
        # Ensure at least 1 pixel width
        self.column_width = max(self.column_width, 1)
        
        # Recording state management
        self.keep_running = True  # Main loop control flag
        # Toggle flag for audio buffer recording (not keyboard-controlled in spectrogram)
        self.recording = False
        # Create unique session name for exported files (includes timestamp)
        self.session_name = exporter.create_session_name('speaker')
        # Buffer to accumulate audio samples when recording is enabled
        self.audio_buffer = []
        
        # Pre-define colors as RGB tuples from config for faster access
        self.WHITE = config.COLORS['white']
        # Define black for clearing and background rendering
        self.BLACK = config.COLORS['black']
        
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
            number_of_chunks=self.audio_config.get('number_of_chunks'),
            # Pass analysis config to disable formants internally
            analysis_config=self.analysis_config,
            # Specify input device (None uses default device)
            input_device_index=self.input_device_index
        )
        # Start audio capture thread (runs in background, fills queue with chunks)
        self.audio_processor.start()
        # Begin recording audio to internal buffer for later export
        self.audio_processor.start_recording()
        
        # Log initialization completion
        logger.info("LiveSpectrogram initialized")
        # Start the main event loop (blocking call)
        self.run()

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

        # Create column surface and fill with color per pixel row
        column_surface = pygame.Surface((width, self.GUI_HEIGHT))
        for y in range(self.GUI_HEIGHT):
            # Map y to spectral index (colors length matches number of freq bins)
            freq_idx = int((y / self.GUI_HEIGHT) * len(colors))
            freq_idx = min(freq_idx, len(colors) - 1)
            color = colors[freq_idx][:3]
            pygame.draw.line(column_surface, color, (0, y), (width - 1, y))

        # Scroll existing spectrogram left and blit new column at right edge
        self.spec_surface.scroll(-width, 0)
        pygame.draw.rect(self.spec_surface, self.BLACK, (self.GUI_WIDTH - width, 0, width, self.GUI_HEIGHT))
        self.spec_surface.blit(column_surface, (self.GUI_WIDTH - width, 0))

    def process_audio_chunk(self, sound):
        """Process incoming Sound object and render spectrogram using pre-computed spectrum.

        Uses the raw magnitude spectrum (in dB) already calculated in the Sound object's analyze_worker thread.
        Applies gain, dynamic range clipping, and color normalization here (in render_spectrogram_column)
        where these parameters can be adjusted in real-time by user keyboard input.
        
        Args:
            sound: Sound object with pre-computed spectrum attributes
        """
        if sound is None:
            return

        # Extract pre-computed spectrum dB values from Sound object
        magnitude_db = sound.spectrum_magnitude_db
        
        # Render using the standard column width
        self.render_spectrogram_column(magnitude_db, self.column_width)

        # Store raw audio for export if recording is enabled
        if self.recording and sound.samples is not None:
            try:
                # Convert float32 samples back to int16 for WAV export
                if sound.samples.dtype == np.float32:
                    int16_samples = (sound.samples * 32768.0).astype(np.int16)
                else:
                    int16_samples = sound.samples.astype(np.int16)
                self.audio_buffer.extend(int16_samples.tolist())
            except Exception:
                pass

    def draw_frequency_grid(self):
        """Draw frequency grid lines and labels for spectrogram axes.
        
        Renders horizontal lines at 1 kHz intervals and adds frequency labels
        on the left side for reference. Makes it easy to estimate frequencies by sight.
        """
        # Create font for rendering frequency labels (16pt Arial, suitable for read on screen)
        font = pygame.font.SysFont('Arial', 16)
        
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
        # Create font for rendering time labels (14pt Arial, suitable for reading)
        font = pygame.font.SysFont('Arial', 14)
        
        # Calculate appropriate time interval to always show 4-5 grid lines
        # Target: 4-5 lines, so interval = display_seconds / 4.5
        target_lines = 4.5
        raw_interval = self.display_seconds / target_lines
        
        # Round to nice numbers: 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, etc.
        nice_intervals = [0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
        # Find the closest nice interval
        interval = min(nice_intervals, key=lambda x: abs(x - raw_interval))
        
        # Draw vertical grid lines at calculated intervals
        current = interval
        while current < self.display_seconds:
            # Calculate x-pixel position: map time to GUI width
            # Time 0s → left edge; display_seconds → right edge
            x_pos = int((current / self.display_seconds) * self.GUI_WIDTH)
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
        overlay_height = 350
        overlay_x = (self.GUI_WIDTH - overlay_width) // 2
        overlay_y = (self.GUI_HEIGHT - overlay_height) // 2
        
        # Create surface with per-pixel alpha for transparency
        overlay_surface = pygame.Surface((overlay_width, overlay_height), pygame.SRCALPHA)
        # Fill with semi-transparent black (RGBA: 0, 0, 0, 220)
        overlay_surface.fill((0, 0, 0, 220))
        
        # Draw border around overlay
        pygame.draw.rect(overlay_surface, (200, 200, 200), (0, 0, overlay_width, overlay_height), 2)
        
        # Create fonts for title and help text
        title_font = pygame.font.SysFont('Arial', 24, bold=True)
        text_font = pygame.font.SysFont('Arial', 18)
        
        # Draw title
        title = title_font.render('Keyboard Controls', True, (255, 255, 255))
        title_rect = title.get_rect(centerx=overlay_width // 2, top=15)
        overlay_surface.blit(title, title_rect)
        
        # Define help text lines (key: description)
        help_lines = [
            ('Ctrl+H', 'Toggle this help overlay'),
            ('ESC', 'Quit application'),
            ('', ''),  # Blank line for spacing
            ('+  / -', 'Decrease / Increase dynamic range'),
            ('Ctrl+ / Ctrl-', 'Increase / Decrease gain'),
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
        
        # Draw footer with current settings
        footer_font = pygame.font.SysFont('Arial', 16)
        footer_y = overlay_height - 50
        
        settings_text = footer_font.render(
            f'Current: Dynamic Range = {self.dynamic_range} dB  |  Gain = {self.gain_db} dB',
            True, (180, 180, 180)
        )
        settings_rect = settings_text.get_rect(centerx=overlay_width // 2, top=footer_y)
        overlay_surface.blit(settings_text, settings_rect)
        
        # Blit overlay to main screen
        self.screen.blit(overlay_surface, (overlay_x, overlay_y))

    def handle_events(self):
        """Handle pygame events including user keyboard input and window resize.
        
        Processes quit signals, dynamic range adjustment (+/- keys),
        gain adjustment (Ctrl+/Ctrl-), help overlay toggle (Ctrl+H),
        and window resize events. Updates display state accordingly.
        """
        
        # Handle window resize events
        if self.event_holder.resize is not None:
           # Update window size
                self.GUI_WIDTH = self.event_holder.resize.w
                self.GUI_HEIGHT = self.event_holder.resize.h
                # Recreate screen with new dimensions
                self.screen = pygame.display.set_mode((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.RESIZABLE)
                # Recreate spectrogram surface with new dimensions
                old_surface = self.spec_surface
                self.spec_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT))
                self.spec_surface.fill((0, 0, 0))
                # Copy old spectrogram data, scaled to fit new dimensions
                if old_surface:
                    # Scale old surface to new size
                    scaled = pygame.transform.scale(old_surface, (self.GUI_WIDTH, self.GUI_HEIGHT))
                    self.spec_surface.blit(scaled, (0, 0))
                # Recalculate pixels per second for new width
                self.pixels_per_second = self.GUI_WIDTH / self.display_seconds
                # Recalculate column width for new dimensions
                window_length_ms = self.spec_config.get('window_length_ms', 5.0)
                time_per_column = window_length_ms / 1000.0
                self.column_width = int(round(self.pixels_per_second * time_per_column))
                self.column_width = max(self.column_width, 1)
        
     
        # Check for window close or ESC key (both trigger shutdown)
        if self.event_holder.quit or self.event_holder.escape:
            # Stop main loop and begin cleanup
            self.quit()
            return
        
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
        
        # HELP OVERLAY TOGGLE WITH CTRL+H
        # Ctrl+H toggles the help overlay display
        if self.event_holder.ctrl_h:
            self.show_help = not self.show_help
            logger.info(f"Help overlay: {'ON' if self.show_help else 'OFF'}")

    def export_recording(self):
        """Export recorded audio to WAV file.
        
        Writes buffered audio samples to timestamped WAV file
        in the recordings directory via the exporter module.
        """
        # Only export if audio was actually recorded (buffer is non-empty)
        if self.audio_buffer:
            # Convert Python list to NumPy array with int16 dtype (CD quality)
            audio_array = np.array(self.audio_buffer, dtype=np.int16)
            # Call exporter to write WAV file with timestamp and speaker name
            wav_path = exporter.export_wav(
                audio_array,
                self.audio_config['sample_rate'],
                self.session_name
            )
            # Log file save location for user reference
            logger.info(f"Exported audio to {wav_path}")

    def draw_dynamic_range_indicator(self):
        """Draw the dynamic range indicator in the top-left corner if not at default value.
        Shows the current dynamic range setting when it differs from the default.
        """
        if self.dynamic_range != self.spec_config['dynamic_range']:
            y_pos = 10
            font = pygame.font.SysFont('Arial', 20)
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
        if self.gain_db != 40.0:
            # Find y position below dynamic range indicator
            y_pos = 10
            if self.dynamic_range != self.spec_config['dynamic_range']:
                y_pos += 35
            font = pygame.font.SysFont('Arial', 20)
            gain_text = font.render(f'Gain: {self.gain_db} dB', True, (255, 255, 255))
            text_rect = gain_text.get_rect(topleft=(10, y_pos))
            bg_rect = text_rect.inflate(10, 6)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            pygame.draw.rect(self.screen, (100, 100, 100), bg_rect, 1)
            self.screen.blit(gain_text, (10, y_pos))
            

    def run(self):
        """Main event loop for real-time spectrogram rendering.
        
        This 60 fps loop continuously:
        1. Drains audio chunks from the processor queue
        2. Processes each chunk through FFT analysis and rendering
        3. Handles user keyboard input
        4. Draws spectrogram, grids, and status indicators
        5. Updates the pygame display
        
        The loop runs until user presses ESC/closes window.
        """
        # Get FPS from config or default to 60 if not set
        clock = pygame.time.Clock()

        # MAIN LOOP: Continues until keep_running flag is set False
        while self.keep_running:
            # Limit frame rate to configured FPS for consistent CPU usage and smooth display
            clock.tick(self.fps)

            # Get all pending pygame events (mouse clicks, keyboard, window events, etc.)
            # This clears the event queue and returns a list of Event objects
            self.events = pygame.event.get()
            # Parse events into easily accessible attributes (quit, resize, etc.)
            # EventHolder converts pygame events into named attributes for simplified checking
            self.event_holder = EventHolder(self.events)
            
            # PROCESS AUDIO CHUNKS FROM QUEUE
            # Drain the queue of all available sounds to keep the display up-to-date.
            # This is non-blocking and ensures the display is as smooth as possible.
            max_sounds_per_frame = 20  # Limit to prevent stalling the app
            for _ in range(max_sounds_per_frame):
                try:
                    # Use get_nowait() for a non-blocking call.
                    # This raises queue.Empty if the queue is empty.
                    sound = self.audio_processor.analyzed_sounds_queue.get_nowait()

                    if sound and sound.spectrum_magnitude_db is not None:
                        self.render_spectrogram_column(sound.spectrum_magnitude_db, self.column_width)

                        # Store raw audio for export if recording is enabled
                        if self.recording and sound.samples is not None:
                            try:
                                if sound.samples.dtype == np.float32:
                                    int16_samples = (sound.samples * 32768.0).astype(np.int16)
                                else:
                                    int16_samples = sound.samples.astype(np.int16)
                                self.audio_buffer.extend(int16_samples.tolist())
                            except Exception:
                                pass
                except queue.Empty:
                    # The queue is empty, so we're done processing for this frame.
                    break
            
            # HANDLE USER INPUT
            # Process keyboard, mouse, and window events
            self.handle_events()
            
            # CLEAR DISPLAY
            # Fill entire screen with black to prevent ghosting artifacts
            self.screen.fill(self.BLACK)
            
            # DRAW SPECTROGRAM
            # Blit the scrolling spectrogram surface (spec_surface) to the pygame screen
            # This displays the time-domain frequency content with proper colors
            self.screen.blit(self.spec_surface, (0, 0))
            
            # DRAW REFERENCE GRIDS
            # Draw horizontal lines at 1kHz intervals with frequency labels
            self.draw_frequency_grid()
            # Draw vertical lines at 1-second intervals for time reference
            self.draw_time_grid()
            
            # Draw dynamic range and gain indicators briefly upon change
            self.draw_dynamic_range_indicator()
            self.draw_gain_indicator()
             
            # DRAW HELP OVERLAY (if toggled on with Ctrl+H)
            if self.show_help:
                self.draw_help_overlay()
            
            # UPDATE DISPLAY
            # Flip pygame double buffer to show rendered frame on screen
            pygame.display.flip()
        
        # CLEANUP AFTER MAIN LOOP EXITS
        # Stop audio processor if it's still running
        if self.audio_processor:
            self.audio_processor.stop()
        # Close pygame and release all resources
        pygame.quit()

    def quit(self):
        """Request application exit by setting keep_running flag.
        
        This signals the main loop to stop, allowing graceful shutdown
        of audio processing and pygame resources.
        """
        # Log quit request for debugging/user tracking
        logger.info("Quit requested")
        # Set flag to break main event loop (checked in run() while condition)
        self.keep_running = False
