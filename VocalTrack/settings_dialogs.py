"""Dialog windows for VocalTrack settings.
This file contains all the individual popup menus where the user 
types in their preferences (like numbers and dropdown choices).
"""

# Bring in the visual building blocks from the PySide6 toolkit
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QComboBox, QLabel, QCheckBox
)

# Bring in the default settings from the main application
from VocalTrack import config
# Bring in the tool that reads and writes saved preferences to the hard drive
from VocalTrack import settings_manager
# Bring in the tool that asks the computer what microphones are plugged in
from VocalTrack import audio_devices

class BaseSettingsDialog(QDialog):
    """A 'cookie-cutter' template for all our popup windows.
    Instead of building the OK and Cancel buttons from scratch 
    every single time, we create a base template here that all 
    the other windows will copy and use.
    """
    def __init__(self, title, parent=None, min_width=400):
        # Set up the basic popup window using the tools provided by PySide6
        super().__init__(parent)
        # Put the title text at the very top of the window frame
        self.setWindowTitle(title)
        # Make sure the window is wide enough so text isn't squished
        self.setMinimumWidth(min_width)
        
        # Create a vertical stacking layout (items will be placed top-to-bottom)
        self.main_layout = QVBoxLayout(self)
        # Create a form layout (a neat two-column list, like a survey)
        self.form = QFormLayout()
        # Put the empty form into our vertical stack
        self.main_layout.addLayout(self.form)
        
        # Standard OK/Cancel Buttons
        # Create a horizontal row layout to hold buttons side-by-side
        self.btn_layout = QHBoxLayout()
        # Create the OK button
        self.ok_btn = QPushButton("OK")
        # Create the Cancel button
        self.cancel_btn = QPushButton("Cancel")
        # If the user clicks OK, tell the window to close and say it was successful
        self.ok_btn.clicked.connect(self.accept)
        # If the user clicks Cancel, tell the window to close and reject changes
        self.cancel_btn.clicked.connect(self.reject)
        # Put the OK button into the horizontal row
        self.btn_layout.addWidget(self.ok_btn)
        # Put the Cancel button into the horizontal row next to it
        self.btn_layout.addWidget(self.cancel_btn)
        
        # Put the horizontal row of buttons at the very bottom of the vertical stack
        self.main_layout.addLayout(self.btn_layout)


