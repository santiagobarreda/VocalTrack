"""
Audio device enumeration and default device utilities for input selection.

This module provides two simple functions that let the rest of the application
discover which microphones and audio input devices are plugged into the computer:

  - get_audio_devices()       → a list of all available input devices
  - get_default_input_device() → the index of the system-chosen default mic

Both functions use Qt's QMediaDevices API, which asks the operating system for
the authoritative device list. This works on Windows (WASAPI), macOS (CoreAudio),
and Linux (ALSA/PulseAudio) without any platform-specific code.

The results are used by the Settings dialog to populate the microphone drop-down,
and by AudioProcessor to open the correct device when recording starts.
"""

# QCoreApplication is needed to initialize Qt's internal event system before we
# can call any Qt multimedia functions. Without it, QMediaDevices will crash.
from PySide6.QtCore import QCoreApplication

# QMediaDevices provides the static methods audioInputs() and defaultAudioInput()
# that return the OS-level list of microphones and the currently selected default.
from PySide6.QtMultimedia import QMediaDevices

# Standard Python logging - lets us emit warnings without crashing if a device
# description call unexpectedly fails.
import logging

# Create a logger scoped to this module. Messages will appear under the name
# "VocalTrack.audio_devices" in any log output, making them easy to filter.
logger = logging.getLogger(__name__)


def _ensure_qt_core_app():
    """
    Make sure a Qt application object exists before calling any Qt multimedia API.

    Qt's device enumeration (QMediaDevices) requires a running QCoreApplication
    or QApplication instance to be present in the process. If the GUI has already
    created a QApplication this function finds and returns it without creating a
    second one. If this module is called in a headless script or unit-test context
    where no Qt application exists yet, a lightweight QCoreApplication is created
    so that the subsequent QMediaDevices calls do not crash.
    """
    # Ask Qt if any application object is already alive in this process.
    app = QCoreApplication.instance()

    if app is None:
        # No Qt application exists yet - create a minimal one.
        # The empty list [] means 'pass no command-line arguments to Qt'.
        # QCoreApplication is lighter than QApplication: it has no GUI widgets,
        # just enough of Qt's infrastructure to support the event system and
        # multimedia subsystem.
        app = QCoreApplication([])

    return app


def get_audio_devices():
    """
    Return a list describing every audio input device the operating system knows about.

    Internally this calls Qt's QMediaDevices.audioInputs(), which queries the OS
    (WASAPI on Windows, CoreAudio on macOS, ALSA/PulseAudio on Linux) for all
    recognized microphones, USB audio interfaces, virtual audio devices, etc.

    Each device is represented as a three-element tuple so the caller can display
    a labelled list in the UI and still refer back to a device by its index number.

    Returns
    -------
    list of tuple
        Each tuple contains:
          - device_index (int)  : zero-based position in Qt's audio input list.
                                  Pass this to AudioProcessor as input_device_index.
          - device_name  (str)  : human-readable label, e.g. "Microphone (Realtek Audio)".
          - is_default   (bool) : True for the device the OS has chosen as the default mic.
                                  Only one device in the list will have this set to True.

        Returns an empty list if no audio input devices are found.
    """
    # Make sure Qt is initialized before we touch QMediaDevices.
    _ensure_qt_core_app()

    # Start with an empty list; we'll append one tuple per device below.
    devices = []

    # Ask Qt for the full list of audio input devices currently available.
    # This is a list of QAudioDevice objects, one per recognized mic/interface.
    inputs = QMediaDevices.audioInputs()

    # Ask Qt which device the operating system currently designates as the default mic.
    # We'll compare each device in the loop below against this to set is_default.
    default_input = QMediaDevices.defaultAudioInput()

    # Iterate over all discovered devices, keeping track of the zero-based index.
    for i, device in enumerate(inputs):
        try:
            # description() returns the human-readable name the OS assigned to this device.
            # If it returns an empty string (rare, but possible for virtual devices),
            # we fall back to a generic label so the UI always shows something useful.
            name = device.description() or f"Input Device {i}"

            # Check whether this device is the OS-selected default by comparing
            # the QAudioDevice objects directly. Qt overloads == for this purpose.
            is_default = (device == default_input)

            # Append the three-element tuple for this device to our results list.
            devices.append((i, name, is_default))

        except Exception as e:
            # It's very unusual for description() or == to raise, but guard against
            # it so a single broken device entry does not prevent the rest from loading.
            logger.warning(f"Could not get info for device {i}: {e}")

    if not devices:
        # Warn if the list is completely empty - this almost certainly means the
        # computer has no microphone, or the audio subsystem is not running.
        logger.warning("No audio input devices found")

    return devices


def get_default_input_device():
    """
    Return the index of the operating system's currently selected default audio input device.

    This is a convenience wrapper around get_audio_devices() logic. It is used
    when the application starts up and no device has been saved in settings yet,
    so we can pre-select a sensible default in the microphone drop-down.

    Returns
    -------
    int or None
        The zero-based index into Qt's audio input list for the default device.
        Returns None if:
          - No audio input devices are available at all, OR
          - Qt cannot identify which device is the system default.
    """
    # Make sure Qt is initialized before we touch QMediaDevices.
    _ensure_qt_core_app()

    # Get the full list of audio input devices from Qt.
    inputs = QMediaDevices.audioInputs()

    # Get the QAudioDevice descriptor that Qt considers the system default.
    default_input = QMediaDevices.defaultAudioInput()

    # Walk through the device list and find the position of the default device.
    for i, device in enumerate(inputs):
        if device == default_input:
            # Found it - return its index so the caller can use it directly as
            # input_device_index when creating an AudioProcessor.
            return i

    # If we reach here, either the list was empty or Qt returned a default device
    # that does not appear in the enumerated list (very unusual). Return None to
    # signal that no valid default could be identified.
    return None
