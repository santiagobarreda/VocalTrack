# Installation and Launch

## System Requirements

### Minimum Requirements

- **Python**: >=3.9 and <3.14
- **Operating System**: Windows, macOS, or Linux
- **Audio**: USB microphone or other reasonable high-quality built-in microphone
- **Display**: 1024×768 minimum resolution

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/santiagobarreda/VocalTrack.git
cd VocalTrack
```

Alternatively, download the ZIP file from GitHub:
1. Navigate to the repository page
2. Click "Code" → "Download ZIP"
3. Extract the archive to your preferred location

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages:

- **PySide6** (≥6.5.0): GUI launcher interface & real-time audio input via QtMultimedia
- **parselmouth** (0.4.0): Praat-based formant/pitch analysis (optional backend)
- **pygame** (2.5.0): Graphics and visualization
- **numpy** (≥1.20.0): Numerical operations

### Step 3: Verify Installation

Test that all dependencies are installed correctly:

```bash
python -c "import parselmouth, pygame, numpy, PySide6; print('All dependencies installed successfully!')"
```

If you see "All dependencies installed successfully!", you're ready to launch VocalTrack.

## Troubleshooting Installation

### QtMultimedia / Audio Dependencies (Linux only)

**Windows & macOS:**

No extra dependencies are required. PySide6 comes with built-in support for audio devices via QtMultimedia.

**Linux:**

On Linux, QtMultimedia relies on the system GStreamer framework. Install the required packages with:

```bash
sudo apt-get install libqt6multimedia6 libqt6multimediawidgets6 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

### Permission Errors

If you encounter permission errors during installation:

**Windows:**
- Run terminal as Administrator, or
- Install packages for current user only: `pip install --user -r requirements.txt`

**macOS/Linux:**
- Use sudo: `sudo pip install -r requirements.txt`, or
- Install for current user: `pip install --user -r requirements.txt`

### Import Errors After Installation

If you see "ModuleNotFoundError" when launching:

1. Re-run: `pip install -r requirements.txt`
2. Check Python version: `python --version` (must be >=3.9 and <3.14)

## Operating System Permissions

### Microphone Access

VocalTrack requires microphone access to function. Ensure OS permissions are granted:

**Windows:**
1. Settings → Privacy & Security → Microphone
2. Enable "Allow apps to access your microphone"
3. Enable "Allow desktop apps to access your microphone"

**macOS:**
1. System Preferences → Security & Privacy → Privacy tab
2. Select "Microphone" from the list
3. Check the box next to Terminal or your Python executable

**Linux:**
No special permissions typically required. If issues occur, check PulseAudio/ALSA settings.

## Launching VocalTrack

### Start the Launcher

From the project root directory:

```bash
python vocaltrack.py
```

The PySide6 launcher window will appear.

### Alternative: Direct Mode Launch (Advanced)

You can bypass the launcher and start a mode directly using Python:

**LiveVowel:**
```python
from VocalTrack.LiveVowel import LiveVowel
app = LiveVowel()
```

**LivePitch:**
```python
from VocalTrack.LivePitch import LivePitch
app = LivePitch()
```

**LiveSpectrogram:**
```python
from VocalTrack.LiveSpectrogram import LiveSpectrogram
app = LiveSpectrogram()
```

**LiveSpectrum:**
```python
from VocalTrack.LiveSpectrum import LiveSpectrum
app = LiveSpectrum()
```

However, using the launcher is recommended for normal use as it provides:
- Persistent settings management
- GUI-based configuration
- Device selection interface
- Benchmarking tools

## Launcher Interface Layout

The VocalTrack launcher window is divided into two main sections:

### Settings Buttons (Top Panel)

These dialogs configure parameters for all visualization modes:

1. **Analysis Settings**
   - Window duration (chunk_ms, number_of_chunks)
   - Formant/pitch analysis bounds (min_f0, max_f0, max_formant)
   - Analysis method (native vs. parselmouth)
   - RMS threshold

2. **Smoother Settings**
   - 1-Euro filter parameters (euro_min_cutoff, euro_beta, euro_dcutoff)
   - Memory buffer size (memory_n)
   - Stability thresholds
   - Velocity power (for adaptive responsiveness)

