"""PySide6 launcher for liveaudio applications."""
import sys
import os

try:
    import PySide6
    _qt_plugin_path = os.path.join(os.path.dirname(PySide6.__file__), "plugins", "platforms")
    if os.path.isdir(_qt_plugin_path):
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _qt_plugin_path)
except Exception:
    pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QDialog, QMessageBox,
    QComboBox, QSizePolicy, QGridLayout, QProgressBar
)
from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QPixmap

from .LiveVowel import LiveVowel
from .LivePitch import LivePitch
from .LiveSpectrogram import LiveSpectrogram
from .LiveSpectrum import LiveSpectrum

from . import config
from . import audio_devices
from . import settings_manager

from .settings_dialogs import (
    AnalysisSettingsDialog, SmootherSettingsDialog, PlottingSettingsDialog,
    PitchPlotSettingsDialog, SpectrogramSettingsDialog, SpectrumSettingsDialog,
    RecordingSettingsDialog
)
from .ipalabels import get_resource_path

class BenchmarkProgressDialog(QDialog):
    """A popup window that blocks the main screen and shows a loading bar while the computer does heavy testing."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Benchmark Recording")
        self.setMinimumWidth(360)

        layout = QVBoxLayout()
        self.status_label = QLabel("Preparing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        note = QLabel("Please speak during recording.")
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color: #666;")
        layout.addWidget(note)
        self.setLayout(layout)

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def set_status(self, text):
        self.status_label.setText(text)


class BenchmarkWorker(QObject):
    """A background helper that runs heavy tasks so the main screen doesn't freeze up."""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str, str)

    def __init__(self, run_fn, output_dir):
        super().__init__()
        self.run_fn = run_fn
        self.output_dir = output_dir

    def run(self):
        try:
            self.status.emit("Starting benchmark...")
            self.run_fn(self._on_progress, self._on_status)
            self.status.emit("Benchmark complete!")
            self.progress.emit(100)
            self.finished.emit(True, "Benchmark complete.", self.output_dir)
        except Exception as exc:
            import traceback
            msg = f"Benchmark failed: {str(exc)}"
            self.status.emit(f"ERROR: {msg}")
            traceback.print_exc()
            self.finished.emit(False, msg, self.output_dir)

    def _on_progress(self, fraction):
        self.progress.emit(int(max(0.0, min(1.0, fraction)) * 100))

    def _on_status(self, text):
        self.status.emit(text)