class AnalysisSettingsDialog(BaseSettingsDialog):
    """Popup window for the core audio math settings.
    This lets the user change how the software chops up the microphone 
    audio and searches for voice frequencies.
    """
    def __init__(self, parent=None):
        # Use our cookie-cutter template and give it the title "Analysis Settings"
        super().__init__("Analysis Settings", parent)
        
        # Get the tool that remembers user preferences
        mgr = settings_manager.get_settings_manager()
        # Look in the save file for the 'analysis' folder. If it's empty, create a blank one.
        saved = mgr.get('analysis', {})
        
        # Create a text box for typing in the audio chunk duration
        # We try to load the saved number. If there is no saved number, use the default from config.py
        self.chunk_input = QLineEdit(str(saved.get('chunk_ms', config.AUDIO_CONFIG.get('chunk_ms', 5))))
        # Put ghost text in the box to tell the user we want milliseconds (ms)
        self.chunk_input.setPlaceholderText("ms")
        # Add a label "Chunk Duration" and place the text box next to it in the form
        self.form.addRow("Chunk Duration (ms):", self.chunk_input)
        
        # Create a text box for the number of audio chunks to process at once
        self.chunks_input = QLineEdit(str(saved.get('number_of_chunks', config.AUDIO_CONFIG.get('number_of_chunks', 5))))
        # Add ghost text showing an example number
        self.chunks_input.setPlaceholderText("e.g. 5")
        # Add it to the form
        self.form.addRow("Number of Chunks:", self.chunks_input)
        
        # Create a text box for the maximum frequency the math should look for
        self.max_formant_input = QLineEdit(str(saved.get('max_formant', config.ANALYSIS_CONFIG.get('max_formant', 5000))))
        # Add ghost text for Hertz (Hz)
        self.max_formant_input.setPlaceholderText("Hz")
        # Add it to the form
        self.form.addRow("Max Formant (Hz):", self.max_formant_input)
        
        # Create a text box for how many formants (vocal resonances) to search for
        self.n_formants_input = QLineEdit(str(saved.get('n_formants', config.ANALYSIS_CONFIG.get('n_formants', 5.5))))
        # Add ghost text example
        self.n_formants_input.setPlaceholderText("e.g. 5.5")
        # Add it to the form
        self.form.addRow("Number of Formants:", self.n_formants_input)
        
        # Create a text box for the lowest possible voice pitch
        self.min_f0_input = QLineEdit(str(saved.get('min_f0', config.ANALYSIS_CONFIG.get('min_f0', 60))))
        # Add ghost text for Hertz
        self.min_f0_input.setPlaceholderText("Hz")
        # Add it to the form
        self.form.addRow("Min f0 (Hz):", self.min_f0_input)
        
        # Create a text box for the highest possible voice pitch
        self.max_f0_input = QLineEdit(str(saved.get('max_f0', config.ANALYSIS_CONFIG.get('max_f0', 300))))
        # Add ghost text for Hertz
        self.max_f0_input.setPlaceholderText("Hz")
        # Add it to the form
        self.form.addRow("Max f0 (Hz):", self.max_f0_input)

        # Create a text box for how confident the math needs to be before drawing a pitch line
        self.min_confidence_input = QLineEdit(str(saved.get('min_confidence', config.ANALYSIS_CONFIG.get('min_confidence', 0.2))))
        # Tell the user the number must be between 0.0 and 1.0
        self.min_confidence_input.setPlaceholderText("0.0 - 1.0")
        # Add it to the form
        self.form.addRow("Min Confidence:", self.min_confidence_input)

        # Create a text box for the silence gate (how loud you must speak to be heard)
        self.min_rms_input = QLineEdit(str(saved.get('min_rms_db', config.AUDIO_CONFIG.get('min_rms_db', -45.0))))
        # Provide an example of a decibel (dBFS) number
        self.min_rms_input.setPlaceholderText("e.g. -45")
        # Add it to the form
        self.form.addRow("Min RMS (dBFS):", self.min_rms_input)

        # Create a dropdown menu to let the user pick which math engine calculates formants
        self.formant_method_combo = QComboBox()
        # Put three choices into the dropdown list
        self.formant_method_combo.addItems(["native", "parselmouth", "custom"])
        # Figure out which one they were using last time
        current_formant = saved.get('formant_method', config.ANALYSIS_CONFIG.get('formant_method', 'native'))
        # Find where that choice lives in our list (is it item 0, 1, or 2?)
        idx = self.formant_method_combo.findText(current_formant)
        # If we found it, make the dropdown display that choice
        if idx >= 0: self.formant_method_combo.setCurrentIndex(idx)
        # Add the dropdown menu to the form
        self.form.addRow("Formant Method:", self.formant_method_combo)

        # Create another dropdown menu, this time for calculating pitch
        self.pitch_method_combo = QComboBox()
        # Put the same three choices in the list
        self.pitch_method_combo.addItems(["native", "parselmouth", "custom"])
        # Figure out what they used last time
        current_pitch = saved.get('pitch_method', config.ANALYSIS_CONFIG.get('pitch_method', 'native'))
        # Find it in the list
        idx = self.pitch_method_combo.findText(current_pitch)
        # Make the dropdown display it
        if idx >= 0: self.pitch_method_combo.setCurrentIndex(idx)
        # Add the pitch dropdown to the form
        self.form.addRow("Pitch Method:", self.pitch_method_combo)
        
    def get_settings(self):
        """Gathers everything the user typed, packages it, and sends it back to the main app."""
        # Return a dictionary (a labeled list of items)
        return {
            # Read the text box, convert it to a whole number (int), and label it 'chunk_ms'
            'chunk_ms': int(self.chunk_input.text()),
            # Read the text box, convert to whole number
            'number_of_chunks': int(self.chunks_input.text()),
            # Read the text box, convert to whole number
            'max_formant': int(self.max_formant_input.text()),
            # Read the text box, convert to a decimal number (float)
            'n_formants': float(self.n_formants_input.text()),
            # Read the text box, convert to whole number
            'min_f0': int(self.min_f0_input.text()),
            # Read the text box, convert to whole number
            'max_f0': int(self.max_f0_input.text()),
            # Read the text box, convert to decimal number
            'min_confidence': float(self.min_confidence_input.text()),
            # Read the text box, convert to decimal number
            'min_rms_db': float(self.min_rms_input.text()),
            # Read the currently selected text from the formant dropdown menu
            'formant_method': self.formant_method_combo.currentText(),
            # Read the currently selected text from the pitch dropdown menu
            'pitch_method': self.pitch_method_combo.currentText(),
        }


