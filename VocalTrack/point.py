# Import pygame library for sprite and surface rendering
import pygame

# Define Point class inheriting from pygame's Sprite class
class Point(pygame.sprite.Sprite):
    """A visual point representing one plotted measurement. Used for LiveVowel and LivePitch,
    and potentially new visualizations in the future. Each Point is a circle drawn on a transparent
    surface, with color and position based on formant data. The Point class also includes a method
    to change its color dynamically, which can be used to indicate changes in voicing or other parameters.

    A point does not keep the audio it was measured from (that would hold every analysis window in
    memory for as long as the point is on screen). It keeps where its analysis window is in the saved
    recording instead, so the audio can be found again in the exported WAV file.

    Args:
        plot_x: X coordinate on screen
        plot_y: Y coordinate on screen
        radius: Circle radius in pixels
        color: RGB tuple for point color
        f1: Smoothed F1 of the point in Hz (LiveVowel)
        f2: Smoothed F2 of the point in Hz (LiveVowel)
        raw_f0: Unsmoothed f0 of the frame in Hz
        recording_time: Center of the analysis window, in seconds from the start of the recording
            (the same time as time_ms in the exported CSV)
        recording_name: Name of the recording the frame belongs to (the start of its file names)
    """
    # Initialize Point instance with optional parameters (defaults provided)
    def __init__(self, plot_x=-100, plot_y=-100, radius=12, color=(166, 33, 64), f1=None, f2=None,
                 raw_f0=None, recording_time=None, recording_name=None):
        # Call parent Sprite class constructor to initialize sprite functionality
        super().__init__()

        # Raw f0 of the frame, and where the frame is in the saved recording
        self.raw_f0 = raw_f0
        self.recording_time = recording_time
        self.recording_name = recording_name
        # Store smoothed F1 and F2 values so we can recalculate coordinates if log/linear scale changes
        self.f1 = f1
        self.f2 = f2
        # Store radius for color changes
        # Save radius value as instance variable (needed later for redraws when changing color)
        self.radius = radius

        # Create a surface for the point
        # Create transparent pygame surface with dimensions to fit circle (2*radius square)
        self.image = pygame.Surface((2*radius, 2*radius), pygame.SRCALPHA)
        # Draw filled circle on surface at center position with specified color
        pygame.draw.circle(self.image, color, (radius, radius), radius)

        # location based on input calculated by function belonging to the GUI class
        # Get rectangle object from image surface for positioning and collision detection
        self.rect = self.image.get_rect()
        # Set center position of rectangle to specified plot coordinates
        self.rect.center = (plot_x, plot_y)
    
    # Define method to change the point's color dynamically
    def set_color(self, color):
        """Change the point's color.
        
        Args:
            color: RGB tuple (e.g., (0, 0, 255) for blue)
        """
        # Clear the surface
        # Fill entire surface with transparent pixels (RGBA 0,0,0,0) to erase old circle
        self.image.fill((0, 0, 0, 0))  # Transparent
        # Redraw circle with new color
        # Draw new filled circle at center with updated color value
        pygame.draw.circle(self.image, color, (self.radius, self.radius), self.radius)
