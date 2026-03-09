# Import os for file path operations
import os
# Import sys for PyInstaller resource path detection
import sys

# Import numpy for matrix operations and loading CSV data
import numpy
# Import pygame for image loading and display
import pygame


class VowelTemplate:
    """Interactive vowel template that displays reference vowel positions on the vowel space.
    
    Provides a visual overlay showing typical F1/F2 values for common vowels from a CSV file.
    Users can scale the template using scroll wheel to adjust its size relative to their voice.
    
    Args:
        screen (pygame.Surface): Display surface to draw on
        gui_info (dict): Dictionary containing GUI settings (size, F1/F2 ranges)
        file_path (str, optional): Path to CSV with vowel data. Defaults to California vowels.
    """
    def __init__(self,
                 screen,
                 gui_info,
                 file_path=None):

        # Store reference to the pygame display surface
        self.screen = screen
        # Store GUI configuration (window size, formant ranges, etc.)
        self.gui_info = gui_info

        # Get the absolute path to the module's directory or PyInstaller bundle
        self.is_bundled = False
        try:
            # When bundled as exe, resources are in _MEIPASS temp directory
            base_path = sys._MEIPASS
            self.is_bundled = True
        except AttributeError:
            # In normal Python, use module directory
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Track whether template is available
        self.enabled = True

        # Use default template file if none specified
        if file_path is None:
            # Templates are always loaded from a local folder, never bundled
            # For both bundled exe and normal Python, navigate to project root
            if self.is_bundled:
                # Bundled: templates folder is at the same level as the executable
                project_root = base_path
            else:
                # Normal Python: templates folder is in the project root
                project_root = os.path.dirname(base_path)
            file_path = os.path.join(project_root, 'templates', 'vowel_template.csv')

        # If no template exists, disable template rendering gracefully
        if not os.path.exists(file_path):
            self.enabled = False
            self.vowel_matrix = numpy.empty((0, 4))
            self.f1 = numpy.array([])
            self.f2 = numpy.array([])
            self.images = []
            self.plot_x = numpy.array([])
            self.plot_y = numpy.array([])
            return

        # Load vowel template data from CSV file
        # Each row represents one vowel with its formant values
        try:
            self.vowel_matrix = numpy.genfromtxt(file_path, delimiter=',')
        except (OSError, ValueError):
            self.enabled = False
            self.vowel_matrix = numpy.empty((0, 4))
            self.f1 = numpy.array([])
            self.f2 = numpy.array([])
            self.images = []
            self.plot_x = numpy.array([])
            self.plot_y = numpy.array([])
            return

        # Store base path for loading images
        self.base_path = base_path
        # Scaling factor for template (1 = 100%, adjustable via scroll wheel)
        self.scale = 1
        # Extract F1 values (second column, index 1) for all vowels
        self.f1 = self.vowel_matrix[:,1]
        # Extract F2 values (third column, index 2) for all vowels
        self.f2 = self.vowel_matrix[:,2]

        # Extract image numbers (first column, index 0) for image filenames
        vowels = self.vowel_matrix[:,0]
        # List to store loaded and scaled vowel symbol images
        self.images = []
        # Load images for each of the 10 vowels in the template
        # Images are bundled in the executable; templates are not
        images_prefix = "VocalTrack/images" if self.is_bundled else "images"
        for i in range(10):
            # Construct path to vowel symbol image using image number from CSV
            image_path = os.path.join(self.base_path, images_prefix, "green", str(int(vowels[i]))+".png")
            # Load image with alpha channel (transparency support)
            self.image_original = pygame.image.load(image_path).convert_alpha()
            # Scale image to standard display size (60x56 pixels)
            self.image = pygame.transform.scale(self.image_original, (60, 56))
            # Add scaled image to list
            self.images.append(self.image)

        # Calculate initial plot coordinates for all vowel symbols
        self.plot_x, self.plot_y = self.point_coordinates ()

    def run_voweltemplate(self, event_holder,state):
        """Update and render the vowel template based on events and current state.
        
        Args:
            event_holder (EventHolder): Object containing current frame's events
            state (str): Current application state ('recording', 'menu', etc.)
        """
        if not self.enabled:
            return
        # Only process template events and drawing during recording state
        if state=="recording":
            # Process scroll wheel events to scale the template
            self.handle_event(event_holder)
            # Draw all vowel symbols at their current positions
            self.draw()

    def draw(self):
        """Draw all vowel symbol images at their calculated screen positions.
        """
        if not self.enabled:
            return
        # Draw each of the 10 vowel symbols at its scaled position
        for i in range(10):
            # Blit (copy) the image to the screen at the calculated coordinates
            self.screen.blit(self.images[i],
                             (self.plot_x[i],
                              self.plot_y[i]))

    def handle_event(self, event_holder):
        """Process scroll wheel events to scale the vowel template multiplicatively.
        
        Scroll up increases formants by 1% each, scroll down decreases by 1%.
        This allows fine-tuning of the template to match a speaker's formant values.
        
        Args:
            event_holder (EventHolder): Object containing current frame's events
        """
        if not self.enabled:
            return
        # Ensure F1 and F2 arrays are float type for scaling calculations
        self.f1 = self.f1.astype(float)
        self.f2 = self.f2.astype(float)

        # Check if scroll wheel was moved up (increase formants by 1%)
        if event_holder.left_scroll_up is not None:
            self.f2 *= 1.01  # Scale F2 up by 1%
            self.f1 *= 1.01  # Scale F1 up by 1%
        # Check if scroll wheel was moved down (decrease formants by 1%)
        if event_holder.left_scroll_down is not None:
            self.f2 *= 0.99  # Scale F2 down by 1%
            self.f1 *= 0.99  # Scale F1 down by 1%

        # Recalculate plot coordinates after scaling
        self.plot_x, self.plot_y = self.point_coordinates ()


    def point_coordinates(self):
        """Convert formant frequencies to screen coordinates using logarithmic scaling.
        
        Translates F1/F2 values from Hz to pixel coordinates within the GUI window,
        using logarithmic spacing to match perceptual vowel space.
        
        Returns:
            tuple: (plot_x, plot_y) numpy arrays of x and y pixel coordinates for each vowel
        """
        # Convert F1 and F2 arrays to integer type for display
        self.f1 = self.f1.astype(int)
        self.f2 = self.f2.astype(int)

        # Calculate log-distance of F2 from minimum F2 in display range
        x_diff = numpy.log(self.f2) - numpy.log(self.gui_info['f2_range'][0])
        # Calculate log-distance of F1 from minimum F1 in display range
        y_diff = numpy.log(self.f1) - numpy.log(self.gui_info['f1_range'][0])

        # Calculate total log-range for F2 (max to min)
        x_range = (numpy.log(self.gui_info['f2_range'][1]) -
                   numpy.log(self.gui_info['f2_range'][0]))

        # Calculate total log-range for F1 (max to min)
        y_range = (numpy.log(self.gui_info['f1_range'][1]) -
                   numpy.log(self.gui_info['f1_range'][0]))

        # Convert to screen x-coordinates (F2 on horizontal axis, inverted: high F2 = left)
        plot_x = ((self.gui_info['gui_size'][0]) -
                  (self.gui_info['gui_size'][0]) * (x_diff / x_range))
        # Convert to screen y-coordinates (F1 on vertical axis: low F1 = top)
        plot_y = self.gui_info['gui_size'][1] * (y_diff / y_range)

        return plot_x, plot_y