3. **Recording Settings**
   - Audio input device selection
   - Displays available QtMultimedia devices

4. **Formant Plot Settings** (LiveVowel)
   - F1/F2 display ranges
   - Display mode (single, track, all)
   - Frequency scale (log/linear)
   - FPS

5. **Pitch Plot Settings** (LivePitch)
   - f0 display range (independent of analysis range)
   - Plot mode (fixed/continuous)
   - Display window duration
   - Frequency scale
   - FPS

6. **Spectrogram Settings** (LiveSpectrogram)
   - Frequency range (max_freq)
   - Display time window (display_seconds)
   - Colormap selection
   - Dynamic range
   - FFT parameters (chunk_ms, padding_length_ms)
   - FPS

7. **Spectrum Settings** (LiveSpectrum)
   - Frequency range (max_freq)
   - Dynamic range
   - FFT parameters
   - Smoothing factor (0-1)
   - FPS

8. **Benchmarking**
   - Launches benchmarking tools
   - Accuracy benchmark (compare against Parselmouth)
   - Timing benchmark (measure processing performance)

### Launch Buttons (Bottom Panel)

Four colored buttons launch visualization modes:

- **LiveVowel** (green button): F1/F2 vowel space tracking
- **LivePitch** (blue button): f0 pitch contour visualization
- **LiveSpectrogram** (purple button): Scrolling spectrogram
- **LiveSpectrum** (orange button): Real-time spectrum analyzer

## Typical First-Run Workflow

### 1. Configure Recording Device

1. Click **Recording Settings** button
2. Select your microphone from the dropdown list
3. Click OK

If no devices appear, verify:
- Microphone is connected and powered on
- OS recognizes the device (check Sound settings)
- QtMultimedia can detect devices: `python -c "from PySide6.QtCore import QCoreApplication; from PySide6.QtMultimedia import QMediaDevices; app = QCoreApplication([]); print(f'{len(QMediaDevices.audioInputs())} input devices found')"`

### 2. Configure Analysis Parameters

1. Click **Analysis Settings** button
2. Set appropriate values for your voice:
   - **min_f0**: Lowest expected f0 (e.g., 60 Hz for male, 120 Hz for female)
   - **max_f0**: Highest expected f0 (e.g., 250 Hz for male, 400 Hz for female)
   - **max_formant**: Upper formant bound (5000 Hz for adult, 5500-8000 Hz for child)
3. Leave other parameters at defaults initially
4. Click OK

### 3. Configure Mode-Specific Display Settings (Optional)

For your first session, defaults are usually fine. You can skip this step.

If you want to customize:

**For LiveVowel:**
- Click **Formant Plot Settings**
- Adjust F1/F2 ranges if needed
- Select display mode (`single` recommended for beginners)
- Click OK

**For LivePitch:**
- Click **Pitch Plot Settings**
- Adjust f0 display range (can differ from analysis range)
- Select plot mode (`fixed` recommended for beginners)
- Click OK

### 4. Launch a Visualization Mode

Click one of the four launch buttons. A Pygame window opens with the real-time visualization.

**Tips for first-time use:**
- Start with **LivePitch** (simplest workflow: hold Space to record)
- Try **LiveVowel** next (press Ctrl+V to toggle recording)
- Experiment with **LiveSpectrogram** for visual phonetics
- Use **LiveSpectrum** for spectral analysis and resonance visualization

## Settings Persistence

### Automatic Saving

All settings configured in the launcher dialogs are automatically saved to:

```
.VocalTrack_settings.json
```

This file is created in the project root directory the first time you modify and save settings.

### Saved Categories

The following setting categories are persisted:

- `analysis` (Analysis Settings dialog)
- `smoother` (Smoother Settings dialog)
- `plotting` (Formant Plot Settings dialog)
- `pitch_plot` (Pitch Plot Settings dialog)
- `spectrogram` (Spectrogram Settings dialog)
- `spectrum` (Spectrum Settings dialog)

**Note:** Recording device selection is also saved and restored automatically.

