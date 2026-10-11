# Import pygame for event handling (mouse, keyboard, window events)
import pygame

# Disable pylint warning about pygame members (they exist but pylint doesn't detect them)
# pylint: disable=no-member

# Number keys 1-5 (top row and keypad), used for the formant markers in LiveSpectrum
NUMBER_KEYS = {
    1: (pygame.K_1, pygame.K_KP1),
    2: (pygame.K_2, pygame.K_KP2),
    3: (pygame.K_3, pygame.K_KP3),
    4: (pygame.K_4, pygame.K_KP4),
    5: (pygame.K_5, pygame.K_KP5),
}


class EventHolder:
    """
    Processes and stores pygame events for easy access in the main loop.

    This class parses the pygame event queue and stores relevant events (mouse clicks, keyboard 
    shortcuts, window events, etc.) as attributes for simple checking. Instead of looping through 
    all events every time this needs to be queried, you can check specific attributes (e.g., ctrl_v, 
    left_click_down). Handles both mouse and keyboard events, including modifier keys (Ctrl, Shift).
    """
    def __init__(self, events):
        """
        Initialize EventHolder by parsing a list of pygame events.

        Args:
            events (list): List of pygame events from pygame.event.get()
        """
        # Store the complete list of pygame events
        self.events = events
        # Initialize all event attributes to None (will be set if event occurs)
        self.right_click_down = None  # Right mouse button pressed
        self.left_click_down = None   # Left mouse button pressed
        self.left_click_up = None     # Left mouse button released
        self.left_scroll_up = None    # Mouse scroll wheel up
        self.left_scroll_down = None  # Mouse scroll wheel down
        self.mouse_move = None        # Mouse moved
        self.quit = None              # Window close button clicked
        self.resize = None            # Window resized
        self.ctrl_v = None            # Ctrl+V pressed (toggle menu/recording)
        self.backspace = None         # Backspace pressed (undo last track)
        self.delete = None            # Delete pressed (clear all tracks)
        self.escape = None            # Escape pressed (quit)
        self.plus_equals = None       # Plus/equals pressed (increase threshold)
        self.minus_underscore = None  # Minus/underscore pressed (decrease threshold)
        self.ctrl_plus = None         # Ctrl+Plus pressed (increase gain)
        self.ctrl_minus = None        # Ctrl+Minus pressed (decrease gain)
        self.ctrl_h = None            # Ctrl+? pressed (toggle help overlay)
        self.ctrl_s = None            # Ctrl+S pressed (save current IPA template)
        self.ctrl_g = None            # Ctrl+G pressed (toggle grid)
        self.ctrl_l = None            # Ctrl+L pressed (toggle log scale / LPC overlay)
        self.ctrl_t = None            # Ctrl+T pressed (toggle template vowels)
        self.ctrl_p = None            # Ctrl+P pressed (toggle performance overlay)
        self.bracket_left = None      # [ pressed (decrease max formant)
        self.bracket_right = None     # ] pressed (increase max formant)
        self.ctrl_bracket_left = None # Ctrl+[ or Ctrl+Down
        self.ctrl_bracket_right = None # Ctrl+] or Ctrl+Up
        self.space_down = None        # Space pressed (start recording)
        self.number_pressed = None    # Number key 1-5 pressed this frame (no Ctrl/Cmd/Alt), as an int

        # Current state of keys and mouse (not events): read here so the visualizers never query
        # pygame directly
        self.shift_held = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)  # Shift is held down
        self.left_mouse_held = bool(pygame.mouse.get_pressed()[0])          # Left mouse button is held
        self.mouse_pos = pygame.mouse.get_pos()                             # Mouse position (x, y)
        held_keys = pygame.key.get_pressed()
        # Number key 1-5 held down (lowest first), as an int, or None
        self.number_held = next((n for n, keys in NUMBER_KEYS.items()
                                 if any(held_keys[k] for k in keys)), None)

        # Treat Ctrl and Command (Meta) as equivalent for cross-platform shortcuts.
        modifier_mask = pygame.KMOD_CTRL | pygame.KMOD_META

        # Parse all events and set attributes for relevant ones
        for event in self.events:
            # Check event type and store if relevant
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Mouse button pressed
                if event.button == 1:
                    self.left_click_down = event
                elif event.button == 3:
                    self.right_click_down = event
                elif event.button == 4:
                    self.left_scroll_up = event
                elif event.button == 5:
                    self.left_scroll_down = event
            elif event.type == pygame.MOUSEWHEEL:
                # Mouse wheel event (pygame 2+)
                if event.y > 0:
                    self.left_scroll_up = event
                elif event.y < 0:
                    self.left_scroll_down = event
            elif event.type == pygame.MOUSEBUTTONUP:
                # Mouse button released
                if event.button == 1:
                    # Left mouse button (button==1) released
                    self.left_click_up = event
            elif event.type == pygame.MOUSEMOTION:
                # Mouse moved (contains position and relative motion info)
                self.mouse_move = event
            elif event.type == pygame.QUIT:
                # User clicked close button on window
                self.quit = event
            elif event.type == pygame.VIDEORESIZE:
                # Window was resized (contains new width and height)
                self.resize = event
            elif event.type == pygame.KEYDOWN:
                # Keyboard key pressed
                if event.mod & modifier_mask and event.key == pygame.K_v:
                    # Ctrl+V pressed - toggle between menu and recording mode
                    self.ctrl_v = event
                elif event.mod & modifier_mask and event.key == pygame.K_t:
                    # Ctrl+T pressed - toggle vowel template
                    self.ctrl_t = event
                elif event.mod & modifier_mask and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    # Ctrl+Plus pressed - increase gain
                    self.ctrl_plus = event
                elif event.mod & modifier_mask and event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    # Ctrl+Minus pressed - decrease gain
                    self.ctrl_minus = event
                elif event.mod & modifier_mask and (event.key in (pygame.K_QUESTION, pygame.K_SLASH) or getattr(event, 'unicode', '') == '?'):
                    # Ctrl+? pressed - toggle help overlay
                    self.ctrl_h = event
                elif event.mod & modifier_mask and event.key == pygame.K_s:
                    # Ctrl+S pressed - save current IPA template
                    self.ctrl_s = event
                elif event.mod & modifier_mask and event.key == pygame.K_g:
                    # Ctrl+G pressed - toggle grid
                    self.ctrl_g = event
                elif event.mod & modifier_mask and event.key == pygame.K_l:
                    # Ctrl+L pressed - toggle log/linear frequency scale
                    self.ctrl_l = event
                elif event.mod & modifier_mask and event.key == pygame.K_p:
                    # Ctrl+P pressed - toggle performance overlay
                    self.ctrl_p = event
                elif event.mod & modifier_mask and event.key in (pygame.K_LEFTBRACKET, pygame.K_DOWN):
                    # Ctrl+[ or Ctrl+Down - decrease max formant
                    self.ctrl_bracket_left = event
                elif event.mod & modifier_mask and event.key in (pygame.K_RIGHTBRACKET, pygame.K_UP):
                    # Ctrl+] or Ctrl+Up - increase max formant
                    self.ctrl_bracket_right = event
                elif event.key == pygame.K_LEFTBRACKET:
                    # [ pressed - decrease max formant
                    self.bracket_left = event
                elif event.key == pygame.K_RIGHTBRACKET:
                    # ] pressed - increase max formant
                    self.bracket_right = event
                elif event.key == pygame.K_BACKSPACE:
                    # Backspace pressed (undo last track)
                    self.backspace = event
                elif event.key == pygame.K_DELETE:
                    # Delete pressed (clear all tracks)
                    self.delete = event
                elif event.key == pygame.K_ESCAPE:
                    # Escape pressed (quit)
                    self.escape = event
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    # Plus/equals pressed (increase threshold)
                    self.plus_equals = event
                elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    # Minus/underscore pressed (decrease threshold)
                    self.minus_underscore = event
                elif event.key == pygame.K_SPACE:
                    # Space pressed (start recording)
                    self.space_down = event
                elif not (event.mod & (modifier_mask | pygame.KMOD_ALT)):
                    # Number key 1-5 (top row or keypad) pressed (formant markers in LiveSpectrum);
                    # the last one pressed this frame wins
                    for n, keys in NUMBER_KEYS.items():
                        if event.key in keys:
                            self.number_pressed = n
