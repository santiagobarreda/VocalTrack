# Import os for file path operations
import os
# Import sys for accessing PyInstaller temp directory when bundled as exe
import sys
# Import json for reading template files
import json
# Import math for log-space scaling
import math
import logging
# Import pygame for image loading and GUI rendering
import pygame

logger = logging.getLogger(__name__)


# The IPA vowel images (1-30): symbol, keyword and description of each. The images are in IPA
# chart order, followed by the two r-colored vowels
IPA_IMAGE_INFO = {
    1: {'symbol': 'i', 'name': 'fleece', 'description': 'Close front unrounded vowel'},
    2: {'symbol': 'y', 'name': 'French u', 'description': 'Close front rounded vowel'},
    3: {'symbol': 'ɨ', 'name': 'roses / Russian yery', 'description': 'Close central unrounded vowel'},
    4: {'symbol': 'ʉ', 'name': 'Swedish u', 'description': 'Close central rounded vowel'},
    5: {'symbol': 'ɯ', 'name': 'Japanese u', 'description': 'Close back unrounded vowel'},
    6: {'symbol': 'u', 'name': 'goose', 'description': 'Close back rounded vowel'},
    7: {'symbol': 'ɪ', 'name': 'kit', 'description': 'Near-close near-front unrounded vowel'},
    8: {'symbol': 'ʏ', 'name': 'German hübsch', 'description': 'Near-close near-front rounded vowel'},
    9: {'symbol': 'ʊ', 'name': 'foot', 'description': 'Near-close near-back rounded vowel'},
    10: {'symbol': 'e', 'name': 'face', 'description': 'Close-mid front unrounded vowel'},
    11: {'symbol': 'ø', 'name': 'French peu / German schön', 'description': 'Close-mid front rounded vowel'},
    12: {'symbol': 'ɘ', 'name': 'Close-mid central unrounded', 'description': 'Close-mid central unrounded vowel'},
    13: {'symbol': 'ɵ', 'name': 'Swedish dumt', 'description': 'Close-mid central rounded vowel'},
    14: {'symbol': 'ɤ', 'name': 'Mandarin e', 'description': 'Close-mid back unrounded vowel'},
    15: {'symbol': 'o', 'name': 'goat', 'description': 'Close-mid back rounded vowel'},
    16: {'symbol': 'ə', 'name': 'schwa / comma', 'description': 'Mid central vowel (schwa)'},
    17: {'symbol': 'ɛ', 'name': 'dress', 'description': 'Open-mid front unrounded vowel'},
    18: {'symbol': 'œ', 'name': 'French neuf / German Hölle', 'description': 'Open-mid front rounded vowel'},
    19: {'symbol': 'ɜ', 'name': 'nurse', 'description': 'Open-mid central unrounded vowel'},
    20: {'symbol': 'ɞ', 'name': 'Irish bird', 'description': 'Open-mid central rounded vowel'},
    21: {'symbol': 'ʌ', 'name': 'strut', 'description': 'Open-mid back unrounded vowel'},
    22: {'symbol': 'ɔ', 'name': 'thought / caught', 'description': 'Open-mid back rounded vowel'},
    23: {'symbol': 'æ', 'name': 'trap / bad', 'description': 'Near-open front unrounded vowel'},
    24: {'symbol': 'ɐ', 'name': 'German aber', 'description': 'Near-open central vowel'},
    25: {'symbol': 'a', 'name': 'Spanish a / German Vater', 'description': 'Open front unrounded vowel'},
    26: {'symbol': 'ɶ', 'name': 'Open front rounded', 'description': 'Open front rounded vowel'},
    27: {'symbol': 'ɑ', 'name': 'father / lot', 'description': 'Open back unrounded vowel'},
    28: {'symbol': 'ɒ', 'name': 'British lot / cloth', 'description': 'Open back rounded vowel'},
    29: {'symbol': 'ɚ', 'name': 'letter (American English)', 'description': 'R-colored mid central vowel'},
    30: {'symbol': 'ɝ', 'name': 'nurse (American English)', 'description': 'R-colored open-mid central unrounded vowel'},
}

# Image number -> IPA symbol, and IPA symbol -> image number
IPA_IMAGE_MAP = {image_num: info['symbol'] for image_num, info in IPA_IMAGE_INFO.items()}
SYMBOL_TO_IMAGE_MAP = {symbol: image_num for image_num, symbol in IPA_IMAGE_MAP.items()}