class SmootherSettingsDialog(BaseSettingsDialog):
    """Popup window for adjusting how the software smooths out shaky tracking lines."""
    def __init__(self, parent=None):
        # Use our cookie-cutter template and name it "Smoother Settings"
        super().__init__("Smoother Settings", parent)
        # Get the settings manager tool
        mgr = settings_manager.get_settings_manager()
        # Find the 'smoother' save folder
        saved = mgr.get('smoother', {})
        
        # Create a text box for memory size (how many past dots it remembers)
        self.memory_input = QLineEdit(str(saved.get('memory_n', config.SMOOTHER_CONFIG.get('memory_n', 5))))
        # Add it to the form
        self.form.addRow("Memory (frames):", self.memory_input)
        
        # Create a text box for stability (how far a dot can jump before we consider it an error)
        self.stability_input = QLineEdit(str(saved.get('stability_threshold', config.SMOOTHER_CONFIG.get('stability_threshold', 0.32))))
        # Add it to the form
        self.form.addRow("Stability Threshold:", self.stability_input)
        
        # Create a text box for skip tolerance (how many bad dots we ignore before starting a new line)
        self.skip_input = QLineEdit(str(saved.get('skip_tolerance', config.SMOOTHER_CONFIG.get('skip_tolerance', 2))))
        # Add it to the form
        self.form.addRow("Skip Tolerance (frames):", self.skip_input)
        
        # Create a visual divider line to separate the basic settings from the advanced math settings
        separator = QLabel("─" * 50)
        # Color the line gray
        separator.setStyleSheet("color: gray;")
        # Add the dividing line to the form
        self.form.addRow(separator)
        
        # Create a bold text label to introduce the 1-Euro math filter section
        euro_label = QLabel("1-Euro Filter Parameters:")
        # Make it bold
        euro_label.setStyleSheet("font-weight: bold;")
        # Add the header to the form
        self.form.addRow(euro_label)
        
        # Text box for minimum cutoff (how much it smooths when the voice is steady)
        self.euro_min_cutoff_input = QLineEdit(str(saved.get('euro_min_cutoff', config.SMOOTHER_CONFIG.get('euro_min_cutoff', 0.05))))
        # Add to form
        self.form.addRow("Min Cutoff (Hz):", self.euro_min_cutoff_input)
        
        # Text box for beta (how much it stops smoothing when the voice moves quickly)
        self.euro_beta_input = QLineEdit(str(saved.get('euro_beta', config.SMOOTHER_CONFIG.get('euro_beta', 1.5))))
        # Add to form
        self.form.addRow("Beta (velocity scale):", self.euro_beta_input)
        
        # Text box for derivative cutoff (advanced math parameter)
        self.euro_dcutoff_input = QLineEdit(str(saved.get('euro_dcutoff', config.SMOOTHER_CONFIG.get('euro_dcutoff', 0.5))))
        # Add to form
        self.form.addRow("Derivative Cutoff (Hz):", self.euro_dcutoff_input)
        
        # Text box for velocity power (how aggressive the filter adapts to speed)
        self.velocity_power_input = QLineEdit(str(saved.get('velocity_power', config.SMOOTHER_CONFIG.get('velocity_power', 1.5))))
        # Add to form
        self.form.addRow("Velocity Power:", self.velocity_power_input)
        
    def get_settings(self):
        """Gathers the smoother settings and packages them up."""
        return {
            # Convert memory to a whole number
            'memory_n': int(self.memory_input.text()),
            # Convert stability to a decimal number
            'stability_threshold': float(self.stability_input.text()),
            # Convert skip tolerance to a whole number
            'skip_tolerance': int(self.skip_input.text()),
            # Convert math parameter to decimal
            'euro_min_cutoff': float(self.euro_min_cutoff_input.text()),
            # Convert math parameter to decimal
            'euro_beta': float(self.euro_beta_input.text()),
            # Convert math parameter to decimal
            'euro_dcutoff': float(self.euro_dcutoff_input.text()),
            # Convert math parameter to decimal
            'velocity_power': float(self.velocity_power_input.text()),
        }



