# Import pygame for event handling (mouse, keyboard, window events)
import pygame

# Disable pylint warning about pygame members (they exist but pylint doesn't detect them)
# pylint: disable=no-member

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
        self.right_click_up = None    # Right mouse button released
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
        self.ctrl_h = None            # Ctrl+H pressed (toggle help overlay)
        self.g_key = None             # G pressed (toggle grid)
        self.h_key = None             # H pressed (toggle help)
        self.ctrl_t = None            # Ctrl+T pressed (toggle template vowels)
        self.space_down = None        # Space pressed (start recording)
        self.space_up = None          # Space released (stop recording)
        self.l_key = None             # L pressed (toggle log/linear frequency scale)

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
                elif event.button == 3:
                    # Right mouse button (button==3) released
                    self.right_click_up = event
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
                if event.mod & pygame.KMOD_CTRL and event.key == pygame.K_v:
                    # Ctrl+V pressed - toggle between menu and recording mode
                    self.ctrl_v = event
                elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_t:
                    # Ctrl+T pressed - toggle vowel template
                    self.ctrl_t = event
                elif event.mod & pygame.KMOD_CTRL and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    # Ctrl+Plus pressed - increase gain
                    self.ctrl_plus = event
                elif event.mod & pygame.KMOD_CTRL and event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    # Ctrl+Minus pressed - decrease gain
                    self.ctrl_minus = event
                elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_h:
                    # Ctrl+H pressed - toggle help overlay
                    self.ctrl_h = event
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
                elif event.key == pygame.K_g:
                    # G pressed (toggle grid)
                    self.g_key = event
                elif event.key == pygame.K_h:
                    # H pressed (toggle help)
                    self.h_key = event
                elif event.key == pygame.K_l:
                    # L pressed (toggle log/linear frequency scale)
                    self.l_key = event
                elif event.key == pygame.K_SPACE:
                    # Space pressed (start recording)
                    self.space_down = event
            elif event.type == pygame.KEYUP:
                # Keyboard key released
                if event.key == pygame.K_SPACE:
                    # Space released (stop recording)
                    self.space_up = event
