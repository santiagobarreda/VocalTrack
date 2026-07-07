# Import threading to run audio capture in a background thread, ensuring the GUI remains responsive
import threading
# Import queue for thread-safe communication between audio capture/analysis threads and the main thread
import queue
import math
# Import Qt core app and QtMultimedia audio capture APIs
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
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
    The chunk size and number of chunks determine the temporal resolution and latency of analysis. Smaller
    chunks and fewer chunks reduce latency but may decrease accuracy. The default configuration provides 
    a good balance for real-time vocal analysis.

    """
    
    def __init__(self, chunk_ms=None, number_of_chunks=None, analysis_config=None, min_rms_db=None, 
                 input_device_index=None, raw_queue_maxsize=50, analyzed_queue_maxsize=50):
        """
        Initialize the audio processor thread and configure audio capture and analysis parameters.

        Args:
            chunk_ms (int, optional): Duration of each audio chunk in milliseconds. Defaults to 5.
            number_of_chunks (int, optional): Number of chunks to stitch together for each analysis window. Defaults to 5.
            analysis_config (dict, optional): Analysis configuration dictionary. Defaults to None.
            min_rms_db (float, optional): Minimum RMS in dB for analysis. If provided, overrides config value.
            input_device_index (int, optional): Audio input device index. None uses system default.
            raw_queue_maxsize (int, optional): Maximum size for raw samples queue. Defaults to 50.
            analyzed_queue_maxsize (int, optional): Maximum size for analyzed sounds queue. Defaults to 50.
        """
        # Initialize the parent QThread class
        super(AudioProcessor, self).__init__()
        
        # ALWAYS calculate sample rate as 2×max_formant (Nyquist theorem)
        # There is no reason to sample faster than 2× the highest frequency we want to analyze
        max_formant = (analysis_config or {}).get('max_formant', 5000)
        sample_rate = 2 * max_formant
        
        # Store analysis sample rate (samples per second, always calculated as 2×max_formant)
        # This is the rate used by Sound analysis and by the recording buffer.
        self.sample_rate = sample_rate
        self.analysis_sample_rate = sample_rate
        self.device_sample_rate = sample_rate
        self.recording_sample_rate = sample_rate
        
        # Safely handle default parameters if None is passed
        if chunk_ms is None:
            chunk_ms = (analysis_config or {}).get('chunk_ms') or 20
        if number_of_chunks is None:
            number_of_chunks = (analysis_config or {}).get('number_of_chunks') or 3
            
        # Store chunk duration in milliseconds
        self.chunk_ms = chunk_ms
        # Store number of chunks to stitch together for each analysis window
        self.number_of_chunks = max(int(number_of_chunks), 1)
        # Store analysis configuration (passed to Sound objects)
        self.analysis_config = analysis_config or {}
        
        # If min_rms_db is explicitly provided, merge it into analysis_config (overrides config value)
        if min_rms_db is not None:
            self.analysis_config['min_rms_db'] = min_rms_db
        
        # Store audio input device index (None = system default)
        self.input_device_index = input_device_index
        
        # Calculate analysis chunk size from chunk duration in ms
        self.chunk_size = round(chunk_ms * sample_rate / 1000)
        self.device_chunk_size = self.chunk_size
        # Window size is solely determined by chunk size and number of chunks
        self.window_samples = self.chunk_size * self.number_of_chunks
        
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
        last_len = max((self.number_of_chunks - 1) * self.chunk_size, 0)
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
        # Device-rate/original recording buffer and analysis-rate/downsampled buffer.
        self.raw_recording = []
        self.downsampled_recording = []
        self.record_original_stream = True
        self.record_downsampled_stream = False
        self.recording_sample_count = 0
        self.downsampled_recording_sample_count = 0
        # Polyphase resampler state (configured in run() once device format is known)
        self._resample_up = 1
        self._resample_down = 1
        self._polyphase_filters = None
        self._polyphase_history = np.zeros(0, dtype=np.float32)
        self._polyphase_phase = 0

    def _configure_resampler(self):
        """
        Configure a streaming polyphase rational resampler for device->analysis conversion.

        This is a native NumPy implementation (no scipy):
        - Rational ratio reduction (up/down)
        - Windowed-sinc low-pass prototype with anti-aliasing
        - Polyphase filter bank for efficient streaming resampling
        """
        in_rate = int(max(1, self.device_sample_rate))
        out_rate = int(max(1, self.analysis_sample_rate))

        g = math.gcd(in_rate, out_rate)
        self._resample_up = max(1, out_rate // g)
        self._resample_down = max(1, in_rate // g)

        if self._resample_up == 1 and self._resample_down == 1:
            self._polyphase_filters = None
            self._polyphase_history = np.zeros(0, dtype=np.float32)
            self._polyphase_phase = 0
            return

        # Prototype low-pass design in upsampled domain.
        # cutoff_rel is relative to Nyquist of the upsampled intermediate sequence.
        cutoff_rel = 1.0 / float(max(self._resample_up, self._resample_down))
        taps_per_phase = 16
        num_taps = 2 * taps_per_phase * self._resample_up + 1
        n = np.arange(num_taps, dtype=np.float64) - (num_taps - 1) / 2.0

        # Windowed-sinc prototype (Hamming), scaled by up factor.
        h = cutoff_rel * np.sinc(cutoff_rel * n)
        h *= np.hamming(num_taps)
        h_sum = float(np.sum(h))
        if abs(h_sum) > 1e-12:
            h /= h_sum
        h *= self._resample_up

        # Pad so prototype length is divisible by number of phases.
        pad = (-len(h)) % self._resample_up
        if pad:
            h = np.pad(h, (0, pad), mode='constant')

        # Build polyphase bank: [phase, taps], reversed for newest-first history dot-product.
        phase_filters = h.reshape(-1, self._resample_up).T[:, ::-1].astype(np.float32)
        self._polyphase_filters = phase_filters
        self._polyphase_history = np.zeros(phase_filters.shape[1], dtype=np.float32)
        self._polyphase_phase = 0

        logger.info(f"Polyphase resampler configured: up={self._resample_up}, down={self._resample_down}, phases={phase_filters.shape[0]}, taps_per_phase={phase_filters.shape[1]}")

    def _resample_chunk(self, normalized_samples):
        """
        Resample one mono chunk using a streaming polyphase filter bank.

        Produces approximately chunk_ms worth of samples at analysis_sample_rate.
        Output is padded/clipped to self.chunk_size to preserve downstream assumptions.
        """
        normalized_samples = np.asarray(normalized_samples, dtype=np.float32)
        if normalized_samples.size == 0:
            return np.zeros(self.chunk_size, dtype=np.float32)

        if self.device_sample_rate == self.analysis_sample_rate and normalized_samples.size == self.chunk_size:
            return normalized_samples

        if normalized_samples.size == 1:
            return np.full(self.chunk_size, normalized_samples[0], dtype=np.float32)

        if self._polyphase_filters is None:
            resampled = normalized_samples
        else:
            outputs = []
            for sample in normalized_samples:
                # Newest-first history for fast dot product against phase filters.
                if self._polyphase_history.size > 1:
                    self._polyphase_history[1:] = self._polyphase_history[:-1]
                self._polyphase_history[0] = sample

                # Emit 0..N output samples depending on rational phase progression.
                while self._polyphase_phase < self._resample_up:
                    coeffs = self._polyphase_filters[self._polyphase_phase]
                    outputs.append(float(np.dot(coeffs, self._polyphase_history)))
                    self._polyphase_phase += self._resample_down
                self._polyphase_phase -= self._resample_up

            if len(outputs) == 0:
                resampled = np.zeros(self.chunk_size, dtype=np.float32)
            else:
                resampled = np.asarray(outputs, dtype=np.float32)

        # Keep exactly one analysis chunk per capture chunk to preserve queue timing.
        if resampled.size > self.chunk_size:
            resampled = resampled[:self.chunk_size]
        elif resampled.size < self.chunk_size:
            if resampled.size > 0:
                resampled = np.pad(resampled, (0, self.chunk_size - resampled.size), mode='edge')
            else:
                resampled = np.zeros(self.chunk_size, dtype=np.float32)

        return np.clip(resampled, -1.0, 1.0)

    def run(self):
        """
        Open the audio stream and continuously read samples into the raw queue for analysis.

        This method runs in the thread and manages audio device initialization, error handling, 
        and resource cleanup. It also starts the analysis worker thread.

        Raises:
            RuntimeError: If no audio device is available or stream initialization fails.
        """
        try:
            # Ensure a Qt application exists before using QtMultimedia APIs
            app = QCoreApplication.instance()
            if app is None:
                app = QCoreApplication([])

            # Check if any audio input devices are available
            inputs = QMediaDevices.audioInputs()
            if not inputs:
                raise RuntimeError("No audio input devices found")

            # Select requested input device by index when provided, otherwise use system default
            if self.input_device_index is not None and 0 <= self.input_device_index < len(inputs):
                input_device = inputs[self.input_device_index]
            else:
                input_device = QMediaDevices.defaultAudioInput()
                if input_device is None or input_device.isNull():
                    input_device = inputs[0]

            # Save requested analysis rate before any device override
            original_sample_rate = self.analysis_sample_rate
            
            # Always open the hardware in its preferred/native format (typically 44.1kHz or 48kHz)
            # This ensures high-fidelity exports and avoids buggy OS/driver-level resampling conversions.
            audio_format = input_device.preferredFormat()

            # Keep the analysis rate unchanged and adapt the device capture chunking + resample in software.
            if audio_format.sampleRate() > 0:
                self.device_sample_rate = audio_format.sampleRate()
                self.device_chunk_size = max(round(self.chunk_ms * self.device_sample_rate / 1000), 1)
                logger.info(f"Device rate {self.device_sample_rate} differs from requested analysis rate {original_sample_rate}; using software resampling")
            else:
                self.device_sample_rate = self.analysis_sample_rate
                self.device_chunk_size = self.chunk_size

            # Recording always follows the true capture device rate.
            self.recording_sample_rate = self.device_sample_rate

            self._configure_resampler()

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
            bytes_per_chunk = self.device_chunk_size * bytes_per_frame
            pending_audio_bytes = bytearray()
            
            # Start the analysis worker thread that consumes raw samples and produces Sound objects
            self.analysis_thread = threading.Thread(target=self.analyze_worker, daemon=True)
            self.analysis_thread.start()
            logger.info("Analysis worker thread started")
            
            # Open an audio input stream from the specified or default microphone
            self.port = QAudioSource(input_device, audio_format)
            self.port.setBufferSize(max(bytes_per_chunk * 8, 4096))
            self.stream = self.port.start()
            if self.stream is None:
                raise RuntimeError("Failed to open audio input stream")
            
            logger.info(f"Audio stream opened: device={self.device_sample_rate}Hz/{self.device_chunk_size} samples, analysis={self.analysis_sample_rate}Hz/{self.chunk_size} samples")
            
            # Main capture loop - runs until self.running is set to False
            while self.running:
                # Pump the event loop for the current thread so QAudioSource can receive audio data
                QCoreApplication.processEvents()

                # Is audio available?
                available = self.stream.bytesAvailable()
                if available <= 0:
                    time.sleep(0.001)
                    continue
                
                # If audio is available, read it into a bytearray buffer. We may get more than one chunk's worth of audio, 
                # so we need to buffer it until we have enough for at least one chunk.
                data = self.stream.read(available)
                if not data:
                    time.sleep(0.001)
                    continue
                
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

                    # Preserve device-rate mono Int16 samples for high-fidelity export.
                    if self.recording_enabled:
                        with self.recording_lock:
                            self.recording_sample_count += len(samples)
                            if self.record_original_stream:
                                self.raw_recording.extend(samples)
                
                    # Resample from device rate to analysis rate when necessary
                    normalized_samples = self._resample_chunk(normalized_samples)

                    # Preserve the downsampled/analysis stream when requested.
                    if self.recording_enabled:
                        with self.recording_lock:
                            self.downsampled_recording_sample_count += len(normalized_samples)
                            if self.record_downsampled_stream:
                                downsampled_samples = np.clip(
                                    normalized_samples * 32767.0,
                                    -32768,
                                    32767
                                ).astype(np.int16)
                                self.downsampled_recording.extend(downsampled_samples)

                    # Try to add normalized samples to the raw queue for analysis
                    try:
                        # Use put_nowait to avoid blocking the real-time audio capture loop
                        self.raw_samples_queue.put_nowait(normalized_samples)
                    except queue.Full:
                        # Queue is full - drop this frame and log a warning
                        # This happens if analysis is slower than audio capture
                        logger.warning("Raw samples queue full, dropping frame")
                    
        except RuntimeError as e:
            # Handle runtime errors (e.g., no audio devices)
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
        
        try:
            while self.running:
                # Try to get the next chunk of normalized audio samples from the raw queue
                try:
                    # Wait up to 0.1 seconds for samples to be available
                    current_samples = self.raw_samples_queue.get(timeout=0.1)
                except queue.Empty:
                    # If no samples available within timeout, continue to avoid fabricating silence
                    continue
                
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
                last_len = max((self.number_of_chunks - 1) * self.chunk_size, 0)
                if last_len > 0:
                    # Keep the last (number_of_chunks - 1) chunks for stitching
                    self.last_samples = samples_output[-last_len:]
                else:
                    # No stitching needed if only one chunk
                    self.last_samples = np.zeros(0)
                
                # Create a Sound object with the windowed samples and perform analysis
                # This is where LPC and pitch tracking happen (relatively expensive operations)
                capture_timestamp = time.perf_counter()
                sound_object = Sound(samples_output, sample_rate=self.sample_rate, **self.analysis_config)
                sound_object.capture_timestamp = capture_timestamp
                
                # Try to queue the analyzed Sound object for the main thread to consume
                try:
                    # Use put_nowait to avoid blocking the analysis thread
                    self.analyzed_sounds_queue.put_nowait(sound_object)
                except queue.Full:
                    # Queue is full - drop this analyzed frame
                    # This happens if the GUI is not consuming analyzed sounds fast enough
                    # Most likely cause is too many windows per GUI refresh cycles
                    logger.warning("Analyzed sounds queue full, dropping frame")
                    
        except Exception as e:
            logger.error(f"Error in analysis worker thread: {e}")
        finally:
            logger.info("Analysis worker thread exiting")

    def get_sound(self, timeout=0.1):
        """
        Retrieve the next analyzed Sound object from the analysis queue.

        Sound objects contain extracted pitch, formants, and other features computed in the analysis worker thread.

        Args:
            timeout (float): Maximum seconds to wait for a Sound object. Use 0.001 for fast polling (e.g., spectrogram), or 0.1 for blocking retrieval (e.g., formant tracking).

        Returns:
            Sound: A Sound object with pitch and formant analysis already complete. If no analyzed sounds are available within timeout, returns a silence Sound object.
        """
        try:
            # Wait up to timeout seconds for an analyzed Sound object to be available
            sound_object = self.analyzed_sounds_queue.get(timeout=timeout)
            return sound_object
        except queue.Empty:
            # If no analyzed sounds available within timeout, return a silence Sound
            logger.debug("No analyzed sounds available (timeout)")
            # Create an empty Sound object with silence
            empty_sound = Sound(np.zeros(self.window_samples, dtype=np.float32), 
                               sample_rate=self.sample_rate, **self.analysis_config)
            return empty_sound

    def get_samples(self):
        """
        Retrieve raw normalized audio samples directly from the capture thread, without analysis.

        Useful for visualization or custom processing. If no samples are available within timeout, returns silence.

        Returns:
            ndarray: Normalized float32 audio samples in range [-1.0, 1.0], or zeros if no samples are available within timeout.
        """
        try:
            # Wait up to 0.1 seconds for raw samples to be available
            samples = self.raw_samples_queue.get(timeout=0.1)
            return samples
        except queue.Empty:
            # If no samples available within timeout, return silence
            logger.debug("No raw samples available (timeout)")
            return np.zeros(self.chunk_size, dtype=np.float32)

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
            self.downsampled_recording_sample_count = 0
            self.record_original_stream = bool(record_original)
            self.record_downsampled_stream = bool(record_downsampled)
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

    def get_recording(self):
        """
        Return the buffered device-rate/original recording as a NumPy array.
        Kept for backward compatibility with existing callers.
        """
        # Use lock to ensure thread-safe access to recording buffer
        with self.recording_lock:
            # Convert list of samples to numpy array and return a copy
            return np.array(self.raw_recording, dtype=np.int16)

    def get_original_recording(self):
        """Return a copy of the buffered device-rate/original recording."""
        with self.recording_lock:
            return np.array(self.raw_recording, dtype=np.int16)

    def get_downsampled_recording(self):
        """Return a copy of the buffered analysis-rate/downsampled recording."""
        with self.recording_lock:
            return np.array(self.downsampled_recording, dtype=np.int16)

    def get_recording_sample_count(self):
        """
        Return the number of device-rate samples captured during the current recording session.
        """
        # Use lock to ensure thread-safe access to recording buffer
        with self.recording_lock:
            return self.recording_sample_count

    def get_recording_sample_rate(self):
        """
        Return the sample rate of the buffered device-rate/original recording stream.
        """
        return int(self.recording_sample_rate)

    def get_original_recording_sample_rate(self):
        """Return the sample rate of the buffered device-rate/original recording stream."""
        return int(self.recording_sample_rate)

    def get_downsampled_recording_sample_rate(self):
        """Return the sample rate of the buffered analysis-rate/downsampled recording stream."""
        return int(self.analysis_sample_rate)