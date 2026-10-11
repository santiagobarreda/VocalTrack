import logging
import numpy
import pygame

from .Smoother import Smoother
from .BaseAudioVisualizer import BaseAudioVisualizer, fit_to_desktop
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
                 input_device_index=None,
                 input_device_name=None):
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
        self.input_device_name = input_device_name  # Name of audio input device; takes priority over the index

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

        # One analysis per display frame: the audio chunk (the analysis time step) is one frame long
        self.audio_config.setdefault('window_ms', config.AUDIO_CONFIG['window_ms'])
        self.audio_config['chunk_ms'] = config.chunk_ms_for_fps(self.pitch_config.get('fps', 60))
        self.analysis_config['window_length'] = self.audio_config['window_ms'] / 1000.0
        self.analysis_config['time_step'] = self.audio_config['chunk_ms'] / 1000.0

        # Shrink the window (same aspect ratio) if it does not fit on this screen
        self.pitch_config['gui_width'], self.pitch_config['gui_height'] = fit_to_desktop(
            self.pitch_config['gui_width'], self.pitch_config['gui_height'])

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
        self.target_fps = self.pitch_config['fps']

        # Core state and buffers
        self.sound = Sound(**self.analysis_config)  # Current audio analysis frame
        self.smoother = Smoother(**self.smoother_config, chunk_ms=self.audio_config.get('chunk_ms'))  # Pitch smoothing object
        self.point = None  # Most recent pitch point (Point object)
        self.track_points = pygame.sprite.Group()  # Points in current track
        self.finished_tracks = []  # List of completed pitch tracks
        self.manual_points = []  # User-placed manual annotation points
        self.sample_rate = self.audio_config['sample_rate']  # Audio sample rate (Hz)

        # Display and analysis parameters
        self.pitch_plot_mode = self.pitch_config.get('pitch_plot_mode', 'fixed')  # 'fixed' or 'continuous' display mode
        self.pitch_display_seconds = max(float(self.pitch_config.get('pitch_display_seconds', 5.0)), 0.1)  # Display window width (s)
        self.time_window_s = self.pitch_display_seconds  # Time window for display (s)
        self.track_start_time = None  # Start time of current track (s)
        self.edge_padding = 15  # Padding (pixels) from right edge for plotting

        # Analysis config for pitch tracking
        self.pitch_analysis_config = self.analysis_config.copy()  # Copy of analysis config for pitch
        self.pitch_analysis_config['formants'] = False  # Ensure formant extraction is off
        self.pitch_analysis_config['min_f0'] = self.analysis_config.get('min_f0', 60)  # Min f0 for analysis (Hz)
        self.pitch_analysis_config['max_f0'] = self.analysis_config.get('max_f0', 500)  # Max f0 for analysis (Hz)

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

        # State flags and buffers
        self.keep_running = True  # Main event loop flag
        self.recording = False  # True if currently recording
        self.started = False  # True after sustained voicing onset
        self.voicing_run = 0  # Number of consecutive voiced frames
        self.unvoiced_run = 0  # Number of consecutive unvoiced frames
        self.session_name = None  # Export file name stem, set at the start of each recording segment
        self.original_audio_buffer = []  # Device-rate audio buffer for WAV export
        self.downsampled_audio_buffer = []  # Analysis-rate audio buffer for WAV export
        self.original_recording_sample_rate = self.sample_rate  # Device-rate export sample rate
        self.downsampled_recording_sample_rate = self.sample_rate  # Analysis-rate export sample rate
        self.pitch_log = []  # Pitch log for current track only
        self.all_pitch_points = []  # All pitch points for all tracks (for CSV export)
        # Number of the last track written to the CSV. Never reused, even when tracks are
        # removed from the display with Backspace/Delete.
        self.last_track_number = 0
        self.continuous_time_offset = 0.0  # Cumulative timeline offset for continuous scrolling mode

        # Calculate grid steps for display axes
        self.calculate_grid_steps()

        # Cache for grid rendering
        self.grid_surface = None
        self.horizontal_grid_surface = None
        self.latest_elapsed_time = 0.0

        logger.info("LivePitch initialized")
        self.run()

    def start_recording(self):
        """
        Begin a new live pitch recording segment.
        Initializes a new audio processor and resets state for a new pitch track.
        """
        if self.recording:  # Avoid double-start
            return  # Exit if already recording
        self.recording = True  # Set recording flag
        self.started = False  # Reset voicing onset flag
        self.voicing_run = 0  # Reset voiced counter
        self.unvoiced_run = 0  # Reset unvoiced counter
        self.track_points = pygame.sprite.Group()  # New active track group
        self.track_start_time = None  # Reset track start time
        if self.pitch_plot_mode == 'fixed':
            self.latest_elapsed_time = 0.0  # Reset elapsed time for fixed mode window
        else:
            self.latest_elapsed_time = self.continuous_time_offset  # Maintain continuous timeline
        # Each recording segment is exported as its own set of files
        self.session_name = self.new_recording_name()
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.all_pitch_points = []
        self.alert_text = None  # Clear any "mic disconnected" banner
        self.pitch_log = []  # Clear pitch log for this track
        self._reset_pitch_smoother()
        # Use the current min RMS threshold, which may have been changed with +/- while paused
        # (before the first segment there is no audio processor for adjust_min_rms to update)
        self.pitch_analysis_config['min_rms_db'] = self.analysis_config.get(
            'min_rms_db', self.pitch_analysis_config.get('min_rms_db'))

        self.audio_processor = AudioProcessor(  # Create audio processor
            chunk_ms=self.audio_config.get('chunk_ms'),  # Chunk duration
            window_ms=self.audio_config.get('window_ms'),  # Analysis window length
            analysis_config=self.pitch_analysis_config,  # Pitch-only config
            input_device_index=self.input_device_index,  # Audio input device
            input_device_name=self.input_device_name
        )  # End processor init
        self.audio_processor.start()  # Start background thread
        self.audio_processor.start_recording(
            record_original=bool(config.EXPORT_CONFIG.get('save_original_audio', True)),
            record_downsampled=bool(config.EXPORT_CONFIG.get('save_downsampled_audio', False))
        )  # Start audio buffering
        self.original_recording_sample_rate = self.audio_processor.get_original_recording_sample_rate()
        self.downsampled_recording_sample_rate = self.audio_processor.get_downsampled_recording_sample_rate()
        logger.info("Recording started")  # Log start
        self.notify_recording(True)

    def stop_recording(self):
        """
        Stop the current recording segment, finalize the current pitch track, and export the
        segment's audio and pitch points as a new set of files.
        """
        if not self.recording:
            return
        self.recording = False

        if self.pitch_plot_mode == 'continuous':
            self.continuous_time_offset = self.latest_elapsed_time

        # Buffer the active track first, so all of this segment's rows are in all_pitch_points
        self._finish_track(min_points=1)

        # Stop recording in the audio processor, collect what it recorded, then stop its thread
        self._collect_recording()
        if self.audio_processor:
            self.audio_processor.stop()

        # Export if data was captured, then clear the buffers so nothing is saved twice
        if self.original_audio_buffer or self.downsampled_audio_buffer or self.all_pitch_points:
            logger.info(f"Exporting session: {self.session_name}")
            self.save(file_type='all')
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.all_pitch_points = []

        logger.info("Recording stopped")
        self.notify_recording(False)

    def _reset_pitch_smoother(self):
        """Reset the smoother's pitch state so the next track starts fresh."""
        self.smoother.f0_history = numpy.full(self.smoother.memory_n, 1)  # Reset smoother history buffer
        self.smoother._pitch_euro_prev_time = None  # Reset 1-Euro filter time tracker
        self.smoother._pitch_euro_x_prev = 1.0  # Reset 1-Euro filter position
        self.smoother._pitch_euro_dx_prev = 0.0  # Reset 1-Euro filter velocity
        self.smoother.pitch_skipped = 0  # Reset skip counter
        self.smoother.valid_pitch_frames = 0  # Reset warm-up frame counter
        self.smoother.plot_f0 = 1.0  # Reset plot frequency
        self.smoother.last_valid_f0 = 1.0  # Reset last valid frequency
        self.smoother.pitch_use = False  # Reset smoother gating

    def _finish_track(self, min_points):
        """
        End the active track. If it has at least min_points points, turn it blue, keep it on screen,
        and buffer its pitch rows for the CSV under a new track number. Shorter tracks are discarded
        along with their rows, so they are never merged into the next track.
        """
        if len(self.track_points.sprites()) >= min_points:
            for pt in self.track_points.sprites():
                pt.set_color((0, 100, 255))
            self.finished_tracks.append(self.track_points)
            self.last_track_number += 1
            for row in self.pitch_log:
                row_with_track = dict(row)
                row_with_track['track'] = self.last_track_number
                self.all_pitch_points.append(row_with_track)
        self.pitch_log = []
        self.track_points = pygame.sprite.Group()

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

    def y_to_freq(self, y):
        """
        Convert Y pixel coordinate to f0 (Hz) based on current frequency scale.
        """
        y_clamped = max(0.0, min(float(y), float(self.GUI_HEIGHT)))
        y_norm = max(0.0, min(1.0, 1.0 - (y_clamped / float(self.GUI_HEIGHT))))
        if self.freq_scale == 'log':
            log_min = numpy.log(max(self.MIN_f0, 1.0))
            log_max = numpy.log(self.MAX_f0)
            return float(numpy.exp(log_min + y_norm * (log_max - log_min)))
        else:
            return float(self.MIN_f0 + y_norm * (self.MAX_f0 - self.MIN_f0))

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
        relative_t = t_sec - window_start  # Time within window (negative when scrolled past left edge)
        # Map time to x, leaving edge_padding pixels at right edge
        usable_width = self.GUI_WIDTH - self.edge_padding  # Width excluding right padding
        plot_x = usable_width * (relative_t / self.time_window_s)  # Map time to x
        plot_y = self.freq_to_y(plot_f0)  # Map f0 to y using helper

        return plot_x, plot_y  # Return pixel coordinates

    def point_coordinates_rel(self, t_rel, plot_f0):
        """
        Convert relative time within a track (seconds) and f0 to screen coordinates for fixed mode.
        """
        t_clamped = max(0.0, min(t_rel, self.time_window_s))
        usable_width = self.GUI_WIDTH - self.edge_padding
        plot_x = usable_width * (t_clamped / self.time_window_s)
        plot_y = self.freq_to_y(plot_f0)
        return plot_x, plot_y

    def main_events(self):
        """
        Process input events (parsed by EventHolder): shared controls, window resize, log/linear
        scale, the Shift + click probe, manual target points, the RMS threshold, and Space.
        """
        eh = self.event_holder
        # Handle common events (grid, help, quit, backspace, delete) from base class
        if not self.handle_base_events(eh):
            return  # Quit was requested

        # Handle window resize events
        if eh.resize is not None:
            # Update internal dimensions
            self.GUI_WIDTH = eh.resize.w
            self.GUI_HEIGHT = eh.resize.h
            # Recreate screen with new dimensions
            self.screen = pygame.display.set_mode((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.RESIZABLE)
            # Update the configuration dictionary so other calculations stay accurate
            self.pitch_config['gui_width'] = self.GUI_WIDTH
            self.pitch_config['gui_height'] = self.GUI_HEIGHT
            # Recreate cached grid surface on resize
            self.grid_surface = None
            self.horizontal_grid_surface = None
            self.update_pitch_points(self.latest_elapsed_time)

        # Handle Ctrl+L to toggle log/linear frequency scale
        if eh.ctrl_l:
            self.freq_scale = 'linear' if self.freq_scale == 'log' else 'log'
            self.pitch_config['freq_scale'] = self.freq_scale
            self.calculate_grid_steps()  # Log and linear scales use different grid spacing
            self.grid_surface = None
            self.horizontal_grid_surface = None
            self.update_pitch_points(self.latest_elapsed_time)

        # Shift + click inspection probe (only when recording is paused/frozen)
        self.update_inspect_probe(eh)

        # Left click (without Shift): place a manual green target point; right click: clear them
        if eh.left_click_down is not None and not eh.shift_held:
            self.manual_points.append(Point(eh.left_click_down.pos[0], eh.left_click_down.pos[1],
                                            radius=6, color=(0, 150, 0)))
        if eh.right_click_down is not None:
            self.manual_points = []

        # +/- keys: minimum RMS threshold
        if eh.plus_equals:
            self.adjust_min_rms(+3)
        if eh.minus_underscore:
            self.adjust_min_rms(-3)

        # Space: start / pause recording
        self.handle_space_toggle(eh)

    def toggle_recording(self):
        """Space: start a new recording segment, or pause (freezing the display)."""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def is_frozen(self):
        """The display is frozen (Shift + click probe allowed) while not recording."""
        return not self.recording

    def _handle_backspace(self):
        """
        Remove the most recently completed pitch track from the display (undo last recording).
        """
        if len(self.finished_tracks) > 0:  # Check if any finished tracks exist
            removed_track = self.finished_tracks.pop()  # Remove last track from list
            logger.info(f"LivePitch: Removed last track (had {len(removed_track.sprites())} points)")
            self.show_notification("Removed last track (Backspace)", duration_ms=1500, bg_color=(255, 230, 230), border_color=(200, 50, 50))
            if len(self.finished_tracks) == 0 and not self.recording:
                self.continuous_time_offset = 0.0
                self.latest_elapsed_time = 0.0

    def _handle_delete(self):
        """
        Clear all completed pitch tracks from the display at once.
        Useful for resetting the visualization without quitting.
        """
        if len(self.finished_tracks) > 0 or len(self.track_points) > 0 or self.continuous_time_offset > 0:
            self.finished_tracks = []  # Clear entire list of finished tracks
            self.track_points = pygame.sprite.Group()
            self.continuous_time_offset = 0.0
            self.latest_elapsed_time = 0.0
            logger.info("LivePitch: Cleared all finished tracks and reset timeline")
            self.show_notification("Cleared all tracks (Delete)", duration_ms=1500, bg_color=(255, 230, 230), border_color=(200, 50, 50))

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
                if self.show_grid:
                    self._draw_grid()
                self.process_sounds()  # Analyze queued sounds into pitch points and tracks
                self.draw_points()  # Draw tracks, the live contour, and manual target points
                self.draw_inspect_overlay()  # Inspection card (Shift+Click while paused)

                self.draw_min_rms_display()  # Draw min_rms_db value if recently changed
                self.draw_notification()  # Draw temporary notification banner (e.g. device warning)
                self.draw_status_indicators()  # Draw [REC] / [PAUSED] status badges
                self._draw_help_overlay()  # Draw optional help overlay (toggle with Ctrl/Cmd+?)
                self.draw_performance_overlay()  # Draw performance diagnostics (toggle with Ctrl/Cmd+P)

                pygame.display.flip()  # Present frame
        finally:  # Always clean up
            self.shutdown()  # Shutdown resources

    def inspect_lines(self, x, y):
        """Inspection card: time and f0 at the probe, and the f0 of the nearest plotted point."""
        f0_val = self.y_to_freq(y)
        usable_w = max(1, self.GUI_WIDTH - self.edge_padding)
        if self.pitch_plot_mode == 'fixed':
            t_val = (x / usable_w) * self.time_window_s
        else:
            window_start = max(self.latest_elapsed_time - self.time_window_s, 0.0)
            t_val = window_start + (x / usable_w) * self.time_window_s

        lines = [
            ("Time", f"{t_val:.2f} s", (255, 255, 255)),
            ("Pitch (f0)", f"{f0_val:.1f} Hz", (0, 220, 255)),
        ]

        # Search for nearest recorded point within 25px
        near_pt = None
        min_dist = 25.0
        all_sprites = []
        for tr in self.finished_tracks:
            all_sprites.extend(tr.sprites())
        all_sprites.extend(self.track_points.sprites())
        for pt in all_sprites:
            if 0 <= pt.rect.centerx <= usable_w:
                dist = ((pt.rect.centerx - x)**2 + (pt.rect.centery - y)**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    near_pt = pt

        if near_pt and hasattr(near_pt, 'f0'):
            lines.append(("Track Point f0", f"{near_pt.f0:.1f} Hz", (100, 255, 120)))
        return lines

    def process_sounds(self):
        """
        Process the analyzed sounds waiting in the queue (while recording): smooth f0, segment
        tracks, log rows for the CSV, create pitch points, and update their positions.
        """
        if self.recording:  # Only process audio when recording
            try:  # Guard against audio errors
                sounds_to_process = self.take_analyzed_sounds()

                if sounds_to_process:
                    latest_elapsed_time = 0.0

                    for sound in sounds_to_process:
                        self.sound = sound

                        # Window center (s) relative to the start of this segment's recording (the
                        # exported WAV), stamped in the capture thread by AudioProcessor
                        chunk_elapsed = sound.recording_time if sound.recording_time is not None else 0.0
                        if self.pitch_plot_mode == 'continuous':
                            elapsed_time = self.continuous_time_offset + chunk_elapsed
                        else:
                            elapsed_time = chunk_elapsed

                        latest_elapsed_time = elapsed_time

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
                            if self.pitch_plot_mode == 'fixed':  # Fixed time mode
                                track_elapsed = elapsed_time - self.track_start_time  # Time since track start
                                if track_elapsed >= self.pitch_display_seconds:  # Exceeded max duration
                                    # Force end of track and STOP RECORDING
                                    self._finish_track(min_points=2)  # Save meaningful tracks
                                    self.started = False  # Reset started flag
                                    self.voicing_run = 0  # Reset voiced counter
                                    self.unvoiced_run = 0  # Reset unvoiced counter
                                    self._reset_pitch_smoother()
                                    # Stop recording upon reaching right edge of window
                                    self.stop_recording()  # Stop audio processor
                                    break  # Recording has ended: ignore any later sounds in this batch

                            if self.sound.voicing and self.sound.f0 >= self.MIN_f0:  # Still voiced
                                self.unvoiced_run = 0  # Reset unvoiced counter
                                self.smoother.smooth_pitch(self.sound, min_f0=self.MIN_f0, max_f0=self.MAX_f0)  # Smooth f0

                                if self.smoother.pitch_use:  # Only plot stable points
                                    self.pitch_log.append({  # Add row to pitch log
                                        'time_ms': int(chunk_elapsed * 1000),  # Timestamp in ms (position in exported WAV)
                                        'f0': self.sound.f0,  # Raw f0 from Sound object
                                        'f0_smoothed': self.smoother.plot_f0,  # Smoothed f0
                                        'voicing': int(self.sound.voicing),  # Voicing flag
                                    })  # End log row

                                    # Create new point (red). It keeps the raw f0 and where the frame is
                                    # in the saved recording, not the audio itself
                                    self.point = Point(0, 0, radius=8, color=(166, 33, 64), raw_f0=self.sound.f0,
                                                       recording_time=chunk_elapsed, recording_name=self.session_name)
                                    self.point.f0 = self.smoother.plot_f0  # Store smoothed f0 on point
                                    self.point.t_sec = elapsed_time  # Store time on point
                                    live_start = self.track_start_time if self.track_start_time is not None else elapsed_time
                                    self.point.t_rel = max(0.0, elapsed_time - live_start)
                                    self.track_points.add(self.point)  # Add to active track
                            else:  # Unvoiced or out of range
                                self.unvoiced_run += 1  # Increment unvoiced counter
                                if self.unvoiced_run >= 3:  # Require 3 consecutive unvoiced frames
                                    self._finish_track(min_points=2)  # Save meaningful tracks
                                    self.started = False  # Reset started flag
                                    self.voicing_run = 0  # Reset voiced counter
                                    self.unvoiced_run = 0  # Reset unvoiced counter
                                    self._reset_pitch_smoother()

                    self.latest_elapsed_time = latest_elapsed_time
                    self.update_pitch_points(latest_elapsed_time)  # Update point positions

                # The audio device dropped out: the segment ended there (frames analyzed before the
                # dropout were processed above), so stop and export it
                if self.recording and self.check_recording_interrupted() is not None:
                    self.stop_recording()
            except Exception as e:  # Handle errors during recording
                logger.error(f"Error during recording: {e}")  # Log error

    def _draw_contour(self, sprites, color):
        """Draw one pitch track: connecting lines in time order, then its points (on screen only)."""
        time_key = 't_rel' if self.pitch_plot_mode == 'fixed' else 't_sec'
        sprites = sorted(sprites, key=lambda pt: getattr(pt, time_key, pt.rect.centerx))
        for p1, p2 in zip(sprites, sprites[1:]):
            # Only draw line if at least part of the segment is on screen
            if not (p1.rect.centerx < 0 and p2.rect.centerx < 0) and not (p1.rect.centerx > self.GUI_WIDTH and p2.rect.centerx > self.GUI_WIDTH):
                if (p1.rect.centery < self.GUI_HEIGHT and p2.rect.centery < self.GUI_HEIGHT):
                    pygame.draw.line(self.screen, self.WHITE, p1.rect.center, p2.rect.center, 4)
                    pygame.draw.line(self.screen, color, p1.rect.center, p2.rect.center, 2)
        for pt in sprites:
            if 0 <= pt.rect.centerx <= self.GUI_WIDTH and pt.rect.centery < self.GUI_HEIGHT:
                self.screen.blit(pt.image, pt.rect)

    def draw_points(self):
        """Draw finished tracks (blue), the active track (red), and manual target points (green)."""
        for finished in self.finished_tracks:
            self._draw_contour(finished.sprites(), (0, 100, 255))
        self._draw_contour(self.track_points.sprites(), (166, 33, 64))

        # Manual target points, joined left to right
        sorted_manual = sorted(self.manual_points, key=lambda pt: pt.rect.centerx)
        for p1, p2 in zip(sorted_manual, sorted_manual[1:]):
            pygame.draw.line(self.screen, (0, 150, 0), p1.rect.center, p2.rect.center, 2)
        for pt in sorted_manual:
            self.screen.blit(pt.image, pt.rect)

    def shutdown(self):
        """
        Clean up audio processing and GUI resources on application exit.

        Ensures proper cleanup by stopping active recording (if any), halting
        background audio thread, saving data, and shutting down pygame.
        """
        try:  # Guard shutdown steps to prevent crash on exit
            if self.recording:  # Check if currently recording
                self.stop_recording()  # Finalize and export the current segment (stops audio)
            elif self.audio_processor:  # If not recording but processor exists
                self.audio_processor.stop()  # Stop background audio thread cleanly
            
            # Save current settings (like window size, min_rms_db) back to manager
            try:
                from . import settings_manager
                mgr = settings_manager.get_settings_manager()
                
                # Save pitch plot settings
                saved_pitch = mgr.get('pitch_plot', {})
                saved_pitch['gui_width'] = self.screen.get_width()
                saved_pitch['gui_height'] = self.screen.get_height()
                mgr.set('pitch_plot', saved_pitch)
                
                # Save analysis settings
                saved_analysis = mgr.get('analysis', {})
                saved_analysis['min_rms_db'] = self.analysis_config.get('min_rms_db', -60.0)
                mgr.set('analysis', saved_analysis)
                
                mgr.save()
                logger.info("LivePitch settings saved successfully")
            except Exception as save_err:
                logger.error(f"Error saving LivePitch settings: {save_err}")

            pygame.quit()  # Shutdown pygame subsystem (closes window, releases display)
            logger.info("LivePitch shutdown complete")  # Log successful shutdown
        except Exception as e:  # Catch any errors during cleanup
            logger.error(f"Error during shutdown: {e}")  # Log error but don't crash

    def update_pitch_points(self, current_time):
        """
        Update pitch point positions within the current time window.

        In fixed mode:
            - Active live track is positioned relative to track_start_time across [0, pitch_display_seconds].
            - Completed/historical tracks stay positioned relative to their own t_rel across [0, pitch_display_seconds].
        In continuous mode:
            - Window scrolls with current_time, displaying points falling within [current_time - time_window_s, current_time].
        """
        if self.pitch_plot_mode == 'fixed':
            live_start = self.track_start_time if self.track_start_time is not None else 0.0
            for pt in list(self.track_points.sprites()):
                t_rel = getattr(pt, 't_rel', max(0.0, pt.t_sec - live_start))
                plot_x, plot_y = self.point_coordinates_rel(t_rel, pt.f0)
                pt.rect.center = (plot_x, plot_y)
            
            for track in self.finished_tracks:
                for pt in track.sprites():
                    t_rel = getattr(pt, 't_rel', 0.0)
                    plot_x, plot_y = self.point_coordinates_rel(t_rel, pt.f0)
                    pt.rect.center = (plot_x, plot_y)
        else:
            window_start = max(current_time - self.time_window_s, 0.0)
            
            for pt in self.track_points.sprites():
                plot_x, plot_y = self.point_coordinates(pt.t_sec, pt.f0, window_start)
                pt.rect.center = (plot_x, plot_y)
                
            for track in self.finished_tracks:
                for pt in track.sprites():
                    plot_x, plot_y = self.point_coordinates(pt.t_sec, pt.f0, window_start)
                    pt.rect.center = (plot_x, plot_y)

    @staticmethod
    def _nice_step(step):
        """Round a grid step to 1, 2, 5 or 10 times a power of ten."""
        magnitude = 10 ** numpy.floor(numpy.log10(step))  # Power of ten (0.1, 1, 10, etc)
        normalized = step / magnitude  # Between 1 and 10
        if normalized <= 1.5:
            return 1.0 * magnitude
        elif normalized <= 3.5:
            return 2.0 * magnitude
        elif normalized <= 7.0:
            return 5.0 * magnitude
        return 10.0 * magnitude

    def calculate_grid_steps(self):
        """
        Calculate grid step sizes for time and frequency axes to produce 4-5 grid lines.
        Steps are rounded to musically or visually meaningful values for clarity.
        """
        # Time grid calculation - aim for 4-5 clean grid lines
        target_grids = 4.5  # Target number of grid lines
        time_step = self.time_window_s / target_grids  # Initial step size
        
        # Round time_step to nice values (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, etc)
        self.time_step = self._nice_step(time_step)
        
        # Frequency grid calculation - depends on scale mode
        if self.freq_scale == 'linear':  # Linear frequency spacing
            # Calculate linear step in Hz
            freq_range = max(self.MAX_f0 - self.MIN_f0, 1.0)  # Total frequency range
            freq_step = freq_range / target_grids  # Initial step size

            # Same rounding as the time step
            self.freq_step = self._nice_step(freq_step)
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

    def save(self, file_type="all"):
        """
        Save recorded pitch data and audio to WAV and CSV files.

        Exports the current recording segment to disk. Creates audio (WAV)
        and pitch data (CSV) files independently in the configured output directory.

        Args:
            file_type (str): Export type (currently only 'all' is supported).
        """
        if file_type != 'all':  # Check export type parameter
            return  # Only full export is implemented; skip partial exports

        # Export audio files if enabled in config and audio was recorded
        self.save_audio_files('pitch')
        base_path = self.output_base_path()

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

    # Grid colours shared by the fixed and continuous displays
    GRID_COLOR = (50, 50, 50)  # Dark gray for grid lines (subtle)
    GRID_LABEL_COLOR = (100, 100, 100)  # Medium gray for label text

    def _draw_frequency_grid(self, surface) -> None:
        """Draw the horizontal frequency grid lines and their labels onto a surface."""
        font = self.default_font_18
        f0 = max(self.MIN_f0, 1.0)
        while f0 <= self.MAX_f0 + 1e-6:
            y = int(self.freq_to_y(f0))
            pygame.draw.line(surface, self.GRID_COLOR, (0, y), (self.GUI_WIDTH, y), 1)
            label = font.render(f"{int(f0)} Hz", True, self.GRID_LABEL_COLOR)
            surface.blit(label, (4, y - 12))
            if self.freq_step_is_ratio:
                f0 *= self.freq_step
            else:
                f0 += self.freq_step

    def create_horizontal_grid_surface(self) -> None:
        """
        Create a cached background surface containing the horizontal frequency grid lines and axis labels
        (continuous mode, where the time lines scroll and are drawn every frame).
        """
        self.horizontal_grid_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.SRCALPHA)
        self.horizontal_grid_surface.fill((0, 0, 0, 0))
        self._draw_frequency_grid(self.horizontal_grid_surface)
        # Convert surface to match screen pixel format for optimized CPU blitting
        self.horizontal_grid_surface = self.horizontal_grid_surface.convert_alpha()

    def create_grid_surface(self) -> None:
        """
        Create a cached background surface containing both horizontal and vertical
        grid lines and axis labels for fixed mode. Pre-rendered once on startup/resize.
        """
        self.grid_surface = pygame.Surface((self.GUI_WIDTH, self.GUI_HEIGHT), pygame.SRCALPHA)
        self.grid_surface.fill((0, 0, 0, 0))
        font = self.default_font_18
        usable_width = self.GUI_WIDTH - self.edge_padding

        # Draw vertical time grid lines (0 to time_window_s)
        t = 0.0
        while t <= self.time_window_s + 1e-6:
            x = int(usable_width * (t / self.time_window_s))
            pygame.draw.line(self.grid_surface, self.GRID_COLOR, (x, 0), (x, self.GUI_HEIGHT), 1)
            label_text = f"{int(round(t))}s" if (self.time_step >= 1.0) else f"{t:.1f}s"
            label = font.render(label_text, True, self.GRID_LABEL_COLOR)
            self.grid_surface.blit(label, (x + 2, self.GUI_HEIGHT - 18))
            t += self.time_step

        self._draw_frequency_grid(self.grid_surface)
        self.grid_surface = self.grid_surface.convert_alpha()

    def _draw_grid(self) -> None:
        """
        Draw time and frequency grid lines and labels for the pitch display.
        In fixed mode, blits the fully pre-rendered static grid surface (0 redraw overhead).
        In continuous mode, blits the cached frequency lines and slides the time lines dynamically.
        """
        if not self.show_grid:
            return

        # Fixed mode: use 100% pre-rendered cached surface
        if self.pitch_plot_mode == 'fixed':
            if self.grid_surface is None:
                self.create_grid_surface()
            self.screen.blit(self.grid_surface, (0, 0))
            return

        # Continuous mode: blit cached horizontal lines + render sliding vertical lines
        if self.horizontal_grid_surface is None:
            self.create_horizontal_grid_surface()
        self.screen.blit(self.horizontal_grid_surface, (0, 0))

        font = self.default_font_18
        usable_width = self.GUI_WIDTH - self.edge_padding

        current_time = getattr(self, 'latest_elapsed_time', 0.0)
        window_start = max(current_time - self.time_window_s, 0.0)
        window_end = window_start + self.time_window_s

        if self.time_step > 0:
            first_t = numpy.ceil(window_start / self.time_step) * self.time_step
        else:
            first_t = window_start

        t = first_t
        while t <= window_end + 1e-6:
            relative_t = t - window_start
            x = int(usable_width * (relative_t / self.time_window_s))
            if 0 <= x <= self.GUI_WIDTH:
                pygame.draw.line(self.screen, self.GRID_COLOR, (x, 0), (x, self.GUI_HEIGHT), 1)
                label_text = f"{int(round(t))}s" if (self.time_step >= 1.0) else f"{t:.1f}s"
                label = font.render(label_text, True, self.GRID_LABEL_COLOR)
                self.screen.blit(label, (x + 2, self.GUI_HEIGHT - 18))
            t += self.time_step

    def _draw_help_overlay(self) -> None:
        """
        Draw a semi-transparent help overlay showing visual color guide and keyboard shortcuts.
        """
        if not self.show_help:
            return

        legend_items = [
            ("Active Vocalization (Live):", (255, 100, 100), "Red contour & dots = real-time f0 tracking of ongoing speech"),
            ("Finalized Tracks (Previous):", (100, 180, 255), "Blue contours & dots = completed pitch tracks preserved on screen"),
            ("Manual Target Contours:", (120, 240, 120), "Green markers & line = pitch targets placed with left-click")
        ]
        help_controls = [
            "Space             - Start / pause real-time recording",
            "Shift + Left click - Probe Time & Pitch (f0) (while paused)",
            "Backspace         - Undo last completed pitch track",
            "Delete            - Clear all completed pitch tracks",
            "+ / -             - Adjust minimum RMS volume threshold",
            "Left click        - Place manual pitch target marker",
            "Right click       - Clear all manual target markers",
            "Ctrl/Cmd+G / +L   - Toggle grid overlay / Log-linear frequency scale",
            "Ctrl/Cmd+P        - Toggle performance monitor overlay",
            "ESC               - Exit application and export session data",
        ]
        self.draw_help_panel("LivePitch Controls & Color Guide", legend_items, help_controls,
                             font_big=self.default_font_24, font_normal=self.default_font_18,
                             font_bold=self.default_font_18, size=(self.GUI_WIDTH, self.GUI_HEIGHT))

    def status_badges(self):
        """[REC] while recording, [PAUSED] otherwise."""
        return [("[REC]", (255, 80, 80))] if self.recording else [("[PAUSED]", (255, 210, 80))]
