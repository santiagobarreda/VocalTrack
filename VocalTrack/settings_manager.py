"""Settings persistence manager for VocalTrack."""

# Import json module for JSON serialization/deserialization of settings
import json
# Import os for file path and directory operations
import os
# Import shutil for file copying operations (settings migration)
import shutil
# Import sys to detect PyInstaller frozen state and get executable path
import sys
# Import Path for object-oriented file path manipulation
from pathlib import Path

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
            # Check if running as PyInstaller bundle (frozen executable)
            if getattr(sys, "frozen", False):
                # Bundled app: store settings next to the executable.
                # Get directory containing the executable file
                exe_dir = Path(sys.executable).resolve().parent
                # Create settings filename in same directory as executable
                settings_file = str(exe_dir / ".VocalTrack_settings.json")
            else:
                # Default location: project root/.VocalTrack_settings.json
                # Get parent directory of current module (VocalTrack/), then parent again (project root)
                project_root = Path(__file__).resolve().parent.parent
                # Create settings filepath in project root directory
                settings_file = str(project_root / ".VocalTrack_settings.json")

                        
        # Store the settings file path for later save operations
        self.settings_file = settings_file
        # Load settings from file (or create empty dict if file doesn't exist)
        self.settings = self.load()
        # If settings file doesn't exist yet, create it with current (empty) settings
        if not os.path.exists(self.settings_file):
            self.save()
    
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
                    return json.load(f)
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
    
    def get_nested(self, *keys, default=None):
        """Get nested setting value.
        
        Args:
            *keys: Nested keys (e.g., 'analysis', 'window_ms')
            default: Default value if path not found
            
        Returns:
            Setting value or default
        """
        # Start at root of settings dictionary
        value = self.settings
        # Traverse nested dictionary path using each key in sequence
        for key in keys:
            # Check if current value is a dictionary (can be further indexed)
            if isinstance(value, dict):
                # Get next level of nesting using current key
                value = value.get(key)
            else:
                # Path is broken (non-dict encountered before end), return default
                return default
        # Return final value if we reached end of path, otherwise return default
        return value if value is not None else default
    
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
    
    def clear(self):
        """Clear all settings."""
        # Replace settings dictionary with empty dictionary (removes all keys)
        self.settings = {}


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
