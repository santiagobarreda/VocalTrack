# Import logging for debug/error messages
import logging
# Import os for file/directory operations
import os

# Import numpy for numerical array operations
import numpy
# Import pygame for graphics and GUI
import pygame

# Import required modules using relative imports
from .Smoother import Smoother
from .BaseAudioVisualizer import BaseAudioVisualizer, fit_to_desktop  # Base class for shared functionality
# Import required classes and modules
from .Sound import Sound
from .AudioProcessor import AudioProcessor
from .EventHolder import EventHolder
from .point import Point
from . import ipalabels
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
                 input_device_index=None,
                 input_device_name=None):
        """
        Initialize LiveVowel application and all audio/GUI components.

        Args:
            gui_config (dict, optional): GUI settings. Uses default if None.
            audio_config (dict, optional): Audio settings. Uses default if None.
            analysis_config (dict, optional): Analysis settings. Uses default if None.
            smoother_config (dict, optional): Smoother settings. Uses default if None.
            input_device_index (int, optional): Audio input device index. Uses default if None.
            input_device_name (str, optional): Audio input device name; takes priority over the index.
        """
        self.input_device_name = input_device_name
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

        # One analysis per display frame: the audio chunk (the analysis time step) is one frame long
        self.audio_config.setdefault('window_ms', config.AUDIO_CONFIG['window_ms'])
        self.audio_config['chunk_ms'] = config.chunk_ms_for_fps(self.gui_info.get('fps', 60))
        self.analysis_config['window_length'] = self.audio_config['window_ms'] / 1000.0
        self.analysis_config['time_step'] = self.audio_config['chunk_ms'] / 1000.0

        # Prepare config dict for base class initialization
        base_config = {
            'audio_config': self.audio_config,
            'analysis_config': self.analysis_config,
        }

        
        
        # Call parent class __init__ (initializes pygame, screen, clock, UI toggles)
        # Shrink the window (same aspect ratio) if it does not fit on this screen
        self.gui_info['gui_size'] = fit_to_desktop(*self.gui_info['gui_size'])
        gui_size = self.gui_info['gui_size']
        super().__init__(
            app_title="Live Vowel",
            config=base_config,
            gui_width=gui_size[0],
            gui_height=gui_size[1],
            input_device_index=input_device_index
        )
        self.target_fps = self.gui_info.get('fps', 60)

        # Create Sound object for formant analysis (will be reused for each frame)
        self.sound = Sound(**self.analysis_config)
        # Create smoother to filter noisy formant trajectories
        self.smoother = Smoother(**self.smoother_config, chunk_ms=self.audio_config.get('chunk_ms'))

        # Pygame sprite groups for rendering points on screen
        self.point = None  # Most recent point, None if no valid point exists
        self.track = pygame.sprite.Group()  # Current trajectory (connected points)
        self.finished_tracks = []  # List of completed track Groups (turned blue, ordered)
        self.all_points = pygame.sprite.Group()  # All points ever created (for export)

        # UI components for display
        data_dir = config.EXPORT_CONFIG.get('data_dir', '.')
        template_file = self.gui_info.get('template_file')
        if template_file in ('None', 'none', '', None):
            template_file = None

        template_path = None
        if template_file:
            if os.path.isabs(template_file) or os.path.exists(template_file):
                template_path = template_file
            elif data_dir and data_dir != '.':
                cand = os.path.join(data_dir, 'templates', template_file)
                if os.path.exists(cand):
                    template_path = cand
            else:
                cand = ipalabels.get_external_path(os.path.join('templates', template_file))
                if os.path.exists(cand):
                    template_path = cand
        elif self.gui_info.get('template_file') not in ('None', 'none'):
            template_path = ipalabels.find_template_file()

        self.ipalabels = ipalabels.IPALabels(self.screen, template_path=template_path, gui_info=self.gui_info)  # IPA vowel labels overlaid on plot

        # Application state: "idle" = IPA picker hidden, "menu" = IPA picker visible
        self.state = "idle"  # Start with IPA picker hidden
        # Flag controlling audio capture. Starts paused with the help overlay shown (like LivePitch);
        # Space, or closing help with Ctrl/Cmd+?, starts recording. The AudioProcessor is created
        # by _start_recording_session().
        self.recording_active = False
        self.audio_processor = None
        # Flag to toggle green template IPA symbols (from template) on/off (Ctrl+T)
        # When True, all template vowels are shown; when False, they are hidden (but can be toggled individually in menu)
        self.show_template = self.gui_info.get('show_vowel_template', False)
        self.keep_running = True  # Set to False to exit application
        # Display mode for visualization ("single", "track", or "all")
        self.display_mode = self.gui_info.get('display_mode', 'single')
        # Frequency scale for axis display ("log" or "linear")
        self.freq_scale = self.gui_info.get('freq_scale', 'log')
        # Track the current track number from smoother to detect when new tracks begin
        self.current_track_number = 0  # Matches smoother's initial track_number

        # Initialize default fonts to avoid recreating them on every frame (heavy OS lookup)
        self.font_20 = pygame.font.SysFont('Arial', 20)
        self.font_16 = pygame.font.SysFont(None, 16)
        self.font_32 = pygame.font.SysFont(None, 32)
        self.badge_font = self.font_16
        # Recording session tracking for file export (named when a recording starts)
        self.session_name = None
        self.original_audio_buffer = []  # Device-rate audio samples for WAV export
        self.downsampled_audio_buffer = []  # Analysis-rate audio samples for WAV export
        self.original_recording_sample_rate = self.audio_config.get('sample_rate', 10000)
        self.downsampled_recording_sample_rate = self.audio_config.get('sample_rate', 10000)
        self.formant_log = []  # Timestamped formant data for CSV export
        
        
         # Cache for grid rendering
        self.grid_surface = None

        # Start the main event loop (blocking call)
        self.run()

    def run(self):
        """
        Run the main event loop for the LiveVowel GUI.
        Handles event polling, audio capture, GUI updates, and rendering.
        """
        # Audio capture is off by default; user starts it explicitly with Space.
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
                # Fill background (white)
                self.fill()
                
                # Draw grid if enabled (toggle with Ctrl/Cmd+G)
                if self.show_grid:
                    if self.grid_surface is None:
                        self.create_grid_surface()
                    self.screen.blit(self.grid_surface, (0, 0))
    
                # Process queued sounds into formant points and tracks, then draw them
                self.process_sounds()
                self.draw_points(self.display_mode)

                # Handle IPA label and template events and rendering
                self.ipa_events()

                # Inspection card (Shift+Click while paused or in the picker)
                self.draw_inspect_overlay()

                # Draw overlays after main content so they are visible.
                self.draw_min_rms_display()
                self.draw_notification()
                if self.show_help:
                    self.draw_help_overlay()
                self.draw_status_indicators()
                self.draw_performance_overlay()
                
                # Swap display buffers to show everything drawn this frame
                # Double buffering prevents tearing/flicker
                pygame.display.flip()
        finally:
            # Always execute cleanup code, even if exception occurs
            # This ensures audio resources are properly released
            self.shutdown()

    def inspect_lines(self, x, y):
        """Inspection card: F1/F2 at the probe, and the values of the nearest plotted point."""
        f1_val, f2_val = self.xy_to_formants(x, y)
        lines = [
            ("F1 (Height)", f"{int(round(f1_val))} Hz", (255, 120, 120)),
            ("F2 (Backness)", f"{int(round(f2_val))} Hz", (100, 180, 255)),
        ]

        # Search for nearest recorded point within 25px
        near_pt = None
        min_dist = 25.0
        all_sprites = list(self.all_points.sprites())
        for tr in self.finished_tracks:
            all_sprites.extend(tr.sprites())
        all_sprites.extend(self.track.sprites())
        for pt in all_sprites:
            dist = ((pt.rect.centerx - x)**2 + (pt.rect.centery - y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                near_pt = pt

        if near_pt:
            pt_f0 = getattr(near_pt, 'raw_f0', None)
            if pt_f0 and pt_f0 > 10.0:
                lines.append(("Recorded f0", f"{pt_f0:.1f} Hz", (120, 255, 140)))
            if hasattr(near_pt, 'f1') and hasattr(near_pt, 'f2') and near_pt.f1 and near_pt.f2:
                lines.append(("Track Formants", f"F1: {int(round(near_pt.f1))} / F2: {int(round(near_pt.f2))} Hz", (255, 230, 100)))
        return lines

    def ipa_events(self):
        """
        Handle IPA label and template events and rendering.
        Draws IPA vowel labels, handles template overlay, and processes scroll wheel scaling.
        """
        # Draw IPA vowel labels; map picker visibility to the string the API expects.
        ipa_state = "menu" if self.state == "menu" else "recording"
        self.ipalabels.run_ipa_buttons(self.event_holder, ipa_state)

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
            self.show_notification(
                "Template vowels: ON" if self.show_template else "Template vowels: OFF",
                duration_ms=1200,
                bg_color=(220, 240, 255),
                border_color=(0, 100, 200)
            )

        # Save the currently toggled green template labels + their positions to a new timestamped template.
        if self.event_holder.ctrl_s:
            self._save_template()

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
                    

    def _save_template(self):
        """Ctrl/Cmd+S: save the shown green labels to a new timestamped template and make it active
        (for this session and, through the settings file, for later launches)."""
        success, output_path, saved_count = self.ipalabels.save_current_template()
        if success:
            logger.info(f"Saved IPA template ({saved_count} labels) to {output_path}")
            new_fname = os.path.basename(output_path)
            self.gui_info['template_file'] = new_fname
            config.LIVEVOWEL_CONFIG['template_file'] = new_fname

            # Persist new template choice to settings manager so it remains active
            try:
                from VocalTrack import settings_manager
                mgr = settings_manager.get_settings_manager()
                mgr.set_nested('plotting', 'template_file', new_fname)
                mgr.save()
            except Exception as e:
                logger.warning(f"Could not persist active template to settings: {e}")

            self.show_notification(
                f"Template saved & active: {new_fname} ({saved_count} vowels)",
                duration_ms=2500,
                bg_color=(200, 255, 200),
                border_color=(0, 150, 0)
            )
        else:
            logger.error(f"Failed to save IPA template to {output_path}")
            self.show_notification(
                "Failed to save template",
                duration_ms=2000,
                bg_color=(255, 200, 200),
                border_color=(200, 0, 0)
            )

    def process_sounds(self):
        """
        Process the analyzed sounds waiting in the queue (while recording): smooth the formants,
        log stable frames for the CSV, create points, and manage tracks.

        Visual Color Conventions:
            - Red dots ((166, 33, 64)): Active live tracking of the current vocalization.
            - Blue dots ((0, 100, 255)): Finalized tracks from previous vocalizations
              (saved to `self.finished_tracks` when phonation ceases).
        """
        # Only process audio when recording is explicitly active (independent of picker).
        if self.recording_active:
            # Take all available analyzed sounds to keep processing in sync with capture
            sounds_to_process = self.take_analyzed_sounds()

            if sounds_to_process:
                for sound in sounds_to_process:
                    self.sound = sound

                    # Time of the analysis window center relative to the start of the recording (WAV),
                    # stamped in the capture thread by AudioProcessor
                    elapsed_time = sound.recording_time if sound.recording_time is not None else 0.0

                    # Apply smoothing filter to formant values
                    # This checks stability and applies temporal filtering
                    # Sets self.smoother.use to True if frame is stable and should be displayed
                    self.smoother.smooth_formants(self.sound)

                    # Finish the visual track when the smoother ends the track (skip tolerance exceeded),
                    # so on-screen tracks match the track_number written to the CSV
                    if self.smoother.track_ended and len(self.track.sprites()) > 0:
                        self._finish_current_track()

                    # Only create/log points for stable, smoothed formant values
                    # smoother.use is True when formants pass stability criteria
                    if self.smoother.use:
                        # Append formant data to export log with precise timestamp
                        # This log is exported to CSV on shutdown
                        self.formant_log.append({
                            'time_ms': int(elapsed_time * 1000),  # Time in milliseconds
                            'f0': self.sound.f0,  # Raw pitch from Sound object
                            'f1': self.sound.f1,  # Raw F1 (first formant, unsmoothed)
                            'f1_smoothed': self.smoother.plot_f1,  # Smoothed F1 (first formant)
                            'f2': self.sound.f2,  # Raw F2 (second formant, unsmoothed)
                            'f2_smoothed': self.smoother.plot_f2,  # Smoothed F2 (second formant)
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
                        # The sprite is the visual representation (red circle). It keeps the raw f0 and
                        # where the frame is in the saved recording, not the audio itself
                        self.point = Point(
                            plot_x,
                            plot_y,
                            f1=self.smoother.plot_f1,
                            f2=self.smoother.plot_f2,
                            raw_f0=self.sound.f0,
                            recording_time=self.sound.recording_time,
                            recording_name=self.session_name
                        )
                        
                        # Check if a new track has started (track number incremented by smoother)
                        # This happens when transitioning from unstable to stable
                        if self.smoother.track_number != self.current_track_number:
                            # Normally already finished when the smoother ended it; this is a safety net
                            if len(self.track.sprites()) > 0:
                                self._finish_current_track()
                            self.current_track_number = self.smoother.track_number
                            logger.info(f"New track {self.current_track_number} started")
                        
                        # Add point to current track group (for connected trajectory visualization)
                        self.track.add(self.point)
                        # Add point to all_points group (permanent collection for export)
                        # Track persists until a new stable track begins (when track_number changes)
                        self.all_points.add(self.point)

            # The audio device dropped out: the recording ended there (frames analyzed before the
            # dropout were processed above), so save it and pause
            if self.check_recording_interrupted() is not None:
                self._stop_recording_session()

    def draw_points(self, track_type="single"):
        """
        Draw the formant points (in recording and picker modes, so tracks stay visible).

        Args:
            track_type (str, optional): Display mode.
                - "single": Show only the active instantaneous point (red).
                - "track": Show active vocalization (red) plus finalized historical tracks (blue).
                - "all": Show all recorded points permanently.
        """
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
            # Then draw current track (red) on top. It stays visible through brief glitches within
            # the smoother's skip tolerance, and is turned blue when the smoother ends the track.
            # Require minimum 5 points, matching the threshold used for saving blue tracks
            if len(self.track.sprites()) >= 5:
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
        
        # Handle Ctrl+? recording pause/resume (help overlay toggle is handled by base class)
        if self.event_holder.ctrl_h:
            # show_help has already been toggled by handle_base_events()
            if self.show_help:
                if self.recording_active:
                    self._stop_recording_session()
            else:
                if not self.recording_active:
                    self._start_recording_session()

        # Check if user pressed Ctrl+L to toggle log/linear frequency scale
        if self.event_holder.ctrl_l:
            self.freq_scale = 'linear' if self.freq_scale == 'log' else 'log'
            self.gui_info['freq_scale'] = self.freq_scale
            scale_status = "logarithmic" if self.freq_scale == 'log' else "linear"
            logger.info(f"Frequency scale toggled to {scale_status}")
            
            # Recalculate coordinates for all existing points
            self._reposition_points()

            # Recalculate coordinates for all IPA labels
            for textbox in self.ipalabels.textboxes:
                if textbox.f1 is not None and textbox.f2 is not None:
                    textbox.rect.center = self.ipalabels._hz_to_pixels(textbox.f1, textbox.f2)
            # Recreate cached grid surface on scale toggle
            self.grid_surface = None
        # Handles +/- keys to adjust minimum RMS threshold
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
            # Move existing points so they stay at their F1/F2 positions
            self._reposition_points()
            # Recreate cached grid surface on resize
            self.grid_surface = None

        # Ctrl+V toggles the IPA vowel picker on/off.
        # Opening the picker also stops any active recording as a side-effect.
        if self.event_holder.ctrl_v is not None:
            if self.state == "idle":
                # Opening picker: stop recording if currently active
                if self.recording_active:
                    self._stop_recording_session()
                self.state = "menu"
            else:
                # Closing picker: resume recording
                self.state = "idle"
                if not self.recording_active:
                    self._start_recording_session()

        # Space (when not in the vowel picker) toggles recording on/off
        self.handle_space_toggle(self.event_holder)

        # Shift + click inspection probe (only when recording is paused or in the picker)
        self.update_inspect_probe(self.event_holder)

    def toggle_recording(self):
        """Space: start a new recording session, or stop (and save) the current one. Ignored while
        the vowel picker is open."""
        if self.state == "menu":
            return
        if not self.recording_active:
            self.inspect_pos = None
            self._start_recording_session()
        else:
            self._stop_recording_session()

    def is_frozen(self):
        """The display can be probed (Shift + click) while recording is paused or the picker is open."""
        return not self.recording_active or self.state == "menu"

    def _handle_backspace(self):
        """Backspace: remove the most recently finished track (from the "track" and "all" displays)."""
        if len(self.finished_tracks) > 0:
            removed_track = self.finished_tracks.pop()
            self.all_points.remove(*removed_track.sprites())
            logger.info(f"Removed last track (had {len(removed_track.sprites())} points)")

    def _handle_delete(self):
        """Delete: clear all finished tracks, and every point except the active track's (the "all" display)."""
        self.finished_tracks = []
        active = set(self.track.sprites())
        self.all_points.remove(*[pt for pt in self.all_points.sprites() if pt not in active])
        logger.info("Cleared all tracks")

    def _reposition_points(self):
        """Recompute screen positions of all plotted points from their F1/F2 (after resize or scale change)."""
        for pt in self.all_points:
            if getattr(pt, 'f1', None) is not None and getattr(pt, 'f2', None) is not None:
                pt.rect.center = self.point_coordinates(self.gui_info, pt.f1, pt.f2)

    def _finish_current_track(self):
        """Turn the active track blue, keep it if it has at least 5 points, then start a new empty track."""
        # Its points are no longer active, so they turn blue (as seen in the "all" display)
        for pt in self.track.sprites():
            pt.set_color((0, 100, 255))  # Blue color for finished tracks
        # Only save tracks with at least 5 points (filters spurious noise bursts)
        if len(self.track.sprites()) >= 5:
            self.finished_tracks.append(self.track)
            logger.info(f"Track {self.current_track_number} marked as finished ({len(self.track.sprites())} points)")
        self.track = pygame.sprite.Group()

    def _start_recording_session(self):
        """Create a fresh audio processor, start capture, and mark recording active."""
        self.audio_processor = AudioProcessor(
            chunk_ms=self.audio_config.get('chunk_ms'),
            window_ms=self.audio_config.get('window_ms'),
            analysis_config=self.analysis_config,
            min_rms_db=self.analysis_config.get('min_rms_db'),
            input_device_index=self.input_device_index,
            input_device_name=self.input_device_name
        )
        self.audio_processor.start()
        self.audio_processor.start_recording(
            record_original=bool(config.EXPORT_CONFIG.get('save_original_audio', True)),
            record_downsampled=bool(config.EXPORT_CONFIG.get('save_downsampled_audio', False))
        )
        self.original_recording_sample_rate = self.audio_processor.get_original_recording_sample_rate()
        self.downsampled_recording_sample_rate = self.audio_processor.get_downsampled_recording_sample_rate()
        self.session_name = self.new_recording_name()
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.formant_log = []
        self.recording_active = True
        self.alert_text = None
        logger.info("Recording session started")
        self.notify_recording(True)

    def _stop_recording_session(self):
        """Stop audio capture, finalise active track, export data, mark recording inactive."""
        if not self.recording_active:
            return
        # Finalise any active track
        self._finish_current_track()
        # Stop the audio processor and collect what it recorded
        self._collect_recording()
        if self.audio_processor is not None:
            self.audio_processor.stop()
        self.recording_active = False
        # Export if data was captured, then clear the buffers so closing the window doesn't save them again
        if self.original_audio_buffer or self.downsampled_audio_buffer or self.formant_log:
            logger.info(f"Exporting session: {self.session_name}")
            self.save(file_type='all')
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        self.formant_log = []
        logger.info("Recording session stopped")
        self.notify_recording(False)

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
        # Extract F1 axis range from configuration (e.g., 200-1200 Hz)
        f1_min, f1_max = gui_info['f1_range']
        # Extract F2 axis range from configuration (e.g., 500-3000 Hz)
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

    def xy_to_formants(self, x, y):
        """Convert screen pixel coordinates (x, y) to F1 and F2 formant frequencies (Hz)."""
        gui_width, gui_height = self.gui_info['gui_size']
        f1_min, f1_max = self.gui_info['f1_range']
        f2_min, f2_max = self.gui_info['f2_range']
        
        x_prop = max(0.0, min(1.0, 1.0 - (float(x) / max(1.0, float(gui_width)))))
        y_prop = max(0.0, min(1.0, float(y) / max(1.0, float(gui_height))))
        
        if self.freq_scale == 'log':
            log_f1_min = numpy.log(max(f1_min, 1.0))
            log_f1_max = numpy.log(f1_max)
            log_f2_min = numpy.log(max(f2_min, 1.0))
            log_f2_max = numpy.log(f2_max)
            f1 = float(numpy.exp(log_f1_min + y_prop * (log_f1_max - log_f1_min)))
            f2 = float(numpy.exp(log_f2_min + x_prop * (log_f2_max - log_f2_min)))
        else:
            f1 = float(f1_min + y_prop * (f1_max - f1_min))
            f2 = float(f2_min + x_prop * (f2_max - f2_min))
        return f1, f2

    def save(self, file_type="all"):
        """Save recorded data to disk in multiple formats.
        
        Exports audio and formant data to recordings/ directory with timestamped filenames.
        File types controlled by config.EXPORT_CONFIG settings independently.
        
        Args:
            file_type (str): Export mode. Currently only 'all' is used.
        """
        if file_type == 'all':
            # Audio files: <data_dir>/recordings/speaker_YYYY-MM-DD_HHMMSS_vowel_original.wav etc.
            self.save_audio_files('vowel')
            base_path = self.output_base_path()

            # Export timestamped CSV formant file if enabled and log has data
            if config.EXPORT_CONFIG.get('save_csv', True) and self.formant_log:
                csv_file = f"{base_path}_formants.csv"
                exporter.save_formants_csv(csv_file, self.formant_log)
                logger.info(f"Formants saved to {csv_file}")

    def status_badges(self):
        """[REC] while recording, [PAUSED] otherwise, and [PICKER] while the vowel picker is open."""
        badges = [("[REC]", (255, 80, 80))] if self.recording_active else [("[PAUSED]", (255, 210, 80))]
        if self.state == "menu":
            badges.append(("[PICKER]", (120, 180, 255)))
        return badges

    def fill(self):
        """Fill screen background with white."""
        self.screen.fill(config.COLORS['white'])

    def create_grid_surface(self):
        """Create a cached background surface containing the grid lines and F1/F2 labels."""
        gui_width, gui_height = self.gui_info['gui_size']
        self.grid_surface = pygame.Surface((gui_width, gui_height), pygame.SRCALPHA)
        self.grid_surface.fill((0, 0, 0, 0))
        
        f1_range = self.gui_info.get('f1_range', (200, 1200))
        f2_range = self.gui_info.get('f2_range', (500, 3000))
        
        grid_color = (200, 200, 200)  # Light gray grid lines
        label_color = (120, 120, 120)  # Gray text for labels
        font = self.font_16  # Use cached small font for labels
        
        # Draw F1 grid lines (horizontal reference lines)
        f1_step = 100  # Hz per grid line
        f1_current = int(f1_range[0] / f1_step) * f1_step  # Start at first grid boundary
        while f1_current <= f1_range[1]:
            # Convert F1 frequency to screen position
            x, y = self.point_coordinates(self.gui_info, f1_current, (f2_range[0] + f2_range[1]) / 2)
            pygame.draw.line(self.grid_surface, grid_color, (0, y), (gui_width, y), 1)
            # Draw F1 label
            label = font.render(f"F1:{int(f1_current)}", True, label_color)
            self.grid_surface.blit(label, (5, y - 8))
            f1_current += f1_step
        
        # Draw F2 grid lines (vertical reference lines)
        f2_step = 200  # Hz per grid line
        f2_current = int(f2_range[0] / f2_step) * f2_step
        while f2_current <= f2_range[1]:
            # Convert F2 frequency to screen position
            x, y = self.point_coordinates(self.gui_info, (f1_range[0] + f1_range[1]) / 2, f2_current)
            pygame.draw.line(self.grid_surface, grid_color, (x, 0), (x, gui_height), 1)
            # Draw F2 label
            label = font.render(f"{int(f2_current)}", True, label_color)
            label_rect = label.get_rect()
            label_rect.centerx = x
            label_rect.top = gui_height - 20
            self.grid_surface.blit(label, label_rect)
            f2_current += f2_step
            
        # Convert surface to match screen pixel format for optimized CPU blitting
        self.grid_surface = self.grid_surface.convert_alpha()

    def draw_help_overlay(self):
        """Draw help overlay showing available controls and visual color conventions."""
        legend_items = [
            ("Active Vocalization (Current):", (255, 100, 100), "Red dots = real-time formant tracking of ongoing speech"),
            ("Finalized Tracks (Previous):", (100, 180, 255), "Blue dots = completed tracks preserved from prior vocalizations"),
            ("IPA Reference Markers:", (120, 240, 120), "Green labels = reference targets from active JSON template")
        ]
        help_controls = [
            "Space             - Start / pause real-time recording",
            "Shift + Left click - Probe Formants (F1, F2) & Pitch (f0) (while paused)",
            "Ctrl/Cmd+V        - Open / close IPA vowel symbol picker (click symbols to show / hide)",
            "Ctrl/Cmd+T        - Toggle reference vowel template overlay",
            "Left click + drag - Move an IPA / template vowel label",
            "Mouse wheel       - Scale all IPA / template labels up or down (~1% per step)",
            "Ctrl/Cmd+S        - Save labels to new timestamped template & activate",
            "+ / -             - Adjust minimum RMS speech threshold",
            "Backspace         - Undo last finalized track (track / all modes)",
            "Delete            - Clear all finalized tracks (track / all modes)",
            "Ctrl/Cmd+G / +L   - Toggle grid overlay / Log-linear frequency scale",
            "Ctrl/Cmd+P        - Toggle performance monitor overlay",
            "ESC               - Exit application and export session data",
        ]
        self.draw_help_panel("LiveVowel Controls & Color Guide", legend_items, help_controls,
                             font_big=self.font_32, font_normal=self.font_20, font_bold=self.font_20,
                             size=self.gui_info['gui_size'])

    def shutdown(self):
        """Clean up resources and export data on application exit.
        
        This is always called via the finally block in run(), ensuring proper
        cleanup even if an exception occurs. Stops audio processing, exports
        recordings, and closes Pygame.
        """
        # Wrap entire cleanup in try/except to prevent shutdown errors from propagating
        try:
            # Stop any active recording and retrieve remaining audio
            try:
                if self.recording_active:
                    self._collect_recording()
            except Exception:
                pass
            # Stop the processor thread regardless of recording state
            if self.audio_processor is not None:
                self.audio_processor.stop()

            # Export any remaining captured data
            if self.original_audio_buffer or self.downsampled_audio_buffer or self.formant_log:
                logger.info(f"Exporting session: {self.session_name}")
                self.save(file_type='all')

            # Save current settings (like window size, freq scale, min_rms_db) back to manager
            try:
                from . import settings_manager
                mgr = settings_manager.get_settings_manager()
                
                # Save plotting settings
                saved_plotting = mgr.get('plotting', {})
                saved_plotting['freq_scale'] = self.freq_scale
                saved_plotting['gui_size'] = list(self.gui_info.get('gui_size', [self.screen.get_width(), self.screen.get_height()]))
                mgr.set('plotting', saved_plotting)
                
                # Save analysis settings
                saved_analysis = mgr.get('analysis', {})
                saved_analysis['min_rms_db'] = self.analysis_config.get('min_rms_db', -60.0)
                mgr.set('analysis', saved_analysis)
                
                mgr.save()
                logger.info("LiveVowel settings saved successfully")
            except Exception as save_err:
                logger.error(f"Error saving LiveVowel settings: {save_err}")

            pygame.quit()
            logger.info("LiveVowel shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")