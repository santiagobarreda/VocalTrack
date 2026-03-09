"""PySide6 launcher for liveaudio applications."""
# Bring in the tools needed to interact with the computer's operating system (like exiting the program)
import sys
import os

# Bring in all the visual building blocks from the PySide6 toolkit (buttons, windows, layouts, etc.)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QDialog, QMessageBox, 
    QComboBox, QSizePolicy, QGridLayout, QProgressBar
)

# Bring in behind-the-scenes toolkit pieces, like timers and background threads
from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QPixmap

# Bring in the actual visualization programs that this launcher will open
from VocalTrack.LiveVowel import LiveVowel
from VocalTrack.LivePitch import LivePitch
from VocalTrack.LiveSpectrogram import LiveSpectrogram
from VocalTrack.LiveSpectrum import LiveSpectrum

# Bring in the configuration settings, audio device tools, and the system that saves user preferences
from VocalTrack import config
from VocalTrack import audio_devices
from VocalTrack import settings_manager

# Bring in the popup windows we created in the other file for the user to change settings
from VocalTrack.settings_dialogs import (
    AnalysisSettingsDialog, SmootherSettingsDialog, PlottingSettingsDialog,
    PitchPlotSettingsDialog, SpectrogramSettingsDialog, SpectrumSettingsDialog,
    RecordingSettingsDialog
)
from VocalTrack.ipalabels import get_resource_path

class BenchmarkProgressDialog(QDialog):
    """A popup window that blocks the main screen and shows a loading bar while the computer does heavy testing."""
    def __init__(self, parent=None):
        # Set up the basic popup window
        super().__init__(parent)
        # Give the popup window a title
        self.setWindowTitle("Benchmark Recording")
        # Make sure the window is wide enough to look normal
        self.setMinimumWidth(360)

        # Create a vertical stacking layout (items placed top to bottom)
        layout = QVBoxLayout()
        # Create text that tells the user what is happening
        self.status_label = QLabel("Preparing...")
        # Center the text in the middle of the window
        self.status_label.setAlignment(Qt.AlignCenter)
        # Add the text to our vertical stack
        layout.addWidget(self.status_label)

        
        # Create a visual loading bar
        self.progress_bar = QProgressBar()
        # Set the bar to go from 0 to 100 percent
        self.progress_bar.setRange(0, 100)
        # Start the bar at empty (0)
        self.progress_bar.setValue(0)
        # Add the loading bar to our vertical stack
        layout.addWidget(self.progress_bar)

        # Create a small reminder text for the user
        note = QLabel("Please speak during recording.")
        # Center the reminder text
        note.setAlignment(Qt.AlignCenter)
        # Color the reminder text grey so it doesn't distract
        note.setStyleSheet("color: #666;")
        # Add the reminder text to the bottom of our vertical stack
        layout.addWidget(note)
        # Apply this whole vertical stack to the popup window
        self.setLayout(layout)

    def set_progress(self, value):
        """Changes how full the loading bar is."""
        # Update the visual bar with the new number
        self.progress_bar.setValue(value)

    def set_status(self, text):
        """Changes the text above the loading bar to tell the user what is happening."""
        # Update the text label with the new message
        self.status_label.setText(text)


