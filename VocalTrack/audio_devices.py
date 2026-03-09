"""
Audio device enumeration and default device utilities for input selection.

This module provides functions to list available audio input devices and to 
get the system's default input device index using PyAudio. It is used for microphone 
selection and device management in real-time audio applications.
"""
# Import PyAudio library for accessing audio hardware
import pyaudio
# Import logging module for error and warning messages
import logging

# Create logger instance for this module (uses module name as logger name)
logger = logging.getLogger(__name__)


# Define function to enumerate all available audio input devices
def get_audio_devices():
    """
    Enumerate all available audio input devices.

    Returns
    -------
    list of tuple
        Each tuple is (device_index, device_name, is_default), where:
        - device_index: int, PyAudio device index
        - device_name: str, human-readable device name
        - is_default: bool, True if this is the system default input device
    """
    # Initialize empty list to store device information tuples
    devices = []
    # Create PyAudio instance to query audio system
    p = pyaudio.PyAudio()
    
    # Attempt to get default input device (wrapped in try/except for systems without one)
    try:
        # Query system for default input device information dictionary
        default_device = p.get_default_input_device_info()
        # Extract device index from default device info
        default_index = default_device['index']
    # Handle OS errors (no default device) or IO errors (device access issues)
    except (OSError, IOError):
        # Set default index to None when no default exists
        default_index = None
        # Log warning message about missing default input device
        logger.warning("No default audio input device found")
    
    # Loop through all detected audio devices by index
    for i in range(p.get_device_count()):
        # Wrap device query in try/except to handle inaccessible devices gracefully
        try:
            # Get device information dictionary for current index
            info = p.get_device_info_by_index(i)
            # Only include devices with input channels
            # Check if device has at least one input channel (microphone capability)
            if info['maxInputChannels'] > 0:
                # Extract human-readable device name string
                name = info['name']
                # Check if this device index matches the default device
                is_default = (i == default_index)
                # Add tuple of (index, name, is_default) to devices list
                devices.append((i, name, is_default))
        # Catch any exception during device info retrieval
        except Exception as e:
            # Log warning with device index and error message
            logger.warning(f"Could not get info for device {i}: {e}")
    
    # Clean up PyAudio instance and release audio system resources
    p.terminate()
    # Return list of available input devices
    return devices


# Define function to get the system's default audio input device
def get_default_input_device():
    """
    Get the system's default audio input device index.

    Returns
    -------
    int or None
        Default device index, or None if no default device is available.
    """
    # Create PyAudio instance to query audio system
    p = pyaudio.PyAudio()
    # Use try/except/finally to ensure cleanup happens regardless of outcome
    try:
        # Query system for default input device information dictionary
        default_device = p.get_default_input_device_info()
        # Extract and store device index from info dictionary
        index = default_device['index']
    # Handle OS errors (no default device) or IO errors (device access issues)
    except (OSError, IOError):
        # Set index to None when no default device exists
        index = None
    # Finally block ensures PyAudio cleanup happens even if exception occurs
    finally:
        # Clean up PyAudio instance and release audio system resources
        p.terminate()
    
    # Return default device index (or None if no default)
    return index
