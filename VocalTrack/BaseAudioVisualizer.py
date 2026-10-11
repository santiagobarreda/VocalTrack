"""Base class for real-time audio visualization applications.

Provides common functionality for LivePitch, LiveVowel, and future audio visualizers.
Encapsulates shared UI controls, event handling, and configuration management.
"""

# Bring in the logging tool to track background events and errors
import logging
import os
# Bring in queue to read the analyzed sounds waiting for the display
import queue
# Bring in Pygame, the graphics engine that draws the windows and shapes
import pygame
# Export settings (folders, which files to save) and the WAV/CSV writers
from . import config as vt_config
from . import exporter

# Create a logger specifically for this file
logger = logging.getLogger(__name__)


def _prepare_sdl():
    """On modern Linux (Wayland), Pygame window resizing is often broken; the X11 backend fixes it.
    Must run before Pygame's display is initialized."""
    import platform
    if platform.system() == "Linux":
        os.environ["SDL_VIDEODRIVER"] = "x11"


def fit_to_desktop(width, height, max_width_frac=0.95, max_height_frac=0.9):
    """Scale a window size down, keeping its aspect ratio, if it does not fit on the screen.

    Sizes that fit are returned unchanged, so defaults and sizes the user chose are kept on
    screens large enough for them. The screen size comes from Pygame, in the same pixel units
    as the window it opens (so display scaling on high-DPI screens is handled consistently).
    The height limit leaves room for the title bar and taskbar.

    Returns:
        tuple: (width, height) in pixels.
    """
    _prepare_sdl()
    try:
        pygame.display.init()
        desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return int(width), int(height)
    scale = min(1.0, desktop_w * max_width_frac / width, desktop_h * max_height_frac / height)
    if scale < 1.0:
        logger.info(f"Window {width:.0f}x{height:.0f} does not fit the {desktop_w}x{desktop_h} screen; "
                    f"using {width * scale:.0f}x{height * scale:.0f}")
    return int(round(width * scale)), int(round(height * scale))