class PlottingSettingsDialog(BaseSettingsDialog):
    """Popup window for adjusting the visual scatter plot (Vowel Space)."""
    def __init__(self, parent=None):
        # Use template, name it "Formant Plotting Settings"
        super().__init__("Formant Plotting Settings", parent)
        # Get save tool
        mgr = settings_manager.get_settings_manager()
        # Find plotting save folder
        saved = mgr.get('plotting', {})
        
        # Fetch the previously saved limits for the graph, or use defaults
        # F1 is usually the vertical axis, F2 is usually the horizontal axis
        default_f1 = saved.get('f1_range', config.LIVEVOWEL_CONFIG.get('f1_range', (200.0, 1100.0)))
        default_f2 = saved.get('f2_range', config.LIVEVOWEL_CONFIG.get('f2_range', (500.0, 2700.0)))
        
        # Create text box for the bottom limit of the F1 axis. Extract the first number from the saved pair [0].
        self.f1_min_input = QLineEdit(str(int(default_f1[0])))
        # Add to form
        self.form.addRow("F1 Min (Hz):", self.f1_min_input)
        # Create text box for the top limit of the F1 axis. Extract the second number [1].
        self.f1_max_input = QLineEdit(str(int(default_f1[1])))
        # Add to form
        self.form.addRow("F1 Max (Hz):", self.f1_max_input)
        
        # Create text box for the left limit of the F2 axis
        self.f2_min_input = QLineEdit(str(int(default_f2[0])))
        # Add to form
        self.form.addRow("F2 Min (Hz):", self.f2_min_input)
        # Create text box for the right limit of the F2 axis
        self.f2_max_input = QLineEdit(str(int(default_f2[1])))
        # Add to form
        self.form.addRow("F2 Max (Hz):", self.f2_max_input)
        
        # Create a text box for Frames Per Second (how fast the animation updates)
        self.fps_input = QLineEdit(str(saved.get('fps', config.LIVEVOWEL_CONFIG.get('fps', 60))))
        # Add to form
        self.form.addRow("FPS:", self.fps_input)
        
        # Create a dropdown menu to let the user pick how the dots look
        self.display_mode_combo = QComboBox()
        # Add three display styles to the list
        self.display_mode_combo.addItems(["Single Point", "Connected Track", "All Points"])
        # Create a hidden dictionary that translates the computer's code words into list positions
        mode_map = {"single": 0, "track": 1, "all": 2}
        # See which code word was saved last time
        current_mode = saved.get('display_mode', config.LIVEVOWEL_CONFIG.get('display_mode', 'single'))
        # Set the dropdown menu to match the saved choice
        self.display_mode_combo.setCurrentIndex(mode_map.get(current_mode, 0))
        # Add dropdown to form
        self.form.addRow("Display Mode:", self.display_mode_combo)
        
        # Create a dropdown menu for how the grid is spaced out
        self.freq_scale_combo = QComboBox()
        # Add options: Logarithmic (squished high numbers) or Linear (evenly spaced)
        self.freq_scale_combo.addItems(["Logarithmic", "Linear"])
        # See what was saved last time
        current_scale = saved.get('freq_scale', config.LIVEVOWEL_CONFIG.get('freq_scale', 'log'))
        # If it was 'log', pick item 0. Otherwise pick item 1.
        self.freq_scale_combo.setCurrentIndex(0 if current_scale == 'log' else 1)
        # Add dropdown to form
        self.form.addRow("Frequency Scale:", self.freq_scale_combo)
        
    def get_settings(self):
        """Gathers settings and translates dropdown choices back into code words."""
        # Create a list of the code words for display modes
        modes = ["single", "track", "all"]
        # Create a list of the code words for scales
        scales = ["log", "linear"]
        return {
            # Package the two F1 text boxes together as a pair (tuple) of decimal numbers
            'f1_range': (float(self.f1_min_input.text()), float(self.f1_max_input.text())),
            # Package the two F2 text boxes together as a pair
            'f2_range': (float(self.f2_min_input.text()), float(self.f2_max_input.text())),
            # Convert FPS to a whole number
            'fps': int(self.fps_input.text()),
            # Look up the code word based on which dropdown item the user clicked
            'display_mode': modes[self.display_mode_combo.currentIndex()],
            # Look up the scale code word based on the dropdown
            'freq_scale': scales[self.freq_scale_combo.currentIndex()],
        }