class BenchmarkWorker(QObject):
    """A background helper that runs heavy tasks so the main screen doesn't freeze up."""
    # Create communication channels to send numbers (progress) back to the main screen
    progress = Signal(int)
    # Create a communication channel to send text (status) back to the main screen
    status = Signal(str)
    # Create a communication channel to say when it's done (success boolean, error message, folder location)
    finished = Signal(bool, str, str)

    def __init__(self, run_fn, output_dir):
        # Set up the basic background helper
        super().__init__()
        # Store the heavy task that needs to be run
        self.run_fn = run_fn
        # Store where the results should be saved
        self.output_dir = output_dir

    def run(self):
        """The actual sequence of instructions the background helper performs."""
        # Try to do the heavy task safely
        try:
            # Send a message to the main screen saying we are starting
            self.status.emit("Starting benchmark...")
            # Run the heavy task, giving it our communication channels so it can report back
            self.run_fn(self._on_progress, self._on_status)
            # Send a message saying the task finished successfully
            self.status.emit("Benchmark complete!")
            # Tell the loading bar to fill up completely to 100%
            self.progress.emit(100)
            # Send the final 'done' signal to the main screen with the location of the files
            self.finished.emit(True, "Benchmark complete.", self.output_dir)
        # If anything crashes or goes wrong during the heavy task...
        except Exception as exc:
            # Bring in a tool to read exactly what caused the crash
            import traceback
            # Create a readable error message
            msg = f"Benchmark failed: {str(exc)}"
            # Send the error message to the main screen
            self.status.emit(f"ERROR: {msg}")
            # Print the detailed crash report to the computer's console for debugging
            traceback.print_exc()
            # Send the final 'done' signal, telling the main screen it failed
            self.finished.emit(False, msg, self.output_dir)

    def _on_progress(self, fraction):
        """Converts a decimal (like 0.5) into a percentage (like 50) and sends it to the loading bar."""
        # Multiply by 100 and make sure the number stays between 0 and 100
        self.progress.emit(int(max(0.0, min(1.0, fraction)) * 100))

    def _on_status(self, text):
        """Sends a text update to the main screen."""
        # Emit the text message through the communication channel
        self.status.emit(text)


