# Import os for file path operations
import os
# Import sys for accessing PyInstaller temp directory when bundled as exe
import sys
# Import csv for reading template files
import csv
# Import math for log-space scaling
import math
from venv import logger
# Import pygame for image loading and GUI rendering
import pygame


# Mapping of image numbers (1-30) to IPA vowel symbols
# This allows showing all 30 images with proper vowel identities
IPA_IMAGE_MAP = {
    1: 'i',      # Close front unrounded
    2: 'y',      # Close front rounded
    3: 'ɨ',      # Close central unrounded
    4: 'ʉ',      # Close central rounded
    5: 'ɯ',      # Close back unrounded
    6: 'u',      # Close back rounded
    7: 'ɪ',      # Near-close front unrounded
    8: 'ʏ',      # Near-close front rounded
    9: 'ʊ',      # Near-close back rounded
    10: 'e',     # Close-mid front unrounded
    11: 'ø',     # Close-mid front rounded
    12: 'ɘ',     # Close-mid central unrounded
    13: 'ɵ',     # Close-mid central rounded
    14: 'ɤ',     # Close-mid back unrounded
    15: 'o',     # Close-mid back rounded
    16: 'ɛ',     # Open-mid front unrounded
    17: 'œ',     # Open-mid front rounded
    18: 'ə',     # Mid central (schwa)
    19: 'ɜ',     # Open-mid central unrounded
    20: 'ɞ',     # Open-mid central rounded
    21: 'ʌ',     # Open-mid back unrounded
    22: 'ɔ',     # Open-mid back rounded
    23: 'æ',     # Near-open front unrounded
    24: 'ɐ',     # Near-open central
    25: 'a',     # Open front unrounded
    26: 'ɶ',     # Open front rounded
    27: 'ɑ',     # Open back unrounded
    28: 'ɒ',     # Open back rounded
    29: 'ɞ',     # Open-mid central rounded (duplicate for completeness)
    30: 'ɑ',     # Open back unrounded (duplicate for completeness)
}

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not bundled, use the current working directory
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_external_path(relative_path):
    """ Get path to files living NEXT to the .exe (like templates) """
    if getattr(sys, 'frozen', False):
        # If running as .exe, look in the folder where the .exe lives
        base_path = os.path.dirname(sys.executable)
    else:
        # If running as script, look in the project root
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class IPALabels:
    """Manage IPA vowel buttons (menu) and draggable vowel labels (recording).

    IPA vowel label buttons and draggable labels for annotating vowel space.
    This module provides two UI building blocks used by the vowel GUI:
    - `MenuButton`: a small clickable button showing an IPA symbol image (black/colored)
    - `RecordingLabel`: a draggable, larger label used to annotate the vowel plot

    Resource expectations:
    - IPA symbol images are loaded from an `images/` directory at runtime. When the
        application is bundled the images may live under the PyInstaller `_MEIPASS`
        temporary directory and are looked up accordingly.
    - Vowel template CSV files (formant reference values) are expected to live in the
        project's `templates/` folder and are intentionally not bundled so users can
    edit templates without rebuilding the executable.

    Responsibilities:
    - Load vowel template rows from a CSV (image number + F1/F2). Templates are
        expected in the project's `templates/` folder and are bundled into the
        executable.
    - Create two UI sets (green template set + blue comparison set) of
        `MenuButton`/`RecordingLabel` widgets for all available IPA images.
    - Convert between F1/F2 (Hz) and pixel coordinates supporting linear or
        logarithmic frequency scaling.

    Args:
            screen (pygame.Surface): Display surface to draw buttons/labels on.
            csv_path (str, optional): Path to CSV file with image numbers and F1/F2
                    data. If not provided the code looks for `templates/vowel_template.csv`
                    in the project root.
            gui_info (dict, optional): GUI configuration dict with keys like
                    `'f1_range'`, `'f2_range'`, and `'freq_scale'` used for Hz↔pixel
                    conversions.
    """
    def __init__(self, screen, csv_path=None, gui_info=None):
        # Store reference to pygame display surface
        self.screen = screen
        # Store GUI info for Hz-to-pixel conversion
        self.gui_info = gui_info or {}
        # Initialize empty event list
        self.events = []

        # Load image specifications from CSV
        if csv_path is None:
            # Look for the "templates" folder sitting next to the .exe
            csv_path = get_external_path(os.path.join("templates", "vowel_template.csv"))
      

        # Parse CSV to get template vowels and their F1/F2 positions
        self.template_data = self._load_csv(csv_path)
        # Create set of image numbers in template for quick lookup
        self.template_image_nums = {v['image_num'] for v in self.template_data}
        
        # List to store all menu button objects
        self.buttons = []
        # List to store all recording label objects
        self.textboxes = []
        
        # Create buttons and labels for ALL 30 available images
        self._create_buttons_and_labels()

    def _load_csv(self, csv_path):
        """Load vowel data from CSV file.
        
        Expected CSV format (no header):
        ImageNumber, F1, F2, F3
        
        Example:
        23, 883.66, 1725.00, 2685.08
        
        Args:
            csv_path (str): Path to CSV file
            
                Returns:
                        list: List of dicts with keys: 'image_num', 'f1', 'f2'

                Notes:
                        - The CSV is expected to contain numeric image IDs and at least two
                            formant columns (F1, F2). Malformed rows are skipped silently.
                        - Template CSV files are intended to be editable by users and should
                            therefore live outside bundled resources (project `templates/`).
        """
        vowels = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 3:
                        try:
                            image_num = int(row[0].strip())
                            f1 = float(row[1])
                            f2 = float(row[2])
                            vowels.append({
                                'image_num': image_num,
                                'f1': f1,
                                'f2': f2
                            })
                        except (ValueError, IndexError):
                            # Skip malformed rows
                            continue
        except FileNotFoundError:
            pass
        
        return vowels

    def _create_buttons_and_labels(self):
        """Create MenuButton and RecordingLabel objects for all IPA symbols.
        
        Creates TWO complete sets:
        1. Green set (rows 0-2): Template vowels enabled by default, green labels
        2. Blue set (rows 3-5): All disabled by default, blue labels
        
        This allows users to compare two different vowel configurations.
        """
        # Button dimensions and spacing in menu mode
        button_width = 55
        button_height = 40
        x_spacing = 3
        y_spacing = 3
        x_start = 40
        y_start = 40
        
        # Calculate grid layout for menu buttons (max 10 columns)
        max_cols = 10
        
        # Create a lookup dict for template data indexed by image number
        template_by_image = {v['image_num']: v for v in self.template_data}
        
        # Create TWO sets of buttons and labels (green template set + blue comparison set)
        for set_idx, (toggle_color, label_color) in enumerate([('green', 'green'), ('blue', 'blue')]):
            for image_num in range(1, 31):
                # Calculate button position in menu grid
                idx = image_num - 1  # Convert to 0-based index
                row = idx // max_cols + (set_idx * 3)  # Offset second set by 3 rows
                col = idx % max_cols
                button_x = x_start + col * (button_width + x_spacing)
                button_y = y_start + row * (button_height + y_spacing)
                
                # Create menu button for this image
                image_filename = f"{image_num}.png"
                tmp_button = MenuButton(
                    button_x,
                    button_y,
                    button_width,
                    button_height,
                    image_filename,
                    toggle_color=toggle_color
                )
                
                # For green set: enable template vowels. For blue set: all disabled
                if set_idx == 0:  # Green set
                    is_template = image_num in self.template_image_nums
                    tmp_button.clicked = is_template
                else:  # Blue set
                    tmp_button.clicked = False
                
                self.buttons.append(tmp_button)
                
                # Create corresponding recording label
                if set_idx == 0 and image_num in self.template_image_nums:
                    # Green set: Get F1/F2 position from template
                    vowel_data = template_by_image[image_num]
                    f1, f2 = vowel_data['f1'], vowel_data['f2']
                    label_x, label_y = self._hz_to_pixels(f1, f2)
                    label_visible = True
                else:
                    # Blue set or non-template green: start at default position (hidden)
                    f1, f2 = None, None
                    label_x = button_x
                    label_y = button_y
                    label_visible = False
                
                tmp_textbox = RecordingLabel(label_x, label_y, image_filename, f1, f2, label_color)
                tmp_textbox.visible = label_visible
                
                # Add label to list
                self.textboxes.append(tmp_textbox)

    def _hz_to_pixels(self, f1, f2):
        """Convert F1/F2 Hz values to pixel coordinates on vowel plot.
        
        Args:
            f1 (float): F1 frequency in Hz
            f2 (float): F2 frequency in Hz
            
        Returns:
            tuple: (x, y) pixel coordinates

        Notes:
            - If `gui_info['freq_scale'] == 'log'` this uses logarithmic mapping
              (recommended for vowel plots). For linear scale a direct linear
              interpolation is used.
        """
        # Get screen dimensions and F1/F2 ranges from gui_info
        # Get current window width in pixels
        screen_width = self.screen.get_width()
        # Get current window height in pixels
        screen_height = self.screen.get_height()
        
        # Default ranges if not specified
        # Get F1 display range (default 200-1100 Hz for adult vowel space)
        f1_range = self.gui_info.get('f1_range', [200, 1100])
        # Get F2 display range (default 500-2700 Hz for adult vowel space)
        f2_range = self.gui_info.get('f2_range', [500, 2700])
        
        # Check if using logarithmic frequency scale (default for vowel plots)
        use_log = self.gui_info.get('freq_scale', 'linear') == 'log'

        if use_log:
            # Log-space mapping preserves shape under log translations
            # Clamp minimum F2 to prevent log(0) error
            f2_min = max(f2_range[0], 1e-6)
            # Clamp maximum F2 to prevent log(0) error
            f2_max = max(f2_range[1], 1e-6)
            # Clamp minimum F1 to prevent log(0) error
            f1_min = max(f1_range[0], 1e-6)
            # Clamp maximum F1 to prevent log(0) error
            f1_max = max(f1_range[1], 1e-6)

            # Calculate x position in log space: high F2 → left, low F2 → right
            # Ratio of log-distance from max F2 to total log-range
            x_ratio = (math.log(f2_max) - math.log(max(f2, 1e-6))) / (math.log(f2_max) - math.log(f2_min))
            # Convert ratio to pixel position
            x = int(x_ratio * screen_width)

            # Calculate y position in log space: low F1 → top, high F1 → bottom
            # Ratio of log-distance from min F1 to total log-range
            y_ratio = (math.log(max(f1, 1e-6)) - math.log(f1_min)) / (math.log(f1_max) - math.log(f1_min))
            # Convert ratio to pixel position
            y = int(y_ratio * screen_height)
        else:
            # Linear mapping
            # F2 max → left edge, F2 min → right edge
            # Calculate normalized distance from F2 max (0=max, 1=min)
            x_ratio = (f2_range[1] - f2) / (f2_range[1] - f2_range[0])
            # Convert to pixel position (left=0, right=screen_width)
            x = int(x_ratio * screen_width)

            # F1 min → top edge, F1 max → bottom edge
            # Calculate normalized distance from F1 min (0=min, 1=max)
            y_ratio = (f1 - f1_range[0]) / (f1_range[1] - f1_range[0])
            # Convert to pixel position (top=0, bottom=screen_height)
            y = int(y_ratio * screen_height)
        
        # Return (x, y) tuple for plotting
        return x, y

    def _pixels_to_hz(self, x, y):
        """Convert pixel coordinates back to F1/F2 Hz values.

        Args:
            x (float): X position in pixels
            y (float): Y position in pixels

        Returns:
            tuple: (f1_hz, f2_hz)

        Notes:
            - This is the inverse of `_hz_to_pixels` and honors the
              `'freq_scale'` setting in `gui_info`.
        """
        # Get current window dimensions
        screen_width = self.screen.get_width()
        # Get window height
        screen_height = self.screen.get_height()
        # Get F1 display range from config (default 200-1100 Hz)
        f1_range = self.gui_info.get('f1_range', [200, 1100])
        # Get F2 display range from config (default 500-2700 Hz)
        f2_range = self.gui_info.get('f2_range', [500, 2700])

        # Calculate normalized position ratios (0.0 to 1.0)
        # Normalize x to 0-1 range (prevent divide by zero)
        x_ratio = x / max(screen_width, 1)
        # Normalize y to 0-1 range (prevent divide by zero)
        y_ratio = y / max(screen_height, 1)

        # Check if using logarithmic frequency scale
        use_log = self.gui_info.get('freq_scale', 'linear') == 'log'

        if use_log:
            # Get log-space F2 range (clamp to prevent log(0))
            f2_min = max(f2_range[0], 1e-6)
            # Get log-space F2 max (clamp to prevent log(0))
            f2_max = max(f2_range[1], 1e-6)
            # Get log-space F1 min (clamp to prevent log(0))
            f1_min = max(f1_range[0], 1e-6)
            # Get log-space F1 max (clamp to prevent log(0))
            f1_max = max(f1_range[1], 1e-6)

            # Reverse log-space mapping for F2 (x → F2)
            # Calculate log(F2) from x_ratio and log-range
            log_f2 = math.log(f2_max) - x_ratio * (math.log(f2_max) - math.log(f2_min))
            # Convert back to linear Hz
            f2 = math.exp(log_f2)

            # Reverse log-space mapping for F1 (y → F1)
            # Calculate log(F1) from y_ratio and log-range
            log_f1 = math.log(f1_min) + y_ratio * (math.log(f1_max) - math.log(f1_min))
            # Convert back to linear Hz
            f1 = math.exp(log_f1)
        else:
            # Invert linear mapping from _hz_to_pixels
            # Reverse F2 calculation: x_ratio → F2
            f2 = f2_range[1] - x_ratio * (f2_range[1] - f2_range[0])
            # Reverse F1 calculation: y_ratio → F1
            f1 = f1_range[0] + y_ratio * (f1_range[1] - f1_range[0])

        # Return (F1, F2) tuple in Hz
        return f1, f2

    def scale_formants(self, factor):
        """Scale all IPA labels multiplicatively in formant space.

        Args:
            factor (float): Multiplicative scale factor for F1 and F2.
        """
        # Loop through all textbox labels
        for textbox in self.textboxes:
            # Get Hz values (from stored values if available, else from pixels)
            # Check if textbox has stored formant values
            if textbox.f1 is not None and textbox.f2 is not None:
                # Use stored Hz values directly
                f1, f2 = textbox.f1, textbox.f2
            else:
                # Convert current pixel position to Hz values
                f1, f2 = self._pixels_to_hz(textbox.rect.x, textbox.rect.y)
            
            # Apply scaling
            # Multiply F1 by scale factor (e.g., 1.01 = 1% increase)
            f1 *= factor
            # Multiply F2 by scale factor
            f2 *= factor
            
            # Update stored Hz values and pixel position
            # Store scaled F1 value
            textbox.f1 = f1
            # Store scaled F2 value
            textbox.f2 = f2
            # Convert scaled Hz values back to pixel coordinates
            new_x, new_y = self._hz_to_pixels(f1, f2)
            # Update label x position
            textbox.rect.x = new_x
            # Update label y position
            textbox.rect.y = new_y

    def scale_formants_log(self, delta):
        """Scale all IPA labels additively in log space.

        Args:
            delta (float): Additive delta in log space (e.g., 0.01).
        """
        # Small value to prevent log(0) errors
        epsilon = 1e-6
        # Loop through all textbox labels
        for textbox in self.textboxes:
            # Get Hz values (from stored values if available, else from pixels)
            # Check if textbox has stored formant values
            if textbox.f1 is not None and textbox.f2 is not None:
                # Use stored Hz values directly
                f1, f2 = textbox.f1, textbox.f2
            else:
                # Convert current pixel position to Hz values
                f1, f2 = self._pixels_to_hz(textbox.rect.x, textbox.rect.y)
            
            # Apply log-space scaling
            # Clamp F1 to prevent log(0)
            f1 = max(f1, epsilon)
            # Clamp F2 to prevent log(0)
            f2 = max(f2, epsilon)
            # Apply additive shift in log space: log(F1) + delta → F1' = exp(log(F1) + delta)
            f1 = math.exp(math.log(f1) + delta)
            # Apply additive shift in log space: log(F2) + delta → F2' = exp(log(F2) + delta)
            f2 = math.exp(math.log(f2) + delta)
            
            # Update stored Hz values and pixel position
            # Store scaled F1 value in Hz
            textbox.f1 = f1
            # Store scaled F2 value in Hz
            textbox.f2 = f2
            # Convert scaled Hz values back to pixel coordinates
            new_x, new_y = self._hz_to_pixels(f1, f2)
            # Update label x position
            textbox.rect.x = new_x
            # Update label y position
            textbox.rect.y = new_y

    def run_ipa_buttons(self, event_holder, state):
        """Handle IPA button rendering and click events based on current state.
        
        Args:
            event_holder: EventHolder instance containing current events
            state (str): Current mode ('menu' or 'recording')
        """
        # Menu mode: display clickable buttons
        if state == "menu":
            # Check if mouse button was pressed this frame
            if event_holder.left_click_down is not None:
                # Loop through all buttons to check for clicks
                for idx, bttn in enumerate(self.buttons):
                    # Check if click position is inside button rectangle
                    if bttn.rect.collidepoint(event_holder.left_click_down.pos):
                        # Toggle the clicked state (True ↔ False)
                        bttn.clicked = not bttn.clicked
                        # Toggle corresponding label visibility (show/hide)
                        self.textboxes[idx].visible = not self.textboxes[idx].visible

            # Draw all buttons on screen
            # Loop through all buttons and render them
            for bttn in self.buttons:
                # Draw button image at its position
                bttn.draw(self.screen)

        # Recording mode: display draggable labels
        elif state == "recording":
            # Track if any label is currently being dragged
            # Flag to prevent multiple labels from being dragged simultaneously
            any_dragging = False
            
            # Loop through all textbox labels
            for txtbx in self.textboxes:
                # Track if label was dragging before event handling
                # Save previous dragging state to detect drag end
                was_dragging = txtbx.is_dragging
                
                # Only allow first label to respond to new click
                # Pass any_dragging flag to prevent multiple simultaneous drags
                txtbx.handle_event(event_holder, any_dragging)
                
                # Update Hz values if label was just released from dragging
                # Check if drag operation just ended this frame
                if was_dragging and not txtbx.is_dragging:
                    # Convert final pixel position back to Hz values
                    txtbx.f1, txtbx.f2 = self._pixels_to_hz(txtbx.rect.x, txtbx.rect.y)
                
                # Check if this label is now dragging
                if txtbx.is_dragging:
                    # Set flag to prevent other labels from starting drags
                    any_dragging = True
                
                # Draw this label if visible
                txtbx.draw(self.screen)

    def handle_resize(self, old_w, old_h, new_w, new_h):
        """Scale and reposition textboxes to fit resized window.
        
        Args:
            old_w (int): Previous window width in pixels
            old_h (int): Previous window height in pixels
            new_w (int): New window width in pixels
            new_h (int): New window height in pixels
        """
        # Loop through all textbox labels
        for textbox in self.textboxes:
            # If textbox has stored Hz values, use those to recalculate position
            # Check if formant frequencies are stored (preferred method)
            if textbox.f1 is not None and textbox.f2 is not None:
                # Recalculate pixel position from Hz values (preserves formant location)
                new_x, new_y = self._hz_to_pixels(textbox.f1, textbox.f2)
                # Update textbox x position
                textbox.rect.x = new_x
                # Update textbox y position
                textbox.rect.y = new_y
            else:
                # Otherwise, scale pixel position proportionally
                # Use proportional scaling if no Hz values available
                textbox.handle_resize(old_w, old_h, new_w, new_h)