class PitchPlotSettingsDialog(BaseSettingsDialog):
    """Popup window for adjusting the real-time pitch graph."""
    def __init__(self, parent=None):
        # Use template, title it "Pitch Plotting Settings"
        super().__init__("Pitch Plotting Settings", parent)
        # Get save tool
        mgr = settings_manager.get_settings_manager()
        # Find pitch plot save folder
        saved = mgr.get('pitch_plot', {})
        
        # Text box for the lowest pitch number on the graph's vertical axis
        self.min_f0_input = QLineEdit(str(saved.get('min_f0', config.LIVEPITCH_CONFIG.get('min_f0', 75))))
        # Add to form
        self.form.addRow("Min f0 (Hz):", self.min_f0_input)
        
        # Text box for the highest pitch number on the vertical axis
        self.max_f0_input = QLineEdit(str(saved.get('max_f0', config.LIVEPITCH_CONFIG.get('max_f0', 500))))
        # Add to form
        self.form.addRow("Max f0 (Hz):", self.max_f0_input)
        
        # Dropdown to choose how the graph moves across the screen over time
        self.mode_combo = QComboBox()
        # Option 1: A page that fills up and wipes clean. Option 2: A constantly sliding tape.
        self.mode_combo.addItems(["Fixed Time", "Continuous Scroll"])
        # Fetch the saved choice
        current_mode = saved.get('pitch_plot_mode', config.LIVEPITCH_CONFIG.get('pitch_plot_mode', 'fixed'))
        # If the code word is 'fixed', pick item 0. Otherwise pick item 1.
        self.mode_combo.setCurrentIndex(0 if current_mode == 'fixed' else 1)
        # Add dropdown to form
        self.form.addRow("Plot Mode:", self.mode_combo)
        
        # Text box for how many seconds of history fit on the screen at once
        self.window_width_input = QLineEdit(str(saved.get('pitch_display_seconds', config.LIVEPITCH_CONFIG.get('pitch_display_seconds', 5.0))))
        # Add to form
        self.form.addRow("Display Window (seconds):", self.window_width_input)
        
        # Dropdown for grid spacing (Log vs Linear)
        self.freq_scale_combo = QComboBox()
        # Add the two options
        self.freq_scale_combo.addItems(["Logarithmic", "Linear"])
        # Fetch saved choice
        current_scale = saved.get('freq_scale', config.LIVEPITCH_CONFIG.get('freq_scale', 'log'))
        # Set dropdown to match
        self.freq_scale_combo.setCurrentIndex(0 if current_scale == 'log' else 1)
        # Add dropdown to form
        self.form.addRow("Frequency Scale:", self.freq_scale_combo)
        
    def get_settings(self):
        """Gathers settings and translates dropdown choices."""
        # List of scale code words
        scales = ["log", "linear"]
        return {
            # Convert min pitch to whole number
            'min_f0': int(self.min_f0_input.text()),
            # Convert max pitch to whole number
            'max_f0': int(self.max_f0_input.text()),
            # A tiny inline logic statement: if dropdown is 0, use "fixed", otherwise use "continuous"
            'pitch_plot_mode': "fixed" if self.mode_combo.currentIndex() == 0 else "continuous",
            # Convert seconds to a decimal number
            'pitch_display_seconds': float(self.window_width_input.text()),
            # Look up the scale code word based on dropdown index
            'freq_scale': scales[self.freq_scale_combo.currentIndex()],
        }