# Project root: the folder containing the VocalTrack package (not the current working directory,
# so images and templates are found wherever VocalTrack is started from)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path):
    """
    Absolute path to a file bundled with the program (e.g. "VocalTrack/images/green/1.png"),
    relative to the project root, or to the PyInstaller bundle folder when running as an .exe.
    """
    base_path = getattr(sys, '_MEIPASS', _PROJECT_ROOT)
    return os.path.join(base_path, relative_path)


def get_external_path(relative_path):
    """
    Absolute path to a user-editable file (e.g. "templates/..."), relative to the project root,
    or to the folder holding the .exe when running as an .exe.
    """
    base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else _PROJECT_ROOT
    return os.path.join(base_path, relative_path)


def _first_template(directory, default_name):
    """The default template in a folder if it is there (matching its name without regard to
    upper/lower case, which differs between file systems), otherwise the first template in
    alphabetical order, or None if the folder has no templates."""
    json_files = sorted((f for f in os.listdir(directory) if f.endswith('.json')), key=str.lower)
    for fname in json_files:
        if fname.lower() == f"{default_name}.json".lower():
            return os.path.join(directory, fname)
    return os.path.join(directory, json_files[0]) if json_files else None


def find_template_file(template_dir="templates", default_name=None):
    """Locate the active vowel template JSON file, checking project data_dir first.

    Used when the selected template cannot be found: the default template if it is there,
    otherwise the first template in alphabetical order."""
    if default_name is None:
        from VocalTrack import config as _config
        default_name = os.path.splitext(_config.FACTORY_LIVEVOWEL_CONFIG['template_file'])[0]
    # 0. Check project data_dir first if configured
    try:
        from VocalTrack import config
        data_dir = config.EXPORT_CONFIG.get('data_dir', '.')
        if data_dir and data_dir != '.':
            proj_dir = os.path.join(data_dir, template_dir)
            if os.path.isdir(proj_dir):
                return _first_template(proj_dir, default_name)
            # When a subject folder is configured, DO NOT fall back to main templates!
            return None
    except Exception:
        pass

    # 1. The default template, or else the first template in the main templates folder
    full_dir = get_external_path(template_dir)
    if os.path.isdir(full_dir):
        return _first_template(full_dir, default_name)

    return None


