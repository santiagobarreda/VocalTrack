# Benchmarking and Performance

VocalTrack includes both offline benchmarking tools for validating analysis accuracy, and a real-time performance monitor for diagnostics during active tracking.

---

## Offline Benchmarking

VocalTrack includes a built-in benchmarking tool accessible from the launcher. This tool compares analysis methods (native or custom vs. Parselmouth) for accuracy and timing performance. The system implements separate specialized functions for each analysis backend: the native implementations use standard signal processing algorithms (LPC for formants, autocorrelation for pitch), while the Parselmouth backend delegates to Praat's well-established algorithms.

Benchmarking is useful for validating measurement accuracy and optimizing analysis settings for your use case. Don't assume that 'errors' mean that Parselmouth is right and the alternate implementations are 'wrong'. Differences require further inspection, but in initial testing, I found plenty of cases where Parselmouth was wrong. It all depends on the specific recording and the settings used.

### Quick Start

1. Launch VocalTrack:
   ```bash
   python vocaltrack.py
   ```

2. Click the **Benchmarking** button in the launcher

3. Select comparison method:
   - `native`: Built-in formant/pitch extraction
   - `custom`: Custom analysis backend (if implemented)
   - Note: Parselmouth is automatically used as the reference standard

4. Click **Run** to start the benchmark

5. Speak continuously during the recording period

6. Results are automatically saved to the `benchmarking/` folder

### What It Measures
- **Formant accuracy**: correlation, RMSE, MAE, and relative error (%) for F1, F2, F3
- **Pitch accuracy**: correlation, RMSE, MAE, and relative error (%) for f0
- **Timing**: mean ms/frame and 95% confidence intervals for both the selected method and Parselmouth (reported separately for formant and pitch)
- **Frame counts**: number of voiced frames used in each comparison

### Output Files
- `benchmarking/formant_raw_comparison.csv`: Per-frame formant values (`timestamp, nF1, nF2, nF3, pF1, pF2, pF3`)
- `benchmarking/pitch_raw_comparison.csv`: Per-frame pitch values (`timestamp, native_f0, praat_f0`)
- `benchmarking/comprehensive_benchmark.md`: Full statistical report (accuracy tables, timing with 95% CIs)
- `benchmarking/benchmark_{timestamp}.wav`: Recorded audio used for the benchmark

**Duration:** ~15 seconds of recording
**Reference Standard:** Parselmouth/Praat is used as the gold standard for comparison. However, it makes plenty of mistakes too, so check the audio!

### Use This When:
- Validating formant/pitch accuracy against Praat
- Comparing native or custom methods against Parselmouth
- Optimizing for real-time performance
- Determining if analysis settings are appropriate for your use case
- Publishing research requiring method validation

### Requirements & Guidelines
* **Software**: `praat-parselmouth` must be installed (installed by default in the setup script).
* **Hardware**: Working microphone and quiet environment.
* **Recording Guidelines**:
  1. Produce vowels continuously during the entire recording.
  2. Use natural, varied speech.
  3. Minimize background noise.
  4. Avoid silences (reduces valid comparison frames).

### Interpreting Results

#### Correlation Coefficients
- **0.95–1.00**: Excellent agreement
- **0.90–0.95**: Good agreement
- **0.80–0.90**: Acceptable
- **<0.80**: Poor agreement (investigate audio)

#### Error Metrics
- **RMSE (Root Mean Square Error)**: Measures average magnitude of errors in Hz. Lower is better.
  - f0 thresholds: <10 Hz (excellent), <20 Hz (good), <50 Hz (acceptable)
  - F1/F2 thresholds: <30 Hz (excellent), <50 Hz (good), <100 Hz (acceptable)
- **Relative Error (%)**: Average absolute percentage difference from Parselmouth. Lower is better.

#### Timing Metrics
- **Mean Latency (ms/frame)**: Time to process one analysis frame. Target is well under **16.67 ms** for 60 FPS real-time visualization. The native method is typically faster than Parselmouth.

