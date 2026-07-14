# Settings Reference

This page documents all configuration settings exposed in the VocalTrack launcher dialogs, plus key runtime config values. All values shown are defaults from `config.py`.

## Settings Persistence

Settings are automatically saved to `.VocalTrack_settings.json` in the project root directory when modified through the launcher dialogs.

**Saved categories:**
- `analysis` (Analysis Settings dialog)
- `smoother` (Smoother Settings dialog)
- `plotting` (Formant Plot Settings dialog)
- `pitch_plot` (Pitch Plot Settings dialog)
- `spectrogram` (Spectrogram Settings dialog)
- `spectrum` (Spectrum Settings dialog)
- Recording device selection (input_device_index)

On startup, VocalTrack loads saved settings and applies them to runtime configurations. Missing values fall back to defaults from `config.py`.

---

## Analysis Settings

Accessed via "Analysis Settings" button in launcher. Controls core acoustic analysis parameters for formant and pitch extraction.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `chunk_ms` | `20` | 10-100 ms | Duration of each audio chunk captured by AudioProcessor. Smaller values = faster updates, larger values = better frequency resolution. |
| `number_of_chunks` | `3` | 1-10 | Number of chunks stitched together to form one analysis window. Total window = chunk_ms × number_of_chunks. |
| `max_formant` | `5000` | 4000-8000 Hz | Upper limit for formant search. Also determines sample rate (sample_rate = 2 × max_formant via Nyquist theorem). Adult male: 5000 Hz, adult female: 5500 Hz, child: 6500-8000 Hz. |
| `n_formants` | `5.5` | 3.0-7.0 | Number of formants to extract. Non-integer values allow algorithm to search for fractional formants for robustness. Typical: 5.5 for adults. |
| `min_f0` | `60` | 40-200 Hz | Minimum f0 for pitch analysis and data filtering. Male: 60-80 Hz, female: 120-150 Hz, child: 180-200 Hz. |
| `max_f0` | `500` | 200-800 Hz | Maximum f0 for pitch analysis and data filtering. Male: 200-300 Hz, female: 350-450 Hz, child: 400-600 Hz. |
| `min_rms_db` | `-60.0` | -90 to -20 dB | Minimum RMS amplitude threshold in dBFS for analysis gating. More negative = capture quieter sounds. Less negative = filter out more noise. Adjustable during recording with `+`/`-` keys. |
| `formant_method` | `'native'` | `'native'`, `'wlp'`, `'parselmouth'`, `'custom'` | Formant extraction backend. `native` = built-in LPC, `wlp` = Weighted Linear Prediction (WLP) with Short-Time Energy (STE) weighting, `parselmouth` = Praat-based, `custom` = user-defined. |
| `pitch_method` | `'native'` | `'native'`, `'parselmouth'`, `'custom'` | Pitch extraction backend. `native` = built-in autocorrelation, `parselmouth` = Praat-based. |
| `robust_formants` | `False` | True/False | (Formerly `robust`) Enable robust formant extraction logic. |
| `window_length` | *Derived* | — | Analysis window duration in seconds. Auto-calculated: `window_length = (chunk_ms × number_of_chunks) / 1000`. Example: 20 ms × 3 = 0.06 s. |
| `time_step` | *Derived* | — | Time between analysis frames in seconds. Auto-calculated: `time_step = chunk_ms / 1000`. Example: 20 ms = 0.02 s. |
| `pre_emphasis_coeff` | `0.97` | 0.0-1.0 | Pre-emphasis filter coefficient for high-frequency boosting. Higher = more emphasis. Standard for speech: 0.97. |
| `pre_emphasis_hz` | `50` | 0-200 Hz | Pre-emphasis cutoff frequency. Frequencies above this are boosted. |
| `min_confidence` | `0.2` | 0.0-1.0 | Minimum confidence threshold for accepting pitch estimates (native method only). |

**Derived values:**
- `sample_rate = 2 × max_formant` (e.g., 5000 Hz → 10000 Hz sample rate)
- `window_length = (chunk_ms × number_of_chunks) / 1000` (e.g., 20 ms × 3 = 0.06 s)
- `time_step = chunk_ms / 1000` (e.g., 20 ms = 0.02 s)

