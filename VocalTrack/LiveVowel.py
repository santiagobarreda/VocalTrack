# Import logging for debug/error messages
import logging
# Import time for timestamp calculations
import time
# Import os for file/directory operations
import os

# Import numpy for numerical array operations
import numpy
# Import pygame for graphics and GUI
import pygame

# Import required modules using relative imports
from .Smoother import Smoother
from .BaseAudioVisualizer import BaseAudioVisualizer  # Base class for shared functionality
# Import required classes and modules
from .Sound import Sound
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from .point import Point
from . import ipalabels, voweltemplate
from . import config, exporter

# Create logger instance for this module
logger = logging.getLogger(__name__)


class LiveVowel(BaseAudioVisualizer):
    """
    Real-time vowel analysis GUI using formant tracking.

    Captures audio, analyzes formants (F1/F2), and displays vowel space trajectory
    in real-time. Supports overlaying a template of reference vowels (green IPA symbols),
    which can be toggled on/off with Ctrl+T. The user can also toggle individual vowels
    in the menu (Ctrl+V) at any time.
    """

    def __init__(self, 
                 gui_config=None,
                 audio_config=None,
                 analysis_config=None,
                 smoother_config=None,
                 input_device_index=None):
        """
        Initialize LiveVowel application and all audio/GUI components.

        Args:
            gui_config (dict, optional): GUI settings. Uses default if None.
            audio_config (dict, optional): Audio settings. Uses default if None.
            analysis_config (dict, optional): Analysis settings. Uses default if None.
            smoother_config (dict, optional): Smoother settings. Uses default if None.
            input_device_index (int, optional): Audio input device index. Uses default if None.
        """
        # Load configuration dictionaries (use defaults if not provided)
        self.gui_info = gui_config or config.LIVEVOWEL_CONFIG.copy()  # GUI display settings
        self.audio_config = audio_config or config.AUDIO_CONFIG.copy()  # Audio settings
        self.analysis_config = analysis_config or config.ANALYSIS_CONFIG.copy()  # Analysis settings
        # Handle legacy 'robust' parameter name (renamed to 'robust_formants')
        if 'robust' in self.analysis_config and 'robust_formants' not in self.analysis_config:
            logger.warning("Parameter 'robust' is deprecated, use 'robust_formants' instead")
            self.analysis_config['robust_formants'] = self.analysis_config.pop('robust')
        self.smoother_config = smoother_config or config.SMOOTHER_CONFIG.copy()  # Smoother settings

        # Force the math we need to be True, overriding any changes made by other visualizers
        self.analysis_config['formants'] = True
        self.analysis_config['pitch'] = True
        self.analysis_config['compute_spectrum'] = False


        # Prepare config dict for base class initialization
        base_config = {
            'audio_config': self.audio_config,
            'analysis_config': self.analysis_config,
        }

        
        
        # Call parent class __init__ (initializes pygame, screen, clock, UI toggles)
        gui_size = self.gui_info['gui_size']
        super().__init__(
            app_title="Live Vowel",
            config=base_config,
            gui_width=gui_size[0],
            gui_height=gui_size[1],
            input_device_index=input_device_index
        )

        # Create Sound object for formant analysis (will be reused for each frame)
        self.sound = Sound(**self.analysis_config)
        # Create audio processor thread to capture microphone input in background
        self.audio_processor = AudioProcessor(
            chunk_ms=self.audio_config.get('chunk_ms'),
            number_of_chunks=self.audio_config.get('number_of_chunks'),
            analysis_config=self.analysis_config,
            min_rms_db=self.audio_config.get('min_rms_db'),
            input_device_index=input_device_index
        )
        # Create smoother to filter noisy formant trajectories
        self.smoother = Smoother(**self.smoother_config)

        # Pygame sprite groups for rendering points on screen
        self.point = None  # Most recent point, None if no valid point exists
        self.track = pygame.sprite.Group()  # Current trajectory (connected points)
        self.finished_tracks = []  # List of completed track Groups (turned blue, ordered)
        self.all_points = pygame.sprite.Group()  # All points ever created (for export)

        # Data storage for export
        self.data = []  # Will store formant data for saving

        # UI components for display
        self.ipalabels = ipalabels.IPALabels(self.screen, gui_info=self.gui_info)  # IPA vowel labels overlaid on plot
        self.voweltemplate = voweltemplate.VowelTemplate(self.screen, self.gui_info)  # Vowel chart template

        # Application state
        self.state = "recording"  # Start in recording mode
        # Flag to toggle green template IPA symbols (from template) on/off (Ctrl+T)
        # When True, all template vowels are shown; when False, they are hidden (but can be toggled individually in menu)
        self.show_template = True  # Start with template visible
        self.keep_running = True  # Set to False to exit application
        # Display mode for visualization ("single", "track", or "all")
        self.display_mode = self.gui_info.get('display_mode', 'single')
        # Frequency scale for axis display ("log" or "linear")
        self.freq_scale = self.gui_info.get('freq_scale', 'log')
        # Track the current track number from smoother to detect when new tracks begin
        self.current_track_number = 0  # Matches smoother's initial track_number
        # Track whether a valid point was created in the current frame
        self.point_created_this_frame = False
        # Track previous smoother.use state to detect when track becomes unstable
        self.last_smoother_use = False
        
        # Recording session tracking for file export
        self.session_name = exporter.create_session_name('speaker')
        self.recording_start_time = None  # Will be set when first frame is captured
        self.audio_buffer = []  # Raw audio samples for WAV export
        self.formant_log = []  # Timestamped formant data for CSV export
        
        # Min RMS display state (temporary indicator shown when adjusted)
        self.min_rms_display_text = ""  # Text to display ("Min RMS: XX dB")
        self.min_rms_display_until = 0  # Timestamp when display should disappear
        
        # Start the main event loop (blocking call)
        self.run()

    def run(self):
        """
        Run the main event loop for the LiveVowel GUI.
        Handles event polling, audio capture, GUI updates, and rendering.
        """
        # Start audio capture thread in background
        self.audio_processor.start()
        # Begin recording audio to buffer
        if self.state == "recording":
            self.audio_processor.start_recording()
        # Log start message to console/log file
        logger.info("LiveVowel started")

        # Main event loop wrapped in try/finally to ensure cleanup on exit
        try:
            # Loop until keep_running flag is set to False (via quit() method)
            while self.keep_running:
                # Limit frame rate to configured FPS (default 60) to prevent excessive CPU usage
                # This blocks briefly to maintain consistent frame timing
                self.clock.tick(self.gui_info.get('fps', 60))

                # Get all pending pygame events (mouse clicks, keyboard, window events, etc.)
                # This clears the event queue and returns a list of Event objects
                self.events = pygame.event.get()
                # Parse events into easily accessible attributes (quit, resize, ctrl_v, etc.)
                # EventHolder converts pygame events into named attributes for simplified checking
                self.event_holder = EventHolder(self.events)

                # Process main GUI events (quit, resize, ctrl_v toggle)
                # This handles application-level controls
                self.main_events()
                # Fill background with appropriate color based on current state
                # White for recording mode, grey for menu mode
                self.fill(state=self.state)
                
                # Draw grid if enabled (toggle with 'g')
                if self.show_grid:
                    self.draw_grid()

                # Handle IPA label and template events and rendering
                self.ipa_events()
    
                # Process audio and render formant points
                # This is the core visualization - captures audio, analyzes formants, plots points
                self.run_points(self.state, track_type=self.display_mode)
                
                # Swap display buffers to show everything drawn this frame
                # Double buffering prevents tearing/flicker
                pygame.display.flip()
        finally:
            # Always execute cleanup code, even if exception occurs
            # This ensures audio resources are properly released
            self.shutdown()

    def ipa_events(self):
        """
        Handle IPA label and template events and rendering.
        Draws IPA vowel labels, handles template overlay, and processes scroll wheel scaling.
        """
        # Draw IPA vowel labels - always show so menu works
        self.ipalabels.run_ipa_buttons(self.event_holder, self.state)

        # Check if user pressed Ctrl+T to toggle all green template vowels on/off
        if self.event_holder.ctrl_t:
            self.show_template = not self.show_template
            # Toggle clicked and visible state ONLY for vowels in the loaded template
            for image_num in self.ipalabels.template_image_nums:
                # Image numbers are 1-30, but button/textbox indices are 0-29
                idx = image_num - 1
                self.ipalabels.buttons[idx].clicked = self.show_template
                self.ipalabels.textboxes[idx].visible = self.show_template
            template_status = "toggled on" if self.show_template else "toggled off"
            logger.debug(f"Template vowels {template_status}")

        # Draw vowel template overlay if enabled in configuration
        # This shows a reference vowel chart that can be scaled/positioned
        if self.gui_info.get('show_vowel_template', False):
            # Update template position/scale based on scroll events and render
            self.voweltemplate.run_voweltemplate(self.event_holder, self.state)

        # Scroll wheel scales all IPA labels in formant space
        if self.event_holder.left_scroll_up is not None:
            if self.freq_scale == 'log':
                self.ipalabels.scale_formants_log(0.01)
            else:
                self.ipalabels.scale_formants(1.01)
        if self.event_holder.left_scroll_down is not None:
            if self.freq_scale == 'log':
                self.ipalabels.scale_formants_log(-0.01)
            else:
                self.ipalabels.scale_formants(0.99)
                    

    def run_points(self, state, track_type="single"):
        """
        Process audio, analyze formants, and render visualization points.

        This is the core method that captures audio each frame, performs formant
        analysis, applies smoothing, and renders the results to the screen.

        Args:
            state (str): Application state ('recording' or 'menu').
            track_type (str, optional): Display mode.
                - "single": Show only current point (default)
                - "track": Show connected trajectory
                - "all": Show all points permanently
        """
        # Reset frame tracking flag at start of each frame
        self.point_created_this_frame = False
        
        # Only process audio and display points when in recording state
        # Menu state skips this entirely (no audio processing)
        if state == "recording":
            # Initialize recording timestamp on first frame
            # This marks the start time for timestamped CSV export
            if self.recording_start_time is None:
                self.recording_start_time = time.time()
            
            # Get the latest audio analysis from the audio processor queue
            # This blocks briefly if no audio is available (up to 0.1s timeout)
            self.sound = self.audio_processor.get_sound()
            
            # Calculate precise elapsed time from number of recorded samples
            # Sample-based timing is more accurate than clock-based timing
            recorded_count = 0
            try:
                # Get total number of samples recorded so far
                recorded_count = self.audio_processor.get_recording_sample_count()
            except Exception:
                # If audio processor not ready, default to 0
                recorded_count = 0
            # Calculate analysis window size in samples
            # Window is chunk_ms * number_of_chunks
            window_ms = self.audio_config.get('chunk_ms', 5) * self.audio_config.get('number_of_chunks', 5)
            window_samples = int(round(
                self.audio_config['sample_rate'] * (window_ms / 1000)
            ))
            # Calculate elapsed recording time, adjusted for window center
            # Subtract half window to align timestamp with center of analysis window
            elapsed_time = max(
                0.0,  # Never negative
                (recorded_count - (window_samples / 2)) / self.audio_config['sample_rate']
            )
            
            # Apply smoothing filter to formant values
            # This checks stability and applies temporal filtering
            # Sets self.smoother.use to True if frame is stable and should be displayed
            self.smoother.smooth_formants(self.sound)

            # Check if track just became unstable (ended)
            # This happens when smoother.use transitions from True to False
            if self.last_smoother_use and not self.smoother.use:
                # Track just ended - finish it immediately
                # Only save tracks with at least 5 points (filters spurious noise bursts)
                # look into making this a parameter?
                if len(self.track.sprites()) >= 5:
                    # Turn all points blue to indicate track is finished
                    for pt in self.track.sprites():
                        pt.set_color((0, 100, 255))  # Blue color for finished tracks
                    # Add current track to finished tracks list
                    self.finished_tracks.append(self.track)
                    logger.info(f"Track {self.current_track_number} marked as finished ({len(self.track.sprites())} points)")
                # Always create new empty track (even if previous was discarded)
                self.track = pygame.sprite.Group()
            
            # Update state for next frame
            self.last_smoother_use = self.smoother.use

            # Only create/log points for stable, smoothed formant values
            # smoother.use is True when formants pass stability criteria
            if self.smoother.use:
                # Append formant data to export log with precise timestamp
                # This log is exported to CSV on shutdown
                self.formant_log.append({
                    'time_ms': int(elapsed_time * 1000),  # Time in milliseconds
                    'f0': self.sound.f0,  # Raw pitch from Sound object
                    'f1': self.smoother.plot_f1,  # Smoothed F1 (first formant)
                    'f2': self.smoother.plot_f2,  # Smoothed F2 (second formant)
                    'f3': self.sound.f3,  # Raw F3 (third formant, not smoothed)
                    'voicing': int(self.sound.voicing),  # 1 if voiced, 0 if unvoiced
                    'track_number': self.smoother.track_number,  # Track ID for grouping contiguous speech
                })
                
                # Convert formant frequencies (Hz) to screen pixel coordinates
                # Uses log-scale mapping with IPA-style orientation
                plot_x, plot_y = self.point_coordinates(
                    self.gui_info,  # Contains F1/F2 ranges and screen size
                    self.smoother.plot_f1,  # Smoothed F1 frequency
                    self.smoother.plot_f2  # Smoothed F2 frequency
                )
                # Create a new Point sprite at calculated screen position
                # Sprite contains the Sound object and visual representation (red circle)
                self.point = Point(self.sound, plot_x, plot_y)
                self.point_created_this_frame = True
                
                # Check if a new track has started (track number incremented by smoother)
                # This happens when transitioning from unstable to stable
                if self.smoother.track_number != self.current_track_number:
                    # Update our stored track number (track was already finished above when it became unstable)
                    self.current_track_number = self.smoother.track_number
                    logger.info(f"New track {self.current_track_number} started")
                
                # Add point to current track group (for connected trajectory visualization)
                self.track.add(self.point)
                # Add point to all_points group (permanent collection for export)
                # Track persists until a new stable track begins (when track_number changes)
                self.all_points.add(self.point)       

        # Render points based on track_type parameter
        # This happens in both recording and menu modes so tracks remain visible
        if track_type == "single":
            # Draw only the most recent point (current position)
            # In single mode, always keep point red (never blue)
            if self.point is not None:
                self.point.set_color((166, 33, 64))  # Red color for active point
                self.screen.blit(self.point.image, self.point.rect)
        elif track_type == "track":
            # Only draw when there are actual tracks to display
            # Draw all finished tracks (blue) first, in order
            if len(self.finished_tracks) > 0:
                for finished_track in self.finished_tracks:
                    if len(finished_track.sprites()) > 0:
                        finished_track.draw(self.screen)
            # Then draw current track (red) on top, ONLY if it's stable and smoother indicates good points
            # Require minimum 5 points to prevent flickering from single unstable points
            # This matches the threshold used for saving blue tracks
            if len(self.track.sprites()) >= 5 and self.smoother.use:
                self.track.draw(self.screen)
        elif track_type == "all":
            # Draw all points ever created (permanent dot visualization)
            if len(self.all_points.sprites()) > 0:
                self.all_points.draw(self.screen)

    def main_events(self):
        """
        Process GUI control events (quit, resize, state toggle, template toggle).

        Handles application-level events:
        - Window close button → quit application
        - Window resize → update layout and rescale IPA labels
        - Ctrl+V → toggle between recording and menu modes
        - Ctrl+T → toggle all template vowels on/off (does not affect menu or individual toggling)
        """
        # Handle base events (quit, grid/help toggle, RMS adjustment, backspace/delete)
        self.handle_base_events(self.event_holder)
        
        # Also support Ctrl+H for help overlay (consistent with LiveSpectrogram)
        if self.event_holder.ctrl_h:
            self.show_help = not self.show_help
            help_status = "shown" if self.show_help else "hidden"
            logger.debug(f"Help overlay {help_status}")

        # Check if user pressed L to toggle log/linear frequency scale
        if self.event_holder.l_key:
            self.freq_scale = 'linear' if self.freq_scale == 'log' else 'log'
            scale_status = "logarithmic" if self.freq_scale == 'log' else "linear"
            logger.info(f"Frequency scale toggled to {scale_status}")

        # Handle +/- keys to adjust minimum RMS threshold
        if self.event_holder.plus_equals:
            self.adjust_min_rms(+3)  # Increase minimum RMS threshold by 3 dB
        
        if self.event_holder.minus_underscore:
            self.adjust_min_rms(-3)  # Decrease minimum RMS threshold by 3 dB

        # Check if user resized the window (drag window edges)
        if self.event_holder.resize is not None:
            # Store old window size for calculating resize ratios
            old_size = self.gui_info['gui_size']
            # Get new window size from resize event
            new_size = self.event_holder.resize.size
            # Update IPA label positions to match new window proportions
            self.ipalabels.handle_resize(old_size[0], old_size[1], 
                                         new_size[0], new_size[1])
            # Update configuration with new window size
            self.gui_info['gui_size'] = new_size

        # Draw min RMS display if recently adjusted
        # Shows current minimum RMS threshold in top-right corner for 1 second
        self.draw_min_rms_display()

        # Draw help overlay if enabled (toggle with 'h')
        if self.show_help:
            self.draw_help_overlay()

        # Check if user pressed Ctrl+V (toggle between recording and menu)
        if self.event_holder.ctrl_v is not None:
            # Determine current state and take appropriate action
            if self.state == "menu":
                # Transitioning from menu → recording mode
                # Create new audio processor with current configuration
                self.audio_processor = AudioProcessor(
                    chunk_ms=self.audio_config.get('chunk_ms'),
                    number_of_chunks=self.audio_config.get('number_of_chunks'),
                    analysis_config=self.analysis_config,
                    input_device_index=self.input_device_index
                )
                # Start background audio capture thread
                self.audio_processor.start()
                # Begin buffering raw audio samples for WAV export
                self.audio_processor.start_recording()
                # Generate new session name with current timestamp
                self.session_name = exporter.create_session_name('speaker')
                # Reset recording start time (will be set on first frame)
                self.recording_start_time = None
                # Clear audio buffer for new recording
                self.audio_buffer = []
                # Clear formant log for new session
                self.formant_log = []
                # Note: Do NOT clear finished_tracks - let user manually clear with Delete
            else:
                # Transitioning from recording → menu mode
                # Turn any active track blue to indicate it's finished
                # Only save tracks with at least 5 points (filters spurious noise bursts)
                if len(self.track.sprites()) >= 5:
                    # Turn all points blue
                    for pt in self.track.sprites():
                        pt.set_color((0, 100, 255))  # Blue color for finished tracks
                    # Append current track to finished tracks list
                    self.finished_tracks.append(self.track)
                    # Create new empty track
                    self.track = pygame.sprite.Group()
                # Stop buffering raw audio samples
                self.audio_processor.stop_recording()
                # Retrieve recorded audio from processor and convert to list
                self.audio_buffer = self.audio_processor.get_recording().tolist()
                # Stop audio capture thread and release resources
                self.audio_processor.stop()
                
                # Export recording data if any was captured during this session
                if self.audio_buffer or self.formant_log:
                    # Log export start to console/log file
                    logger.info(f"Exporting session: {self.session_name}")
                    # Call save method to write WAV and CSV files
                    self.save(file_type='all')

            # Toggle state: "recording" ↔ "menu"
            self.state = "recording" if self.state == "menu" else "menu"

    def _handle_backspace(self):
        """Handle backspace key press - remove most recently finished track."""
        # Remove the most recently finished track
        if len(self.finished_tracks) > 0:
            removed_track = self.finished_tracks.pop()
            logger.info(f"Removed last track (had {len(removed_track.sprites())} points)")

    def _handle_delete(self):
        """Handle delete key press - clear all finished tracks."""
        # Clear all finished tracks
        self.finished_tracks = []
        logger.info("Cleared all tracks")


    def point_coordinates(self, gui_info, plot_f1, plot_f2):
        """Convert formant frequencies to screen coordinates using configured scale (log or linear).
        
        Maps F1/F2 frequencies to (x, y) pixel positions using logarithmic or linear scaling.
        Uses IPA vowel chart conventions:
        - F1 increases downward (higher F1 = lower tongue position)
        - F2 increases leftward (higher F2 = more front articulation)
        
        Args:
            gui_info (dict): Configuration containing:
                - 'f1_range': (min_hz, max_hz) tuple for F1 axis
                - 'f2_range': (min_hz, max_hz) tuple for F2 axis  
                - 'gui_size': (width, height) tuple in pixels
            plot_f1 (float): First formant frequency in Hz
            plot_f2 (float): Second formant frequency in Hz
            
        Returns:
            tuple: (x, y) screen coordinates in pixels
        """
        # Extract F1 axis range from configuration (e.g., 200-1100 Hz)
        f1_min, f1_max = gui_info['f1_range']
        # Extract F2 axis range from configuration (e.g., 500-2700 Hz)
        f2_min, f2_max = gui_info['f2_range']
        # Extract window dimensions in pixels
        gui_width, gui_height = gui_info['gui_size']

        # Prevent log(0) errors: clamp formant values to minimum of 1 Hz
        # Values ≤ 0 can occur when analysis fails or no voicing detected
        plot_f1 = max(plot_f1, 1)
        plot_f2 = max(plot_f2, 1)
        
        # Calculate position based on selected frequency scale
        if self.freq_scale == 'log':  # Logarithmic scaling
            # Calculate position in log-scale F2 range (horizontal axis)
            x_diff = numpy.log(plot_f2) - numpy.log(f2_min)
            # Calculate position in log-scale F1 range (vertical axis)
            y_diff = numpy.log(plot_f1) - numpy.log(f1_min)
            # Calculate total log-scale range for F2 (horizontal span)
            x_range = numpy.log(f2_max) - numpy.log(f2_min)
            # Calculate total log-scale range for F1 (vertical span)
            y_range = numpy.log(f1_max) - numpy.log(f1_min)
        else:  # Linear scaling
            # Calculate position in linear F2 range (horizontal axis)
            x_diff = plot_f2 - f2_min
            # Calculate position in linear F1 range (vertical axis)
            y_diff = plot_f1 - f1_min
            # Calculate total linear range for F2 (horizontal span)
            x_range = f2_max - f2_min
            # Calculate total linear range for F1 (vertical span)
            y_range = f1_max - f1_min

        # Convert to screen coordinates:
        # X: Right side minus proportion (high F2 appears on left, IPA convention)
        plot_x = gui_width - gui_width * (x_diff / x_range)
        # Y: Top is 0, multiply proportion by height (high F1 appears low on screen)
        plot_y = gui_height * (y_diff / y_range)

        # Return pixel coordinates as tuple
        return plot_x, plot_y

    def summarize(self):
        """Compile recorded data into summary arrays for analysis/export.
        
        Legacy method that packages sprite data into numpy arrays.
        Currently not used by save() method which has moved to timestamped CSV format.
        """
        # Get list of all Point sprites created during session
        points = self.all_points.sprites()
        # Package data into list of arrays:
        self.data = [
            # Array of f0 values from each point's Sound object
            numpy.array([sprite.sound.f0 for sprite in points]),
            # Array of track numbers (trajectory IDs from smoother)
            numpy.array(self.smoother.track),
            # Array of raw audio samples from each point's Sound object
            numpy.array([sprite.sound.samples for sprite in points]),
        ]

    def save(self, file_type="all"):
        """Save recorded data to disk in multiple formats.
        
        Exports audio and formant data to recordings/ directory with timestamped filenames.
        File types controlled by config.EXPORT_CONFIG settings.
        
        Args:
            file_type (str): Export mode. Currently only 'all' is used.
        """
        # Check if user wants all export formats (currently the only option)
        if file_type == 'all':
            # Check if saving recordings is enabled
            if not config.EXPORT_CONFIG.get('save_recordings', False):  # Check if saving is enabled (default: False)
                logger.info("Recording save is disabled - skipping export")  # Log that save is disabled
                return  # Exit without saving
            
            # Get export directory from configuration (default 'recordings')
            output_dir = config.EXPORT_CONFIG.get('output_dir', 'recordings')
            # Build base filename path: recordings/speaker_YYYY-MM-DD_HHMMSS
            base_path = os.path.join(output_dir, self.session_name)
            
            # Export WAV audio file if enabled and audio buffer has data
            # First conditional checks config setting for WAV export
            if config.EXPORT_CONFIG.get('save_wav', True):
                # Ensure audio buffer is populated (should be done in main_events)
                if not self.audio_buffer:
                    # Fallback: get recording from processor if buffer somehow empty
                    self.audio_buffer = self.audio_processor.get_recording().tolist()
            # Second conditional verifies both config setting and non-empty buffer
            if config.EXPORT_CONFIG.get('save_wav', True) and self.audio_buffer:
                # Construct WAV filename: speaker_YYYY-MM-DD_HHMMSS.wav
                wav_file = f"{base_path}.wav"
                # Call exporter utility to write 16-bit mono WAV file
                exporter.save_wav(wav_file, numpy.array(self.audio_buffer), 
                                self.audio_config['sample_rate'])
                # Log successful export to console/log file
                logger.info(f"Audio saved to {wav_file}")
            
            # Export timestamped CSV formant file if enabled and log has data
            # Check both config setting and non-empty formant log
            if config.EXPORT_CONFIG.get('save_csv', True) and self.formant_log:
                # Construct CSV filename: speaker_YYYY-MM-DD_HHMMSS_formants.csv
                csv_file = f"{base_path}_formants.csv"
                # Call exporter utility to write CSV with columns:
                # time_ms, f0, f1, f2, f3, voicing, track_number
                # Only includes voiced frames within configured f0 range
                exporter.save_formants_csv(csv_file, self.formant_log)
                # Log successful export to console/log file
                logger.info(f"Formants saved to {csv_file}")

    def fill(self, state):
        """Fill screen with solid background color based on application state.
        
        Args:
            state (str): Application state ('menu' or 'recording')
        """
        # Check current state and draw appropriate background
        if state == "menu":
            # Menu mode: Light grey background (RGB 200,200,200)
            # Visually distinct from recording to indicate paused state
            self.screen.fill((200, 200, 200))
        elif state == "recording":
            # Recording mode: White background (RGB 255,255,255)
            # Clean background for vowel space visualization
            self.screen.fill(config.COLORS['white'])

    def adjust_min_rms(self, delta_db):
        """Adjust the minimum RMS threshold and update display.
        
        Args:
            delta_db (float): Change in dB (positive to increase, negative to decrease).
        """
        if self.state != "recording" or not hasattr(self, 'audio_processor'):
            return  # Only adjust when recording
        
        # Get current value from analysis_config (default to -60 if not set)
        current_rms = self.analysis_config.get('min_rms_db', -60.0)
        # Calculate new value, clamped to reasonable range [-90, -10]
        new_rms = max(-90.0, min(-10.0, current_rms + delta_db))
        
        # Update config and audio processor
        self.analysis_config['min_rms_db'] = new_rms
        if hasattr(self.audio_processor, 'analysis_config'):
            self.audio_processor.analysis_config['min_rms_db'] = new_rms
        
        # Set display text and timestamp
        self.min_rms_display_text = f"Min RMS: {new_rms:.0f} dB"
        self.min_rms_display_until = pygame.time.get_ticks() + 1000  # Show for 1 second (milliseconds)
        
        # Log adjustment at debug level to avoid spam from frequent key presses
        logger.debug(f"Min RMS adjusted to {new_rms:.0f} dB")

    def draw_min_rms_display(self):
        """Draw minimum RMS threshold display when recently adjusted.
        
        Shows a temporary indicator in the top-left corner when the user adjusts
        the min RMS threshold with +/- keys. Display disappears after 1 second.
        Styling matches other temporary indicators like dynamic range/gain displays.
        """
        # Check if display time window is still active
        # min_rms_display_until is set to pygame.time.get_ticks() + 1000 when adjusted
        if hasattr(self, 'min_rms_display_until') and pygame.time.get_ticks() < self.min_rms_display_until:
            # Create font for text rendering (20 point Arial, matches other indicators)
            font = pygame.font.SysFont('Arial', 20)
            # Render text: white foreground, using stored display text from adjust_min_rms()
            display_text = font.render(self.min_rms_display_text, True, (255, 255, 255))
            # Get text rect and create slightly larger background rect
            # topleft at (10, 10) positions display in top-left corner
            text_rect = display_text.get_rect(topleft=(10, 10))
            # Inflate rect by 10 pixels horizontally, 6 pixels vertically for padding
            bg_rect = text_rect.inflate(10, 6)
            # Draw black background for text
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            # Draw gray border around background
            pygame.draw.rect(self.screen, (100, 100, 100), bg_rect, 1)
            # Blit text onto background
            self.screen.blit(display_text, (10, 10))

    def draw_grid(self):
        """Draw F1/F2 grid lines on the vowel space."""
        f1_range = self.gui_info.get('f1_range', (200, 1100))
        f2_range = self.gui_info.get('f2_range', (500, 2700))
        
        grid_color = (200, 200, 200)  # Light gray grid lines
        label_color = (120, 120, 120)  # Gray text for labels
        font = pygame.font.SysFont(None, 16)  # Small font for labels
        
        # Draw F1 grid lines (horizontal reference lines)
        f1_step = 100  # Hz per grid line
        f1_current = int(f1_range[0] / f1_step) * f1_step  # Start at first grid boundary
        while f1_current <= f1_range[1]:
            # Convert F1 frequency to screen position
            x, y = self.point_coordinates(self.gui_info, f1_current, (f2_range[0] + f2_range[1]) / 2)
            pygame.draw.line(self.screen, grid_color, (0, y), (self.gui_info['gui_size'][0], y), 1)
            # Draw F1 label
            label = font.render(f"F1:{int(f1_current)}", True, label_color)
            self.screen.blit(label, (5, y - 8))
            f1_current += f1_step
        
        # Draw F2 grid lines (vertical reference lines)
        f2_step = 200  # Hz per grid line
        f2_current = int(f2_range[0] / f2_step) * f2_step
        while f2_current <= f2_range[1]:
            # Convert F2 frequency to screen position
            x, y = self.point_coordinates(self.gui_info, (f1_range[0] + f1_range[1]) / 2, f2_current)
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, self.gui_info['gui_size'][1]), 1)
            # Draw F2 label
            label = font.render(f"{int(f2_current)}", True, label_color)
            label_rect = label.get_rect()
            label_rect.centerx = x
            label_rect.top = self.gui_info['gui_size'][1] - 20
            self.screen.blit(label, label_rect)
            f2_current += f2_step

    def draw_help_overlay(self):
        """Draw help overlay showing available controls."""
        # Semi-transparent overlay
        overlay_color = (30, 30, 30)
        overlay_alpha = 200
        overlay_surface = pygame.Surface(self.gui_info['gui_size'])
        overlay_surface.set_alpha(overlay_alpha)
        overlay_surface.fill(overlay_color)
        self.screen.blit(overlay_surface, (0, 0))
        
        # Help text
        font_big = pygame.font.SysFont(None, 32)
        font_normal = pygame.font.SysFont(None, 24)
        text_color = (255, 255, 255)
        
        help_text = [
            "=== LiveVowel Controls ===",
            "",
            "CTRL+V - Toggle recording/menu mode",
            "CTRL+T - Toggle template vowels on/off",
            "+/-    - Adjust minimum RMS threshold",
            "Backspace - Undo last track",
            "Delete - Clear all tracks",
            "G      - Toggle grid",
            "H or Ctrl+H - Toggle this help overlay",
        ]
        
        # Draw title
        title = font_big.render(help_text[0], True, text_color)
        title_rect = title.get_rect(center=(self.gui_info['gui_size'][0] // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw help lines
        y_pos = 120
        for line in help_text[2:]:
            if line:
                text_surf = font_normal.render(line, True, text_color)
                text_rect = text_surf.get_rect(left=100, top=y_pos)
                self.screen.blit(text_surf, text_rect)
            y_pos += 40
        
        # Footer text
        footer = font_normal.render("Press 'H' to close help", True, (200, 200, 200))
        footer_rect = footer.get_rect(center=(self.gui_info['gui_size'][0] // 2, self.gui_info['gui_size'][1] - 30))
        self.screen.blit(footer, footer_rect)

    def quit(self):
        """Signal the main loop to exit gracefully.
        
        Sets keep_running flag to False, which will cause the while loop
        in run() to terminate on its next iteration.
        """
        # Log quit request to console/log file
        logger.info("Quit requested")
        # Set flag that controls main loop - False will exit on next iteration
        self.keep_running = False

    def shutdown(self):
        """Clean up resources and export data on application exit.
        
        This is always called via the finally block in run(), ensuring proper
        cleanup even if an exception occurs. Stops audio processing, exports
        recordings, and closes Pygame.
        """
        # Turn any active track blue to indicate recording has ended
        if len(self.track.sprites()) > 0:  # Only save non-empty tracks
            finished_track = pygame.sprite.Group()  # Create new group for this finished track
            for pt in self.track.sprites():
                pt.set_color((0, 100, 255))  # Blue color for finished tracks
                finished_track.add(pt)  # Add to this finished track group
            # Append to list of finished tracks
            self.finished_tracks.append(finished_track)
        
        # Wrap entire cleanup in try/except to prevent shutdown errors from propagating
        try:
            # Nested try block for audio processor cleanup (may fail if already stopped)
            try:
                # Stop buffering raw audio samples
                self.audio_processor.stop_recording()
                # Retrieve any remaining audio from buffer if not already done
                if not self.audio_buffer:
                    # Get recorded samples and convert numpy array to Python list
                    self.audio_buffer = self.audio_processor.get_recording().tolist()
            except Exception:
                # Silently ignore audio processor errors (e.g., already stopped)
                # Using bare except to catch any possible error during cleanup
                pass
            # Stop audio capture thread and release PyAudio resources
            # Always call even if stop_recording failed
            self.audio_processor.stop()
            
            # Auto-export recordings if any data was captured
            # Check if either audio buffer or formant log has data
            if self.audio_buffer or self.formant_log:
                # Log export start to console/log file
                logger.info(f"Exporting session: {self.session_name}")
                # Call save method to write WAV and CSV files
                self.save(file_type='all')
            
            # Close Pygame and release graphics resources
            # This also closes the window
            pygame.quit()
            # Log successful shutdown to console/log file
            logger.info("LiveVowel shutdown complete")
        except Exception as e:
            # Log any errors that occur during shutdown
            # Uses exception object to include error details
            logger.error(f"Error during shutdown: {e}")
        finally:
            # Always reset session state, even if errors occurred
            # This ensures clean state if LiveVowel is restarted
            # Reset recording start timestamp
            self.recording_start_time = None
            # Clear audio buffer list
            self.audio_buffer = []
            # Clear formant log list
            self.formant_log = []
            # Generate new session name for next recording
            self.session_name = exporter.create_session_name('speaker')