class LauncherWindow(QMainWindow):
    """The main menu window that the user sees when they open the program."""
    
    def __init__(self):
        # Set up the main window structure
        super().__init__()
        # Give the window a title at the very top
        self.setWindowTitle("VocalTrack")
        # Ensure the window can't be shrunk too small to read
        self.setMinimumSize(400, 400)
        
        # Create a blank placeholder for the user's chosen microphone
        self.audio_input_device = None
        
        # Create a blank canvas to hold all our buttons
        central = QWidget()
        # Put the blank canvas into the center of the main window
        self.setCentralWidget(central)
        # Create a vertical stacking system for our canvas
        main_layout = QVBoxLayout(central)
        
        # Create the big title image (logo). Falls back to text if image missing.
        title = QLabel()
        try:
            logo_path = get_resource_path(os.path.join("VocalTrack", "images", "VocalTrackLogo_.png"))
            pix = QPixmap(logo_path)
            if not pix.isNull():
                pix = pix.scaledToWidth(380, Qt.SmoothTransformation)
                title.setPixmap(pix)
            else:
                raise FileNotFoundError(logo_path)
        except Exception:
            # Fallback to plain text title if image can't be loaded
            title.setText("VocalTrack")
            title.setStyleSheet("font-size: 28px; font-weight: bold;")
            title.setAlignment(Qt.AlignCenter)
        # Center the title (image or text) horizontally
        title.setAlignment(Qt.AlignCenter)
        # Put the title at the top of our vertical stack
        main_layout.addWidget(title)
        
        
        # Create a subtle box to group all the settings buttons together
        settings_group = QGroupBox("")
        # Create a grid (like a spreadsheet) to align the settings buttons
        settings_layout = QGridLayout()
        
        # Add the 'Analysis Settings' button to the top left of the grid
        self._add_settings_btn(settings_layout, "Analysis Settings", self.open_analysis_settings, 0, 0)
        # Add the 'Smoother Settings' button below it
        self._add_settings_btn(settings_layout, "Smoother Settings", self.open_smoother_settings, 1, 0)
        # Add the 'Recording Settings' button below that
        self._add_settings_btn(settings_layout, "Recording Settings", self.open_recording_settings, 2, 0)
        # Add the 'Benchmarking' button at the bottom left
        self._add_settings_btn(settings_layout, "Benchmarking", self.open_benchmark_settings_dialog, 3, 0)
        
        # Add the 'Formant Plot Settings' button to the top right of the grid
        self._add_settings_btn(settings_layout, "Formant Plot Settings", self.open_plotting_settings, 0, 1)
        # Add the 'Pitch Plot Settings' button below it
        self._add_settings_btn(settings_layout, "Pitch Plot Settings", self.open_pitch_plot_settings, 1, 1)
        # Add the 'Spectrogram Settings' button below that
        self._add_settings_btn(settings_layout, "Spectrogram Settings", self.open_spectrogram_settings, 2, 1)
        # Add the 'Spectrum Settings' button at the bottom right
        self._add_settings_btn(settings_layout, "Spectrum Settings", self.open_spectrum_settings, 3, 1)
        
        # Apply the grid of buttons to the grouping box
        settings_group.setLayout(settings_layout)
        # Add the grouping box to our main vertical stack
        main_layout.addWidget(settings_group)
        # Add an invisible stretchy space to push the launch buttons to the bottom
        main_layout.addStretch()
        
        # Create another grid just for the big colored launch buttons
        launch_layout = QGridLayout()
        # Create the green button to start the LiveVowel tool
        self.start_vowel_btn = self._create_launch_btn("LiveVowel", "#4CAF50", "#45a049", lambda: self._launch_module(LiveVowel, "LiveVowel"))
        # Create the blue button to start the LivePitch tool
        self.start_pitch_btn = self._create_launch_btn("LivePitch", "#2196F3", "#1e88e5", lambda: self._launch_module(LivePitch, "LivePitch"))
        # Create the purple button to start the LiveSpectrogram tool (and tell it it needs extra information to run)
        self.start_spectrogram_btn = self._create_launch_btn("LiveSpectrogram", "#9C27B0", "#7B1FA2", lambda: self._launch_module(LiveSpectrogram, "LiveSpectrogram", True))
        # Create the orange button to start the LiveSpectrum tool (and tell it it needs extra information to run)
        self.start_spectrum_btn = self._create_launch_btn("LiveSpectrum", "#e07319", "#c76412", lambda: self._launch_module(LiveSpectrum, "LiveSpectrum", True))
        
        # Place the green button in the top left of the launch grid
        launch_layout.addWidget(self.start_vowel_btn, 0, 0)
        # Place the blue button in the top right
        launch_layout.addWidget(self.start_pitch_btn, 0, 1)
        # Place the purple button in the bottom left
        launch_layout.addWidget(self.start_spectrogram_btn, 1, 0)
        # Place the orange button in the bottom right
        launch_layout.addWidget(self.start_spectrum_btn, 1, 1)
        # Add this grid of launch buttons to the very bottom of the main vertical stack
        main_layout.addLayout(launch_layout)
        
        # Create a text label at the very bottom to tell the user the system status
        self.status_label = QLabel("Ready to launch")
        # Center this text
        self.status_label.setAlignment(Qt.AlignCenter)
        # Color it grey and give it a little space on top
        self.status_label.setStyleSheet("margin-top: 10px; color: #666;")
        # Add it to the main layout
        main_layout.addWidget(self.status_label)
        
        # Create empty folders (dictionaries) to hold the settings the user chooses
        self.analysis_settings = {}
        self.smoother_settings = {}
        self.plotting_settings = {}
        self.pitch_plot_settings = {}
        self.spectrogram_settings = {}
        self.spectrum_settings = {}
        self.recording_settings = {}

        # Create empty placeholders for the background testing tools
        self._benchmark_thread = None
        self._benchmark_worker = None
        self._benchmark_dialog = None
        
        # Ask the system to load any settings the user saved last time they opened the app
        self.load_saved_settings()

    def _add_settings_btn(self, layout, text, callback, row, col):
        """A mini-factory that builds a standard settings button and puts it in the grid."""
        # Create the button with the given text
        btn = QPushButton(text)
        # Make sure it's tall enough to click easily
        btn.setMinimumHeight(40)
        # Connect the click action to the specific popup window it should open
        btn.clicked.connect(callback)
        # Place it in the grid at the specified row and column
        layout.addWidget(btn, row, col)

    def _create_launch_btn(self, text, bg, hover, callback):
        """A mini-factory that builds the big, colored launch buttons."""
        # Create the button with the given text
        btn = QPushButton(text)
        # Make it stretch out horizontally to fill space, but keep its height fixed
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Make it nice and tall
        btn.setMinimumHeight(50)
        # Apply the specific colors and rounded corners using CSS styling
        btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 16px; background-color: {bg}; color: white;
                border-radius: 5px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)
        # Connect the click action to the program it is supposed to launch
        btn.clicked.connect(callback)
        # Return the finished button
        return btn
    
    def load_saved_settings(self):
        """Pulls saved preferences from the computer's hard drive and puts them in memory."""
        # Get the tool responsible for reading the saved file
        mgr = settings_manager.get_settings_manager()
        # If there are saved analysis settings, put them in our memory folder
        if saved := mgr.get('analysis', {}): self.analysis_settings = saved
        # If there are saved smoother settings, put them in our memory folder
        if saved := mgr.get('smoother', {}): self.smoother_settings = saved
        # If there are saved plotting settings, put them in our memory folder
        if saved := mgr.get('plotting', {}): self.plotting_settings = saved
        # If there are saved pitch settings, put them in our memory folder
        if saved := mgr.get('pitch_plot', {}): self.pitch_plot_settings = saved
        # If there are saved spectrogram settings, put them in our memory folder
        if saved := mgr.get('spectrogram', {}): self.spectrogram_settings = saved
        # If there are saved spectrum settings, put them in our memory folder
        if saved := mgr.get('spectrum', {}): self.spectrum_settings = saved
        # If there are saved recording settings, put them in our memory folder
        if saved := mgr.get('recording', {}): self.recording_settings = saved
    
    def open_analysis_settings(self):
        """Opens the Analysis popup and saves the choices if the user clicks OK."""
        # Create the popup window
        dialog = AnalysisSettingsDialog(self)
        # Wait for the user to interact. If they click OK...
        if dialog.exec() == QDialog.Accepted:
            # Grab all the choices they made
            self.analysis_settings = dialog.get_settings()
            # Calculate how much audio time they are analyzing at once
            window_ms = self.analysis_settings['chunk_ms'] * self.analysis_settings['number_of_chunks']
            # If the audio chunk is too small or too big, show a warning popup
            if window_ms < 20 or window_ms > 100:
                QMessageBox.warning(self, "Warning", f"Total analysis window ({window_ms}ms) is suboptimal. Edit code if intentional.")            # Apply and save settings immediately
            self.apply_settings()
    def open_smoother_settings(self):
        """Opens the Smoother popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = SmootherSettingsDialog(self)
        # If the user clicks OK, save their choices
        if dialog.exec() == QDialog.Accepted:
            self.smoother_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()
    
    def open_plotting_settings(self):
        """Opens the Plotting popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = PlottingSettingsDialog(self)
        # If the user clicks OK, save their choices
        if dialog.exec() == QDialog.Accepted:
            self.plotting_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()
    
    def open_pitch_plot_settings(self):
        """Opens the Pitch Plot popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = PitchPlotSettingsDialog(self)
        # If the user clicks OK, save their choices
        if dialog.exec() == QDialog.Accepted:
            self.pitch_plot_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()
    
    def open_spectrogram_settings(self):
        """Opens the Spectrogram popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = SpectrogramSettingsDialog(self)
        # If the user clicks OK, save their choices
        if dialog.exec() == QDialog.Accepted:
            self.spectrogram_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()
    
    def open_spectrum_settings(self):
        """Opens the Spectrum popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = SpectrumSettingsDialog(self)
        # If the user clicks OK, save their choices
        if dialog.exec() == QDialog.Accepted:
            self.spectrum_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()
    
    def open_recording_settings(self):
        """Opens the Microphone selection popup and saves choices if user clicks OK."""
        # Create the popup window
        dialog = RecordingSettingsDialog(self)
        # If the user clicks OK...
        if dialog.exec() == QDialog.Accepted:
            # Save the internal ID of the microphone they chose
            self.audio_input_device = dialog.get_device_index()
            # Save the recording preferences (save_recordings checkbox)
            self.recording_settings = dialog.get_settings()
            # Apply and save settings immediately
            self.apply_settings()

    def _get_benchmark_output_dir(self):
        """Creates a 'benchmarking' folder to save results in."""
        # Find the path to the folder where the program is currently running, and add "benchmarking"
        base_dir = os.path.join(os.getcwd(), "benchmarking")
        # Ask the operating system to create this folder (if it doesn't already exist)
        os.makedirs(base_dir, exist_ok=True)
        # Return the path to this folder
        return base_dir

    def _start_benchmark_worker(self, run_fn, output_dir):
        """Sets up a background thread so a heavy task can run without freezing the app."""
        # If a background task is already running, stop and do nothing
        if self._benchmark_thread is not None: return

        # Create the loading bar popup window
        self._benchmark_dialog = BenchmarkProgressDialog(self)
        # Lock the rest of the application so the user can't click other things
        self._benchmark_dialog.setModal(True)
        # Create an empty background thread
        self._benchmark_thread = QThread(self)
        # Wrap our heavy task in the worker object
        self._benchmark_worker = BenchmarkWorker(run_fn, output_dir)
        # Move the worker object into the background thread
        self._benchmark_worker.moveToThread(self._benchmark_thread)

        # Tell the thread to start running the worker's instructions when it wakes up
        self._benchmark_thread.started.connect(self._benchmark_worker.run)
        # Link the worker's progress messages to the loading bar
        self._benchmark_worker.progress.connect(self._benchmark_dialog.set_progress)
        # Link the worker's text messages to the loading screen text
        self._benchmark_worker.status.connect(self._benchmark_dialog.set_status)
        # Link the worker's finish message to our cleanup function
        self._benchmark_worker.finished.connect(self._on_benchmark_finished)
        # Tell the thread to shut itself down when the worker is finished
        self._benchmark_worker.finished.connect(self._benchmark_thread.quit)
        # Tell the system to delete the worker from memory when it's done
        self._benchmark_worker.finished.connect(self._benchmark_worker.deleteLater)
        # Tell the system to delete the thread from memory when it's done
        self._benchmark_thread.finished.connect(self._benchmark_thread.deleteLater)

        # Wake up the background thread and let it start working
        self._benchmark_thread.start()
        # Show the loading bar popup to the user
        self._benchmark_dialog.show()

    def _on_benchmark_finished(self, ok, msg, output_dir):
        """Cleans up the screen after a background task finishes."""
        # If the loading popup is open, close it
        if self._benchmark_dialog: self._benchmark_dialog.close()
        # If the background thread hasn't quite shut down yet, wait for up to 2 seconds
        if self._benchmark_thread and self._benchmark_thread.isRunning(): self._benchmark_thread.wait(2000)
        # Wipe all memory of the background thread and popup
        self._benchmark_thread = self._benchmark_worker = self._benchmark_dialog = None
        
        # If the task succeeded, show a popup telling the user where the files are
        if ok: QMessageBox.information(self, "Benchmark Complete", f"Results saved to:\n{output_dir}")
        # If the task failed, show a warning popup with the error message
        else: QMessageBox.warning(self, "Benchmark Failed", msg)

    def open_benchmark_settings_dialog(self):
        """Creates the popup menu to configure comprehensive benchmark test."""
        # Create a generic popup window
        dialog = QDialog(self)
        # Title it
        dialog.setWindowTitle("Comprehensive Benchmark")
        # Give it a vertical stacking layout
        layout = QVBoxLayout(dialog)

        # Add info label explaining what the test does
        info_label = QLabel(
            "Records 15 seconds of speech and compares Parselmouth\n"
            "against your chosen method for both accuracy and timing.\n"
            "Saves audio, raw data CSVs, and comprehensive report."
        )
        layout.addWidget(info_label)
        layout.addSpacing(10)

        # Create a dropdown menu to pick the method to compare against Parselmouth
        method_combo = QComboBox()
        # Add the two method options
        method_combo.addItems(["native", "custom"])

        # Add instructions and dropdown to the layout
        layout.addWidget(QLabel("Compare Parselmouth against:"))
        layout.addWidget(method_combo)

        # Create the buttons to run or cancel
        btn_layout = QHBoxLayout()
        ok_btn, cancel_btn = QPushButton("Run"), QPushButton("Cancel")
        # Link the buttons to accept or reject the popup
        ok_btn.clicked.connect(dialog.accept); cancel_btn.clicked.connect(dialog.reject)
        # Add them to the window
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Stop here and wait for the user. If they don't click Run, exit out.
        if dialog.exec() != QDialog.Accepted: return

        # Find the folder to save files to
        output_dir = self._get_benchmark_output_dir()
        # Read the chosen method from the dropdown
        method = method_combo.currentText()

        # Check if the complex 'Parselmouth' software is actually installed on the computer
        from VocalTrack.utils.get_formants import _HAS_PARSELMOUTH
        if not _HAS_PARSELMOUTH:
            # If it's missing, warn the user and stop
            QMessageBox.warning(self, "Required", "Pip install praat-parselmouth")
            return

        # Bring in the benchmarking tools
        from VocalTrack import benchmarking
        # Create a tiny custom function that tells the background thread exactly what to do
        def run_fn(progress_cb, status_cb):
            # Run the comprehensive benchmark (includes both accuracy and timing)
            benchmarking.run_comprehensive_benchmark(
                base_method=method, 
                output_dir=output_dir, 
                duration_seconds=15.0, 
                progress_callback=progress_cb, 
                status_callback=status_cb
            )
        # Send this custom function into the background thread
        self._start_benchmark_worker(run_fn, output_dir)
    
    def apply_settings(self):
        """Takes all the settings the user chose and applies them to the software's brain."""
        # Get the tool responsible for saving data
        mgr = settings_manager.get_settings_manager()
        
        # If the user changed analysis settings...
        if self.analysis_settings:
            # Math: the audio sample rate must be exactly double the highest frequency we want to track
            config.AUDIO_CONFIG['sample_rate'] = 2 * self.analysis_settings.get('max_formant', 5000)
            # Push the chunk size into the global brain
            config.AUDIO_CONFIG['chunk_ms'] = self.analysis_settings.get('chunk_ms', 5)
            # Push the chunk quantity into the global brain
            config.AUDIO_CONFIG['number_of_chunks'] = self.analysis_settings.get('number_of_chunks', 5)
            # Push the silence threshold into the global brain
            config.AUDIO_CONFIG['min_rms_db'] = self.analysis_settings.get('min_rms_db', -60.0)
            # Update a whole bunch of math settings simultaneously
            config.ANALYSIS_CONFIG.update({
                'max_formant': self.analysis_settings.get('max_formant', 5000),
                'n_formants': self.analysis_settings.get('n_formants', 5.5),
                # Math: The physical window size is the chunk size multiplied by the number of chunks, divided by 1000 to convert to seconds
                'window_length': (config.AUDIO_CONFIG['chunk_ms'] * config.AUDIO_CONFIG['number_of_chunks']) / 1000.0,
                # Math: The time step is how fast it updates, which is one chunk size converted to seconds
                'time_step': config.AUDIO_CONFIG['chunk_ms'] / 1000.0,
                'min_f0': self.analysis_settings.get('min_f0', 60),
                'max_f0': self.analysis_settings.get('max_f0', 300),
                'min_confidence': self.analysis_settings.get('min_confidence', 0.2),
                'min_rms_db': self.analysis_settings.get('min_rms_db', -60.0),
                'formant_method': self.analysis_settings.get('formant_method', 'native'),
                'pitch_method': self.analysis_settings.get('pitch_method', 'native')                
            })
            # Command the system to memorize these analysis settings
            mgr.set('analysis', self.analysis_settings)
        
        # If the user changed smoother settings...
        if self.smoother_settings:
            # Push them into the global brain
            config.SMOOTHER_CONFIG.update(self.smoother_settings)
            # Command the system to memorize them
            mgr.set('smoother', self.smoother_settings)
        
        # If the user changed vowel plotting settings...
        if self.plotting_settings:
            # Push them into the global brain
            config.LIVEVOWEL_CONFIG.update(self.plotting_settings)
            # Command the system to memorize them
            mgr.set('plotting', self.plotting_settings)
        
        # If the user changed pitch plot settings...
        if self.pitch_plot_settings:
            # Push them into the global brain
            config.LIVEPITCH_CONFIG.update(self.pitch_plot_settings)
            # Command the system to memorize them
            mgr.set('pitch_plot', self.pitch_plot_settings)
        
        # If the user changed spectrogram settings...
        if self.spectrogram_settings:
            # Push them into the global brain
            config.LIVESPECTROGRAM_CONFIG.update(self.spectrogram_settings)
            # Command the system to memorize them
            mgr.set('spectrogram', self.spectrogram_settings)
        
        # If the user changed spectrum settings...
        if self.spectrum_settings:
            # Push them into the global brain
            config.LIVESPECTRUM_CONFIG.update(self.spectrum_settings)
            # Command the system to memorize them
            mgr.set('spectrum', self.spectrum_settings)
        
        # If the user changed recording settings...
        if self.recording_settings:
            # Push them into the global brain
            config.EXPORT_CONFIG.update(self.recording_settings)
            # Command the system to memorize them
            mgr.set('recording', self.recording_settings)
        
        # Tell the system to write all these memories permanently to the hard drive
        mgr.save()

    def _set_launch_buttons_enabled(self, state: bool):
        """Turns the four big launch buttons on or off."""
        # Loop through all four buttons
        for btn in (self.start_vowel_btn, self.start_pitch_btn, self.start_spectrogram_btn, self.start_spectrum_btn):
            # Turn it on (True) or off (False)
            btn.setEnabled(state)

    def _launch_module(self, module_class, name, needs_extra_args=False):
        """Starts one of the visualization programs when the user clicks a launch button."""
        # First, force all user settings to apply to the global brain
        self.apply_settings()
        # Change the text to say the program is starting
        self.status_label.setText(f"{name} running...")
        # Disable all the launch buttons so the user can't click them twice
        self._set_launch_buttons_enabled(False)
        # Hide the main menu window completely so it isn't distracting
        self.hide()

        try:
            # Create isolated clones of the master config so modules don't permanently mutate global state
            audio_cfg = config.AUDIO_CONFIG.copy()
            analysis_cfg = config.ANALYSIS_CONFIG.copy()
            
            # Check if this specific program requires extra information to run
            if needs_extra_args:
                # Figure out which configuration file to pass it based on its name
                cfg = config.LIVESPECTROGRAM_CONFIG if "Spectrogram" in name else config.LIVESPECTRUM_CONFIG
                # Figure out which user overrides to pass it based on its name
                user_cfg = self.spectrogram_settings if "Spectrogram" in name else self.spectrum_settings
                
                # Start the program with isolated configs
                module_class(
                    spec_config=dict(cfg, **user_cfg), 
                    audio_config=audio_cfg, 
                    analysis_config=analysis_cfg, 
                    input_device_index=self.audio_input_device
                )
            else:
                # Just start the program with isolated configs
                module_class(
                    audio_config=audio_cfg, 
                    analysis_config=analysis_cfg, 
                    input_device_index=self.audio_input_device
                )
        # If the program crashes...
        except Exception as e:
            # Get the crash reporting tool
            import traceback; traceback.print_exc()
            # Show the error text on the main menu
            self.status_label.setText(f"Error: {e}")
        # When the visualization program finally closes (either normally or by crashing)...
        finally:
            # Un-hide the main menu window
            self.show()
            # Turn the launch buttons back on
            self._set_launch_buttons_enabled(True)
            # Change the text back to normal
            self.status_label.setText("Ready to launch")