class BaseAudioVisualizer:
    """The master blueprint for all audio visualizer windows.
    
    Instead of writing the code to create a window, handle the ESC key, or draw
    the volume popup for every single tool, we write it once here. All the specific 
    tools (like LivePitch or LiveVowel) will inherit these abilities automatically.
    """
    
    def __init__(self, app_title="Audio Visualizer", config=None, 
                 gui_width=800, gui_height=600, input_device_index=None):
        """Sets up the blank canvas, the clock, and the basic memory slots.
        
        Args:
            app_title (str): The text that appears at the top of the window.
            config (dict): A folder of settings to guide the math and audio.
            gui_width (int): Starting window width in pixels.
            gui_height (int): Starting window height in pixels.
            input_device_index (int): The secret ID number of the chosen microphone.
        """
        # Save the settings folder, or create a blank one if none was provided
        self.config = config or {}
        # Remember which microphone to use
        self.input_device_index = input_device_index
        
        # Force the X11 backend on Linux (see _prepare_sdl)
        _prepare_sdl()

        # Turn on the Pygame graphics engine
        pygame.init()
        
        # --- THE RESIZE FIX ---
        # Create the blank canvas of the requested size, and explicitly tell Pygame
        # to allow the user to drag the edges to resize it!
        self.screen = pygame.display.set_mode((gui_width, gui_height), pygame.RESIZABLE)
        
        # Put the title text at the very top of the window frame
        pygame.display.set_caption(app_title)
        # Create a metronome (clock) to control how fast the graphics draw
        self.clock = pygame.time.Clock()
        
        # Remember the starting dimensions of the window
        self.gui_width = gui_width
        self.gui_height = gui_height
        
        # Create empty memory slots to hold keyboard and mouse clicks
        self.event_holder = None
        self.events = []
        # Create a switch to keep the program running. If flipped to False, the app closes.
        self.keep_running = True
        
        # Create switches for universal visual settings (Grid, Help, and Performance menu)
        self.show_grid = True
        self.show_help = True
        self.show_performance = False
        self.target_fps = 60
        # Look in the settings to see if the user wants Logarithmic or Linear spacing
        self.freq_scale = self.config.get('freq_scale', 'log')
        
        # Memory slots for the temporary popup that shows the volume threshold
        self.min_rms_display_text = None
        self.min_rms_display_until = 0.0
        
        # Pull out the specific folders for audio settings and math analysis settings
        self.audio_config = config.get('audio_config', {})
        self.analysis_config = config.get('analysis_config', {})
        
        # Create empty slots for the background microphone listener tool
        self.audio_processor = None
        # Start with the recording switch turned off
        self.recording = False
        # Timestamped name shared by every recording made from this window (its opening time),
        # and how many recordings have been named so far
        self.window_name = exporter.create_session_name('speaker')
        self.recording_count = 0

        # Log that the base setup was successful
        logger.debug(f"BaseAudioVisualizer initialized: {app_title}")

        # Memory slots for on-screen notification banners (e.g., audio device warnings)
        self.notification_text = None
        self.notification_until = 0.0
        self.notification_bg_color = (255, 235, 150)
        self.notification_border_color = (200, 150, 0)
        # Banner that stays on screen until cleared (e.g. recording stopped by a device disconnect)
        self.alert_text = None

        # Inspection / probe overlay state (activated by Shift + click when display is frozen/paused)
        self.inspect_pos = None

        # Initialize default fonts to avoid recreating them on every frame (heavy OS lookup)
        self.default_font_28 = pygame.font.SysFont(None, 28)
        self.default_font_24 = pygame.font.SysFont(None, 24)
        self.default_font_18 = pygame.font.SysFont(None, 18)

        # Font and padding of the status badges ([REC], [PAUSED], ...) in the top-right corner;
        # visualizers may change them
        self.badge_font = self.default_font_18
        self.badge_padding = (8, 4)

    def handle_base_events(self, event_holder):
        """Translates keyboard presses that do the exact same thing in every visualizer.
        
        Args:
            event_holder: The tool containing the current keyboard/mouse actions.
            
        Returns:
            bool: False if the user asked to quit, True if the program should keep going.
        """
        # If the user presses Ctrl+G...
        if event_holder.ctrl_g:
            # Flip the grid switch (turn it on if it's off, or off if it's on)
            self.show_grid = not self.show_grid
            # Log the change
            grid_status = "ON" if self.show_grid else "OFF"
            logger.debug(f"Grid toggled {grid_status}")
        
        # If the user presses Ctrl+?...
        if event_holder.ctrl_h:
            # Flip the help menu switch
            self.show_help = not self.show_help
            # Log the change
            help_status = "shown" if self.show_help else "hidden"
            logger.debug(f"Help overlay {help_status}")
        
        # If the user presses Ctrl+P...
        if event_holder.ctrl_p:
            self.show_performance = not self.show_performance
            perf_status = "ON" if self.show_performance else "OFF"
            logger.debug(f"Performance overlay toggled {perf_status}")
        
        # Backspace: the specific undo action for this visualizer (one key-down event per press)
        if event_holder.backspace:
            self._handle_backspace()

        # Delete: the specific clear-all action for this visualizer
        if event_holder.delete:
            self._handle_delete()

        # If the user hits ESC on the keyboard or clicks the red X on the window...
        if event_holder.escape or event_holder.quit:
            # Run the shutdown sequence
            self.quit()
            # Return False to tell the main loop to stop spinning
            return False
        
        # If we didn't quit, return True so the main loop keeps running
        return True

    def _handle_backspace(self):
        """A blank placeholder. Specific visualizers will replace this with their own logic."""
        pass

    def _handle_delete(self):
        """A blank placeholder. Specific visualizers will replace this with their own logic."""
        pass

    # ------------------------------------------------------------------
    # Recording toggle, frozen-display probe, and status badges (shared by all visualizers)
    # ------------------------------------------------------------------
    def handle_space_toggle(self, event_holder):
        """Space starts or pauses recording (see toggle_recording)."""
        if event_holder.space_down is not None:
            self.toggle_recording()

    def toggle_recording(self):
        """Pause (freeze) or resume live capture and recording. LiveSpectrogram and LiveSpectrum use
        this version; LiveVowel and LivePitch replace it with their own recording sessions."""
        if self.paused:
            self._resume_recording()
        else:
            self._pause_recording()

    def is_frozen(self):
        """True while the display is frozen (paused), when Shift + click can probe it."""
        return getattr(self, 'paused', False)

    def update_inspect_probe(self, event_holder):
        """Shift + left click (or drag) while the display is frozen places the inspection probe;
        releasing Shift removes it."""
        if event_holder.shift_held:
            if self.is_frozen() and (event_holder.left_click_down is not None or event_holder.left_mouse_held):
                self.inspect_pos = event_holder.mouse_pos
        else:
            self.inspect_pos = None

    def inspect_lines(self, x, y):
        """Lines for the inspection card at pixel (x, y): list of (label, value, color). Each
        visualizer supplies its own."""
        return []

    def draw_inspect_overlay(self):
        """Draw the inspection card at the probe position while the display is frozen."""
        if self.inspect_pos is not None and self.is_frozen():
            self.draw_inspect_tooltip(self.inspect_pos, self.inspect_lines(*self.inspect_pos))

    def status_badges(self):
        """Badges for the top-right corner as (text, color) pairs. LiveSpectrogram and LiveSpectrum
        use this version; the other visualizers add or replace badges."""
        badges = []
        if self.paused:
            badges.append(("[PAUSED]", (255, 210, 80)))
        if self.recording:
            badges.append(("[REC]", (255, 80, 80)))
        return badges

    def draw_status_indicators(self):
        """Draw the status badges in the top-right corner, right to left."""
        x_offset = self.screen.get_width() - 15
        for text, color in self.status_badges():
            text_surf = self.badge_font.render(text, True, (0, 0, 0))
            text_rect = text_surf.get_rect(topright=(x_offset, 10))
            bg_rect = text_rect.inflate(*self.badge_padding)
            pygame.draw.rect(self.screen, color, bg_rect, border_radius=3)
            pygame.draw.rect(self.screen, (50, 50, 50), bg_rect, 1, border_radius=3)
            self.screen.blit(text_surf, text_rect)
            x_offset -= (bg_rect.width + 8)

    def notify_recording(self, on):
        """Show the 'Recording ON' / 'Recording OFF' notification."""
        if on:
            self.show_notification("Recording ON (Live)", duration_ms=1500, bg_color=(200, 255, 200), border_color=(0, 150, 0))
        else:
            self.show_notification("Recording OFF (Frozen - Space to resume)", duration_ms=2500, bg_color=(255, 240, 180), border_color=(200, 160, 0))

    def adjust_min_rms(self, delta_db):
        """Changes the volume threshold (silence gate) so the mic ignores background noise.
        
        Args:
            delta_db (float): How many decibels to add or subtract from the threshold.
        """
        # Safety check: make sure we actually have settings folders to update
        if not hasattr(self, 'audio_config') or not hasattr(self, 'analysis_config'):
            return
        
        # Look up the threshold the analysis is using. If one doesn't exist, assume it is -60 decibels.
        current_rms = self.analysis_config.get('min_rms_db', self.audio_config.get('min_rms_db', -60.0))
        # Math: Add the requested change, but don't let it go lower than -90 or higher than -10.
        new_rms = max(-90.0, min(-10.0, current_rms + delta_db))
        
        # Update the numbers in our local settings folders
        self.audio_config['min_rms_db'] = new_rms
        self.analysis_config['min_rms_db'] = new_rms
        
        # If the background microphone listener is currently running...
        if self.audio_processor and hasattr(self.audio_processor, 'analysis_config'):
            # Reach into its brain and update the threshold there too so it takes effect instantly
            self.audio_processor.analysis_config['min_rms_db'] = new_rms
        
        # Create the text for the visual popup (e.g., "Min RMS: -57 dB")
        self.min_rms_display_text = f"Min RMS: {new_rms:.0f} dB"
        # Tell the system to keep this popup on screen for exactly 1000 milliseconds (1 second)
        self.min_rms_display_until = pygame.time.get_ticks() + 1000
        
        # Log the change
        logger.debug(f"Min RMS adjusted to {new_rms:.0f} dB")

    def draw_min_rms_display(self):
        """Draws the temporary volume threshold popup in the top left corner (clear of the status badges)."""
        # Find out exactly how many milliseconds the program has been running
        current_time = pygame.time.get_ticks()
        
        # If we have text to show, AND the 1-second timer hasn't run out yet...
        if self.min_rms_display_text and current_time < self.min_rms_display_until:
            # Use cached font to avoid expensive OS lookups
            font = self.default_font_28
            # Create an image of the text colored black
            text_surface = font.render(self.min_rms_display_text, True, (0, 0, 0))
            # Get the exact mathematical dimensions of that text image
            text_rect = text_surface.get_rect()
            
            # Pin the text box to the top left corner, leaving a small gap from the edges
            # (the top right corner holds the [REC]/[PAUSED] status badges)
            text_rect.topleft = (10, 10)
            
            # Create a background box that is slightly larger than the text itself (padding)
            bg_rect = text_rect.inflate(10, 6)
            # Draw the solid white background box
            pygame.draw.rect(self.screen, (255, 255, 255), bg_rect)
            # Draw a dark gray outline around the box
            pygame.draw.rect(self.screen, (100, 100, 100), bg_rect, 2)
            
            # Stamp the black text image on top of the white background box
            self.screen.blit(text_surface, text_rect)
            
        # If the 1-second timer HAS run out...
        elif current_time >= self.min_rms_display_until:
            # Delete the text from memory so we stop trying to draw it
            self.min_rms_display_text = None

    def show_notification(self, text, duration_ms=3000, bg_color=(255, 235, 150), border_color=(200, 150, 0)):
        """Displays a temporary on-screen notification banner (e.g. device warning) in the top center."""
        self.notification_text = text
        self.notification_until = pygame.time.get_ticks() + duration_ms
        self.notification_bg_color = bg_color
        self.notification_border_color = border_color

    def draw_notification(self):
        """Draws any active temporary notification banner on screen."""
        # Check if underlying audio processor has any device status update to broadcast
        if self.audio_processor and getattr(self.audio_processor, 'device_status_message', None):
            self.show_notification(self.audio_processor.device_status_message, duration_ms=3500)
            self.audio_processor.device_status_message = None

        current_time = pygame.time.get_ticks()
        if getattr(self, 'notification_text', None) and current_time < self.notification_until:
            font = getattr(self, 'default_font_24', None) or pygame.font.SysFont(None, 24)
            text_surf = font.render(self.notification_text, True, (30, 30, 30))
            text_rect = text_surf.get_rect()
            screen_rect = self.screen.get_rect()
            text_rect.midtop = (screen_rect.centerx, 15)
            bg_rect = text_rect.inflate(24, 12)
            
            bg_color = getattr(self, 'notification_bg_color', (255, 235, 150))
            border_color = getattr(self, 'notification_border_color', (200, 150, 0))
            
            pygame.draw.rect(self.screen, bg_color, bg_rect, border_radius=4)
            pygame.draw.rect(self.screen, border_color, bg_rect, 2, border_radius=4)
            self.screen.blit(text_surf, text_rect)
        elif getattr(self, 'notification_text', None) and current_time >= self.notification_until:
            self.notification_text = None

        # Persistent alert banner, below the temporary notifications
        if getattr(self, 'alert_text', None):
            font = getattr(self, 'default_font_24', None) or pygame.font.SysFont(None, 24)
            text_surf = font.render(self.alert_text, True, (255, 255, 255))
            text_rect = text_surf.get_rect()
            text_rect.midtop = (self.screen.get_rect().centerx, 60)
            bg_rect = text_rect.inflate(24, 12)
            pygame.draw.rect(self.screen, (190, 30, 30), bg_rect, border_radius=4)
            pygame.draw.rect(self.screen, (110, 0, 0), bg_rect, 2, border_radius=4)
            self.screen.blit(text_surf, text_rect)

    def check_recording_interrupted(self):
        """
        Return the time (s) at which a device disconnect stopped the recording, or None.

        When it did, show a banner that stays up until the next recording starts. The caller
        then ends and saves the recording through its normal stop path.
        """
        if self.audio_processor is None or not hasattr(self.audio_processor, 'take_recording_interruption'):
            return None
        stopped_at = self.audio_processor.take_recording_interruption()
        if stopped_at is not None:
            self.alert_text = f"Mic disconnected: recording stopped at {stopped_at:.1f} s and saved. Space = new recording"
        return stopped_at

    def quit(self):
        """Starts the sequence to shut down the application."""
        logger.info("Quit requested")
        # Flip the main power switch to False. The main loop will notice this and stop spinning.
        self.keep_running = False

    def shutdown(self):
        """The final cleanup routine before the window disappears forever."""
        # If the background microphone listener is active...
        if self.audio_processor:
            # Tell it to stop listening and close its connection to the hardware
            self.audio_processor.stop()
        # Completely shut down the Pygame graphics engine
        pygame.quit()
        logger.info("Application shutdown complete")

    # ------------------------------------------------------------------
    # Saving recordings (shared by all visualizers)
    # ------------------------------------------------------------------
    def new_recording_name(self):
        """Name for the next recording's files: the window's timestamped name plus a running
        number (speaker_2026-01-29_143022_01, _02, ...), so one window's recordings sort together."""
        self.recording_count += 1
        return f"{self.window_name}_{self.recording_count:02d}"

    def output_base_path(self):
        """Path prefix for this session's files: <data_dir>/<output_dir>/<session_name>."""
        data_dir = vt_config.EXPORT_CONFIG.get('data_dir', '.')
        output_subdir = vt_config.EXPORT_CONFIG.get('output_dir', 'recordings')
        output_dir = output_subdir if os.path.isabs(output_subdir) else os.path.join(data_dir, output_subdir)
        return os.path.join(output_dir, self.session_name)

    def save_audio_files(self, file_tag, original_rate=None):
        """
        Write the buffered original and downsampled audio as WAV files, as enabled in the
        export settings: <session>_<file_tag>_original.wav and <session>_<file_tag>_downsampled.wav.

        Args:
            file_tag (str): Mode name used in the file names (e.g. 'vowel', 'spectrum').
            original_rate (int, optional): Sample rate of the original audio. Defaults to
                self.original_recording_sample_rate.
        """
        base_path = self.output_base_path()
        if vt_config.EXPORT_CONFIG.get('save_original_audio', True) and self.original_audio_buffer:
            wav_file = f"{base_path}_{file_tag}_original.wav"
            exporter.save_wav(wav_file, self.original_audio_buffer,
                              original_rate or self.original_recording_sample_rate)
            logger.info(f"Original audio saved to {wav_file}")
        if vt_config.EXPORT_CONFIG.get('save_downsampled_audio', False) and self.downsampled_audio_buffer:
            wav_file = f"{base_path}_{file_tag}_downsampled.wav"
            exporter.save_wav(wav_file, self.downsampled_audio_buffer,
                              self.downsampled_recording_sample_rate)
            logger.info(f"Downsampled audio saved to {wav_file}")

    def _collect_recording(self):
        """Stop recording in the audio processor and append what it recorded to the export buffers."""
        if self.audio_processor:
            self.audio_processor.stop_recording()
            self.original_recording_sample_rate = self.audio_processor.get_original_recording_sample_rate()
            self.downsampled_recording_sample_rate = self.audio_processor.get_downsampled_recording_sample_rate()
            # The export buffers are lists of int16 arrays, written one after the other on export
            for buffer, recording in ((self.original_audio_buffer, self.audio_processor.get_original_recording()),
                                      (self.downsampled_audio_buffer, self.audio_processor.get_downsampled_recording())):
                if recording.size:
                    buffer.append(recording)

    def export_recording(self):
        """Save the buffered audio (LiveSpectrum/LiveSpectrogram) and clear the buffers."""
        self.save_audio_files(self.file_tag)
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []

    def _pause_recording(self):
        """Freeze the display, stop recording, and export the recorded audio (LiveSpectrum/LiveSpectrogram)."""
        self.paused = True
        self.recording = False
        logger.info(f"{self.file_tag}: recording stopped (frozen)")
        self.notify_recording(False)
        self._collect_recording()
        if self.original_audio_buffer or self.downsampled_audio_buffer:
            self.export_recording()

    def _resume_recording(self):
        """Resume the live display and start a new recording in new files (LiveSpectrum/LiveSpectrogram)."""
        self.paused = False
        self.recording = True
        self.inspect_pos = None
        self.alert_text = None  # Clear any "mic disconnected" banner
        self.session_name = self.new_recording_name()
        self.original_audio_buffer = []
        self.downsampled_audio_buffer = []
        if self.audio_processor:
            self.audio_processor.start_recording(
                record_original=bool(vt_config.EXPORT_CONFIG.get('save_original_audio', True)),
                record_downsampled=bool(vt_config.EXPORT_CONFIG.get('save_downsampled_audio', False))
            )
        logger.info(f"{self.file_tag}: recording started (live)")
        self.notify_recording(True)

    def take_analyzed_sounds(self):
        """Return the analyzed Sound objects waiting in the queue, oldest first, emptying the queue."""
        sounds = []
        while self.audio_processor is not None:
            try:
                sound = self.audio_processor.analyzed_sounds_queue.get_nowait()
            except queue.Empty:
                break
            if sound is not None:
                sounds.append(sound)
        return sounds

    def draw_help_panel(self, title, legend_items, controls, font_big, font_normal, font_bold, size):
        """
        Draw the full-window help overlay of LiveVowel and LivePitch: a title, the color legend,
        the list of controls, and a footer.

        Args:
            title (str): Heading at the top of the overlay.
            legend_items (list): (header, header color, description) for each color convention.
            controls (list): One line of text per control.
            font_big, font_normal, font_bold: Fonts for the title, the text, and the legend headers.
            size (tuple): (width, height) of the window in pixels.
        """
        gui_w, gui_h = size
        # Semi-transparent dark background
        overlay = pygame.Surface((gui_w, gui_h))
        overlay.set_alpha(220)
        overlay.fill((30, 30, 30))
        self.screen.blit(overlay, (0, 0))

        # Title
        title_surf = font_big.render(title, True, (255, 255, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(gui_w // 2, 35)))

        # Color legend
        y_pos = 70
        for header, color, desc in legend_items:
            self.screen.blit(font_bold.render(header, True, color), (gui_w // 2 - 280, y_pos))
            self.screen.blit(font_normal.render(desc, True, (220, 220, 220)), (gui_w // 2 - 260, y_pos + 22))
            y_pos += 46

        y_pos += 10
        # Separator line
        pygame.draw.line(self.screen, (100, 100, 100), (gui_w // 2 - 300, y_pos), (gui_w // 2 + 300, y_pos), 1)
        y_pos += 15

        for line in controls:
            self.screen.blit(font_normal.render(line, True, (255, 255, 255)), (gui_w // 2 - 260, y_pos))
            y_pos += 26

        # Footer text
        footer = font_normal.render("Press Ctrl/Cmd+? to close help", True, (180, 180, 180))
        self.screen.blit(footer, footer.get_rect(center=(gui_w // 2, gui_h - 25)))

    def draw_performance_overlay(self):
        """Draws a real-time performance diagnostic overlay in the top-right corner."""
        if not getattr(self, 'show_performance', False):
            return

        # Fetch metrics
        actual_fps = self.clock.get_fps()
        target_fps = getattr(self, 'target_fps', 60)

        # Get actual chunk duration from processor if available, fallback to config
        if self.audio_processor is not None:
            chunk_ms = getattr(self.audio_processor, 'chunk_ms', 20.0)
        else:
            chunk_ms = self.audio_config.get('chunk_ms', 20.0)
        expected_audio_rate = 1000.0 / chunk_ms if chunk_ms > 0 else 50.0

        # Safely get rates from audio processor
        is_audio_running = self.audio_processor is not None and getattr(self.audio_processor, 'running', False)
        if is_audio_running:
            capture_rate = self.audio_processor.get_capture_rate()
            analysis_rate = self.audio_processor.get_analysis_rate()
            queue_size = self.audio_processor.get_analysis_queue_size()
            queue_max = self.audio_processor.get_analysis_queue_maxsize()
        else:
            capture_rate = 0.0
            analysis_rate = 0.0
            queue_size = 0
            queue_max = 50

        # Build lines of text
        fps_pct = (actual_fps / target_fps * 100) if target_fps > 0 else 0.0
        capture_pct = (capture_rate / expected_audio_rate * 100) if expected_audio_rate > 0 else 0.0
        analysis_pct = (analysis_rate / expected_audio_rate * 100) if expected_audio_rate > 0 else 0.0

        lines = [
            "PERFORMANCE MONITOR",
            f"GUI FPS:  {actual_fps:4.1f} / {target_fps} fps ({fps_pct:.2f}%)",
            f"Audio In: {capture_rate:4.1f} / {expected_audio_rate:.1f} ch/s ({capture_pct:.2f}%)",
            f"Analysis: {analysis_rate:4.1f} / {expected_audio_rate:.1f} win/s ({analysis_pct:.2f}%)",
            f"Queue:    {queue_size} / {queue_max} chunks"
        ]

        # Draw panel container (semi-transparent dark gray)
        padding = 10
        line_height = 20
        panel_w = 260
        panel_h = padding * 2 + len(lines) * line_height - 5

        # Position panel in top right, below the status badges ([REC], [PAUSED], ...)
        screen_rect = self.screen.get_rect()
        panel_x = screen_rect.right - panel_w - 10
        panel_y = 40

        # Create overlay surface for transparency
        overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        # Fill with semi-transparent dark gray (RGBA)
        overlay.fill((30, 30, 30, 200))
        # Draw a thin light gray border outline
        pygame.draw.rect(overlay, (200, 200, 200, 255), (0, 0, panel_w, panel_h), 1)

        # Render text
        font = self.default_font_18
        
        # Color coding helper
        def get_color(actual, target, toleration=0.90, critical=0.75):
            if target <= 0:
                return (255, 255, 255)
            ratio = actual / target
            if ratio >= toleration:
                return (100, 255, 100) # Light Green
            elif ratio >= critical:
                return (255, 255, 100) # Light Yellow
            else:
                return (255, 100, 100) # Light Red

        for i, line in enumerate(lines):
            y_offset = padding + i * line_height
            if i == 0:
                # Title - white and bold-ish
                text_surface = font.render(line, True, (255, 255, 255))
            elif i == 1:
                # GUI FPS
                col = get_color(actual_fps, target_fps)
                text_surface = font.render(line, True, col)
            elif i == 2:
                # Audio capture rate
                col = get_color(capture_rate, expected_audio_rate) if is_audio_running else (150, 150, 150)
                lbl = line if is_audio_running else "Audio In: Idle"
                text_surface = font.render(lbl, True, col)
            elif i == 3:
                # DSP analysis rate
                col = get_color(analysis_rate, expected_audio_rate) if is_audio_running else (150, 150, 150)
                lbl = line if is_audio_running else "Analysis: Idle"
                text_surface = font.render(lbl, True, col)
            elif i == 4:
                # Analysis queue size
                col = get_color(queue_max - queue_size, queue_max, toleration=0.90, critical=0.50) if is_audio_running else (150, 150, 150)
                text_surface = font.render(line, True, col)

            overlay.blit(text_surface, (10, y_offset))

        self.screen.blit(overlay, (panel_x, panel_y))

    def draw_inspect_tooltip(self, pos, lines, title=None):
        """
        Draw a sleek, high-visibility inspection card with crosshairs at pos.
        
        Args:
            pos (tuple): (x, y) screen pixel coordinates.
            lines (list): List of (label, value_str, color) tuples or string lines.
            title (str, optional): Optional header title for the tooltip card.
        """
        if not pos:
            return
        x, y = int(pos[0]), int(pos[1])
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()

        # 1. Draw crisp crosshair overlay centered at (x, y)
        cross_surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        # Subtle horizontal and vertical guide lines across screen
        pygame.draw.line(cross_surf, (0, 200, 255, 120), (0, y), (screen_w, y), 1)
        pygame.draw.line(cross_surf, (0, 200, 255, 120), (x, 0), (x, screen_h), 1)
        # Concentric reticle rings
        pygame.draw.circle(cross_surf, (0, 220, 255, 230), (x, y), 6, 2)
        pygame.draw.circle(cross_surf, (255, 255, 255, 255), (x, y), 2)
        self.screen.blit(cross_surf, (0, 0))

        # 2. Render tooltip card content
        font = self.default_font_18
        rendered_lines = []
        if title:
            t_surf = font.render(title, True, (0, 220, 255))
            rendered_lines.append(t_surf)
        
        for item in lines:
            if isinstance(item, tuple) and len(item) == 3:
                label, val, col = item
                lbl_s = font.render(f"{label}: ", True, (200, 200, 200))
                val_s = font.render(str(val), True, col)
                comb_w = lbl_s.get_width() + val_s.get_width()
                comb_h = max(lbl_s.get_height(), val_s.get_height())
                comb_surf = pygame.Surface((comb_w, comb_h), pygame.SRCALPHA)
                comb_surf.blit(lbl_s, (0, 0))
                comb_surf.blit(val_s, (lbl_s.get_width(), 0))
                rendered_lines.append(comb_surf)
            elif isinstance(item, str):
                rendered_lines.append(font.render(item, True, (240, 240, 240)))

        if not rendered_lines:
            return

        box_w = max(surf.get_width() for surf in rendered_lines) + 24
        box_h = sum(surf.get_height() + 4 for surf in rendered_lines) + 16

        # Position box offset from cursor, clamped safely within window bounds
        box_x = x + 18
        box_y = y - box_h - 12
        if box_x + box_w > screen_w - 10:
            box_x = x - box_w - 18
        if box_x < 10:
            box_x = 10
        if box_y < 10:
            box_y = y + 18
        if box_y + box_h > screen_h - 10:
            box_y = screen_h - box_h - 10

        # Draw semi-transparent card background with cyan border
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (20, 24, 32, 230), (0, 0, box_w, box_h), border_radius=6)
        pygame.draw.rect(box_surf, (0, 180, 255, 220), (0, 0, box_w, box_h), 1, border_radius=6)

        # Blit text lines onto card
        cur_y = 8
        for surf in rendered_lines:
            box_surf.blit(surf, (12, cur_y))
            cur_y += surf.get_height() + 4

        self.screen.blit(box_surf, (box_x, box_y))