class SpectrogramSettingsDialog(BaseSettingsDialog):
    """Popup window for adjusting the colorful scrolling audio heatmap (Spectrogram)."""
    def __init__(self, parent=None):
        # Use template, title it "Spectrogram Settings"
        super().__init__("Spectrogram Settings", parent)
        # Get save tool
        mgr = settings_manager.get_settings_manager()
        # Find spectrogram save folder
        saved = mgr.get('spectrogram', {})
        
        # Text box for how high the vertical frequency axis should go
        self.max_freq_input = QLineEdit(str(saved.get('max_freq', config.LIVESPECTROGRAM_CONFIG.get('max_freq', 5000))))
        # Add to form
        self.form.addRow("Max Frequency (Hz):", self.max_freq_input)
        
        # Text box for how many seconds of audio history stay on screen
        self.display_seconds_input = QLineEdit(str(saved.get('display_seconds', config.LIVESPECTROGRAM_CONFIG.get('display_seconds', 1.0))))
        # Add to form
        self.form.addRow("Display Window (seconds):", self.display_seconds_input)
        
        # Text box for animation speed (frames per second)
        self.fps_input = QLineEdit(str(saved.get('fps', config.LIVESPECTROGRAM_CONFIG.get('fps', 60))))
        # Add to form
        self.form.addRow("FPS:", self.fps_input)
        
        # Dropdown menu to choose the heat-map color theme
        self.colormap_combo = QComboBox()
        # Add a list of standard scientific color names (viridis, plasma, etc.)
        self.colormap_combo.addItems(["viridis", "plasma", "inferno", "magma", "cividis", "twilight", "turbo"])
        # Fetch the saved color name
        current_colormap = saved.get('colormap', config.LIVESPECTROGRAM_CONFIG.get('colormap', 'plasma'))
        # Find the text in the dropdown that matches the saved name
        idx = self.colormap_combo.findText(current_colormap)
        # Set the dropdown to display that color name
        if idx >= 0: self.colormap_combo.setCurrentIndex(idx)
        # Add to form
        self.form.addRow("Colormap:", self.colormap_combo)
        
        # Text box for dynamic range (controls contrast: how dark the quiet sounds appear)
        self.dynamic_range_input = QLineEdit(str(saved.get('dynamic_range', config.LIVESPECTROGRAM_CONFIG.get('dynamic_range', 40))))
        # Add to form
        self.form.addRow("Dynamic Range (dB):", self.dynamic_range_input)

        # Text box for chunk duration (how wide each vertical pixel slice is in time)
        self.chunk_ms_input = QLineEdit(str(saved.get('chunk_ms', config.LIVESPECTROGRAM_CONFIG.get('chunk_ms', 15.0))))
        # Add to form
        self.form.addRow("Chunk Duration (ms):", self.chunk_ms_input)

        # Text box for overlapping slices to make the image smoother
        self.number_of_chunks_input = QLineEdit(str(saved.get('number_of_chunks', config.LIVESPECTROGRAM_CONFIG.get('number_of_chunks', 3))))
        # Add to form
        self.form.addRow("Number of Chunks:", self.number_of_chunks_input)
        
        # Text box for padding (a math trick to increase vertical pixel resolution)
        self.padding_length_input = QLineEdit(str(saved.get('padding_length_ms', config.LIVESPECTROGRAM_CONFIG.get('padding_length_ms', 20.0))))
        # Add to form
        self.form.addRow("Padding Length (ms):", self.padding_length_input)
        
    def get_settings(self):
        """Gathers settings for the spectrogram."""
        return {
            # Convert max frequency to whole number
            'max_freq': int(self.max_freq_input.text()),
            # Convert display width to decimal number
            'display_seconds': float(self.display_seconds_input.text()),
            # Convert FPS to whole number
            'fps': int(self.fps_input.text()),
            # For the color map, just grab the actual text string directly
            'colormap': self.colormap_combo.currentText(),
            # Convert contrast number to whole number
            'dynamic_range': int(self.dynamic_range_input.text()),
            # Convert chunk size to decimal
            'chunk_ms': float(self.chunk_ms_input.text()),
            # Convert chunk count to whole number
            'number_of_chunks': int(self.number_of_chunks_input.text()),
            # Convert padding to decimal
            'padding_length_ms': float(self.padding_length_input.text()),
        }



