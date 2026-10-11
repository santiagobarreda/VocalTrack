# Import threading to run audio capture in a background thread, ensuring the GUI remains responsive
import threading
# Import queue for thread-safe communication between audio capture/analysis threads and the main thread
import queue
import math
# Import Qt core app and QtMultimedia audio capture APIs
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices, QAudio
# Import numpy for efficient numerical array operations on audio samples
import numpy as np
# Import logging for debug/error messages and warnings
import logging
import time

# Import the Sound class for pitch and formant analysis (using relative import)
from .Sound import Sound
try:
    # Try to import config and set up logging level from configuration
    from . import config
    logging.basicConfig(level=config.PERFORMANCE_CONFIG.get('logging_level', logging.WARNING))
except (ImportError, AttributeError):
    # Silently continue if config import fails or PERFORMANCE_CONFIG missing
    # This happens during some test scenarios or if config doesn't define PERFORMANCE_CONFIG
    pass

# Create a logger instance for this module
logger = logging.getLogger(__name__)


class AudioProcessor(QThread):
    """
    Continuously captures audio from the system microphone and queues samples for analysis.

    This class runs in a separate thread to avoid blocking the main GUI thread. Audio samples 
    are buffered and made available for analysis and visualization. Analysis (pitch and formant extraction) 
    is performed in a dedicated worker thread to ensure real-time performance.

    The sample rate is always calculated as 2 × max_formant (Nyquist theorem) for efficient analysis. There 
    is no option to override this, as higher rates waste computation time.
    Audio is captured in chunks of chunk_ms, and each new chunk triggers one analysis of the most
    recent window_ms of audio. The chunk is therefore the time step between analyses (the visualizers
    set it to one display frame, or to the time step setting in LiveSpectrogram), and consecutive
    windows overlap by window_ms - chunk_ms.

    """
    
    # Input devices that recently failed to deliver audio (name -> time of the failure), shared by
    # all AudioProcessors so that a new recording does not begin by retrying a device that just failed
    _failed_devices = {}

    def __init__(self, chunk_ms=None, window_ms=None, analysis_config=None, min_rms_db=None,
                 input_device_index=None, raw_queue_maxsize=50, analyzed_queue_maxsize=50,
                 input_device_name=None):
        """
        Initialize the audio processor thread and configure audio capture and analysis parameters.

        Args:
            chunk_ms (float, optional): Duration of each audio chunk in milliseconds, which is the
                time step between analyses. Defaults to one frame of a 60 Hz display.
            window_ms (float, optional): Length of each analysis window in milliseconds. Defaults to
                the analysis_config window_length, or 50.
            analysis_config (dict, optional): Analysis configuration dictionary. Defaults to None.
            min_rms_db (float, optional): Minimum RMS in dB for analysis. If provided, overrides config value.
            input_device_index (int, optional): Audio input device index. None uses system default.
            raw_queue_maxsize (int, optional): Maximum size for raw samples queue. Defaults to 50.
            analyzed_queue_maxsize (int, optional): Maximum size for analyzed sounds queue. Defaults to 50.
            input_device_name (str, optional): Audio input device name. Takes priority over
                input_device_index, whose position in the device list can change when devices
                are plugged in or removed.
        """
        # Initialize the parent QThread class
        super(AudioProcessor, self).__init__()
        
        # ALWAYS calculate sample rate as 2×max_formant (Nyquist theorem)
        # There is no reason to sample faster than 2× the highest frequency we want to analyze
        max_formant = (analysis_config or {}).get('max_formant', 5000)
        sample_rate = 2 * max_formant
        # A visualizer may request a higher stream rate (LiveSpectrum does, so max formant can be
        # changed live; formant analysis then resamples each window to 2 x max_formant)
        requested_rate = (analysis_config or {}).get('analysis_sample_rate')
        if requested_rate:
            sample_rate = int(requested_rate)
        
        # Store analysis sample rate (samples per second, always calculated as 2×max_formant)
        # This is the rate used by Sound analysis and by the recording buffer.
        self.sample_rate = sample_rate
        self.analysis_sample_rate = sample_rate
        self.device_sample_rate = sample_rate
        self.recording_sample_rate = sample_rate
        
        # Safely handle default parameters if None is passed
        if chunk_ms is None:
            chunk_ms = (analysis_config or {}).get('chunk_ms') or config.chunk_ms_for_fps(60)
        if window_ms is None:
            window_ms = (analysis_config or {}).get('window_ms') or \
                1000.0 * float((analysis_config or {}).get('window_length', 0.05))

        # Store chunk duration in milliseconds (the time step between analyses)
        self.chunk_ms = chunk_ms
        # Store analysis window length in milliseconds
        self.window_ms = window_ms
        # Store analysis configuration (passed to Sound objects)
        self.analysis_config = analysis_config or {}
        
        # If min_rms_db is explicitly provided, merge it into analysis_config (overrides config value)
        if min_rms_db is not None:
            self.analysis_config['min_rms_db'] = min_rms_db
        
        # Store audio input device name and index (None = system default)
        self.input_device_name = input_device_name or None
        self.input_device_index = input_device_index
        
        # Calculate analysis chunk size from chunk duration in ms
        self.chunk_size = max(round(chunk_ms * sample_rate / 1000), 1)
        self.device_chunk_size = self.chunk_size

        # Spectrum window size from the window length (independent of the chunk size)
        self.spectrum_window_samples = max(round(window_ms * sample_rate / 1000), 1)

        # Formant & pitch analysis window length from the analysis settings (window_ms in seconds)
        formant_window_sec = float((analysis_config or {}).get('window_length', config.ANALYSIS_CONFIG.get('window_length', 0.05)))
        self.formant_window_samples = max(int(round(formant_window_sec * sample_rate)), self.spectrum_window_samples)
        
        # Total stitched buffer size handed to Sound: max of spectrum window and formant window
        self.window_samples = max(self.spectrum_window_samples, self.formant_window_samples)
        
        # Inform Sound of the exact spectrum slice length
        self.analysis_config['spectrum_window_samples'] = self.spectrum_window_samples
        
        # Qt audio stream object (initialized in run())
        self.stream = None
        
        # Thread-safe queue for passing normalized audio vectors from capture thread to analysis thread
        # Contains float32 numpy arrays (normalized to [-1.0, 1.0])
        self.raw_samples_queue = queue.Queue(maxsize=raw_queue_maxsize)
        
        # Thread-safe queue for passing analyzed Sound objects from analysis thread to main thread
        # Contains Sound objects with pitch/formants already calculated
        self.analyzed_sounds_queue = queue.Queue(maxsize=analyzed_queue_maxsize)
        
        # Flag to control thread execution (set to False to stop thread)
        self.running = True
        
        # Calculate how many samples from previous chunks to keep for stitching
        last_len = max(self.window_samples - self.chunk_size, 0)
        # Buffer to store samples from previous chunk for overlap-add
        self.last_samples = np.zeros(last_len)
        
        # Analysis thread handle (will be started in run())
        self.analysis_thread = None
        # Store QAudioSource instance for proper cleanup
        self.port = None
        # Flag indicating whether to save raw audio to buffer
        self.recording_enabled = False
        # Thread lock to protect recording buffer from concurrent access
        self.recording_lock = threading.Lock()
        # Rates and counters for the performance monitor overlay
        self.captured_chunks_count = 0
        self.analyzed_windows_count = 0
        self.last_rate_update_time = time.perf_counter()
        self.current_capture_rate = 0.0
        self.current_analysis_rate = 0.0
        # Device-rate/original recording and analysis-rate/downsampled recording, each kept as a
        # list of int16 arrays (one per chunk) that is joined when the recording is collected
        self.raw_recording = []
        self.downsampled_recording = []
        self.record_original_stream = True
        self.record_downsampled_stream = False
        self.recording_sample_count = 0
        # Device error / status broadcast to visualizers
        self.device_status_message = None
        # Reconnection state: remember which device we're supposed to be on so we can find
        # it again by name if it drops out, and throttle how often we retry.
        self._connected_device_name = None
        self._preferred_device_name = None
        self._last_reconnect_attempt = 0.0
        self._reconnect_interval_sec = 2.0
        # A stream that delivers no audio is treated as disconnected: Qt can go on listing a device
        # after it has been unplugged, and opening it then succeeds without ever producing audio
        self._no_audio_start_sec = 2.0  # Time allowed for the first audio after a stream is opened
        self._no_audio_stall_sec = 1.0  # Time without audio on a stream that had been delivering it
        self._failed_retry_sec = 5.0    # How long a device that failed is left alone
        self._last_data_time = 0.0
        self._stream_verified = False       # The current stream has delivered audio
        self._stream_failed_before = False  # A stream failed earlier (for the "Reconnected" message)
        # Second audio source used to check the preferred device while a fallback device is in use
        self._probe_port = None
        self._probe_stream = None
        self._probe_started = 0.0
        self._last_probe_time = 0.0
        # Polyphase resampler state (configured in run() once device format is known)
        self._resample_up = 1
        self._resample_down = 1
        self._polyphase_filters = None
        self._polyphase_history = np.zeros(0, dtype=np.float64)
        self._resample_delay = 0.0     # Filter group delay, in device samples
        self._resample_in_count = 0    # Device samples fed to the resampler on the current stream
        self._resample_out_count = 0   # Analysis samples produced on the current stream
        # Resampled audio waiting to be cut into analysis chunks, and the position of each sample
        # in the original recording (device samples since start_recording; NaN when not recording)
        self._analysis_fifo = np.zeros(0, dtype=np.float32)
        self._analysis_fifo_pos = np.zeros(0, dtype=np.float64)
        # Sequence number of each analysis chunk, so the analysis thread can detect gaps
        # (chunks dropped because the queue was full, or a new stream after a reconnect)
        self._chunk_seq = 0
        # Sample rate of the current recording, fixed by its first recorded chunk, so a
        # reconnect to another device afterwards cannot change the rate reported for export
        self._recording_rate = None
        # Time (s) at which a device disconnect stopped the recording, until a visualizer takes it
        self._recording_interrupted_at = None

    def _configure_resampler(self):
        """
        Configure a streaming polyphase rational resampler for device->analysis conversion.

        This is a native NumPy implementation (no scipy):
        - Rational ratio reduction (up/down)
        - Kaiser-windowed sinc low-pass prototype: flat to 90% of the lower Nyquist frequency,
          at least 70 dB of attenuation from that Nyquist frequency up (anti-aliasing)
        - Polyphase filter bank, evaluated for a whole chunk at once
        """
        in_rate = int(max(1, self.device_sample_rate))
        out_rate = int(max(1, self.analysis_sample_rate))

        g = math.gcd(in_rate, out_rate)
        self._resample_up = max(1, out_rate // g)
        self._resample_down = max(1, in_rate // g)

        # A new stream starts a new resampler timeline and discards any partial chunk
        self._resample_in_count = 0
        self._resample_out_count = 0
        self._analysis_fifo = np.zeros(0, dtype=np.float32)
        self._analysis_fifo_pos = np.zeros(0, dtype=np.float64)

        if self._resample_up == 1 and self._resample_down == 1:
            self._polyphase_filters = None
            self._polyphase_history = np.zeros(0, dtype=np.float64)
            self._resample_delay = 0.0
            return

        # Prototype low-pass design in the upsampled domain. Frequencies are relative to the
        # Nyquist frequency of the upsampled sequence; the lower of the input/output Nyquist
        # frequencies is 1/M on that scale.
        M = float(max(self._resample_up, self._resample_down))
        atten_db = 70.0
        passband_edge = 0.90 / M
        stopband_edge = 1.00 / M
        cutoff = 0.5 * (passband_edge + stopband_edge)
        transition = stopband_edge - passband_edge
        # Kaiser window length and shape for the requested attenuation and transition width
        num_taps = int(math.ceil((atten_db - 7.95) / (2.285 * math.pi * transition))) | 1
        beta = 0.1102 * (atten_db - 8.7)
        n = np.arange(num_taps, dtype=np.float64) - (num_taps - 1) / 2.0
        h = cutoff * np.sinc(cutoff * n) * np.kaiser(num_taps, beta)
        # Unity DC gain after upsampling by up
        h *= self._resample_up / np.sum(h)

        # Pad so prototype length is divisible by number of phases.
        pad = (-len(h)) % self._resample_up
        if pad:
            h = np.pad(h, (0, pad), mode='constant')

        # Polyphase bank [phase, k] = h[phase + k * up]; output y[m] = sum_k bank[p, k] * x[n - k]
        # with n = (m * down) // up and p = (m * down) % up
        self._polyphase_filters = h.reshape(-1, self._resample_up).T.copy()
        self._polyphase_history = np.zeros(self._polyphase_filters.shape[1] - 1, dtype=np.float64)
        # The linear-phase filter delays the output by (num_taps - 1) / 2 upsampled samples
        self._resample_delay = (num_taps - 1) / 2.0 / self._resample_up

        logger.info(f"Polyphase resampler configured: up={self._resample_up}, down={self._resample_down}, "
                    f"phases={self._polyphase_filters.shape[0]}, taps_per_phase={self._polyphase_filters.shape[1]}")

    def _resample_chunk(self, normalized_samples):
        """
        Resample one mono device chunk using the streaming polyphase filter bank.

        The number of output samples varies from chunk to chunk whenever the rate ratio does not
        divide the chunk evenly; nothing is padded or dropped.

        Returns:
            tuple: (resampled float32 samples, float64 array giving each output sample's time on
            the current stream in device samples, corrected for the filter delay)
        """
        x = np.asarray(normalized_samples, dtype=np.float64)
        start_in = self._resample_in_count
        end_in = start_in + x.size

        if self._polyphase_filters is None:
            self._resample_in_count = end_in
            self._resample_out_count += x.size
            return x.astype(np.float32), np.arange(start_in, end_in, dtype=np.float64)

        up, down = self._resample_up, self._resample_down
        n_taps = self._polyphase_filters.shape[1]
        # buf[j] holds device sample (start_in - (n_taps - 1) + j) of the current stream
        buf = np.concatenate([self._polyphase_history, x])

        # Every output sample whose newest input sample has now arrived: m * down / up < end_in
        m_end = -(-(end_in * up) // down)
        m = np.arange(self._resample_out_count, m_end, dtype=np.int64)
        pos = m * down
        n = pos // up
        phase = pos % up
        idx = (n - start_in + n_taps - 1)[:, None] - np.arange(n_taps)[None, :]
        y = np.einsum('ij,ij->i', self._polyphase_filters[phase], buf[idx])

        if n_taps > 1:
            self._polyphase_history = buf[-(n_taps - 1):]
        self._resample_in_count = end_in
        self._resample_out_count = m_end

        times = pos / float(up) - self._resample_delay
        return np.clip(y, -1.0, 1.0).astype(np.float32), times

    def _process_device_chunk(self, normalized_samples, samples):
        """
        Record one mono device chunk, resample it to the analysis rate, and queue complete
        analysis chunks for the analysis thread.

        Args:
            normalized_samples (ndarray): float32 samples in [-1, 1] at the device rate.
            samples (ndarray): The same samples as int16, for the original-rate recording.
        """
        # Preserve device-rate mono Int16 samples for high-fidelity export.
        recorded_count = None
        with self.recording_lock:
            if self.recording_enabled:
                if self._recording_rate is None:
                    self._recording_rate = self.recording_sample_rate
                self.recording_sample_count += len(samples)
                if self.record_original_stream:
                    self.raw_recording.append(np.array(samples, dtype=np.int16))
                recorded_count = self.recording_sample_count

        stream_end = self._resample_in_count + len(normalized_samples)
        resampled, times = self._resample_chunk(normalized_samples)

        # Position of each analysis sample in the original recording (device samples since
        # start_recording): the newest recorded device sample is recorded_count - 1 and is
        # stream sample stream_end - 1
        if recorded_count is not None:
            positions = recorded_count - (stream_end - times)
            with self.recording_lock:
                # Skip the few output samples (filter delay) that precede the recording start,
                # so the downsampled recording starts at the same instant as the original
                keep = positions >= 0
                if self.record_downsampled_stream:
                    downsampled_samples = np.clip(resampled[keep] * 32767.0, -32768, 32767).astype(np.int16)
                    self.downsampled_recording.append(downsampled_samples)
        else:
            positions = np.full(resampled.size, np.nan)

        self._analysis_fifo = np.concatenate([self._analysis_fifo, resampled])
        self._analysis_fifo_pos = np.concatenate([self._analysis_fifo_pos, positions])

        # Cut the resampled stream into fixed-size analysis chunks
        while self._analysis_fifo.size >= self.chunk_size:
            chunk = self._analysis_fifo[:self.chunk_size]
            last_pos = self._analysis_fifo_pos[self.chunk_size - 1]
            self._analysis_fifo = self._analysis_fifo[self.chunk_size:]
            self._analysis_fifo_pos = self._analysis_fifo_pos[self.chunk_size:]

            # Time (s) of the chunk's last sample in the exported original WAV, or None
            last_time = None if np.isnan(last_pos) else last_pos / float(self.recording_sample_rate)
            seq = self._chunk_seq
            self._chunk_seq += 1

            # Use put_nowait to avoid blocking the real-time audio capture loop
            try:
                self.raw_samples_queue.put_nowait((chunk, last_time, seq))
                with self.recording_lock:
                    self.captured_chunks_count += 1
            except queue.Full:
                # Analysis is slower than capture: drop this chunk. The analysis thread sees the
                # gap in sequence numbers and does not stitch across it.
                logger.warning("Raw samples queue full, dropping frame")

    def _find_device_by_name(self, name):
        """Look up a currently-available QAudioDevice by its description string, or None."""
        if not name:
            return None
        for device in QMediaDevices.audioInputs():
            if device.description() == name:
                return device
        return None

    def _candidate_devices(self):
        """
        Input devices to try, best first: the preferred device, then the system default, then the
        rest. Devices that failed to deliver audio in the last _failed_retry_sec are left out, so
        the next attempt goes to another device.
        """
        now = time.perf_counter()
        devices = []
        preferred = self._find_device_by_name(self._preferred_device_name)
        for device in [preferred, QMediaDevices.defaultAudioInput()] + list(QMediaDevices.audioInputs()):
            if device is None or device.isNull():
                continue
            name = device.description()
            if any(d.description() == name for d in devices):
                continue
            if now - AudioProcessor._failed_devices.get(name, -1e9) < self._failed_retry_sec:
                continue
            devices.append(device)
        return devices

    def _open_stream(self, input_device):
        """
        Open a QAudioSource stream on the given device, configuring the device sample rate,
        chunk size, and resampler for it. Used both for the first connection and for
        reconnecting after a disconnect (the device's native format may differ each time).

        A stream that opens is not yet known to work: Qt can go on listing a device after it has
        been unplugged, and opening it then succeeds without ever delivering audio. The capture
        loop confirms the stream when audio arrives, and gives up on it otherwise.

        Returns (audio_format, bytes_per_chunk) on success, or None if the stream failed to start.
        """
        # Always open the hardware in its preferred/native format (typically 44.1kHz or 48kHz)
        # This ensures high-fidelity exports and avoids buggy OS/driver-level resampling conversions.
        audio_format = input_device.preferredFormat()

        # Keep the analysis rate unchanged and adapt the device capture chunking + resample in software.
        device_sample_rate = audio_format.sampleRate() if audio_format.sampleRate() > 0 else self.analysis_sample_rate
        device_chunk_size = max(round(self.chunk_ms * device_sample_rate / 1000), 1)

        # Similarly, if the audio format is not Int16, we will need to convert raw bytes to Int16 ourselves in the capture loop.
        # We will still request Int16, but if we get something else (e.g., Float), we can handle it in software.
        bytes_per_frame = audio_format.bytesPerFrame()
        if bytes_per_frame <= 0:
            bytes_per_sample = {
                QAudioFormat.SampleFormat.UInt8: 1,
                QAudioFormat.SampleFormat.Int16: 2,
                QAudioFormat.SampleFormat.Int32: 4,
                QAudioFormat.SampleFormat.Float: 4,
            }.get(audio_format.sampleFormat(), 2)
            bytes_per_frame = bytes_per_sample * max(1, audio_format.channelCount())
        bytes_per_chunk = device_chunk_size * bytes_per_frame

        port = QAudioSource(input_device, audio_format)
        port.setBufferSize(max(bytes_per_chunk * 8, 4096))
        stream = port.start()
        if stream is None:
            return None

        # The stream started: use its rate from here on. Recording always follows the true capture device rate.
        self.device_sample_rate = device_sample_rate
        self.device_chunk_size = device_chunk_size
        self.recording_sample_rate = device_sample_rate
        self._configure_resampler()
        # Skip a sequence number so the analysis thread never stitches audio from different streams
        self._chunk_seq += 1

        self.port = port
        self.stream = stream
        self._connected_device_name = input_device.description()
        self._last_data_time = time.perf_counter()
        self._stream_verified = False
        logger.info(
            f"Audio stream opened: device='{self._connected_device_name}' "
            f"{self.device_sample_rate}Hz/{self.device_chunk_size} samples, analysis={self.analysis_sample_rate}Hz/{self.chunk_size} samples"
        )
        return audio_format, bytes_per_chunk

    def _close_stream(self):
        """Stop and forget the current stream (if any)."""
        try:
            if self.port:
                self.port.stop()
        except Exception:
            pass
        self.port = None
        self.stream = None

    def _stream_failed(self):
        """
        The current stream reported an error or stopped delivering audio. End any recording here
        (audio from another device is never spliced in), close the stream, and leave the device
        alone for _failed_retry_sec so the next attempt goes to another device.
        """
        name = self._connected_device_name
        AudioProcessor._failed_devices[name] = time.perf_counter()
        self._interrupt_recording()
        if self._stream_verified:
            self.device_status_message = f"Audio device '{name}' disconnected - attempting to reconnect"
        else:
            self.device_status_message = f"No audio from '{name}' - trying another device"
        self._stream_failed_before = True
        self._close_stream()
        self._last_reconnect_attempt = 0.0  # try another device straight away

    def _announce_stream(self):
        """Tell the user which device is in use, once a newly opened stream has delivered audio."""
        name = self._connected_device_name
        if self._preferred_device_name and name != self._preferred_device_name:
            self.device_status_message = f"'{self._preferred_device_name}' unavailable - using '{name}'"
            logger.warning(f"Preferred audio device '{self._preferred_device_name}' unavailable; using '{name}'")
        elif self._stream_failed_before:
            self.device_status_message = f"Reconnected to '{name}'"
            logger.info(f"Reconnected to preferred audio device '{name}'")
        self._stream_failed_before = False

    def _maybe_reconnect(self):
        """
        With no stream open, try the candidate devices in order (at most once every
        _reconnect_interval_sec) until one opens. If the preferred device is missing or has just
        failed, this falls back to another device so capture can resume.

        Returns (audio_format, bytes_per_chunk) if a stream was opened, else None.
        """
        now = time.perf_counter()
        if now - self._last_reconnect_attempt < self._reconnect_interval_sec:
            return None
        self._last_reconnect_attempt = now

        for device in self._candidate_devices():
            opened = self._open_stream(device)
            if opened is not None:
                return opened

        # Keep a message that has not been shown yet (e.g. that the device just disconnected)
        if not self.device_status_message:
            waiting_for = f" - waiting for '{self._preferred_device_name}'" if self._preferred_device_name else ""
            self.device_status_message = f"No working audio input device{waiting_for}"
        return None

    def _stop_probe(self):
        """Stop the second audio source used to check the preferred device (if any)."""
        try:
            if self._probe_port:
                self._probe_port.stop()
        except Exception:
            pass
        self._probe_port = None
        self._probe_stream = None

    def _probe_preferred(self):
        """
        While a fallback device is in use and nothing is being recorded, look for the preferred
        device by name every _reconnect_interval_sec. If it is listed, check that it delivers audio
        with a second audio source, so the current stream is not disturbed, and switch back to it
        once it does.

        Returns (audio_format, bytes_per_chunk) if the active stream just changed, else None.
        """
        if self.recording_enabled:
            self._stop_probe()  # never switch devices during a recording; switch back once it has stopped
            return None

        now = time.perf_counter()
        name = self._preferred_device_name
        if self._probe_port is None:
            if now - self._last_probe_time < self._reconnect_interval_sec:
                return None
            self._last_probe_time = now
            device = self._find_device_by_name(name)
            if device is None or now - AudioProcessor._failed_devices.get(name, -1e9) < self._failed_retry_sec:
                return None
            self._probe_port = QAudioSource(device, device.preferredFormat())
            self._probe_stream = self._probe_port.start()
            self._probe_started = now
            return None

        if self._probe_stream is not None and self._probe_stream.bytesAvailable() > 0:
            # The preferred device is delivering audio again: switch back to it
            self._stop_probe()
            device = self._find_device_by_name(name)
            if device is None:
                return None
            AudioProcessor._failed_devices.pop(name, None)
            self._close_stream()
            self._stream_failed_before = True  # so that "Reconnected" is shown
            return self._open_stream(device)

        if now - self._probe_started > self._no_audio_start_sec:
            # Listed, but not delivering audio (e.g. still unplugged): leave it alone for a while
            self._stop_probe()
            AudioProcessor._failed_devices[name] = now
        return None

    def run(self):
        """
        Open the audio stream and continuously read samples into the raw queue for analysis.

        This method runs in the thread and manages audio device selection, reconnection, error
        handling, and resource cleanup. It also starts the analysis worker thread.
        """
        try:
            # Ensure a Qt application exists before using QtMultimedia APIs
            app = QCoreApplication.instance()
            if app is None:
                app = QCoreApplication([])

            # Check if any audio input devices are available
            inputs = QMediaDevices.audioInputs()
            if not inputs:
                logger.error("No audio input devices found")

            # The device to use and keep returning to: the requested one by name (stable), else by
            # index (only used when no name was saved), otherwise the system default. If it is
            # missing or delivers no audio, capture starts on another device and switches to this
            # one when it works (never during a recording).
            preferred = self.input_device_name
            if preferred is None and self.input_device_index is not None and 0 <= self.input_device_index < len(inputs):
                preferred = inputs[self.input_device_index].description()
            if preferred is None:
                default_device = QMediaDevices.defaultAudioInput()
                if default_device is not None and not default_device.isNull():
                    preferred = default_device.description()
                elif inputs:
                    preferred = inputs[0].description()
            self._preferred_device_name = preferred

            # The stream is opened by the capture loop below, which also reopens it when needed
            audio_format = None
            bytes_per_chunk = 0
            pending_audio_bytes = bytearray()

            # Start the analysis worker thread that consumes raw samples and produces Sound objects
            self.analysis_thread = threading.Thread(target=self.analyze_worker, daemon=True)
            self.analysis_thread.start()
            logger.info("Analysis worker thread started")

            # Main capture loop - runs until self.running is set to False
            while self.running:
                # Pump the event loop for the current thread so QAudioSource can receive audio data
                QCoreApplication.processEvents()

                # Check if hardware audio input reported an error or stopped unexpectedly
                if self.port is not None:
                    err = self.port.error()
                    err_val = getattr(err, 'value', err)
                    if err not in (QAudio.Error.NoError, QAudio.NoError, 0) and err_val != 0:
                        logger.warning(f"Audio input device error: {err}")
                        self._stream_failed()

                # With no stream, try to open one (the preferred device first). On a fallback
                # device, keep checking whether the preferred device is back.
                opened = None
                if self.stream is None:
                    opened = self._maybe_reconnect()
                elif self._connected_device_name != self._preferred_device_name:
                    opened = self._probe_preferred()
                if opened is not None:
                    audio_format, bytes_per_chunk = opened
                    pending_audio_bytes = bytearray()

                if self.stream is None:
                    # No audio device available at all yet; keep polling without busy-looping
                    time.sleep(0.05)
                    continue

                # Is audio available?
                available = self.stream.bytesAvailable()
                if available <= 0:
                    # A working device delivers audio continuously, even in silence. None for this
                    # long means the device is gone, although Qt reported no error
                    limit = self._no_audio_stall_sec if self._stream_verified else self._no_audio_start_sec
                    if time.perf_counter() - self._last_data_time > limit:
                        logger.warning(f"No audio from '{self._connected_device_name}' for {limit:g} s; treating it as disconnected")
                        self._stream_failed()
                    else:
                        time.sleep(0.001)
                    continue

                # If audio is available, read it into a bytearray buffer. We may get more than one chunk's worth of audio,
                # so we need to buffer it until we have enough for at least one chunk.
                data = self.stream.read(available)
                if not data:
                    time.sleep(0.001)
                    continue

                # Audio has arrived: the stream works
                self._last_data_time = time.perf_counter()
                if not self._stream_verified:
                    self._stream_verified = True
                    self._announce_stream()

                # Append new audio bytes to the pending buffer and process in chunk-sized pieces
                pending_audio_bytes.extend(bytes(data))

                # Process pending audio bytes in chunks until we have less than one chunk left
                while len(pending_audio_bytes) >= bytes_per_chunk:

                    # Extract the next chunk of audio bytes for processing and remove it from the pending buffer
                    raw_chunk = bytes(pending_audio_bytes[:bytes_per_chunk])
                    del pending_audio_bytes[:bytes_per_chunk]

                    # Interpret raw audio bytes according to the sample format
                    # and convert to normalized float32 samples
                    sample_format = audio_format.sampleFormat()
                    channels = max(1, audio_format.channelCount())

                    # Convert raw bytes to numpy array of the appropriate dtype based on sample format
                    # Then normalize to float32 in range [-1.0, 1.0] for analysis. Also keep raw int16 samples for recording.
                    if sample_format == QAudioFormat.SampleFormat.Int16:
                        raw = np.frombuffer(raw_chunk, dtype=np.int16)
                        normalized_samples = raw.astype(np.float32) / 32768.0
                        samples = raw
                    elif sample_format == QAudioFormat.SampleFormat.Int32:
                        raw = np.frombuffer(raw_chunk, dtype=np.int32)
                        normalized_samples = raw.astype(np.float32) / 2147483648.0
                        samples = np.clip(normalized_samples * 32767.0, -32768, 32767).astype(np.int16)
                    elif sample_format == QAudioFormat.SampleFormat.UInt8:
                        raw = np.frombuffer(raw_chunk, dtype=np.uint8)
                        normalized_samples = (raw.astype(np.float32) - 128.0) / 128.0
                        samples = np.clip(normalized_samples * 32767.0, -32768, 32767).astype(np.int16)
                    elif sample_format == QAudioFormat.SampleFormat.Float:
                        raw = np.frombuffer(raw_chunk, dtype=np.float32)
                        normalized_samples = np.clip(raw.astype(np.float32), -1.0, 1.0)
                        samples = np.clip(normalized_samples * 32767.0, -32768, 32767).astype(np.int16)
                    else:
                        raise RuntimeError(f"Unsupported audio sample format: {sample_format}")

                    # If the audio is stereo, we take only the first channel for analysis and recording to keep it simple.
                    if channels > 1:
                        normalized_samples = normalized_samples.reshape(-1, channels)[:, 0]
                        samples = samples.reshape(-1, channels)[:, 0]

                    # Record, resample to the analysis rate, and queue analysis chunks
                    self._process_device_chunk(normalized_samples, samples)

        except RuntimeError as e:
            # Handle runtime errors (e.g., an unsupported sample format)
            logger.error(f"Runtime error: {e}")
            self.running = False
        except Exception as e:
            logger.error(f"Audio capture error: {e}")
            self.running = False
        finally:
            # Always clean up resources, even if an error occurred
            self._cleanup()

    def _cleanup(self):
        """
        Clean up audio resources (stream and QAudioSource instance) properly.
        Ensures that resources are released even if an error occurs.
        """
        try:
            self._stop_probe()
            if self.port:
                self.port.stop()
            self.stream = None
            self.port = None
            logger.info("Audio stream closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def stop(self):
        """
        Stop the audio processor thread gracefully and wait for it to terminate.
        """
        self.running = False
        if self.isRunning():
            if not self.wait(2000):
                logger.warning("Audio processor thread did not respond to stop signal")

    def analyze_worker(self):
        """
        Worker thread that consumes normalized audio vectors and produces Sound objects.

        This thread:
            1. Pulls normalized float32 audio vectors from raw_samples_queue
            2. Stitches overlapping windows for temporal continuity
            3. Creates Sound objects and performs pitch/formant analysis
            4. Queues analyzed Sound objects to analyzed_sounds_queue

        Runs in a separate thread to prevent analysis from blocking audio capture.
        """
        logger.info("Analysis worker thread started")

        # Sequence number of the previous chunk, and how many contiguous samples the stitched
        # window currently holds (zero-padding at startup or after a gap does not count)
        last_seq = None
        contiguous_samples = 0

        try:
            while self.running:
                # Try to get the next chunk of normalized audio samples from the raw queue
                try:
                    # Wait up to 0.1 seconds for samples to be available
                    current_samples, chunk_last_time, seq = self.raw_samples_queue.get(timeout=0.1)
                except queue.Empty:
                    # If no samples available within timeout, continue to avoid fabricating silence
                    continue

                # A gap in sequence numbers means chunks were dropped (queue full) or the stream
                # was reopened: discard the history instead of stitching across the gap
                if last_seq is not None and seq != last_seq + 1:
                    self.last_samples = np.zeros(max(self.window_samples - self.chunk_size, 0))
                    contiguous_samples = 0
                last_seq = seq
                contiguous_samples = min(contiguous_samples + len(current_samples), self.window_samples)

                # Concatenate previous samples with current samples to create overlapping window
                # This improves temporal resolution and reduces edge effects in analysis
                samples_output = np.concatenate([self.last_samples, current_samples], axis=0)
                
                # Ensure output is exactly window_samples long
                if samples_output.shape[0] > self.window_samples:
                    # If too long, keep only the most recent window_samples
                    samples_output = samples_output[-self.window_samples:]
                elif samples_output.shape[0] < self.window_samples:
                    # If too short, pad with zeros at the beginning
                    pad_len = self.window_samples - samples_output.shape[0]
                    samples_output = np.pad(samples_output, (pad_len, 0))

                # Update last_samples buffer for next iteration
                last_len = max(self.window_samples - self.chunk_size, 0)
                if last_len > 0:
                    # Keep the historical buffer for overlap stitching
                    self.last_samples = samples_output[-last_len:]
                else:
                    # No stitching needed if only one chunk
                    self.last_samples = np.zeros(0)

                # Only analyze windows made entirely of contiguous audio (not the zero-padded
                # windows at startup or right after a gap)
                if contiguous_samples < self.window_samples:
                    continue

                # Create a Sound object with the windowed samples and perform analysis
                # This is where LPC and pitch tracking happen (relatively expensive operations)
                try:
                    sound_object = Sound(samples_output, sample_rate=self.sample_rate, **self.analysis_config)
                except Exception as e:
                    # Skip this frame but keep analyzing; one bad frame must not stop the session.
                    # Log each distinct error once so a persistent failure doesn't flood the log.
                    if str(e) != getattr(self, '_last_analysis_error', None):
                        self._last_analysis_error = str(e)
                        logger.error(f"Analysis failed for a frame, skipping it: {e}")
                    continue
                # Time (s) of the analysis window's center relative to the start of the recording,
                # derived from the capture-thread sample count so it lines up with the exported WAV
                if chunk_last_time is not None:
                    half_window_sec = (self.window_samples - 1) / 2.0 / float(self.sample_rate)
                    sound_object.recording_time = max(0.0, chunk_last_time - half_window_sec)

                # Try to queue the analyzed Sound object for the main thread to consume
                try:
                    # Use put_nowait to avoid blocking the analysis thread
                    self.analyzed_sounds_queue.put_nowait(sound_object)
                    with self.recording_lock:
                        self.analyzed_windows_count += 1
                except queue.Full:
                    # Queue is full - drop this analyzed frame
                    # This happens if the GUI is not consuming analyzed sounds fast enough
                    # Most likely cause is too many windows per GUI refresh cycles
                    logger.warning("Analyzed sounds queue full, dropping frame")
                    
        except Exception as e:
            logger.error(f"Error in analysis worker thread: {e}")
        finally:
            logger.info("Analysis worker thread exiting")

    def start_recording(self, record_original=True, record_downsampled=False):
        """
        Begin buffering audio samples for export.

        Args:
            record_original (bool): Whether to buffer the device-rate/original stream.
            record_downsampled (bool): Whether to buffer the analysis-rate/downsampled stream.
        """
        # Use lock to ensure thread-safe access to recording buffer
        with self.recording_lock:
            # Clear any previous recording data
            self.raw_recording = []
            self.downsampled_recording = []
            self.recording_sample_count = 0
            self.record_original_stream = bool(record_original)
            self.record_downsampled_stream = bool(record_downsampled)
            self._recording_rate = None
            self._recording_interrupted_at = None
            # Enable recording flag even if neither stream is saved so timing still works.
            self.recording_enabled = True

    def stop_recording(self):
        """
        Stop buffering raw audio samples. Disables recording flag.
        """
        # Use lock to ensure thread-safe access to recording state
        with self.recording_lock:
            # Disable recording flag (audio thread will stop saving samples)
            self.recording_enabled = False

    def _interrupt_recording(self):
        """Stop the recording because the audio device dropped out, remembering when it stopped.
        If nothing has been recorded yet (the device never delivered audio), the recording simply
        starts when a working device is found."""
        with self.recording_lock:
            if self.recording_enabled and self.recording_sample_count > 0:
                self.recording_enabled = False
                self._recording_interrupted_at = self.recording_sample_count / float(self.get_original_recording_sample_rate())
                logger.warning(f"Recording stopped at {self._recording_interrupted_at:.2f} s: audio device disconnected")

    def take_recording_interruption(self):
        """
        Return the time (s) at which a device disconnect stopped the recording, or None.
        Each interruption is returned once, so the visualizer handles it once.
        """
        with self.recording_lock:
            interrupted_at = self._recording_interrupted_at
            self._recording_interrupted_at = None
            return interrupted_at

    @staticmethod
    def _joined(chunks):
        """Join a list of recorded chunks into a list holding one array. The joined array replaces
        the chunks, so a long recording is not held twice."""
        return [np.concatenate(chunks)] if len(chunks) > 1 else chunks

    def get_original_recording(self):
        """Return the buffered device-rate/original recording as one int16 array."""
        with self.recording_lock:
            self.raw_recording = self._joined(self.raw_recording)
            return self.raw_recording[0] if self.raw_recording else np.zeros(0, dtype=np.int16)

    def get_downsampled_recording(self):
        """Return the buffered analysis-rate/downsampled recording as one int16 array."""
        with self.recording_lock:
            self.downsampled_recording = self._joined(self.downsampled_recording)
            return self.downsampled_recording[0] if self.downsampled_recording else np.zeros(0, dtype=np.int16)

    def get_original_recording_sample_rate(self):
        """
        Return the sample rate of the buffered device-rate/original recording stream.
        """
        return int(self._recording_rate or self.recording_sample_rate)


    def get_downsampled_recording_sample_rate(self):
        """Return the sample rate of the buffered analysis-rate/downsampled recording stream."""
        return int(self.analysis_sample_rate)

    def _update_rates(self):
        """Update capture and analysis rates over a 1-second interval."""
        now = time.perf_counter()
        elapsed = now - self.last_rate_update_time
        if elapsed >= 1.0:
            with self.recording_lock:
                self.current_capture_rate = self.captured_chunks_count / elapsed
                self.current_analysis_rate = self.analyzed_windows_count / elapsed
                self.captured_chunks_count = 0
                self.analyzed_windows_count = 0
                self.last_rate_update_time = now

    def get_capture_rate(self):
        """Return the current mono audio chunk capture rate per second."""
        self._update_rates()
        return self.current_capture_rate

    def get_analysis_rate(self):
        """Return the current DSP window analysis rate per second."""
        self._update_rates()
        return self.current_analysis_rate

    def get_analysis_queue_size(self):
        """Return the current number of raw audio chunks waiting in the analysis queue."""
        return self.raw_samples_queue.qsize()

    def get_analysis_queue_maxsize(self):
        """Return the maximum size of the analysis queue."""
        return self.raw_samples_queue.maxsize