# Import pygame library for sprite and surface rendering
import pygame

# Define Point class inheriting from pygame's Sprite class
class Point(pygame.sprite.Sprite):
    """A visual point representing a formant measurement. Used for LiveVoice and LivePitch,
    and potentially new visualizations in the future. Each Point is a circle drawn on a transparent 
    surface, with color and position based on formant data. The Point class also includes a method 
    to change its color dynamically, which can be used to indicate changes in voicing or other parameters.

    Args:
        sound: Sound object with formant data
        plot_x: X coordinate on screen
        plot_y: Y coordinate on screen
        radius: Circle radius in pixels
        color: RGB tuple for point color
    """
    # Initialize Point instance with optional parameters (defaults provided)
    def __init__(self, sound=None, plot_x=-100, plot_y=-100, radius=12, color=(166, 33, 64)):
        # Call parent Sprite class constructor to initialize sprite functionality
        super().__init__()

        # sound and sound information for the frame/point
        # Store reference to Sound object containing audio analysis data for this point
        self.sound = sound
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