class SpectrumSettingsDialog(BaseSettingsDialog):
    """Popup window for adjusting the static line graph showing audio frequencies."""
    def __init__(self, parent=None):
        # Use template, title it "Spectrum Settings"
        super().__init__("Spectrum Settings", parent)
        # Get save tool
        mgr = settings_manager.get_settings_manager()
        # Find spectrum save folder
        saved = mgr.get('spectrum', {})
        
        # Text box for the right-side limit of the horizontal frequency axis
        self.max_freq_input = QLineEdit(str(saved.get('max_freq', config.LIVESPECTRUM_CONFIG.get('max_freq', 5000))))
        # Add to form
        self.form.addRow("Max Frequency (Hz):", self.max_freq_input)
        
        # Text box for the contrast/depth of the vertical decibel axis
        self.dynamic_range_input = QLineEdit(str(saved.get('dynamic_range', config.LIVESPECTRUM_CONFIG.get('dynamic_range', 40))))
        # Add to form
        self.form.addRow("Dynamic Range (dB):", self.dynamic_range_input)

        # Text box for how much audio time is analyzed to draw one line
        self.chunk_ms_input = QLineEdit(str(saved.get('chunk_ms', config.LIVESPECTRUM_CONFIG.get('chunk_ms', 15.0))))
        # Add to form
        self.form.addRow("Chunk Duration (ms):", self.chunk_ms_input)

        # Text box for chunk overlap count
        self.number_of_chunks_input = QLineEdit(str(saved.get('number_of_chunks', config.LIVESPECTRUM_CONFIG.get('number_of_chunks', 3))))
        # Add to form
        self.form.addRow("Number of Chunks:", self.number_of_chunks_input)
        
        # Text box for display framerate
        self.fps_input = QLineEdit(str(saved.get('fps', config.LIVESPECTRUM_CONFIG.get('fps', 60))))
        # Add to form
        self.form.addRow("Display FPS:", self.fps_input)
        
        # Text box for the padding math trick to make the line curve smoother
        self.padding_length_input = QLineEdit(str(saved.get('padding_length_ms', config.LIVESPECTRUM_CONFIG.get('padding_length_ms', 20.0))))
        # Add to form
        self.form.addRow("Padding Length (ms):", self.padding_length_input)

        # Text box for exponential smoothing (how much the line wiggles vs flows)
        self.smoothing_input = QLineEdit(str(saved.get('smoothing', config.LIVESPECTRUM_CONFIG.get('smoothing', 0.7))))
        # Add to form
        self.form.addRow("Smoothing (0-1):", self.smoothing_input)
        
    def get_settings(self):
        """Gathers settings for the spectrum line graph."""
        return {
            # Convert max freq to whole number
            'max_freq': int(self.max_freq_input.text()),
            # Convert dynamic range to whole number
            'dynamic_range': int(self.dynamic_range_input.text()),
            # Convert chunk size to decimal
            'chunk_ms': float(self.chunk_ms_input.text()),
            # Convert chunk count to whole number
            'number_of_chunks': int(self.number_of_chunks_input.text()),
            # Convert FPS to whole number
            'fps': int(self.fps_input.text()),
            # Convert padding size to decimal
            'padding_length_ms': float(self.padding_length_input.text()),
            # Convert line smoothing value to decimal
            'smoothing': float(self.smoothing_input.text()),
        }



