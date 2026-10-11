"""Settings persistence manager for VocalTrack."""

# Import json module for JSON serialization/deserialization of settings
import json
# Import os for file path and directory operations
import os
# Import sys to detect PyInstaller frozen state and get executable path
import sys
# Import Path for object-oriented file path manipulation
from pathlib import Path
# Import config for translating old analysis method names in loaded settings
from . import config

class SettingsManager:
    """Manages loading and saving application settings to/from JSON file."""
    
    def __init__(self, settings_file=None):
        """Initialize settings manager.
        
        Args:
            settings_file (str, optional): Path to settings JSON file.
                If None, uses default location in the project folder.
        """
        # Check if settings_file path was explicitly provided
        if settings_file is None:
            settings_file = self._default_settings_file()

        # The main settings file. It always records which subject/data folder is active
        # (in its 'recording' section) so the folder is restored on the next startup.
        self.root_settings_file = settings_file
        # The file currently being read/written (the root file, or a subject/data folder's file)
        self.settings_file = settings_file
        # Resolved path of the active subject/data folder (None = project root)
        self.project_dir = None
        # Load settings from file (or create empty dict if file doesn't exist)
        self.settings = self.load()
        # If settings file doesn't exist yet, create it with current (empty) settings
        if not os.path.exists(self.settings_file):
            self.save()

    @staticmethod
    def _default_settings_file():
        """Return the default settings path: next to the executable when bundled, else the project root."""
        if getattr(sys, "frozen", False):
            # Bundled app: store settings next to the executable.
            base_dir = Path(sys.executable).resolve().parent
        else:
            # Project root: parent directory of this module's folder (VocalTrack/)
            base_dir = Path(__file__).resolve().parent.parent
        return str(base_dir / ".VocalTrack_settings.json")

    def switch_project_dir(self, project_dir):
        """Switch the active settings file to a specific subject/data directory.

        Does nothing if that folder is already active, so settings changed in memory are not
        overwritten by the folder's file every time settings are applied.

        Args:
            project_dir (str): Path to subject/data directory. If '.' or empty, resets to default root.

        Returns:
            bool: True if settings were loaded from the newly selected folder's settings file.
        """
        new_dir = None if (not project_dir or project_dir == '.') else str(Path(project_dir).resolve())
        if new_dir == self.project_dir:
            return False
        self.project_dir = new_dir
        self.settings_file = (self.root_settings_file if new_dir is None
                              else str(Path(new_dir) / ".VocalTrack_settings.json"))

        # Load the folder's settings if present. Keep the current 'recording' section, which
        # holds the folder and device the user just chose.
        if os.path.exists(self.settings_file):
            new_settings = self.load()
            if new_settings:
                recording = self.settings.get('recording')
                self.settings.update(new_settings)
                if recording is not None:
                    self.settings['recording'] = recording
                return True
        return False
    
    def load(self):
        """Load settings from file.
        
        Returns:
            dict: Settings dictionary, empty dict if file doesn't exist
        """
        # Check if settings file exists on disk
        if os.path.exists(self.settings_file):
            try:
                # Open settings file in read mode with default UTF-8 encoding
                with open(self.settings_file, 'r') as f:
                    # Parse JSON file contents into Python dictionary
                    settings = json.load(f)
                # Translate analysis method names saved by earlier versions ('native')
                if isinstance(settings, dict) and isinstance(settings.get('analysis'), dict):
                    config.update_method_names(settings['analysis'])
                # Convert window settings saved by earlier versions (chunk_ms x number_of_chunks)
                if isinstance(settings, dict):
                    config.update_window_settings(settings)
                return settings
            except (json.JSONDecodeError, IOError) as e:
                # Print warning if file is corrupted or unreadable (don't crash app)
                print(f"Warning: Could not load settings from {self.settings_file}: {e}")
                # Return empty dictionary as fallback
                return {}
        # File doesn't exist, return empty dictionary (first run scenario)
        return {}
    
    def save(self):
        """Save current settings to file."""
        try:
            # Get directory path from settings_file path (or use '.' if no directory)
            # exist_ok=True prevents error if directory already exists
            os.makedirs(os.path.dirname(self.settings_file) or '.', exist_ok=True)
            # Open settings file in write mode (overwrites if exists)
            with open(self.settings_file, 'w') as f:
                # Serialize settings dictionary to JSON with 2-space indentation for readability
                json.dump(self.settings, f, indent=2)
        except IOError as e:
            # Print warning if file cannot be written (don't crash app)
            print(f"Warning: Could not save settings to {self.settings_file}: {e}")

        # When a subject/data folder is active, also record it in the root settings file
        # so the same folder is reopened on the next startup
        if self.settings_file != self.root_settings_file and 'recording' in self.settings:
            try:
                root = {}
                if os.path.exists(self.root_settings_file):
                    with open(self.root_settings_file, 'r') as f:
                        root = json.load(f)
                root['recording'] = self.settings['recording']
                with open(self.root_settings_file, 'w') as f:
                    json.dump(root, f, indent=2)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not update {self.root_settings_file}: {e}")
    
    def set(self, key, value):
        """Set a setting value.
        
        Args:
            key (str): Setting key (e.g., 'analysis', 'pitch_plot')
            value (dict): Setting value
        """
        # Update settings dictionary with new key-value pair (overwrites if exists)
        self.settings[key] = value
    
    def get(self, key, default=None):
        """Get a setting value.
        
        Args:
            key (str): Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        # Retrieve value from settings dictionary, return default if key doesn't exist
        return self.settings.get(key, default)
    
    def set_nested(self, *keys_and_value):
        """Set nested setting value.
        
        Args:
            *keys_and_value: Keys followed by value
                e.g., set_nested('analysis', 'window_ms', 50)
        """
        # Split arguments: all but last are keys, last is the value to set
        *keys, value = keys_and_value
        
        # Create nested structure if needed
        # Start at root of settings dictionary
        current = self.settings
        # Traverse all keys except the last one, creating dicts as needed
        for key in keys[:-1]:
            # Check if key doesn't exist in current level
            if key not in current:
                # Create empty dictionary for this key (auto-vivification)
                current[key] = {}
            # Move to next level of nesting
            current = current[key]
        
        # Set the value at the final key location
        current[keys[-1]] = value


# Global settings manager instance
# Module-level variable to store singleton settings manager
_settings_manager = None

def init_settings(settings_file=None):
    """Initialize the global settings manager.
    
    Args:
        settings_file (str, optional): Path to settings JSON file
    """
    # Access module-level global variable
    global _settings_manager
    # Create new SettingsManager instance and store in global variable
    _settings_manager = SettingsManager(settings_file)

def get_settings_manager():
    """Get the global settings manager instance.
    
    Returns:
        SettingsManager: Global settings manager
    """
    # Access module-level global variable
    global _settings_manager
    # If not yet initialized, create default instance
    if _settings_manager is None:
        # Initialize with default settings file location
        _settings_manager = SettingsManager()
    # Return the singleton settings manager instance
    return _settings_manager