class MenuButton:
    """A clickable button that displays different images based on state (clicked/unclicked).
    
    Loads both a colored (clicked) and black (unclicked) version of the IPA symbol image.
    
    Args:
        x (int): X coordinate of button position
        y (int): Y coordinate of button position
        width (int): Button width in pixels
        height (int): Button height in pixels
        image_filename (str): Filename for button image (e.g., "1.png")
        toggle_color (str): Color for toggled state ('green' or 'blue')
    """

    def __init__(self, x, y, width, height, image_filename="button.png", toggle_color="green"):
        self.filename = image_filename
        self.rect = pygame.Rect(x, y, width, height)
        self.clicked = False  # Track whether the button is currently clicked
        self.toggle_color = toggle_color  # Store which color to use for toggle

        # Try to get PyInstaller bundled resource path first
        self.is_bundled = False
        try:
            # When bundled as exe, resources are in _MEIPASS temp directory
            self.base_path = sys._MEIPASS
            self.is_bundled = True
        except AttributeError:
            # In normal Python, use module directory
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        # Cache both colored and black button images to avoid reloading every frame
        self._load_images()

    def _load_images(self):
        """Load and cache both button image variants (colored and black).

        Images are looked up in an `images/` directory relative to the project or
        under the PyInstaller `_MEIPASS` directory when bundled. If image files
        are missing a small colored placeholder surface is created so the UI
        remains functional.
        """
        # This will find the images regardless of whether you are in a script or EXE
        black_path = get_resource_path(os.path.join("VocalTrack", "images", "black", self.filename))
        color_path = get_resource_path(os.path.join("VocalTrack", "images", self.toggle_color, self.filename))
        
        try:
            self.image_black = pygame.image.load(black_path).convert_alpha()
            self.image_black = pygame.transform.scale(self.image_black, (40, 38))
            self.image_colored = pygame.image.load(color_path).convert_alpha()
            self.image_colored = pygame.transform.scale(self.image_colored, (40, 38))
        except OSError:
            # If images not found, create placeholder colored rectangles
            self.image_black = pygame.Surface((40, 38))
            self.image_black.fill((30, 30, 30))
            self.image_colored = pygame.Surface((40, 38))
            # Use appropriate color for placeholder
            color_rgb = (50, 150, 50) if self.toggle_color == 'green' else (50, 100, 200)
            self.image_colored.fill(color_rgb)

    def draw(self, screen):
        """Draw the button on screen using appropriate image based on clicked state.
        
        Args:
            screen (pygame.Surface): Display surface to draw button on
        """
        # Select appropriate image based on button state
        image = self.image_colored if self.clicked else self.image_black
        screen.blit(image, self.rect.topleft)