class LauncherWindow(QMainWindow):
    """The main menu window that the user sees when they open the program."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VocalTrack")
        self.setMinimumSize(400, 400)

        self.audio_input_device = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

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
            title.setText("VocalTrack")
            title.setStyleSheet("font-size: 28px; font-weight: bold;")
            title.setAlignment(Qt.AlignCenter)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        settings_group = QGroupBox("")
        settings_layout = QGridLayout()

        self._add_settings_btn(settings_layout, "Analysis Settings", self.open_analysis_settings, 0, 0)
        self._add_settings_btn(settings_layout, "Smoother Settings", self.open_smoother_settings, 1, 0)
        self._add_settings_btn(settings_layout, "Recording Settings", self.open_recording_settings, 2, 0)
        self._add_settings_btn(settings_layout, "Benchmarking", self.open_benchmark_settings_dialog, 3, 0)

        self._add_settings_btn(settings_layout, "Formant Plot Settings", self.open_plotting_settings, 0, 1)
        self._add_settings_btn(settings_layout, "Pitch Plot Settings", self.open_pitch_plot_settings, 1, 1)
        self._add_settings_btn(settings_layout, "Spectrogram Settings", self.open_spectrogram_settings, 2, 1)
        self._add_settings_btn(settings_layout, "Spectrum Settings", self.open_spectrum_settings, 3, 1)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        main_layout.addStretch()

        launch_layout = QGridLayout()
        self.start_vowel_btn = self._create_launch_btn("LiveVowel", "#4CAF50", "#45a049", lambda: self._launch_module(LiveVowel, "LiveVowel"))
        self.start_pitch_btn = self._create_launch_btn("LivePitch", "#2196F3", "#1e88e5", lambda: self._launch_module(LivePitch, "LivePitch"))
        self.start_spectrogram_btn = self._create_launch_btn("LiveSpectrogram", "#9C27B0", "#7B1FA2", lambda: self._launch_module(LiveSpectrogram, "LiveSpectrogram", True))
        self.start_spectrum_btn = self._create_launch_btn("LiveSpectrum", "#e07319", "#c76412", lambda: self._launch_module(LiveSpectrum, "LiveSpectrum", True))

        launch_layout.addWidget(self.start_vowel_btn, 0, 0)
        launch_layout.addWidget(self.start_pitch_btn, 0, 1)
        launch_layout.addWidget(self.start_spectrogram_btn, 1, 0)
        launch_layout.addWidget(self.start_spectrum_btn, 1, 1)
        main_layout.addLayout(launch_layout)

        self.status_label = QLabel("Ready to launch")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("margin-top: 10px; color: #666;")
        main_layout.addWidget(self.status_label)

        self.analysis_settings = {}
        self.smoother_settings = {}
        self.plotting_settings = {}
        self.pitch_plot_settings = {}
        self.spectrogram_settings = {}
        self.spectrum_settings = {}
        self.recording_settings = {}

        self._benchmark_thread = None
        self._benchmark_worker = None
        self._benchmark_dialog = None

        self.load_saved_settings()

    def _add_settings_btn(self, layout, text, callback, row, col):
        btn = QPushButton(text)
        btn.setMinimumHeight(40)
        btn.clicked.connect(callback)
        layout.addWidget(btn, row, col)

    def _create_launch_btn(self, text, bg, hover, callback):
        btn = QPushButton(text)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setMinimumHeight(50)
        btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 16px; background-color: {bg}; color: white;
                border-radius: 5px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """)
        btn.clicked.connect(callback)
        return btn

    def load_saved_settings(self):
        mgr = settings_manager.get_settings_manager()
        if saved := mgr.get('analysis', {}): self.analysis_settings = saved
        if saved := mgr.get('smoother', {}): self.smoother_settings = saved
        if saved := mgr.get('plotting', {}): self.plotting_settings = saved
        if saved := mgr.get('pitch_plot', {}): self.pitch_plot_settings = saved
        if saved := mgr.get('spectrogram', {}): self.spectrogram_settings = saved
        if saved := mgr.get('spectrum', {}): self.spectrum_settings = saved
        if saved := mgr.get('recording', {}): self.recording_settings = saved

    def open_analysis_settings(self):
        dialog = AnalysisSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.analysis_settings = dialog.get_settings()
            window_ms = self.analysis_settings['chunk_ms'] * self.analysis_settings['number_of_chunks']
            if window_ms < 20 or window_ms > 100:
                QMessageBox.warning(self, "Warning", f"Total analysis window ({window_ms}ms) is suboptimal. Edit code if intentional.")
            self.apply_settings()

    def open_smoother_settings(self):
        dialog = SmootherSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.smoother_settings = dialog.get_settings()
            self.apply_settings()

    def open_plotting_settings(self):
        dialog = PlottingSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.plotting_settings = dialog.get_settings()
            self.apply_settings()

    def open_pitch_plot_settings(self):
        dialog = PitchPlotSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.pitch_plot_settings = dialog.get_settings()
            self.apply_settings()

    def open_spectrogram_settings(self):
        dialog = SpectrogramSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.spectrogram_settings = dialog.get_settings()
            self.apply_settings()

    def open_spectrum_settings(self):
        dialog = SpectrumSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.spectrum_settings = dialog.get_settings()
            self.apply_settings()

    def open_recording_settings(self):
        dialog = RecordingSettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.audio_input_device = dialog.get_device_index()
            self.recording_settings = dialog.get_settings()
            self.apply_settings()

    def _get_benchmark_output_dir(self):
        base_dir = os.path.join(os.getcwd(), "benchmarking")
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    def _start_benchmark_worker(self, run_fn, output_dir):
        if self._benchmark_thread is not None: return

        self._benchmark_dialog = BenchmarkProgressDialog(self)
        self._benchmark_dialog.setModal(True)
        self._benchmark_thread = QThread(self)
        self._benchmark_worker = BenchmarkWorker(run_fn, output_dir)
        self._benchmark_worker.moveToThread(self._benchmark_thread)

        self._benchmark_thread.started.connect(self._benchmark_worker.run)
        self._benchmark_worker.progress.connect(self._benchmark_dialog.set_progress)
        self._benchmark_worker.status.connect(self._benchmark_dialog.set_status)
        self._benchmark_worker.finished.connect(self._on_benchmark_finished)
        self._benchmark_worker.finished.connect(self._benchmark_thread.quit)
        self._benchmark_worker.finished.connect(self._benchmark_worker.deleteLater)
        self._benchmark_thread.finished.connect(self._benchmark_thread.deleteLater)

        self._benchmark_thread.start()
        self._benchmark_dialog.show()

    def _on_benchmark_finished(self, ok, msg, output_dir):
        if self._benchmark_dialog: self._benchmark_dialog.close()
        if self._benchmark_thread and self._benchmark_thread.isRunning(): self._benchmark_thread.wait(2000)
        self._benchmark_thread = self._benchmark_worker = self._benchmark_dialog = None

        if ok: QMessageBox.information(self, "Benchmark Complete", f"Results saved to:\n{output_dir}")
        else: QMessageBox.warning(self, "Benchmark Failed", msg)

    def open_benchmark_settings_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Comprehensive Benchmark")
        layout = QVBoxLayout(dialog)

        info_label = QLabel(
            "Records 15 seconds of speech and compares Parselmouth\n"
            "against your chosen method for both accuracy and timing.\n"
            "Saves audio, raw data CSVs, and comprehensive report."
        )
        layout.addWidget(info_label)
        layout.addSpacing(10)

        method_combo = QComboBox()
        method_combo.addItems(["native", "custom"])

        layout.addWidget(QLabel("Compare Parselmouth against:"))
        layout.addWidget(method_combo)

        btn_layout = QHBoxLayout()
        ok_btn, cancel_btn = QPushButton("Run"), QPushButton("Cancel")
        ok_btn.clicked.connect(dialog.accept); cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(ok_btn); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted: return

        output_dir = self._get_benchmark_output_dir()
        method = method_combo.currentText()

        from .utils.get_formants import _HAS_PARSELMOUTH
        if not _HAS_PARSELMOUTH:
            QMessageBox.warning(self, "Required", "Pip install praat-parselmouth")
            return

        from . import benchmarking
        def run_fn(progress_cb, status_cb):
            benchmarking.run_comprehensive_benchmark(
                base_method=method,
                output_dir=output_dir,
                duration_seconds=15.0,
                progress_callback=progress_cb,
                status_callback=status_cb
            )
        self._start_benchmark_worker(run_fn, output_dir)

    def apply_settings(self):
        mgr = settings_manager.get_settings_manager()

        if self.analysis_settings:
            config.AUDIO_CONFIG['sample_rate'] = 2 * self.analysis_settings.get('max_formant', 5000)
            config.AUDIO_CONFIG['chunk_ms'] = self.analysis_settings.get('chunk_ms', 5)
            config.AUDIO_CONFIG['number_of_chunks'] = self.analysis_settings.get('number_of_chunks', 5)
            config.AUDIO_CONFIG['min_rms_db'] = self.analysis_settings.get('min_rms_db', -60.0)
            config.ANALYSIS_CONFIG.update({
                'max_formant': self.analysis_settings.get('max_formant', 5000),
                'n_formants': self.analysis_settings.get('n_formants', 5.5),
                'window_length': (config.AUDIO_CONFIG['chunk_ms'] * config.AUDIO_CONFIG['number_of_chunks']) / 1000.0,
                'time_step': config.AUDIO_CONFIG['chunk_ms'] / 1000.0,
                'min_f0': self.analysis_settings.get('min_f0', 60),
                'max_f0': self.analysis_settings.get('max_f0', 300),
                'min_confidence': self.analysis_settings.get('min_confidence', 0.2),
                'min_rms_db': self.analysis_settings.get('min_rms_db', -60.0),
                'formant_method': self.analysis_settings.get('formant_method', 'native'),
                'pitch_method': self.analysis_settings.get('pitch_method', 'native')
            })
            mgr.set('analysis', self.analysis_settings)

        if self.smoother_settings:
            config.SMOOTHER_CONFIG.update(self.smoother_settings)
            mgr.set('smoother', self.smoother_settings)

        if self.plotting_settings:
            config.LIVEVOWEL_CONFIG.update(self.plotting_settings)
            mgr.set('plotting', self.plotting_settings)

        if self.pitch_plot_settings:
            config.LIVEPITCH_CONFIG.update(self.pitch_plot_settings)
            mgr.set('pitch_plot', self.pitch_plot_settings)

        if self.spectrogram_settings:
            config.LIVESPECTROGRAM_CONFIG.update(self.spectrogram_settings)
            mgr.set('spectrogram', self.spectrogram_settings)

        if self.spectrum_settings:
            config.LIVESPECTRUM_CONFIG.update(self.spectrum_settings)
            mgr.set('spectrum', self.spectrum_settings)

        if self.recording_settings:
            self.recording_settings.setdefault('save_original_audio', config.EXPORT_CONFIG.get('save_original_audio', True))
            self.recording_settings.setdefault('save_downsampled_audio', config.EXPORT_CONFIG.get('save_downsampled_audio', False))
            config.EXPORT_CONFIG.update(self.recording_settings)
            mgr.set('recording', self.recording_settings)

        mgr.save()

    def _set_launch_buttons_enabled(self, state: bool):
        for btn in (self.start_vowel_btn, self.start_pitch_btn, self.start_spectrogram_btn, self.start_spectrum_btn):
            btn.setEnabled(state)

    def _launch_module(self, module_class, name, needs_extra_args=False):
        self.apply_settings()
        self.status_label.setText(f"{name} running...")
        self._set_launch_buttons_enabled(False)
        self.hide()

        try:
            audio_cfg = config.AUDIO_CONFIG.copy()
            analysis_cfg = config.ANALYSIS_CONFIG.copy()

            if needs_extra_args:
                cfg = config.LIVESPECTROGRAM_CONFIG if "Spectrogram" in name else config.LIVESPECTRUM_CONFIG
                user_cfg = self.spectrogram_settings if "Spectrogram" in name else self.spectrum_settings
                app_instance = module_class(
                    spec_config=dict(cfg, **user_cfg),
                    audio_config=audio_cfg,
                    analysis_config=analysis_cfg,
                    input_device_index=self.audio_input_device
                )
                if "Spectrogram" in name:
                    self.spectrogram_settings['gui_width'] = app_instance.spec_config['gui_width']
                    self.spectrogram_settings['gui_height'] = app_instance.spec_config['gui_height']
                else:
                    self.spectrum_settings['gui_width'] = app_instance.spec_config['gui_width']
                    self.spectrum_settings['gui_height'] = app_instance.spec_config['gui_height']
            else:
                app_instance = module_class(
                    audio_config=audio_cfg,
                    analysis_config=analysis_cfg,
                    input_device_index=self.audio_input_device
                )
                if name == "LiveVowel":
                    self.plotting_settings['gui_size'] = app_instance.gui_info['gui_size']
                elif name == "LivePitch":
                    self.pitch_plot_settings['gui_width'] = app_instance.pitch_config['gui_width']
                    self.pitch_plot_settings['gui_height'] = app_instance.pitch_config['gui_height']
        except Exception as e:
            import traceback; traceback.print_exc()
            self.status_label.setText(f"Error: {e}")
        finally:
            # Save any on-the-fly window resize changes to user settings
            mgr = settings_manager.get_settings_manager()
            if self.plotting_settings:
                config.LIVEVOWEL_CONFIG.update(self.plotting_settings)
                mgr.set('plotting', self.plotting_settings)
            if self.pitch_plot_settings:
                config.LIVEPITCH_CONFIG.update(self.pitch_plot_settings)
                mgr.set('pitch_plot', self.pitch_plot_settings)
            if self.spectrogram_settings:
                config.LIVESPECTROGRAM_CONFIG.update(self.spectrogram_settings)
                mgr.set('spectrogram', self.spectrogram_settings)
            if self.spectrum_settings:
                config.LIVESPECTRUM_CONFIG.update(self.spectrum_settings)
                mgr.set('spectrum', self.spectrum_settings)
            mgr.save()

            self.show()
            self._set_launch_buttons_enabled(True)
            self.status_label.setText("Ready to launch")


