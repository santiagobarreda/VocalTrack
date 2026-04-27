
# Logging for status and debug messages
import logging
# Numpy for numerical operations and signal processing
import numpy as np
# Pygame for real-time graphics rendering
import pygame
# Queue for thread-safe audio data transfer
import queue

# Import base visualizer and audio processing utilities
from .BaseAudioVisualizer import BaseAudioVisualizer
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from . import config

# Logger for this module
logger = logging.getLogger(__name__)


class LiveSpectrum(BaseAudioVisualizer):
    """
    Real-time frequency spectrum visualizer with a continuous line plot.

    This class displays the average power spectrum of live audio input in real time.
    Each frame, it collects all available sound objects from the queue, averages their
    power across frequency bins, and updates the display as a static (non-scrolling)
    spectrum. This approach ensures smooth, up-to-date visualization even with short
    analysis windows.
    """

    def __init__(self,
                 gui_width=None,
                 gui_height=None,
                 max_freq=None,
                 dynamic_range=None,
                 spec_config=None,
                 audio_config=None,
                 analysis_config=None,
                 input_device_index=None):
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

        # Store audio device selection for AudioProcessor
        self.input_device_index = input_device_index

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
        self.chunk_ms = self.spec_config.get('chunk_ms', 15.0)
        self.number_of_chunks = self.spec_config.get('number_of_chunks', 3)
        self.max_freq = self.spec_config.get('max_freq', 5000)
        self.dynamic_range = self.spec_config.get('dynamic_range', 40)
        self.fps = self.spec_config.get('fps', 60)
        self.smoothing = self.spec_config.get('smoothing', 0.7)

        # Set max_formant for analysis (controls sample rate)
        self.analysis_config['max_formant'] = int(self.max_freq)

        # Calculate FFT size (NFFT) based on window and padding
        sample_rate = 2 * int(self.max_freq)
        window_length_ms = self.chunk_ms * self.number_of_chunks
        window_samples = int(round(window_length_ms / 1000.0 * sample_rate))
        padding_length_ms = self.spec_config.get('padding_length_ms', 20.0)
        zero_pad_samples = int(round((padding_length_ms / 1000.0) * sample_rate))
        nfft = window_samples + zero_pad_samples

        # Configure spectrum computation in analysis_config
        self.analysis_config['compute_spectrum'] = True  # Enable FFT spectrum in Sound objects
        self.analysis_config['spectrum_nfft'] = nfft  # FFT size
        self.analysis_config['spectrum_dynamic_range'] = self.dynamic_range
        self.analysis_config['spectrum_gain_db'] = 0.0  # No gain by default

        # Disable unnecessary analysis for spectrum display
        self.analysis_config['formants'] = False
        self.analysis_config['pitch'] = False
        
        # Prepare config for base class
        base_config = {
            'audio_config': self.audio_config,
            'analysis_config': self.analysis_config,
        }

        # Initialize parent class (sets up pygame, screen, etc.)
        gui_size = self.spec_config.get('gui_width', 1200), self.spec_config.get('gui_height', 600)
        super().__init__(
            app_title="Live Spectrum",
            config=base_config,
            gui_width=gui_size[0],
            gui_height=gui_size[1],
            input_device_index=input_device_index
        )

        # Create audio processor for background audio capture
        self.audio_processor = AudioProcessor(
            chunk_ms=self.chunk_ms,
            number_of_chunks=self.number_of_chunks,
            analysis_config=self.analysis_config,
            input_device_index=input_device_index
        )

        # Calculate window parameters for display info
        self.window_length_ms = self.chunk_ms * self.number_of_chunks
        self.window_length_sec = self.window_length_ms / 1000.0

        # Spectrum display state
        self.current_spectrum_db = None  # Averaged spectrum for drawing
        self.current_frequencies = None  # Frequency bins for spectrum
        self.sounds_processed_this_frame = 0  # Number of sounds processed this frame
        self.gain_offset_db = 0.0  # Gain offset in dB (adjustable with +/-)

        # Start the main event loop (blocking)
        self.run()

    def run(self):
        """
        Main event loop for real-time spectrum rendering.

        Runs at the configured frame rate (default 60 fps), performing:
            1. Draining all audio chunks from the processor queue
            2. Averaging their power spectra
            3. Handling user keyboard input
            4. Drawing the spectrum line plot and grid
            5. Updating the pygame display

        The loop continues until the user presses ESC or closes the window.
        """
        # Start audio capture thread
        self.audio_processor.start()
        # Log start message
        logger.info("LiveSpectrum started")

        # Create clock for frame rate limiting
        clock = pygame.time.Clock()
        
        # MAIN LOOP: Continues until keep_running flag is set False
        try:
            while self.keep_running:
                # Limit frame rate to configured FPS (default 60) to prevent excessive CPU usage
                clock.tick(self.fps)

                # Get all pending pygame events (keyboard, window events, etc.)
                self.events = pygame.event.get()
                # Parse events into easily accessible attributes
                self.event_holder = EventHolder(self.events)

                # Process main GUI events (quit, resize, grid toggle, help toggle, etc.)
                self.main_events()
                
                # COLLECT ALL SOUNDS FROM QUEUE
                # Drain the entire queue and average their spectra
                self.collect_and_average_spectrum()

                # Fill background with white
                self.screen.fill(config.COLORS['white'])
                
                # Draw grid if enabled (toggle with 'g')
                if self.show_grid:
                    self.draw_grid()

                # Draw spectrum line plot
                if self.current_spectrum_db is not None and self.current_frequencies is not None:
                    self.draw_spectrum_line()

                # Draw help overlay if enabled (toggle with 'h')
                if self.show_help:
                    self.draw_help_overlay()

                # Swap display buffers to show everything drawn this frame
                pygame.display.flip()
        finally:
            # Always execute cleanup code, even if exception occurs
            self.shutdown()

    def collect_and_average_spectrum(self):
        """
        Applies exponential smoothing to every sound object in the queue sequentially.
        This ensures consistent temporal dynamics regardless of frame rate. 
        """
        self.sounds_processed_this_frame = 0
        alpha = self.smoothing  # e.g., 0.7
        
        # Process every sound currently waiting in the queue
        while True:
            try:
                sound = self.audio_processor.analyzed_sounds_queue.get_nowait()
                
                if sound and sound.spectrum_magnitude_db is not None:
                    new_data = sound.spectrum_magnitude_db
                    
                    # If this is the very first sound ever, just initialize
                    if self.current_spectrum_db is None:
                        self.current_spectrum_db = new_data
                    else:
                        # SEQUENTIAL EXPONENTIAL SMOOTHING
                        # Every new chunk updates the 'running' state
                        self.current_spectrum_db = (alpha * new_data) + ((1 - alpha) * self.current_spectrum_db)
                    
                    # Update frequency axis if provided
                    if sound.spectrum_frequencies is not None:
                        self.current_frequencies = sound.spectrum_frequencies
                        
                    self.sounds_processed_this_frame += 1
                    
            except queue.Empty:
                break


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
        
        # Get screen dimensions
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        
        # Define plot area margins
        left_margin = 60  # Space for frequency labels on left
        right_margin = 20  # Space on right edge
        top_margin = 40  # Space for title at top
        bottom_margin = 60  # Space for frequency axis labels at bottom
        
        # Calculate usable plot area dimensions
        plot_width = screen_width - left_margin - right_margin
        plot_height = screen_height - top_margin - bottom_margin        
            
        # Get spectrum and frequencies up to max_freq
        spectrum_subset = spectrum #[:freq_limit_idx]
        freq_subset = frequencies #[:freq_limit_idx]
        
        # Another safety check: ensure we have data to plot
        if len(spectrum_subset) == 0 or len(freq_subset) == 0:
            return
        
        # Apply gain offset to spectrum values (actual dBFS with gain adjustment)
        spectrum_with_gain = spectrum_subset + self.gain_offset_db
        
        # Fixed Y-axis range: from 0 dB (top) to -dynamic_range dB (bottom)
        y_axis_max = 0.0  # 0 dB at top
        y_axis_min = -float(self.dynamic_range)  # -dynamic_range dB at bottom
        
        # Convert spectrum coordinates to screen pixel coordinates
        points = []
        for freq, mag_db in zip(freq_subset, spectrum_with_gain):
            # Normalize frequency from 0-max_freq to 0-1
            freq_normalized = float(freq) / float(self.max_freq)
            # Convert to pixel X position
            x_pixel = float(left_margin) + freq_normalized * float(plot_width)
            
            # Map magnitude dB from y_axis_min to y_axis_max range to 0-1
            # Clamp to display range (values above 0 dB are clipped, below floor fade out)
            mag_clamped = np.clip(float(mag_db), y_axis_min, y_axis_max)
            # Normalize: 0 dB maps to 1.0, -dynamic_range dB maps to 0.0
            mag_normalized = (mag_clamped - y_axis_min) / (y_axis_max - y_axis_min)
            # Convert to pixel Y position (invert because Y increases downward)
            y_pixel = float(screen_height) - float(bottom_margin) - mag_normalized * float(plot_height)
            
            # Convert to Python int for pygame (handles numpy types)
            points.append((int(x_pixel), int(y_pixel)))
        
            # Draw the continuous spectrum line in a single C-level call
            if points and len(points) > 1:
                # Arguments: surface, color, closed (False = don't connect end to start), points list, width
                pygame.draw.lines(self.screen, (0, 150, 255), False, points, 4)
                
        # Draw axes
        # Left axis (Y-axis for magnitude)
        pygame.draw.line(self.screen, (0, 0, 0), 
                         (left_margin, top_margin), 
                         (left_margin, screen_height - bottom_margin), 2)
        
        # Bottom axis (X-axis for frequency)
        pygame.draw.line(self.screen, (0, 0, 0),
                         (left_margin, screen_height - bottom_margin),
                         (screen_width - right_margin, screen_height - bottom_margin), 2)

        # Draw frequency axis labels
        font = pygame.font.SysFont('Arial', 14)
        freq_labels = [0, self.max_freq // 4, self.max_freq // 2, 3 * self.max_freq // 4, self.max_freq]
        for freq in freq_labels:
            x_pixel = left_margin + (freq / self.max_freq) * plot_width
            label_text = font.render(f"{freq}", True, (50, 50, 50))
            text_rect = label_text.get_rect(center=(x_pixel, screen_height - bottom_margin + 25))
            self.screen.blit(label_text, text_rect)

        # Draw magnitude axis labels (dB) - fixed range from 0 dB to -dynamic_range dB
        # Y-axis extends from 0 dB (top) to -dynamic_range dB (bottom)
        db_labels = [0, -self.dynamic_range // 3, -2 * self.dynamic_range // 3, -self.dynamic_range]
        for db_val in db_labels:
            # Map dB value to pixel position (0 dB at top, -dynamic_range at bottom)
            mag_normalized = (db_val - (-self.dynamic_range)) / (0.0 - (-self.dynamic_range))
            y_pixel = screen_height - bottom_margin - mag_normalized * plot_height
            label_text = font.render(f"{int(db_val)} dB", True, (50, 50, 50))
            text_rect = label_text.get_rect(right=(left_margin - 10), centery=y_pixel)
            self.screen.blit(label_text, text_rect)

        # Draw title and info
        title_font = pygame.font.SysFont('Arial', 18, bold=True)
        title = title_font.render("Frequency Spectrum", True, (0, 0, 0))
        title_rect = title.get_rect(topleft=(20, 10))
        self.screen.blit(title, title_rect)
        
        # Draw frame info including padding_length_ms and number of bins
        #padding_ms = self.spec_config.get('padding_length_ms', 20.0)
        #nfft = self.analysis_config.get('spectrum_nfft', 512)
        #num_bins = len(spectrum_subset)
        #info_text = f"Sounds: {self.sounds_processed_this_frame} | Window: {self.window_length_ms:.0f}ms | Padding: {padding_ms:.0f}ms | NFFT: {nfft} | Bins: {num_bins}"
        #info_font = pygame.font.SysFont('Arial', 12)
        #info_surface = info_font.render(info_text, True, (100, 100, 100))
        #info_rect = info_surface.get_rect(topright=(screen_width - 20, 10))
        #self.screen.blit(info_surface, info_rect)

    def draw_grid(self):
        """
        Draw grid lines on the spectrum plot for visual reference.

        Vertical lines mark frequency divisions; horizontal lines mark dB divisions.
        Grid lines help users interpret the spectrum plot axes.
        """
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        
        # Define plot area margins (must match draw_spectrum_line)
        left_margin = 60
        right_margin = 20
        top_margin = 40
        bottom_margin = 60
        
        plot_width = screen_width - left_margin - right_margin
        plot_height = screen_height - top_margin - bottom_margin
        
        grid_color = (200, 200, 200)  # Light gray grid
        
        # Draw vertical grid lines for frequency
        num_freq_lines = 4
        for i in range(1, num_freq_lines):
            x_pos = left_margin + (i / num_freq_lines) * plot_width
            pygame.draw.line(self.screen, grid_color, 
                           (x_pos, top_margin),
                           (x_pos, screen_height - bottom_margin), 1)
        
        # Draw horizontal grid lines for magnitude
        num_mag_lines = 4
        for i in range(1, num_mag_lines):
            y_pos = top_margin + (i / num_mag_lines) * plot_height
            pygame.draw.line(self.screen, grid_color,
                           (left_margin, y_pos),
                           (screen_width - right_margin, y_pos), 1)

    def draw_help_overlay(self):
        """
        Display help text overlay with keyboard shortcuts for user interaction.
        """
        help_text = [
            "KEYBOARD SHORTCUTS:",
            "G: Toggle Grid",
            "H: Toggle Help",
            "+/-: Adjust Gain",
            "ESC: Quit"
        ]
        
        font = pygame.font.SysFont('Arial', 14)
        line_height = 25
        start_y = 80
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
        Process GUI events including quit, grid/help toggle, and gain adjustment.

        Handles keyboard shortcuts for toggling grid/help overlays and adjusting gain.
        """
        # Handle base events (quit, grid/help toggle)
        self.handle_base_events(self.event_holder)
        
        # Handle gain adjustment with +/- keys (3 dB per press)
        if self.event_holder.plus_equals:
            self.gain_offset_db += 3.0
            logger.info(f"Gain increased to {self.gain_offset_db} dB")
        
        if self.event_holder.minus_underscore:
            self.gain_offset_db -= 3.0
            logger.info(f"Gain decreased to {self.gain_offset_db} dB")

    def shutdown(self):
        """
        Clean up resources and close the application safely.

        Stops the audio processor, quits pygame, and logs shutdown status.
        """
        try:
            # Stop audio capture thread
            if self.audio_processor:
                self.audio_processor.stop()
            # Close Pygame
            pygame.quit()
            logger.info("LiveSpectrum shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
