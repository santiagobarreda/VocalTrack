"""Base class for real-time audio visualization applications.

Provides common functionality for LivePitch, LiveVowel, and future audio visualizers.
Encapsulates shared UI controls, event handling, and configuration management.
"""

# Bring in the logging tool to track background events and errors
import logging
# Bring in Pygame, the graphics engine that draws the windows and shapes
import pygame
# Bring in the tool to talk directly to the Windows operating system
#import ctypes

# Tell Windows that this software knows how to scale itself on high-resolution screens
# This prevents Windows from locking the window size when we create an executable (.exe)
#try:
#    ctypes.windll.user32.SetProcessDPIAware()
#except AttributeError:
    # If the user is on a Mac or Linux, just ignore this Windows-specific command
#    pass

# Create a logger specifically for this file
logger = logging.getLogger(__name__)


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
        
        # Create switches for universal visual settings (Grid and Help menu)
        self.show_grid = True
        self.show_help = False
        # Look in the settings to see if the user wants Logarithmic or Linear spacing
        self.freq_scale = self.config.get('freq_scale', 'log')
        
        # Memory slots to prevent "double-clicking" if the user holds a key down too long
        self.last_backspace_pressed = False
        self.last_delete_pressed = False
        
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
        
        # Log that the base setup was successful
        logger.debug(f"BaseAudioVisualizer initialized: {app_title}")

    def handle_base_events(self, event_holder):
        """Translates keyboard presses that do the exact same thing in every visualizer.
        
        Args:
            event_holder: The tool containing the current keyboard/mouse actions.
            
        Returns:
            bool: False if the user asked to quit, True if the program should keep going.
        """
        # If the user presses the 'G' key...
        if event_holder.g_key:
            # Flip the grid switch (turn it on if it's off, or off if it's on)
            self.show_grid = not self.show_grid
            # Log the change
            grid_status = "ON" if self.show_grid else "OFF"
            logger.debug(f"Grid toggled {grid_status}")
        
        # If the user presses the 'H' key...
        if event_holder.h_key:
            # Flip the help menu switch
            self.show_help = not self.show_help
            # Log the change
            help_status = "shown" if self.show_help else "hidden"
            logger.debug(f"Help overlay {help_status}")
        
        # If the user presses the Backspace key...
        if event_holder.backspace:
            # Check if this is a fresh press (not just holding the key down from last frame)
            if not self.last_backspace_pressed:
                # Trigger the specific undo action for this visualizer
                self._handle_backspace()
                # Remember that the key is currently being held down
                self.last_backspace_pressed = True
        # If the backspace key is NOT being pressed...
        else:
            # Reset the memory so it can be pressed again later
            self.last_backspace_pressed = False
        
        # If the user presses the Delete key...
        if event_holder.delete:
            # Check if it's a fresh press
            if not self.last_delete_pressed:
                # Trigger the specific clear-all action for this visualizer
                self._handle_delete()
                # Remember the key is held
                self.last_delete_pressed = True
        # If the delete key is NOT being pressed...
        else:
            # Reset the memory
            self.last_delete_pressed = False
        
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

    def adjust_min_rms(self, delta_db):
        """Changes the volume threshold (silence gate) so the mic ignores background noise.
        
        Args:
            delta_db (float): How many decibels to add or subtract from the threshold.
        """
        # Safety check: make sure we actually have settings folders to update
        if not hasattr(self, 'audio_config') or not hasattr(self, 'analysis_config'):
            return
        
        # Look up the current threshold. If one doesn't exist, assume it is -60 decibels.
        current_rms = self.audio_config.get('min_rms_db', -60.0)
        # Math: Add the requested change, but don't let it go lower than -90 or higher than -20.
        new_rms = max(-90.0, min(-20.0, current_rms + delta_db))
        
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

    def toggle_grid(self):
        """A shortcut function to let other parts of the code flip the grid switch."""
        self.show_grid = not self.show_grid
        logger.debug(f"Grid toggled to {self.show_grid}")

    def toggle_help(self):
        """A shortcut function to let other parts of the code flip the help menu switch."""
        self.show_help = not self.show_help
        logger.debug(f"Help toggled to {self.show_help}")

    def draw_min_rms_display(self):
        """Draws the temporary volume threshold popup in the top right corner."""
        # Find out exactly how many milliseconds the program has been running
        current_time = pygame.time.get_ticks()
        
        # If we have text to show, AND the 1-second timer hasn't run out yet...
        if self.min_rms_display_text and current_time < self.min_rms_display_until:
            # Create a font that is large enough to read easily
            font = pygame.font.SysFont(None, 28)
            # Create an image of the text colored black
            text_surface = font.render(self.min_rms_display_text, True, (0, 0, 0))
            # Get the exact mathematical dimensions of that text image
            text_rect = text_surface.get_rect()
            
            # Ask Pygame how big the window is right now (in case the user stretched it)
            screen_rect = self.screen.get_rect()
            # Pin the text box to the top right corner, leaving a tiny 10 pixel gap from the edges
            text_rect.topright = (screen_rect.right - 10, 10)
            
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