def main():
    """The absolute starting point of the whole application."""
    # Tell the settings manager to prepare itself
    settings_manager.init_settings()
    # Fetch the settings manager
    mgr = settings_manager.get_settings_manager()
    
    # Check if we have saved settings. If yes, immediately apply them to the global brain
    if analysis := mgr.get('analysis'): config.ANALYSIS_CONFIG.update(analysis)
    if pitch := mgr.get('pitch_plot'): config.LIVEPITCH_CONFIG.update(pitch)
    if plot := mgr.get('plotting'): config.LIVEVOWEL_CONFIG.update(plot)
    if spec := mgr.get('spectrogram'): config.LIVESPECTROGRAM_CONFIG.update(spec)
    if spectrum := mgr.get('spectrum'): config.LIVESPECTRUM_CONFIG.update(spectrum)
    
    # Start the core operating system windowing engine
    app = QApplication(sys.argv)
    # Apply a modern visual theme so it looks the same on Mac, Windows, and Linux
    app.setStyle('Fusion')
    # Create the main menu window
    window = LauncherWindow()
    # Make the main menu visible on screen
    window.show()
    # Run the program continuously until the user clicks the X to close it
    sys.exit(app.exec())

# A standard Python check to make sure the program only runs if it is opened directly
if __name__ == "__main__":
    # Start the program
    main()