### Loading Settings on Startup

When you launch `vocaltrack.py`, the application:

1. Checks for `.VocalTrack_settings.json` in the project root
2. Loads saved settings if the file exists
3. Applies loaded settings to all runtime configurations
4. Falls back to defaults from `config.py` for any missing values

### Resetting to Defaults

To reset all settings to defaults:

1. Close VocalTrack if running
2. Delete or rename `.VocalTrack_settings.json`
3. Restart `vocaltrack.py`

Alternatively, manually edit `.VocalTrack_settings.json` in a text editor.

### Sharing Settings Between Users

To share your optimized settings:

1. Copy `.VocalTrack_settings.json` from one installation
2. Paste into another installation's project root
3. Launch VocalTrack—settings will be applied automatically

## Exit Behavior

### Closing the Launcher

Clicking the X button on the launcher window closes only the launcher. Any running visualization modes continue independently.

### Closing a Visualization Mode

**Method 1: Keyboard**
- Press `Esc` key

**Method 2: Mouse**
- Click the X button on the Pygame window

**For LiveVowel and LivePitch:**
- Audio and CSV files are automatically exported to `recordings/` on quit
- Files are named with timestamps/suffixes: `speaker_YYYY-MM-DD_HHMMSS_vowel_original.wav` (and/or `_downsampled.wav`), `speaker_YYYY-MM-DD_HHMMSS_formants.csv` for LiveVowel; `speaker_YYYY-MM-DD_HHMMSS_pitch_original.wav` (and/or `_downsampled.wav`), `speaker_YYYY-MM-DD_HHMMSS_pitch.csv` for LivePitch
- Audio saving can be toggled on/off in the recording settings dialog

**For LiveSpectrogram and LiveSpectrum:**
- Window closes immediately (visualization-only modes)
- No automatic export by default

## Verifying Audio Input

Before recording, verify that VocalTrack is receiving audio:

1. Launch any visualization mode
2. Speak into the microphone
3. Watch for visual feedback:
   - **LiveVowel**: Formant points should appear when speaking
   - **LivePitch**: Pitch contour should appear when holding Space
   - **LiveSpectrogram**: Spectrogram should show acoustic energy
   - **LiveSpectrum**: Spectrum should show peaks at harmonics

If no feedback appears:

1. Check Recording Settings—verify correct device is selected
2. Increase microphone volume in OS settings
3. Reduce `min_rms_db` threshold (make more negative, e.g., -70 dB)
4. Test microphone in another app to confirm it's working

## Command-Line Options (Advanced)

VocalTrack does not currently support command-line arguments for the launcher. All configuration is done through the GUI dialogs.

For advanced scripting and automation, import modes directly in Python and pass configuration dictionaries:

```python
from VocalTrack import config
from VocalTrack.LivePitch import LivePitch

# Override defaults
custom_config = config.LIVEPITCH_CONFIG.copy()
custom_config['min_f0'] = 100
custom_config['max_f0'] = 400

# Launch with custom config
app = LivePitch(pitch_config=custom_config)
```

## Updating VocalTrack

To update to the latest version:

1. Navigate to the project directory
2. Pull latest changes:

```bash
git pull origin main
```

3. Update dependencies:

```bash
pip install --upgrade -r requirements.txt
```

4. Restart VocalTrack

## Troubleshooting Launch Issues

### Launcher Won't Start

**Error: "No module named 'PySide6'"**
- Solution: `pip install PySide6>=6.5.0`

**Error: "No module named 'VocalTrack'"**
- Solution: Ensure you're running `python vocaltrack.py` from the project root directory

**Window appears blank or frozen**
- Solution: Update graphics drivers, try running on primary display

### Visualization Mode Won't Launch

**Error: "No suitable audio device found"**
- Solution: Connect microphone, verify in Recording Settings

**Error: "Invalid audio device index"**
- Solution: Open Recording Settings and reselect your device

**Pygame window opens then immediately closes**
- Solution: Check terminal for error messages, verify all dependencies are installed

For additional troubleshooting, see [Troubleshooting.md](Troubleshooting.md).