class RecordingSettingsDialog(BaseSettingsDialog):
    """Popup window for selecting which physical microphone to use and recording options."""
    def __init__(self, parent=None):
        # Use template, title it "Recording Settings", and make it slightly wider to fit long microphone names
        super().__init__("Recording Settings", parent, min_width=450)
        
        # Get the tool that remembers user preferences
        mgr = settings_manager.get_settings_manager()
        # Look in the save file for the 'recording' folder. If it's empty, create a blank one.
        saved = mgr.get('recording', {})
        
        # Create a dropdown menu
        self.device_combo = QComboBox()
        # Ask the custom audio tool to look at the computer and build a list of all plugged-in microphones
        self.devices = audio_devices.get_audio_devices()
        
        # If the computer didn't find ANY microphones...
        if not self.devices:
            # Put a fake warning item in the dropdown
            self.device_combo.addItem("No input devices found", None)
            # Lock the dropdown so the user can't click it
            self.device_combo.setEnabled(False)
        # If microphones WERE found...
        else:
            # Loop through the list of found microphones one by one
            # It gives us an ID number, a name, and a True/False if it's the computer's primary mic
            for device_idx, device_name, is_default in self.devices:
                # Create a text label. If it's the primary mic, add the word "[DEFAULT]" to the end.
                display_name = f"{device_name} {'[DEFAULT]' if is_default else ''}"
                # Add the name to the dropdown, and secretly attach its computer ID number to it
                self.device_combo.addItem(display_name, device_idx)
                # If this specific mic is the default...
                if is_default:
                    # Force the dropdown menu to pre-select it automatically
                    self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
        
        # Add the completed dropdown menu to the form layout
        self.form.addRow("Audio Input Device:", self.device_combo)
        
        # Create a checkbox to enable/disable saving recordings
        self.save_recordings_checkbox = QCheckBox("Save recordings (WAV and CSV files)")
        # Set the initial state from saved settings (default: False/unchecked)
        is_checked = saved.get('save_recordings', config.EXPORT_CONFIG.get('save_recordings', False))
        self.save_recordings_checkbox.setChecked(is_checked)
        # Add the checkbox to the form
        self.form.addRow("", self.save_recordings_checkbox)
        
        # Create a small text label to help the user understand what to do
        info_label = QLabel("Select your microphone or audio input device. Enable 'Save recordings' to export audio and data from LivePitch and LiveVowel modes.")
        # Color the text gray and make it small
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        # Allow the text to wrap to a new line if the window gets too small
        info_label.setWordWrap(True)
        # Sneak this help text into the main vertical stack right below the form, but above the OK button
        self.main_layout.insertWidget(1, info_label)
    
    def get_device_index(self):
        """Retrieves the secret computer ID number of the chosen microphone."""
        # If there are no mics, or the dropdown is locked...
        if self.device_combo.count() == 0 or not self.device_combo.isEnabled():
            # Return nothing (the software will just try to guess the default later)
            return None
        # Otherwise, fetch the secret ID data attached to the currently selected dropdown item
        return self.device_combo.currentData()
    
    def get_settings(self):
        """Gathers the recording settings and packages them for the main app."""
        return {
            'save_recordings': self.save_recordings_checkbox.isChecked()
        }