class IPALabels:
    """Manage IPA vowel buttons (menu) and draggable vowel labels (recording).

    IPA vowel label buttons and draggable labels for annotating vowel space.
    This module provides two UI building blocks used by the vowel GUI:
    - `MenuButton`: a small clickable button showing an IPA symbol image (black/colored)
    - `RecordingLabel`: a draggable, larger label used to annotate the vowel plot

    Resource expectations:
    - IPA symbol images are loaded from an `images/` directory at runtime.
    - Vowel template JSON files (formant reference values) live in the `templates/` folder.

    Args:
        screen (pygame.Surface): Display surface to draw buttons/labels on.
        template_path (str, optional): Path to template JSON file. If None, auto-discovered.
        gui_info (dict, optional): GUI configuration dict used for Hz↔pixel conversions.
    """
    def __init__(self, screen, template_path=None, gui_info=None):
        # Store reference to pygame display surface
        self.screen = screen
        # Store GUI info for Hz-to-pixel conversion
        self.gui_info = gui_info or {}

        # Locate active template file if not specified
        if template_path is None:
            if self.gui_info.get('template_file') in ('None', 'none'):
                template_path = None
            else:
                template_path = find_template_file()
        elif template_path in ('None', 'none', ''):
            template_path = None

        # Store active template path so runtime edits can be persisted
        self.template_path = template_path

        # Parse template to get vowels and their F1/F2 positions
        self.template_data = self._load_template(template_path) if template_path else []
        # Create set of image numbers in template for quick lookup
        self.template_image_nums = {v['image_num'] for v in self.template_data}
        
        # List to store all menu button objects
        self.buttons = []
        # List to store all recording label objects
        self.textboxes = []
        
        # Create buttons and labels for ALL 30 available images
        self._create_buttons_and_labels()

    def save_current_template(self, file_path=None):
        """Persist the current green IPA template toggles and positions to JSON.

        The first 30 buttons/labels are the green template set. Any green label whose
        button is currently toggled on is written to the template with its current F1/F2
        position in Hz and full phonetic metadata.

        Args:
            file_path (str, optional): Output template path. If None, saves to a new
                timestamped template file (custom_template_YYYY-MM-DD_HHMMSS.json) to
                prevent overwriting active reference templates.

        Returns:
            tuple: (success: bool, output_path: str, saved_count: int)
        """
        from datetime import datetime

        if file_path is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            filename = f"custom_template_{timestamp}.json"

            # Determine destination directory:
            # 1. Directory of current self.template_path if valid
            # 2. Configured project data_dir/templates
            # 3. Base application templates directory
            target_dir = None
            if self.template_path and os.path.dirname(self.template_path):
                candidate_dir = os.path.dirname(self.template_path)
                if os.path.isdir(candidate_dir):
                    target_dir = candidate_dir

            if not target_dir:
                try:
                    from VocalTrack import config
                    data_dir = config.EXPORT_CONFIG.get('data_dir', '.')
                    if data_dir and data_dir != '.':
                        target_dir = os.path.join(data_dir, "templates")
                except Exception:
                    pass

            if not target_dir:
                target_dir = get_external_path("templates")

            output_path = os.path.abspath(os.path.join(target_dir, filename))
        else:
            output_path = file_path
            if not output_path.endswith('.json'):
                output_path = output_path + '.json'
            output_path = os.path.abspath(output_path)

        vowel_entries = []
        for idx in range(30):
            button = self.buttons[idx]
            textbox = self.textboxes[idx]
            if not button.clicked:
                continue

            image_num = idx + 1
            info = IPA_IMAGE_INFO.get(image_num, {})
            symbol = info.get('symbol', IPA_IMAGE_MAP.get(image_num, ''))
            name = info.get('name', '')
            desc = info.get('description', '')

            if textbox.f1 is not None and textbox.f2 is not None:
                f1_hz, f2_hz = round(float(textbox.f1), 1), round(float(textbox.f2), 1)
            else:
                f1_calc, f2_calc = self._pixels_to_hz(*textbox.rect.center)
                f1_hz, f2_hz = round(float(f1_calc), 1), round(float(f2_calc), 1)

            vowel_entries.append({
                "image_num": image_num,
                "symbol": symbol,
                "name": name,
                "description": desc,
                "f1": f1_hz,
                "f2": f2_hz
            })

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            template_obj = {
                "name": f"Custom Vowel Template ({now_str})",
                "description": f"User-configured vowel targets saved from LiveVowel on {now_str}",
                "vowels": vowel_entries
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template_obj, f, indent=2, ensure_ascii=False)
        except OSError:
            return False, output_path, len(vowel_entries)

        self.template_path = output_path
        self.template_data = self._load_template(output_path)
        self.template_image_nums = {v['image_num'] for v in self.template_data}

        return True, output_path, len(vowel_entries)

    @staticmethod
    def _load_template(file_path):
        """Load vowel template data from a JSON file.

        Returns:
            list: List of dicts with keys: 'image_num', 'symbol', 'name', 'description', 'f1', 'f2'
        """
        if not file_path or not os.path.exists(file_path):
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            vowels_list = data.get('vowels', data) if isinstance(data, dict) else data
            vowels = []
            used_image_nums = set()
            for entry in vowels_list:
                if not isinstance(entry, dict):
                    continue
                symbol = str(entry.get('symbol', entry.get('ipa', entry.get('letter', '')))).strip()
                img_num = entry.get('image_num')
                if img_num is None:
                    if symbol in SYMBOL_TO_IMAGE_MAP:
                        img_num = SYMBOL_TO_IMAGE_MAP[symbol]
                    elif symbol.lower() in SYMBOL_TO_IMAGE_MAP:
                        img_num = SYMBOL_TO_IMAGE_MAP[symbol.lower()]
                    else:
                        # No image for this symbol: skip it (don't draw it as another vowel)
                        logger.warning(f"Template {os.path.basename(file_path)}: no IPA image for symbol "
                                       f"{symbol!r}, skipping it")
                        continue
                else:
                    img_num = int(img_num)
                # Each image is one label, so a second vowel with the same symbol would replace the first
                if img_num in used_image_nums:
                    logger.warning(f"Template {os.path.basename(file_path)}: symbol {symbol!r} appears more "
                                   f"than once, keeping the first")
                    continue

                try:
                    f1 = float(entry.get('f1', entry.get('F1', 0)))
                    f2 = float(entry.get('f2', entry.get('F2', 0)))
                    if f1 > 0 and f2 > 0:
                        used_image_nums.add(img_num)
                        vowels.append({
                            'image_num': img_num,
                            'symbol': symbol or IPA_IMAGE_MAP.get(img_num, ''),
                            'name': entry.get('name', entry.get('keyword', '')),
                            'description': entry.get('description', ''),
                            'f1': f1,
                            'f2': f2
                        })
                except (ValueError, TypeError):
                    continue
            return vowels
        except Exception as e:
            logger.warning(f"Could not read vowel template {file_path}: {e}")
            return []

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
                    tmp_button.clicked = is_template and self.gui_info.get('show_vowel_template', False)
                else:  # Blue set
                    tmp_button.clicked = False
                
                self.buttons.append(tmp_button)
                
                # Create corresponding recording label
                if set_idx == 0 and image_num in self.template_image_nums:
                    # Green set: Get F1/F2 position from template
                    vowel_data = template_by_image[image_num]
                    f1, f2 = vowel_data['f1'], vowel_data['f2']
                    label_x, label_y = self._hz_to_pixels(f1, f2)
                    label_visible = self.gui_info.get('show_vowel_template', False)
                else:
                    # Blue set or non-template green: start at default position (hidden)
                    f1, f2 = None, None
                    label_x = button_x
                    label_y = button_y
                    label_visible = False
                
                tmp_textbox = RecordingLabel(label_x, label_y, image_filename, f1, f2, label_color)
                if f1 is not None and f2 is not None:
                    # Labels with a formant position are placed by their center (the symbol's center)
                    tmp_textbox.rect.center = (label_x, label_y)
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
        # Get F1 display range (default 200-1200 Hz for adult vowel space)
        f1_range = self.gui_info.get('f1_range', [200, 1200])
        # Get F2 display range (default 500-3000 Hz for adult vowel space)
        f2_range = self.gui_info.get('f2_range', [500, 3000])
        
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
        # Get F1 display range from config (default 200-1200 Hz)
        f1_range = self.gui_info.get('f1_range', [200, 1200])
        # Get F2 display range from config (default 500-3000 Hz)
        f2_range = self.gui_info.get('f2_range', [500, 3000])

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
                f1, f2 = self._pixels_to_hz(*textbox.rect.center)
            
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
            textbox.rect.center = self._hz_to_pixels(f1, f2)

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
                f1, f2 = self._pixels_to_hz(*textbox.rect.center)
            
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
            textbox.rect.center = self._hz_to_pixels(f1, f2)

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
                    txtbx.f1, txtbx.f2 = self._pixels_to_hz(*txtbx.rect.center)
                
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
                textbox.rect.center = self._hz_to_pixels(textbox.f1, textbox.f2)
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

        # Cache both colored and black button images to avoid reloading every frame
        self._load_images()

    def _load_images(self):
        """Load and cache both button image variants (colored and black).

        Images are found with get_resource_path (the project folder, or the
        PyInstaller bundle when running as an .exe). If image files
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
        # Rectangle for positioning and collision detection, the same size as the drawn image
        # so rect.center is the symbol's center (the point that corresponds to f1/f2)
        self.rect = pygame.Rect(x, y, 60, 56)
        
        # Store formant values in Hz (to avoid pixel rounding errors)
        self.f1 = f1
        self.f2 = f2
        
        # Offset from mouse position when dragging (for smooth drag)
        self.offset_x = 0
        self.offset_y = 0

        # Flag to track whether label is currently being dragged
        self.is_dragging = False

        # Label starts invisible - only shown when button is clicked in menu
        self.visible = False

        # Same image location as MenuButton: VocalTrack/images/[color]/[file]
        image_path = get_resource_path(os.path.join("VocalTrack", "images", label_color, image_filename))
        
        try:
            self.image_original = pygame.image.load(image_path).convert_alpha()
            self.image = pygame.transform.scale(self.image_original, (60, 56))
        except OSError:
            # Image missing: draw a plain colored box instead
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

