import logging
import os
import numpy
import pygame

from .Smoother import Smoother
from .BaseAudioVisualizer import BaseAudioVisualizer
from .Sound import Sound
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from .point import Point
from . import config, exporter

logger = logging.getLogger(__name__)


class LivePitch(BaseAudioVisualizer):
    """
    Real-time pitch (f0) analysis and visualization.

    Captures audio and displays the fundamental frequency (f0) over time as a continuous pitch contour.
    Provides real-time visual feedback for pitch tracking, supporting both fixed and continuous display modes.
    """

    def __init__(self,
                 min_f0=None,
                 max_f0=None,
                 gui_width=None,
                 gui_height=None,
                 sample_rate=None,
                 pitch_config=None,
                 audio_config=None,
                 smoother_config=None,
                 analysis_config=None,
                 input_device_index=None):
        """
        Initialize the LivePitch visualizer with optional configuration overrides.

        Args:
            min_f0 (int, optional): Minimum f0 to display (Hz). Uses config default if None.
            max_f0 (int, optional): Maximum f0 to display (Hz). Uses config default if None.
            gui_width (int, optional): Window width in pixels. Uses config default if None.
            gui_height (int, optional): Window height in pixels. Uses config default if None.
            sample_rate (int, optional): Audio sample rate (Hz). Uses config default if None.
            pitch_config (dict, optional): Override entire pitch config.
            audio_config (dict, optional): Override entire audio config.
            smoother_config (dict, optional): Override smoother config.
            analysis_config (dict, optional): Override analysis config.
            input_device_index (int, optional): Audio input device index. Uses default if None.
        """
        
        # Get config information from arguments or defaults
        self.pitch_config = pitch_config or config.LIVEPITCH_CONFIG.copy()  # Pitch display and UI settings
        self.audio_config = audio_config or config.AUDIO_CONFIG.copy()      # Audio capture and processing settings
        self.smoother_config = smoother_config or config.SMOOTHER_CONFIG.copy()  # Pitch smoothing parameters
        self.analysis_config = analysis_config or config.ANALYSIS_CONFIG.copy()  # Analysis settings (formants, pitch, etc.)
        self.input_device_index = input_device_index  # Index of audio input device (None = default)

        # Apply user overrides if provided
        if min_f0 is not None:
            self.pitch_config['min_f0'] = min_f0  # Minimum f0 for display (Hz)
        if max_f0 is not None:
            self.pitch_config['max_f0'] = max_f0  # Maximum f0 for display (Hz)
        if gui_width is not None:
            self.pitch_config['gui_width'] = gui_width  # Window width (pixels)
        if gui_height is not None:
            self.pitch_config['gui_height'] = gui_height  # Window height (pixels)
        if sample_rate is not None:
            self.audio_config['sample_rate'] = sample_rate  # Audio sample rate (Hz)

        # Ensure only pitch is analyzed for this visualizer
        self.analysis_config['formants'] = False  # Disable formant analysis
        self.analysis_config['pitch'] = True      # Enable pitch analysis
        self.analysis_config['compute_spectrum'] = False  # Disable spectrum computation

        # Initialize base class and GUI
        super().__init__(
            app_title="Live Pitch",
            config={
                'audio_config': self.audio_config,
                'analysis_config': self.analysis_config,
                'freq_scale': self.pitch_config.get('freq_scale', 'log'),
            },
            gui_width=self.pitch_config['gui_width'],
            gui_height=self.pitch_config['gui_height'],
            input_device_index=input_device_index
        )

        # Core state and buffers
        self.sound = Sound(**self.analysis_config)  # Current audio analysis frame
        self.smoother = Smoother(**self.smoother_config)  # Pitch smoothing object
        self.point = None  # Most recent pitch point (Point object)
        self.all_points = pygame.sprite.Group()  # All pitch points (for export)
        self.track_points = pygame.sprite.Group()  # Points in current track
        self.finished_tracks = []  # List of completed pitch tracks
        self.manual_points = []  # User-placed manual annotation points
        self.sample_rate = self.audio_config['sample_rate']  # Audio sample rate (Hz)

        # Display and analysis parameters
        self.pitch_plot_mode = self.pitch_config.get('pitch_plot_mode', 'fixed')  # 'fixed' or 'continuous' display mode
        self.pitch_display_seconds = max(float(self.pitch_config.get('pitch_display_seconds', 5.0)), 0.1)  # Display window width (s)
        self.time_window_s = self.pitch_display_seconds  # Time window for display (s)
        self.track_start_time = None  # Start time of current track (s)
        self.track_duration = 0.0  # Duration of current track (s)
        self.window_start_time = 0.0  # Left edge of display window (continuous mode)
        self.continuous_scroll_offset = 0.0  # Scroll offset for continuous mode (s)
        self.edge_padding = 15  # Padding (pixels) from right edge for plotting

        # Analysis config for pitch tracking
        self.pitch_analysis_config = self.analysis_config.copy()  # Copy of analysis config for pitch
        self.pitch_analysis_config['formants'] = False  # Ensure formant extraction is off
        self.pitch_analysis_config['min_f0'] = self.analysis_config.get('min_f0', 75)  # Min f0 for analysis (Hz)
        self.pitch_analysis_config['max_f0'] = self.analysis_config.get('max_f0', 300)  # Max f0 for analysis (Hz)

        # Log f0 ranges for debugging
        logger.info(f"Pitch analysis f0 range: {self.pitch_analysis_config['min_f0']}-{self.pitch_analysis_config['max_f0']} Hz (from analysis_config)")
        logger.info(f"Pitch display f0 range: {self.pitch_config.get('min_f0', 75)}-{self.pitch_config.get('max_f0', 500)} Hz (display only)")

        # GUI constants for drawing
        self.GUI_WIDTH = self.pitch_config['gui_width']  # Window width (pixels)
        self.GUI_HEIGHT = self.pitch_config['gui_height']  # Window height (pixels)
        self.MIN_f0 = self.pitch_config['min_f0']  # Minimum f0 for display scaling (Hz)
        self.MAX_f0 = self.pitch_config['max_f0']  # Maximum f0 for display scaling (Hz)
        self.WHITE = config.COLORS['white']  # RGB tuple for white
        self.BLACK = config.COLORS['black']  # RGB tuple for black
        self.BLUE = config.COLORS['blue']    # RGB tuple for blue

        # State flags and buffers
        self.keep_running = True  # Main event loop flag
        self.recording = False  # True if currently recording
        self.started = False  # True after sustained voicing onset
        self.voicing_run = 0  # Number of consecutive voiced frames
        self.unvoiced_run = 0  # Number of consecutive unvoiced frames
        self.last_space_pressed = False  # For spacebar debouncing
        self.space_released_since_recording_stop = True  # Track if space was released after forced stop
        self.session_name = exporter.create_session_name('speaker')  # Unique session name for export
        self.recording_start_time = None  # Start time of current recording (s)
        self.audio_buffer = []  # Raw audio buffer for WAV export
        self.pitch_log = []  # Pitch log for current track only
        self.all_pitch_points = []  # All pitch points for all tracks (for CSV export)

        # Calculate grid steps for display axes
        self.calculate_grid_steps()

        logger.info("LivePitch initialized")
        self.run()

    def quit(self):
        """
        Request application exit and stop the main event loop.
        """
        logging.info("Quit requested")  # Log quit request
        self.keep_running = False  # Stop the main loop

    def start_recording(self):
        """
        Begin a new push-to-talk recording segment.
        Initializes a new audio processor and resets state for a new pitch track.
        """
        if self.recording:  # Avoid double-start
            return  # Exit if already recording
        self.recording = True  # Set recording flag
        self.started = False  # Reset voicing onset flag
        self.voicing_run = 0  # Reset voiced counter
        self.unvoiced_run = 0  # Reset unvoiced counter
        self.track_points = pygame.sprite.Group()  # New active track group
        self.recording_start_time = None  # Reset recording start time
        self.track_start_time = None  # Reset track start time
        # Don't clear audio_buffer - accumulate across all tracks
        self.pitch_log = []  # Clear pitch log for this track
        # Don't create new session_name - use the one from __init__ for all tracks
        self.smoother._f0_history = []  # Reset smoother history
        self.smoother._f0_smooth = None  # Reset smoother state
        self.smoother.pitch_use = False  # Reset smoother gating

        self.audio_processor = AudioProcessor(  # Create audio processor
            chunk_ms=self.audio_config.get('chunk_ms'),  # Chunk duration
            number_of_chunks=self.audio_config.get('number_of_chunks'),  # Number of chunks
            analysis_config=self.pitch_analysis_config,  # Pitch-only config
            input_device_index=self.input_device_index  # Audio input device
        )  # End processor init
        self.audio_processor.start()  # Start background thread
        self.audio_processor.start_recording()  # Start audio buffering
        logger.info("Recording started")  # Log start

    def stop_recording(self):
        """
        Stop the current recording segment and buffer results (no export).
        Finalizes the current pitch track and stores pitch points for export.
        """
        if not self.recording:
            return
        self.recording = False

        if self.audio_processor:
            self.audio_processor.stop_recording()
            # Accumulate audio from this track into the buffer
            self.audio_buffer.extend(self.audio_processor.get_recording().tolist())
            self.audio_processor.stop()

        if len(self.track_points.sprites()) >= 2:
            for pt in self.track_points.sprites():
                pt.set_color((0, 100, 255))
            self.finished_tracks.append(self.track_points)
            # Buffer pitch points for this track with track number
            track_num = len(self.finished_tracks)
            for row in self.pitch_log:
                row_with_track = dict(row)
                row_with_track['track'] = track_num
                self.all_pitch_points.append(row_with_track)
        logger.info("Recording stopped")

    def freq_to_y(self, f0):
        """
        Convert f0 (Hz) to Y pixel coordinate based on the current frequency scale (log or linear).
        Returns the vertical position for plotting the given frequency.
        """
        f0 = max(f0, 1.0)  # Clamp f0 to positive
        if self.freq_scale == 'log':  # Logarithmic scaling
            y_diff = numpy.log(f0) - numpy.log(self.MIN_f0)  # Log-scaled delta
            y_range = numpy.log(self.MAX_f0) - numpy.log(self.MIN_f0)  # Log-scaled range
        else:  # Linear scaling
            y_diff = f0 - self.MIN_f0  # Linear delta
            y_range = self.MAX_f0 - self.MIN_f0  # Linear range
        return self.GUI_HEIGHT - self.GUI_HEIGHT * (y_diff / y_range)  # Map to pixel Y

    def point_coordinates(self, t_sec, plot_f0, window_start):
        """
        Convert time and f0 to screen coordinates (log or linear scale).

        Args:
            t_sec (float): Absolute time in seconds.
            plot_f0 (float): Fundamental frequency in Hz.
            window_start (float): Left edge of display window in seconds.

        Returns:
            tuple: (x, y) screen coordinates for plotting.
        """
        relative_t = max(t_sec - window_start, 0.0)  # Time within window
        # Map time to x, leaving edge_padding pixels at right edge
        usable_width = self.GUI_WIDTH - self.edge_padding  # Width excluding right padding
        plot_x = usable_width * (relative_t / self.time_window_s)  # Map time to x
        plot_y = self.freq_to_y(plot_f0)  # Map f0 to y using helper

        return plot_x, plot_y  # Return pixel coordinates

    def main_events(self):
        """
        Process input events using EventHolder and raw key events.
        Handles window resizing, mouse clicks, and keyboard shortcuts for pitch visualization.
        """
        # Handle common events (grid, help, quit, debouncing) from base class
        if not self.handle_base_events(self.event_holder):
            return  # Quit was requested
        
        # Handle window resize events
        if self.event_holder.resize is not None:
            # Update internal dimensions
            self.GUI_WIDTH = self.event_holder.resize.w
            self.GUI_HEIGHT = self.event_holder.resize.h
            # Recreate screen with new dimensions
            self.screen = pygame.display.set_mode((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.RESIZABLE)
            # Update the configuration dictionary so other calculations stay accurate
            self.pitch_config['gui_width'] = self.GUI_WIDTH
            self.pitch_config['gui_height'] = self.GUI_HEIGHT
        
        if self.event_holder and self.event_holder.quit is not None:  # Window close
            self.quit()  # Quit application

        if self.event_holder and self.event_holder.left_click_down is not None:  # Left click
            manual_point = Point(  # Create manual point
                None,  # No Sound object
                self.event_holder.left_click_down.pos[0],  # X position
                self.event_holder.left_click_down.pos[1],  # Y position
                radius=6,  # Small marker radius
                color=(0, 150, 0)  # Green marker
            )  # End manual point creation
            self.manual_points.append(manual_point)  # Store manual point

        if self.event_holder and self.event_holder.right_click_down is not None:  # Right click
            self.manual_points = []  # Clear manual points

        # Pitch-specific event handling (RMS adjustment and recording control)
        if self.event_holder.plus_equals:  # +/= key
            self.adjust_min_rms(+3)  # Increase min_rms_db by 3 dB
            
        if self.event_holder.minus_underscore:  # -/_ key
            self.adjust_min_rms(-3)  # Decrease min_rms_db by 3 dB

        # Handle space key for push-to-talk recording
        if self.event_holder.space_down:  # Space key pressed
            # In fixed mode, only allow restart if space was released after last stop
            if self.space_released_since_recording_stop:  # Allow new recording
                self.start_recording()  # Start push-to-talk
                self.space_released_since_recording_stop = False  # Mark that we started
                
        if self.event_holder.space_up:  # Space key released
            self.stop_recording()  # Stop push-to-talk
            self.space_released_since_recording_stop = True  # Space released, allow restart on next press

    def _handle_backspace(self):
        """
        Remove the most recently completed pitch track from the display (undo last recording).
        """
        if len(self.finished_tracks) > 0:  # Check if any finished tracks exist
            self.finished_tracks.pop()  # Remove last track from list (undo last recording)

    def _handle_delete(self):
        """
        Clear all completed pitch tracks from the display at once.
        Useful for resetting the visualization without quitting.
        """
        self.finished_tracks = []  # Clear entire list of finished tracks

    def run(self):
        """
        Main event loop for real-time pitch visualization.
        Handles event polling, drawing, and updating the display at the configured frame rate.
        """
        logger.info("LivePitch started")  # Log start

        try:  # Ensure cleanup in finally
            while self.keep_running:  # Main loop
                self.clock.tick(self.pitch_config['fps'])  # Cap frame rate
                self.events = pygame.event.get()  # Read pygame events
                self.event_holder = EventHolder(self.events)  # Parse events
                self.main_events()  # Handle input events

                self.screen.fill(config.COLORS['white'])  # Clear background
                self.run_points()  # Process audio and draw points
                self.draw_min_rms_display()  # Draw min_rms_db value if recently changed
                self._draw_grid()  # Draw optional grid overlay (toggle with 'g')
                self._draw_help_overlay()  # Draw optional help overlay (toggle with 'h')

                pygame.display.flip()  # Present frame
        finally:  # Always clean up
            self.shutdown()  # Shutdown resources

    def run_points(self):
        """
        Process audio, update pitch points, and render the pitch view.
        Handles pitch smoothing, track segmentation, and drawing of pitch contours.
        """
        if self.recording:  # Only process audio when recording
            try:  # Guard against audio errors
                self.sound = self.audio_processor.get_sound()  # Get next analysis frame

                recorded_count = 0  # Default sample count
                try:  # Try to read sample count
                    recorded_count = self.audio_processor.get_recording_sample_count()  # Recorded samples
                except Exception:  # Fallback if count unavailable
                    recorded_count = 0  # Use zero samples

                # Calculate window size from chunk_ms and number_of_chunks
                chunk_ms = self.audio_config.get('chunk_ms', 25)
                number_of_chunks = self.audio_config.get('number_of_chunks', 2)
                window_ms = chunk_ms * number_of_chunks
                window_samples = int(round(  # Window size in samples
                    self.audio_config['sample_rate'] * (window_ms / 1000)  # Convert ms to samples
                ))  # End window sample calc
                elapsed_time = max(  # Compute elapsed time
                    0.0,  # Clamp at zero
                    (recorded_count - (window_samples / 2)) / self.audio_config['sample_rate']  # Center window time
                )  # End elapsed time calc

                if not self.started:  # Waiting for sustained voicing
                    if self.sound.voicing and self.sound.f0 >= self.MIN_f0:  # Voiced and in range
                        self.voicing_run += 1  # Increment voiced counter
                    else:  # Not voiced or out of range
                        self.voicing_run = 0  # Reset voiced counter
                    if self.voicing_run >= 3:  # Require 3 consecutive voiced frames
                        self.started = True  # Allow plotting
                        self.track_start_time = elapsed_time  # Record track start time

                if self.started:  # After voicing onset
                    # Check if fixed mode has exceeded max duration
                    should_process = True  # Flag to process this frame
                    if self.pitch_plot_mode == 'fixed':  # Fixed time mode
                        track_elapsed = elapsed_time - self.track_start_time  # Time since track start
                        if track_elapsed >= self.pitch_display_seconds:  # Exceeded max duration
                            # Force end of track and STOP RECORDING
                            if len(self.track_points.sprites()) >= 2:  # Save meaningful tracks
                                for pt in self.track_points.sprites():  # Iterate track points
                                    pt.set_color((0, 100, 255))  # Mark finished track
                                self.finished_tracks.append(self.track_points)  # Save track
                            self.track_points = pygame.sprite.Group()  # Reset active track
                            self.started = False  # Reset started flag
                            self.voicing_run = 0  # Reset voiced counter
                            self.unvoiced_run = 0  # Reset unvoiced counter
                            self.smoother._f0_history = []  # Reset smoother history
                            self.smoother._f0_smooth = None  # Reset smoother state
                            self.smoother.pitch_use = False  # Reset smoother gate
                            # Stop recording and require spacebar release before restart
                            self.stop_recording()  # Stop audio processor
                            self.space_released_since_recording_stop = False  # Require spacebar release
                            should_process = False  # Skip further processing for this frame
                    
                    # Process audio only if track not ended
                    if should_process:  # Continue processing
                        if self.sound.voicing and self.sound.f0 >= self.MIN_f0:  # Still voiced
                            self.unvoiced_run = 0  # Reset unvoiced counter
                            self.smoother.smooth_pitch(self.sound, min_f0=self.MIN_f0, max_f0=self.MAX_f0)  # Smooth f0

                            if self.smoother.pitch_use:  # Only plot stable points
                                self.pitch_log.append({  # Add row to pitch log
                                    'time_ms': int(elapsed_time * 1000),  # Timestamp in ms
                                    'f0': self.smoother.plot_f0,  # Smoothed f0
                                    'voicing': int(self.sound.voicing),  # Voicing flag
                                })  # End log row

                                self.point = Point(self.sound, 0, 0, radius=8)  # Create new point
                                self.point.f0 = self.smoother.plot_f0  # Store f0 on point
                                self.point.t_sec = elapsed_time  # Store time on point
                                self.all_points.add(self.point)  # Add to all points
                                self.track_points.add(self.point)  # Add to active track
                        else:  # Unvoiced or out of range
                            self.unvoiced_run += 1  # Increment unvoiced counter
                            if self.unvoiced_run >= 3:  # Require 3 consecutive unvoiced frames
                                if len(self.track_points.sprites()) >= 2:  # Save meaningful tracks
                                    for pt in self.track_points.sprites():  # Iterate track points
                                        pt.set_color((0, 100, 255))  # Mark finished track
                                    self.finished_tracks.append(self.track_points)  # Save track
                                self.track_points = pygame.sprite.Group()  # Reset active track
                                self.started = False  # Reset started flag
                                self.voicing_run = 0  # Reset voiced counter
                                self.unvoiced_run = 0  # Reset unvoiced counter
                                self.smoother._f0_history = []  # Reset smoother history
                                self.smoother._f0_smooth = None  # Reset smoother state
                                self.smoother.pitch_use = False  # Reset smoother gate

                    self.update_pitch_points(elapsed_time)  # Update point positions
            except Exception as e:  # Handle errors during recording
                logger.error(f"Error during recording: {e}")  # Log error
                self.stop_recording()  # Stop recording on error

        for finished in self.finished_tracks:  # Draw finished tracks first
            finished.draw(self.screen)  # Draw finished track group

        tmp_sprites = sorted(self.track_points.sprites(), key=lambda pt: pt.t_sec)  # Sort by time
        for i in range(len(tmp_sprites) - 1):  # Draw lines between consecutive points
            if (tmp_sprites[i].rect.center[1] < self.GUI_HEIGHT and  # Ensure y is visible
                tmp_sprites[i + 1].rect.center[1] < self.GUI_HEIGHT):  # Ensure y is visible
                pygame.draw.line(  # Draw thick white line for outline
                    self.screen, self.WHITE,  # Target and color
                    tmp_sprites[i].rect.center,  # Line start
                    tmp_sprites[i + 1].rect.center,  # Line end
                    4)  # Line width
                pygame.draw.line(  # Draw thin blue line for core
                    self.screen, self.BLUE,  # Target and color
                    tmp_sprites[i].rect.center,  # Line start
                    tmp_sprites[i + 1].rect.center,  # Line end
                    2)  # Line width

        self.track_points.draw(self.screen)  # Draw active track points

        for i in range(len(self.manual_points) - 1):  # Draw manual point lines
            pygame.draw.line(  # Draw green connecting line
                self.screen, (0, 150, 0),  # Target and color
                self.manual_points[i].rect.center,  # Line start
                self.manual_points[i + 1].rect.center,  # Line end
                2)  # Line width
        for pt in self.manual_points:  # Draw manual points
            self.screen.blit(pt.image, pt.rect)  # Blit point sprite

    def shutdown(self):
        """
        Clean up audio processing and GUI resources on application exit.

        Ensures proper cleanup by stopping active recording (if any), halting
        background audio thread, saving data, and shutting down pygame.
        """
        try:  # Guard shutdown steps to prevent crash on exit
            if self.recording:  # Check if currently recording
                self.stop_recording()  # Finalize current recording (stops audio, saves to finished_tracks)
            elif self.audio_processor:  # If not recording but processor exists
                self.audio_processor.stop()  # Stop background audio thread cleanly
            # Save all buffered tracks to WAV and CSV files
            self.save(file_type='all')
            pygame.quit()  # Shutdown pygame subsystem (closes window, releases display)
            logger.info("LivePitch shutdown complete")  # Log successful shutdown
        except Exception as e:  # Catch any errors during cleanup
            logger.error(f"Error during shutdown: {e}")  # Log error but don't crash

    def update_pitch_points(self, current_time):
        """
        Update pitch point positions within the current time window.

        In fixed mode: window goes from track_start_time to track_start_time + pitch_display_seconds.
        In continuous mode: window scrolls with current_time, showing the last pitch_display_seconds.
        """
        if self.pitch_plot_mode == 'fixed' and self.track_start_time is not None:  # Fixed mode
            # Window spans from track start to track start + duration
            window_start = self.track_start_time  # Fixed left edge
            window_end = self.track_start_time + self.pitch_display_seconds  # Fixed right edge
        else:  # Continuous mode
            # Window scrolls with current time
            window_start = max(current_time - self.time_window_s, 0.0)  # Window start time
            window_end = current_time  # Window end follows current time
        
        for pt in list(self.track_points.sprites()):  # Iterate over track points
            if pt.t_sec < window_start:  # Drop points outside window
                self.track_points.remove(pt)  # Remove from track
                continue  # Skip update for removed points
            plot_x, plot_y = self.point_coordinates(pt.t_sec, pt.f0, window_start)  # Compute coords
            pt.rect.center = (plot_x, plot_y)  # Update sprite position

    def calculate_grid_steps(self):
        """
        Calculate grid step sizes for time and frequency axes to produce 4-5 grid lines.
        Steps are rounded to musically or visually meaningful values for clarity.
        """
        # Time grid calculation - aim for 4-5 clean grid lines
        target_grids = 4.5  # Target number of grid lines
        time_step = self.time_window_s / target_grids  # Initial step size
        
        # Round time_step to nice values (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, etc)
        magnitude = 10 ** numpy.floor(numpy.log10(time_step))  # Get magnitude (0.1, 1, 10, etc)
        normalized = time_step / magnitude  # Normalize to 1-10 range
        
        # Choose nice step from [1, 2, 5] based on normalized value
        if normalized <= 1.5:  # Round to 1
            nice_step = 1.0
        elif normalized <= 3.5:  # Round to 2
            nice_step = 2.0
        elif normalized <= 7.0:  # Round to 5
            nice_step = 5.0
        else:  # Round to 10
            nice_step = 10.0
        
        # Reconstruct final time step with nice rounded value
        self.time_step = nice_step * magnitude  # Final time step
        
        # Frequency grid calculation - depends on scale mode
        if self.freq_scale == 'linear':  # Linear frequency spacing
            # Calculate linear step in Hz
            freq_range = max(self.MAX_f0 - self.MIN_f0, 1.0)  # Total frequency range
            freq_step = freq_range / target_grids  # Initial step size

            # Same rounding logic as time step
            magnitude = 10 ** numpy.floor(numpy.log10(freq_step))  # Magnitude
            normalized = freq_step / magnitude  # Normalize

            # Round to nice values
            if normalized <= 1.5:
                nice_step = 1.0
            elif normalized <= 3.5:
                nice_step = 2.0
            elif normalized <= 7.0:
                nice_step = 5.0
            else:
                nice_step = 10.0

            # Final linear frequency step
            self.freq_step = nice_step * magnitude
            # Flag for rendering code: use additive spacing
            self.freq_step_is_ratio = False
        else:  # Logarithmic frequency spacing
            # Log-space frequency grid uses multiplicative ratios
            log_freq_range = numpy.log(self.MAX_f0) - numpy.log(self.MIN_f0)  # Log range
            log_freq_step = log_freq_range / target_grids  # Log step size

            # freq_step represents ratio (e.g., 2.0 for octave, 1.5 for perfect fifth)
            self.freq_step = numpy.exp(log_freq_step)  # Convert back to ratio

            # Round to musically nice ratios: 1.5 (perfect fifth), 2.0 (octave), 3.0 (octave + fifth)
            if self.freq_step <= 1.7:  # Round to fifth
                self.freq_step = 1.5
            elif self.freq_step <= 2.5:  # Round to octave
                self.freq_step = 2.0
            else:  # Round to octave + fifth
                self.freq_step = 3.0
            # Flag for rendering code: use multiplicative spacing
            self.freq_step_is_ratio = True

    def draw_grid(self):
        """
        Draw time and frequency grid lines for the pitch display.
        This method wraps _draw_grid for backward compatibility.
        """
        self._draw_grid()  # Call the actual implementation

    def save(self, file_type="all"):
        """
        Save recorded pitch data and audio to WAV and CSV files.

        Exports the current recording session to disk. Creates both audio (WAV)
        and pitch data (CSV) files in the configured output directory.

        Args:
            file_type (str): Export type (currently only 'all' is supported).
        """
        if file_type != 'all':  # Check export type parameter
            return  # Only full export is implemented; skip partial exports

        # Check if saving recordings is enabled
        if not config.EXPORT_CONFIG.get('save_recordings', False):  # Check if saving is enabled (default: False)
            logger.info("Recording save is disabled - skipping export")  # Log that save is disabled
            return  # Exit without saving

        # Determine output directory and construct base filename
        output_dir = config.EXPORT_CONFIG.get('output_dir', 'recordings')  # Get output folder from config (default: 'recordings')
        base_path = os.path.join(output_dir, self.session_name)  # Build base path using session timestamp

        # Export audio file if enabled in config and audio was recorded
        if config.EXPORT_CONFIG.get('save_wav', True) and self.audio_buffer:  # Check WAV export enabled and buffer not empty
            wav_file = f"{base_path}_pitch.wav"  # Construct WAV filename with _pitch suffix
            exporter.save_wav(wav_file, numpy.array(self.audio_buffer), self.sample_rate)  # Write audio buffer to WAV file
            logger.info(f"Audio saved to {wav_file}")  # Log successful WAV export

        # Export all buffered pitch points for all tracks, with track number
        if config.EXPORT_CONFIG.get('save_csv', True) and self.all_pitch_points:
            csv_file = f"{base_path}_pitch.csv"
            exporter.save_pitch_csv(
                csv_file,
                self.all_pitch_points,
                min_f0=self.MIN_f0,
                max_f0=self.MAX_f0
            )
            logger.info(f"Pitch saved to {csv_file}")

    def _draw_grid(self) -> None:
        """
        Draw grid overlay with time and frequency labels for the pitch display.
        Only drawn if show_grid is enabled.
        """
        if not self.show_grid:  # Only draw if enabled
            return  # Skip grid drawing
        
        # Define visual styling for grid elements
        grid_color = (50, 50, 50)  # Dark gray for grid lines (subtle)
        label_color = (100, 100, 100)  # Medium gray for label text (readable but not dominant)
        font = pygame.font.SysFont(None, 18)  # System font at 18pt for axis labels
        
        # Draw vertical time grid lines using calculated step
        t = 0.0  # Start at time zero (right edge is most recent)
        while t <= self.time_window_s + 1e-6:  # Loop through time axis (epsilon for floating-point tolerance)
            x = int(self.GUI_WIDTH * (t / self.time_window_s))  # Convert time to horizontal pixel position
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, self.GUI_HEIGHT), 1)  # Draw vertical line from top to bottom
            label = font.render(f"{int(t)}s", True, label_color)  # Create time label (e.g., "0s", "2s")
            self.screen.blit(label, (x + 2, self.GUI_HEIGHT - 18))  # Draw label at bottom of line (slight offset)
            t += self.time_step  # Move to next time grid line

        # Draw horizontal frequency grid lines using calculated step
        f0 = max(self.MIN_f0, 1.0)  # Start at minimum frequency (avoid log(0) issues)
        while f0 <= self.MAX_f0 + 1e-6:  # Loop through frequency axis (epsilon for floating-point tolerance)
            y = int(self.freq_to_y(f0))  # Convert frequency to vertical pixel position (respects log/linear scale)
            pygame.draw.line(self.screen, grid_color, (0, y), (self.GUI_WIDTH, y), 1)  # Draw horizontal line across display
            label = font.render(f"{int(f0)} Hz", True, label_color)  # Create frequency label (e.g., "100 Hz")
            self.screen.blit(label, (4, y - 12))  # Draw label on left side of line (above line)
            if getattr(self, 'freq_step_is_ratio', True):  # Check if using log scale (multiplicative steps)
                f0 *= self.freq_step  # Log mode: multiply by ratio (e.g., 1.5 = musical fifth, 2.0 = octave)
            else:  # Linear scale mode
                f0 += self.freq_step  # Linear mode: add Hz value (e.g., +50 Hz)

    def _draw_help_overlay(self) -> None:
        """
        Draw a semi-transparent help overlay showing keyboard shortcuts.

        Only displayed when show_help is True (toggled with 'h' key).
        Shows all available keyboard commands for controlling the pitch visualizer.
        """
        if not self.show_help:  # Check if help overlay is enabled
            return  # Skip drawing if help is off
        
        # Create semi-transparent dark background for readability
        overlay = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT))  # Create surface matching screen size
        overlay.set_alpha(200)  # Set transparency (0=transparent, 255=opaque)
        overlay.fill((30, 30, 30))  # Fill with dark gray background
        self.screen.blit(overlay, (0, 0))  # Draw overlay on main screen
        
        # Define help text content showing all keyboard shortcuts
        help_text = [  # List of help strings
            "KEYBOARD SHORTCUTS",  # Title line (rendered larger)
            "",  # Blank line for spacing
            "SPACE - Start/stop recording (push-to-talk)",  # Toggle recording mode
            "+/= - Increase volume threshold",  # Raise RMS dB threshold
            "-/_ - Decrease volume threshold",  # Lower RMS dB threshold
            "G - Toggle grid overlay",  # Show/hide time and frequency grid
            "H - Toggle this help",  # Show/hide this overlay
            "ESC - Quit application",  # Exit the program
        ]  # End help text definition
        
        # Setup fonts for title and body text
        font_title = pygame.font.Font(None, 32)  # Larger font for title (32pt)
        font_text = pygame.font.Font(None, 24)  # Smaller font for shortcuts (24pt)
        margin = 50  # Pixel margin from screen edges
        y = margin  # Starting vertical position (top margin)
        
        # Draw title line (first element)
        title_surface = font_title.render(help_text[0], True, (255, 255, 255))  # Render title in white
        self.screen.blit(title_surface, (margin, y))  # Draw at top-left with margin
        y += 50  # Move down to leave space before shortcuts
        
        # Draw individual shortcut lines
        for line in help_text[2:]:  # Skip title and blank line, iterate over shortcuts
            text_surface = font_text.render(line, True, (200, 200, 200))  # Render in light gray
            self.screen.blit(text_surface, (margin, y))  # Draw at current position
            y += 30  # Move down for next line (30px spacing)