**Notes:**
- Modified settings are immediately applied to `self.audio_config` and `self.analysis_config` in running visualizers
- For LiveVowel/LivePitch, changes to `min_rms_db` can be made in-window with `+`/`-` keys
- Formant/pitch methods can be changed without restarting, but may require reinitialization

### Analysis Method Details

**Native Methods** (default, recommended for real-time use):
- **Formants**: Uses Linear Predictive Coding (LPC) analysis implemented in Python/NumPy
  - Function: `get_formants_native()` in `VocalTrack/utils/get_formants.py`
  - Strengths: Fast (<1 ms per frame), no external dependencies beyond NumPy
  - Algorithm: Levinson-Durbin LPC followed by root-finding on the prediction filter polynomial

- **Pitch**: Uses autocorrelation-based fundamental frequency estimation
  - Function: `get_pitch_native()` in `VocalTrack/utils/get_pitch.py`
  - Strengths: Fast (<0.5 ms per frame), robust to pitch-halving errors via confidence weighting
  - Algorithm: Autocorrelation with parabolic interpolation and confidence-based voicing detection

**WLP Methods** (recommended for high-pitch/nasalized speech):
- **Formants**: Uses Weighted Linear Prediction (WLP) with Short-Time Energy (STE) weighting implemented in Python/NumPy
  - Function: `get_formants_wlp()` in `VocalTrack/utils/get_formants.py`
  - Strengths: Highly robust to high pitch ($F_0$) and nasalization. De-emphasizes low-energy signal regions to avoid glottal open-phase excitation contamination. Fast (<2 ms per frame) and has no external dependencies.
  - Algorithm: WLP covariance formulation solved via normal equations with a short-time energy (1.5 ms window) weight vector.

**Parselmouth Methods** (for benchmarking and validation):
- **Formants**: Delegates to Praat's formant extraction via Parselmouth library
  - Function: `get_formants_parselmouth()` in `VocalTrack/utils/get_formants.py`
  - Strengths: Industry-standard reference, robust across diverse voices
  - Requires: `praat-parselmouth` package (pip install praat-parselmouth)

- **Pitch**: Delegates to Praat's pitch tracking via Parselmouth library
  - Function: `get_pitch_parselmouth()` in `VocalTrack/utils/get_pitch.py`
  - Strengths: Highly reliable, used in many published studies
  - Requires: `praat-parselmouth` package

**Custom Methods** (for advanced users):
- **Formants**: User-defined function at `get_formants_custom()` in `VocalTrack/utils/get_formants.py`
- **Pitch**: User-defined function at `get_pitch_custom()` in `VocalTrack/utils/get_pitch.py`
- Allows researchers to implement alternative algorithms and integrate them into the real-time pipeline
- Must return dictionary with required keys (see docstrings in respective files)

---

## Smoother Settings

Accessed via "Smoother Settings" button in launcher. Controls the 1-Euro filter and trajectory smoothing behavior.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `memory_n` | `3` | 1-10 frames | Number of frames kept in smoothing memory buffer. Larger = smoother but slower to respond. |
| `stability_threshold` | `0.15` | 0.05-0.50 | Normalized stability threshold for accepting trajectories. Lower = accept more erratic tracks, higher = stricter gating. |
| `skip_tolerance` | `2` | 0-10 frames | Number of unstable frames tolerated before resetting trajectory. Higher = more forgiving of brief instabilities. |
| `hold_unvoiced` | `True` | True/False | Whether to maintain trajectory during brief unvoiced segments. True = preserve tracks across voicing drops (recommended). |
| `use_euro_filter` | `True` | True/False | Enable 1-Euro temporal smoothing of formants and pitch. |
| `euro_min_cutoff` | `0.05` | 0.001-1.0 Hz | 1-Euro filter baseline cutoff frequency. Lower = smoother but slower to respond. Typical: 0.01-0.1 Hz. |
| `euro_beta` | `1.5` | 0.0-5.0 | 1-Euro filter responsiveness to velocity. Higher = more adaptive to fast changes. Typical: 1.0-2.0. |
| `euro_dcutoff` | `0.5` | 0.1-2.0 Hz | 1-Euro filter cutoff for derivative (velocity) smoothing. Lower = smoother velocity estimates. |
| `velocity_power` | `1.5` | 0.5-3.0 | Exponent for non-linear velocity influence. >1 = snap quickly to fast changes, <1 = linear response. |