def main():
    """Entry point for the VocalTrack application."""
    settings_manager.init_settings()
    mgr = settings_manager.get_settings_manager()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Query monitor resolution on startup to configure smart defaults if no saved settings exist
    screen = app.primaryScreen()
    has_large_screen = True
    if screen:
        screen_size = screen.size()
        # If screen vertical resolution is less than 1080 (e.g., 768p or lower), flag as small screen
        if screen_size.height() < 1080:
            has_large_screen = False

    # Check for saved settings, update in-memory config
    analysis = mgr.get('analysis')
    if analysis:
        config.ANALYSIS_CONFIG.update(analysis)

    pitch = mgr.get('pitch_plot')
    if pitch:
        config.LIVEPITCH_CONFIG.update(pitch)
    elif not has_large_screen:
        # Override to small screen defaults for 768p
        config.LIVEPITCH_CONFIG['gui_width'] = 1400
        config.LIVEPITCH_CONFIG['gui_height'] = 900

    plot = mgr.get('plotting')
    if plot:
        config.LIVEVOWEL_CONFIG.update(plot)
    elif not has_large_screen:
        # Override to small screen defaults for 768p
        config.LIVEVOWEL_CONFIG['gui_size'] = (1200.0, 900.0)

    spec = mgr.get('spectrogram')
    if spec:
        config.LIVESPECTROGRAM_CONFIG.update(spec)
    elif not has_large_screen:
        # Override to small screen defaults for 768p
        config.LIVESPECTROGRAM_CONFIG['gui_width'] = 1400
        config.LIVESPECTROGRAM_CONFIG['gui_height'] = 900

    spectrum = mgr.get('spectrum')
    if spectrum:
        config.LIVESPECTRUM_CONFIG.update(spectrum)
    elif not has_large_screen:
        # Override to small screen defaults for 768p
        config.LIVESPECTRUM_CONFIG['gui_width'] = 1400
        config.LIVESPECTRUM_CONFIG['gui_height'] = 900

    window = LauncherWindow()
    window.show()
    sys.exit(app.exec())