class RecordingLabel:
    """A draggable label widget that displays an IPA symbol image during recording sessions.
    
    Shows a colored image that stays visible during recording mode and can be
    repositioned by the user.
    
    Args:
        x (int): Initial X coordinate in pixels
        y (int): Initial Y coordinate in pixels
        image_filename (str): Image filename for the label (e.g., "1.png")
        f1 (float, optional): F1 frequency in Hz
        f2 (float, optional): F2 frequency in Hz
        label_color (str): Color for the label ('green' or 'blue')
    """

    def __init__(self, x, y, image_filename="1.png", f1=None, f2=None, label_color="green"):
        # Store image filename for loading
        self.filename = image_filename
        # Create rectangle for positioning and collision detection
        self.rect = pygame.Rect(x, y, 80, 70)
        
        # Store formant values in Hz (to avoid pixel rounding errors)
        self.f1 = f1
        self.f2 = f2
        
        # Store label color
        self.label_color = label_color

        # Offset from mouse position when dragging (for smooth drag)
        self.offset_x = 0
        self.offset_y = 0

        # Flag to track whether label is currently being dragged
        self.is_dragging = False

        # Label starts invisible - only shown when button is clicked in menu
        self.visible = False

        # Use the same get_resource_path helper as MenuButton
        # This matches the internal EXE structure: VocalTrack/images/[color]/[file]
        image_path = get_resource_path(os.path.join("VocalTrack", "images", label_color, image_filename))
        
        try:
            self.image_original = pygame.image.load(image_path).convert_alpha()
            self.image = pygame.transform.scale(self.image_original, (60, 56))
        except OSError:
            # This is what you were seeing! If the path above is wrong, it draws a box:
            logger.error(f"RecordingLabel failed to load: {image_path}")
            self.image_original = pygame.Surface((60, 56))
            color_rgb = (50, 150, 50) if label_color == 'green' else (50, 100, 200)
            self.image_original.fill(color_rgb)
            self.image = self.image_original



    def draw(self, screen):
        """Draw the label on screen if visible.
        
        Args:
            screen (pygame.Surface): Display surface to draw on
        """
        if self.visible:
            screen.blit(self.image, self.rect.topleft)

    def handle_event(self, event_holder, textbox_moving):
        """Process mouse events for dragging the label during recording mode.
        
        Args:
            event_holder (EventHolder): Object containing current frame's events
            textbox_moving (bool): Whether any textbox is currently being dragged
        """
        # Only process events if no other textbox is currently moving
        if not textbox_moving:
            # Check for left mouse button press
            if event_holder.left_click_down is not None:
                # Check if click is on this label
                if self.rect.collidepoint(event_holder.left_click_down.pos):
                    # Start dragging this label
                    self.is_dragging = True
                    # Get mouse position at click
                    mouse_x, mouse_y = event_holder.left_click_down.pos
                    # Calculate offset from label position to mouse (for smooth dragging)
                    self.offset_x = self.rect.x - mouse_x
                    self.offset_y = self.rect.y - mouse_y

            # Check for mouse movement
            if event_holder.mouse_move is not None:
                # If this label is being dragged, update its position
                if self.is_dragging:
                    # Get current mouse position
                    mouse_x, mouse_y = event_holder.mouse_move.pos
                    # Update label position to follow mouse, maintaining offset
                    self.rect.x = mouse_x + self.offset_x
                    self.rect.y = mouse_y + self.offset_y

            # Check for left mouse button release
            if event_holder.left_click_up is not None:
                # Stop dragging this label
                self.is_dragging = False

    def handle_resize(self, old_w, old_h, new_w, new_h):
        """Scale label position proportionally when window is resized.
        
        Args:
            old_w (int): Previous window width in pixels
            old_h (int): Previous window height in pixels
            new_w (int): New window width in pixels
            new_h (int): New window height in pixels
        """
        # Scale x position proportionally to width change
        self.rect.x = int(self.rect.x * (new_w / old_w))
        # Scale y position proportionally to height change
        self.rect.y = int(self.rect.y * (new_h / old_h))