## Detailed 1-Euro Filter Explanation

The 1-Euro filter is an adaptive first-order low-pass filter (exponential moving average) designed specifically for real-time tracking systems to address the classic tradeoff between noise reduction (smoothing) and responsiveness (latency). It was proposed by Casiez, Roussel, and Vogel (2012) and is widely used for filtering raw human-computer interaction inputs (e.g., in Google's MediaPipe framework).

### How it Works (Under the Hood)

For any real-time tracking stream, we want to smooth out high-frequency jitter when the tracked value (formants or pitch) is relatively stationary, but we want the filter to quickly "let go" and track the signal closely with minimal delay when the speaker makes a rapid articulatory transition (such as a diphthong or a pitch glide). To achieve this, the 1-Euro filter dynamically adapts its smoothing cutoff frequency based on the **velocity (rate of change)** of the input signal.

### Step-by-Step Algorithm & Math

Let $X$ represent the input coordinate sequence (formant or pitch in log-space) and $dt$ represent the time delta between consecutive samples.

#### 1. Dynamic Time Delta Calculation ($dt$)
In a real-time system, frames can occasionally be dropped or skipped if they are unvoiced or fail the stability gate. Rather than assuming a constant time step, VocalTrack dynamically adjusts the time delta $dt$ at each step:

$$
dt = dt_{\text{base}} + (dt_{\text{base}} \times \text{skipped\_frames})
$$

where $dt_{\text{base}} = \frac{\text{chunk\_ms}}{1000}$ (e.g., $0.02$ seconds for a $20$ ms chunk).

#### 2. Compute Raw Velocity ($dx_i$)
At each time step $i$, the raw rate of change is calculated as the difference between the new input value $x_i$ and the previously filtered value $\hat{x}_{i-1}$, divided by the time elapsed:
$$
dx_i = \frac{x_i - \hat{x}_{i-1}}{dt}$$

#### 3. Smooth the Velocity ($\hat{dx}_i$)
Because raw velocity measurements are highly susceptible to noise (which could cause the cutoff frequency to fluctuate erratically), the velocity itself is low-pass filtered using a fixed cutoff frequency $f_{c, d}$ (`euro_dcutoff`):
$$
    \alpha_d = \frac{1}{1 + \frac{\tau_d}{dt}}
    \text{where} \quad \tau_d = \frac{1}{2 \pi \cdot f_{c, d}}
$$
$$
    \hat{dx}_i = \alpha_d \cdot dx_i + (1 - \alpha_d) \cdot \hat{dx}_{i-1}
$$

#### 4. Calculate the Adaptive Cutoff Frequency ($f_c$)

The cutoff frequency $f_c$ for the primary signal is computed as a function of the smoothed velocity magnitude $|\hat{dx}_i|$:

$$f_c = f_{c, \min} + \beta \cdot |\hat{dx}_i|^{\text{power}}$$

* $f_{c, \min}$ (`euro_min_cutoff`) is the baseline cutoff frequency when the signal is stationary.
* $\beta$ (`euro_beta`) is the speed coefficient.
* `power` (`velocity_power`) is a scaling exponent (default: $1.5$). By raising the velocity to a power $>1.0$, the filter reacts exponentially faster to rapid movements.
* A safety bound ensures $f_c$ never drops to zero: $f_c = \max(10^{-6}, f_c)$.

#### 5. Smooth the Main Signal ($\hat{x}_i$)

The main smoothing coefficient $\alpha$ is dynamically computed from the adaptive cutoff frequency $f_c$:

$$
    \alpha = \frac{1}{1 + \frac{\tau}{dt}}
    \quad \text{where} \quad
    \tau = \frac{1}{2 \pi \cdot f_c}
$$

And the final filtered output value $\hat{x}_i$ is blended:
$$
    \hat{x}_i = \alpha \cdot x_i + (1 - \alpha) \cdot \hat{x}_{i-1}
$$

### Parameter Breakdown

| Parameter | Math Symbol | Role in Filtering | Visual Behavior |
|-----------|-------------|-------------------|-----------------|
| `euro_min_cutoff` | $f_{c, \min}$ | Baseline cutoff frequency (Hz) at zero speed. | **Lower values** (e.g., $0.01 - 0.05$) create heavy smoothing and suppress steady-state jitter, but can introduce minor delay when starting a sound. **Higher values** (e.g., $0.1 - 0.5$) reduce steady-state smoothing. |
| `euro_beta` | $\beta$ | Speed coefficient multiplier. | Controls how quickly the filter "opens up" (increases cutoff frequency) in response to velocity. **Higher values** (e.g., $1.5 - 2.0$) eliminate lag during rapid transitions but may allow more noise through. |
| `euro_dcutoff` | $f_{c, d}$ | Velocity smoothing cutoff frequency (Hz). | Prevents rapid raw velocity noise from destabilizing the adaptive cutoff. A value of $0.5$ Hz ensures stable transitions. |
| `velocity_power` | $\text{power}$ | Exponential scaling of velocity magnitude. | Controls the snap responsiveness. Values $>1.0$ (e.g., $1.5$) ensure that slow drift remains heavily filtered while rapid movements snap instantly to target frequencies. |

#### Tuning Guide for 1-Euro Filter Parameters

This guide helps you adjust the 1-Euro filter parameters to balance noise reduction and responsiveness for formant tracking.

**1. If tracking is too jittery (noisy):**

* **Increase `memory_n`**: Use 3 to 5 (default is 3). This increases the number of past frames used in the initial average, reducing high-frequency noise.
* **Decrease `euro_min_cutoff`**: Set to $0.02$ (default is 0.05). A lower baseline cutoff reduces jitter during stationary speech.
* **Decrease `euro_beta`**: Set to 1.0 (default is 1.5). A smaller speed coefficient reduces responsiveness to small movements, which can be noisy.

**2. If tracking is too sluggish (slow to respond):**

* **Decrease `memory_n`**: Set to 2 (default is 3). Reduces the number of frames in the initial average, increasing responsiveness.
* **Increase `euro_min_cutoff`**: Set to 0.1 (default is 0.05). A higher baseline cutoff allows faster tracking of value changes.
* **Increase `euro_beta`**: Set to 2.0 (default is 1.5). A larger speed coefficient makes the filter react more quickly to velocity changes.

**3. If formants jump between tracks:**

* **Increase `stability_threshold`**: Set to 0.25 (default is 0.15). Requires a stronger formant signal before switching tracks.
* **Decrease `skip_tolerance`**: Set to 1 (default is 2). Reduces how many frames can be skipped before switching tracks, keeping the filter tied to the current formant.
* **Decrease `stability_threshold`**: Set to 0.10 (default is 0.15). Lowers the threshold to switch tracks more easily when the formant is detected.

**4. If tracks break during normal speech:**

* **Set `hold_unvoiced = True`**: This keeps the last valid formant value when the signal is unvoiced (no sound detected).
* **Increase `skip_tolerance`**: Set to 3 (default is 2). Allows more skipped frames before declaring the formant lost.
* **Decrease `stability_threshold`**: Set to 0.10 (default is 0.15). Makes it easier to regain a track after a brief interruption.

2. **Too sluggish (slow response)**:
   - Decrease `memory_n` (3 → 2)
   - Increase `euro_min_cutoff` (0.05 → 0.1)
   - Increase `euro_beta` (1.5 → 2.0)

3. **Formants jump between tracks**:
   - Increase `stability_threshold` (0.15 → 0.25)
   - Decrease `skip_tolerance` (2 → 1)

4. **Tracks break during normal speech**:
   - Set `hold_unvoiced = True`
   - Increase `skip_tolerance` (2 → 3)
   - Decrease `stability_threshold` (0.15 → 0.10)

---

## Formant Plot Settings (LiveVowel)

Accessed via "Formant Plot Settings" button in launcher. Controls LiveVowel display parameters.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `f1_range` | `(200, 1200)` | (100, 1500) Hz | Vertical axis range for F1 formant. Lower values at top (inverted axis). Typical: 200-1200 Hz for adults. |
| `f2_range` | `(500, 3000)` | (300, 3500) Hz | Horizontal axis range for F2 formant. Higher values at left (inverted axis). Typical: 500-3000 Hz for adults. |
| `fps` | `60` | 15-120 | Frame rate for display refresh. Higher = smoother but more CPU. Typical: 30-60 fps. |
| `display_mode` | `'single'` | `'single'`, `'track'`, `'all'` | Visualization mode. `single` = latest point only, `track` = current trajectory, `all` = all trajectories. |
| `freq_scale` | `'log'` | `'log'`, `'linear'` | Frequency axis scaling. `log` = logarithmic (perceptually uniform), `linear` = linear Hz. |
| `show_vowel_template` | `False` | True/False | Whether to display vowel template overlay on startup. Toggle with `Ctrl+T` during use. |
| `gui_size` | `(900, 650)` | (400, 800) pixels | Window dimensions (width, height). Larger = more detail, smaller = less CPU. |

**F1/F2 Range Guidelines:**

**Adult speakers:**
- F1: 200-1200 Hz (covers /i/ to /a/)
- F2: 500-3000 Hz (covers /u/ to /i/)

**Child speakers:**
- F1: 250-1500 Hz
- F2: 700-3500 Hz

**Narrow ranges for specific vowels:**
- Front vowels only: F1: 200-600 Hz, F2: 1500-3000 Hz
- Back vowels only: F1: 300-1200 Hz, F2: 500-1500 Hz

**Frequency scale:**
- Logarithmic: Better matches perceptual spacing, traditional vowel charts
- Linear: Better for measuring exact Hz differences

---

## Pitch Plot Settings (LivePitch)

Accessed via "Pitch Plot Settings" button in launcher. Controls LivePitch display parameters.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `gui_width` | `1200` | 400-2000 pixels | Window width. Wider = more temporal detail visible. |
| `gui_height` | `650` | 300-1000 pixels | Window height. Taller = better frequency resolution on display. |
| `min_f0` | `75` | 40-200 Hz | Lower bound of f0 display range. Independent of analysis min_f0. |
| `max_f0` | `500` | 200-800 Hz | Upper bound of f0 display range. Independent of analysis max_f0. |
| `fps` | `60` | 15-120 | Frame rate for display refresh. Higher = smoother animation, more CPU. |
| `pitch_plot_mode` | `'fixed'` | `'fixed'`, `'continuous'` | Display mode. `fixed` = fixed-width time window, `continuous` = expanding timeline. |
| `pitch_display_seconds` | `5.0` | 1.0-20.0 s | Display window width in seconds. Larger = more temporal context, smaller = faster scrolling. |
| `display_seconds` | `5.0` | 1.0-20.0 s | Alias for `pitch_display_seconds` (both used in different contexts). |
| `freq_scale` | `'log'` | `'log'`, `'linear'` | Frequency axis scaling. `log` = logarithmic (musical intervals), `linear` = linear Hz. |

**Display f0 vs. Analysis f0:**

- **Analysis f0 range** (from Analysis Settings): Defines bounds for pitch *extraction*
- **Display f0 range** (from Pitch Plot Settings): Defines bounds for *visualization*

You can have different ranges. For example:
- Analysis: `min_f0=60`, `max_f0=400` (wide extraction range)
- Display: `min_f0=100`, `max_f0=300` (narrower display zoom)

**Plot Mode:**
- **Fixed**: Time window remains constant width (e.g., 5 seconds). Older data scrolls off left edge. Good for real-time monitoring.
- **Continuous**: Timeline expands as recording progresses. All data remains visible but becomes compressed. Good for recording full utterances for later review.

**Display Window Duration:**
- Short (1-3 s): Quick feedback, fast scrolling
- Medium (5-7 s): Default, good for sentences
- Long (10-20 s): Extended context, slower scrolling



## Spectrogram Settings (LiveSpectrogram)

Accessed via "Spectrogram Settings" button in launcher. Controls LiveSpectrogram display and FFT parameters.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `gui_width` | `1200` | 600-2400 pixels | Window width. Wider = more temporal resolution (more time visible). |
| `gui_height` | `650` | 300-1200 pixels | Window height. Taller = better frequency resolution on Y-axis. |
| `max_freq` | `5000` | 1000-10000 Hz | Maximum frequency displayed on Y-axis. Limited by Nyquist (sample_rate/2). Typical: 5000 Hz for speech. |
| `display_seconds` | `3.0` | 0.5-5.0 s | Time window duration in seconds. Controls horizontal scroll speed. Smaller = faster scroll. |
| `colormap` | `'plasma'` | Any matplotlib colormap | Color mapping for magnitude visualization. `plasma`, `viridis`, `magma` recommended (perceptually uniform). |
| `dynamic_range` | `40` | 20-80 dB | Dynamic range in dB for amplitude display. Smaller = more detail, larger = more contrast. Adjustable with `+`/`-` during use. |
| `fps` | `60` | 15-120 | Frame rate for display refresh. Higher = smoother scrolling, more CPU. |
| `chunk_ms` | `6.0` | 5-50 ms | Duration of each audio chunk for spectral analysis. Smaller = better time resolution, larger = better frequency resolution. |
| `number_of_chunks` | `1` | 1-10 | Number of chunks combined into analysis window. Total window = chunk_ms × number_of_chunks. |
| `padding_length_ms` | `20.0` | 0-100 ms | Zero-padding duration in milliseconds for FFT. Increases frequency resolution without changing time resolution. Larger = smoother frequency axis, more computation. |

**Key parameters:**

**Time-frequency tradeoff:**
- Shorter `chunk_ms` × `number_of_chunks` → Better time resolution (narrower window)
- Longer `chunk_ms` × `number_of_chunks` → Better frequency resolution (wider window)  
- Standard wideband: 20-40 ms window (good for formants)
- Narrowband: 100+ ms window (good for harmonics)

**Dynamic range:**
- Small (20-30 dB): See detail in quiet regions, less contrast
- Medium (40 dB): Default, balanced
- Large (50-60 dB): Strong contrast, hide quiet detail

**Max frequency:**
- Speech: 5000 Hz (sufficient for F1-F3)
- Extended: 8000 Hz (captures high fricatives)
- Limited: 3000 Hz (focus on low formants)

**Colormaps:**
- Perceptually uniform: `plasma` (default), `viridis`, `magma`, `inferno`
- Traditional: `hot`, `jet` (not perceptually uniform but familiar)

**In-window adjustments:**
- `+`/`-`: Adjust dynamic range
- `Ctrl++`/`Ctrl+-`: Adjust gain (brightness)

---

## Spectrum Settings (LiveSpectrum)

Accessed via "Spectrum Settings" button in launcher. Controls LiveSpectrum display and FFT parameters.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `gui_width` | `1200` | 600-2400 pixels | Window width. Affects X-axis frequency scale rendering. |
| `gui_height` | `650` | 300-1200 pixels | Window height. Affects Y-axis amplitude scale rendering. |
| `max_freq` | `5000` | 1000-10000 Hz | Maximum frequency displayed on X-axis. Limited by Nyquist. Typical: 5000 Hz for speech. |
| `dynamic_range` | `40` | 20-80 dB | Dynamic range in dB for Y-axis amplitude display. Controls vertical scale compression. |
| `fps` | `60` | 15-120 | Frame rate for display refresh. Higher = smoother updates, more CPU. |
| `chunk_ms` | `15.0` | 5-50 ms | Duration of each audio chunk for FFT analysis. |
| `number_of_chunks` | `3` | 1-10 | Number of chunks combined into analysis window (15 ms × 3 = 45 ms). |
| `padding_length_ms` | `20.0` | 0-100 ms | Zero-padding duration for FFT. Increases frequency bin density (smoother spectrum line). |
| `smoothing` | `0.7` | 0.0-1.0 | Response factor (alpha) for exponential smoothing. 1.0 = no smoothing (instantaneous), 0.0 = maximum smoothing (frozen). Typical: 0.5-0.8. |

**Smoothing parameter:**

Controls temporal averaging of spectrum across frames:

```
new_spectrum = (smoothing × current_spectrum) + ((1 - smoothing) × old_spectrum)
```

- `1.0`: No smoothing, instantaneous spectrum (very jittery)
- `0.7`: Default, balanced stability and responsiveness
- `0.5`: Moderate smoothing, slightly slower response
- `0.3`: Heavy smoothing, very stable but slow
- `0.0`: Maximum smoothing, frozen (no updates)

**FFT parameters:**

- Longer analysis window (chunk_ms × number_of_chunks) = better frequency resolution
- More zero-padding (padding_length_ms) = smoother frequency axis (more interpolation)
- Frequency resolution ≈ sample_rate / (window_samples + padding_samples)

**In-window adjustments:**
- `+`/`-`: Adjust gain offset (shift spectrum up/down)

---

## Recording Settings

Accessed via "Recording Settings" button in launcher. Selects audio input device.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `input_device_index` | System default | 0 to device_count-1 | QtMultimedia device index for microphone/audio input. `None` = system default. |
| `save_recordings` | `False` | True/False | Enable/disable saving any recordings (WAV/CSV). Must be True to save output. |
| `save_original_audio` | `True` | True/False | Save the device-rate/original audio stream as WAV (if `save_recordings` is True). |
| `save_downsampled_audio` | `False` | True/False | Save the analysis-rate/downsampled audio stream as WAV (if `save_recordings` is True). |

**Device selection:**

The dialog displays all available audio input devices detected by PySide6's QtMultimedia API in a dropdown. Each device shows:
- Device index
- Device name

**If no devices appear:**
- Microphone may not be connected
- OS may not recognize device
- PySide6/QtMultimedia dependencies may be missing (e.g. GStreamer on Linux)
- Check OS microphone permissions

**Testing device selection:**

```python
from PySide6.QtCore import QCoreApplication
from PySide6.QtMultimedia import QMediaDevices
app = QCoreApplication([])
devices = QMediaDevices.audioInputs()
for i, device in enumerate(devices):
    print(f"{i}: {device.description()}")
```

---

## Export Config (Code-Level Settings)

These settings are defined in `config.EXPORT_CONFIG` but not exposed in launcher dialogs. Modify in code or config file.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `save_recordings` | `False` | Enable/disable saving any recordings (WAV and CSV) for LiveVowel/LivePitch. |
| `save_wav` | `True` | Enable WAV file export (when `save_recordings` is True). |
| `save_original_audio` | `True` | Save the device-rate/original audio stream as WAV. |
| `save_downsampled_audio`| `False` | Save the analysis-rate/downsampled audio stream as WAV. |
| `save_csv` | `True` | Enable CSV file export (when `save_recordings` is True). |
| `output_dir` | `'recordings'` | Output directory for session files (relative to project root). |

**To modify:**

Edit `VocalTrack/config.py`:

```python
EXPORT_CONFIG = {
    'save_recordings': False,  # Enable/disable saving recordings (off by default)
    'save_wav': True,  # Save audio as WAV (when save_recordings is True)
    'save_original_audio': True,  # Save the device-rate/original audio stream as WAV
    'save_downsampled_audio': False,  # Save the analysis-rate/downsampled audio stream as WAV
    'save_csv': True,  # Save timestamped CSV with formants (when save_recordings is True)
    'output_dir': 'recordings',  # Output directory for files
}
```

---

## Performance Config (Code-Level Settings)

These settings control logging verbosity and are not exposed in launcher dialogs.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `logging_level` | `30` | Python logging level. 10=DEBUG, 20=INFO, 30=WARNING (default), 40=ERROR. |

**To enable debug logging:**

Edit `VocalTrack/config.py`:

```python
PERFORMANCE_CONFIG = {
    'logging_level': 10,  # Enable DEBUG messages
}
```

---

## Color Config (Code-Level Settings)

These settings define RGB colors used in visualizations and are not exposed in launcher dialogs.

| Parameter | Default (RGB) | Description |
|-----------|---------------|-------------|
| `white` | `(255, 255, 255)` | White color (text, grid lines). |
| `black` | `(0, 0, 0)` | Black color (background). |
| `blue` | `(0, 0, 255)` | Blue color (formant points, pitch contour). |
| `grey` | `(50, 50, 50)` | Dark grey (UI elements). |

**To customize colors:**

Edit `VocalTrack/config.py`:

```python
COLORS = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'blue': (100, 150, 255),  # Custom lighter blue
    'grey': (50, 50, 50),
}
```

---

## Configuration File Hierarchy

VocalTrack uses a three-tier configuration system:

1. **Code defaults** (`config.py`): Hardcoded defaults
2. **Saved settings** (`.VocalTrack_settings.json`): User preferences from launcher
3. **Runtime overrides** (passed to visualizer constructors): Programmatic overrides

**Precedence:** Runtime overrides > Saved settings > Code defaults

**Example:**

```python
# Code default in config.py
LIVEPITCH_CONFIG = {'min_f0': 75, 'max_f0': 500}

# Saved in .VocalTrack_settings.json
{"pitch_plot": {"min_f0": 100, "max_f0": 400}}

# Runtime override
app = LivePitch(min_f0=120, max_f0=350)

# Actual value used: min_f0=120, max_f0=350 (runtime wins)
```

---

## Resetting Settings

**Method 1: Delete settings file**

```bash
# From project root
rm .VocalTrack_settings.json
# or on Windows
del .VocalTrack_settings.json
```

**Method 2: Reset in code**

Modify `VocalTrack/settings_manager.py` to skip loading saved settings (advanced).

**Method 3: Manual edit**

Edit `.VocalTrack_settings.json` in a text editor and remove specific sections or set values to `null`.

---

## Settings Best Practices

1. **Start with defaults**: Don't modify settings until you understand their effect
2. **Change one parameter at a time**: Easier to diagnose issues
3. **Document your changes**: Keep notes on what works for your use case
4. **Share optimized configs**: Copy `.VocalTrack_settings.json` between installations
5. **Back up working configs**: Save copies before experimenting with extreme values
6. **Use in-window adjustments first**: Try `+`/`-` keys before opening dialogs
7. **Reset if confused**: Delete `.VocalTrack_settings.json` and start fresh

---

## Quick Reference: Common Configuration Tasks

**Task: Optimize for male voice**
- Analysis Settings: `min_f0=60`, `max_f0=250`, `max_formant=5000`
- Formant Plot: `f1_range=(200, 1100)`, `f2_range=(500, 2500)`
- Pitch Plot: `min_f0=60`, `max_f0=250`

**Task: Optimize for female voice**
- Analysis Settings: `min_f0=120`, `max_f0=400`, `max_formant=5500`
- Formant Plot: `f1_range=(200, 1200)`, `f2_range=(700, 3000)`
- Pitch Plot: `min_f0=100`, `max_f0=400`

**Task: Optimize for child voice**
- Analysis Settings: `min_f0=180`, `max_f0=500`, `max_formant=7000`
- Formant Plot: `f1_range=(250, 1500)`, `f2_range=(800, 3500)`
- Pitch Plot: `min_f0=150`, `max_f0=500`

**Task: Reduce CPU usage**
- All modes: Reduce `fps` from 60 to 30
- Spectrogram/Spectrum: Reduce `max_freq` from 5000 to 3000
- Spectrogram/Spectrum: Reduce `padding_length_ms` from 20 to 10

**Task: Improve tracking stability**
- Smoother Settings: Increase `memory_n` from 3 to 5
- Smoother Settings: Decrease `euro_min_cutoff` from 0.05 to 0.02
- Smoother Settings: Increase `stability_threshold` from 0.15 to 0.25

**Task: Improve tracking responsiveness**
- Smoother Settings: Decrease `memory_n` from 3 to 2
- Smoother Settings: Increase `euro_min_cutoff` from 0.05 to 0.10
- Smoother Settings: Increase `euro_beta` from 1.5 to 2.0