---

## Real-Time Performance Monitoring

VocalTrack includes a real-time **Performance Monitor Overlay** that can be toggled on/off inside any visualizer (`LivePitch`, `LiveVowel`, `LiveSpectrum`, `LiveSpectrogram`) by pressing **`Ctrl+P`** (or `Cmd+P` on macOS).

This overlay displays actual throughput rates alongside their expected/programmed targets to help diagnose UI render lag, microphone capture latency, and background DSP processor bottlenecks.

### Metrics Explained

The overlay displays five key metrics in a semi-transparent panel:

1. **GUI FPS (Frames Per Second)**:
   - **What it is**: The actual drawing and screen refresh rate of the Pygame graphics loop.
   - **Calculation**: Derived using Pygame's internal `self.clock.get_fps()`.
   - **Target**: Set in the configuration of each visualizer (default: 60 FPS).
   - **Performance Diagnostic**: A drop in actual FPS indicates the main rendering thread is lagging (e.g., due to slow layout rendering, excessive coordinate calculations, or general system overhead).

2. **Audio In (Audio Capture Rate)**:
   - **What it is**: The rate at which raw audio chunks are successfully read from the microphone device and queued for analysis.
   - **Calculation**: Counted thread-safely in PySide's audio input capture loop inside `AudioProcessor.py`. The count is evaluated and reset every 1.0 second.
   - **Target**: Dynamically calculated as $1000 / \text{chunk\_ms}$ (e.g., **50.0 ch/s** for a 20ms chunk or **66.7 ch/s** for a 15ms chunk).
   - **Performance Diagnostic**: A drop in this rate indicates the microphone driver or hardware is under-running or dropping samples, which impacts analysis continuity.

3. **Analysis (DSP Window Rate)**:
   - **What it is**: The rate of completed window analyses (pitch/formants) in the background worker thread.
   - **Calculation**: Counted in the analysis thread of `AudioProcessor.py` every time a window of audio samples is processed into a `Sound` object and successfully queued for plotting.
   - **Target**: Should match the expected Audio In capture rate (e.g., **50.0 win/s** for a 20ms chunk).
   - **Performance Diagnostic**: If this rate falls behind, the DSP algorithms (native LPC/autocorrelation, or Parselmouth/Praat) are taking longer to compute than the chunk duration. This causes the input queues to overflow and drop frames.

4. **Queue (Batch Pileup)**:
   - **What it is**: The number of analyzed windows processed in the current GUI frame.
   - **Calculation**: Measured in the main thread when draining the `analyzed_sounds_queue` via non-blocking `get_nowait()`.
   - **Performance Diagnostic**: In a healthy, low-latency state, this should be **0 or 1** (meaning every audio window is processed and drawn immediately). If the GUI thread lags or frame rate drops, audio windows will stack up in the queue, resulting in a pileup of 2+ windows which are drawn all at once, leading to visual stuttering.

5. **Throughput Percentages**:
   - Each rate displays a percentage indicator in parentheses (e.g., `(99.67%)`), calculated as:
     $$\text{Throughput Percentage} = \frac{\text{Actual Rate}}{\text{Target Rate}} \times 100\%$$

### Visual Health Indicators (Color Coding)

To make diagnostics quick and intuitive, the text colors of the overlay change dynamically based on target achievement:
- **Green** ($\ge 90\%$ of target): Healthy operation. The pipeline is running smoothly with minimal latency.
- **Yellow** ($75\%$ to $90\%$ of target): Warning. The system is dropping frames or chunks slightly (minor processing delays).
- **Red** ($< 75\%$ of target): Critical bottleneck. The app is experiencing significant lag, buffer drops, or thread thrashes.
- **Queue Count Warning**: The `Queue` line shows **Green** for 0–1 windows, **Yellow** for 2–3 windows, and **Red** for 4+ windows (pileups).
