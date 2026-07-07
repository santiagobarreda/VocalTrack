# Troubleshooting

This guide provides solutions to common issues encountered when installing, configuring, and using VocalTrack.

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Audio Input Problems](#audio-input-problems)
3. [Visualization Issues](#visualization-issues)
4. [Export and File Output Problems](#export-and-file-output-problems)
5. [Performance Issues](#performance-issues)
6. [Analysis Quality Issues](#analysis-quality-issues)
7. [Settings and Configuration Issues](#settings-and-configuration-issues)
8. [Platform-Specific Issues](#platform-specific-issues)
9. [Known Limitations](#known-limitations)

---

## Installation Issues

### PySide6 / QtMultimedia Audio Issues

**Problem**: VocalTrack is unable to initialize audio or no audio devices are detected, or you get errors regarding QtMultimedia.

**Solution**:
VocalTrack uses **QtMultimedia** (part of `PySide6`) for real-time audio input. Unlike PyAudio, it does not require installing external wrappers or compiling PortAudio. However, you must ensure PySide6 is fully installed.

**Windows & macOS:**
Reinstall PySide6:
```bash
pip uninstall PySide6
pip install PySide6>=6.5.0
```

**Linux (Ubuntu/Debian):**
On Linux, QtMultimedia requires system multimedia plugins (GStreamer) and GStreamer codecs. Install them via:
```bash
sudo apt-get install libqt6multimedia6 libqt6multimediawidgets6 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

### No module named 'PySide6'

**Problem**: `ImportError: No module named 'PySide6'` when launching `vocaltrack.py`.

**Solution**:
```bash
pip install PySide6>=6.5.0
```

If installation fails due to build errors, try:
```bash
pip install --upgrade pip setuptools wheel
pip install PySide6
```

### No module named 'VocalTrack'

**Problem**: `ModuleNotFoundError: No module named 'VocalTrack'` when running scripts.

**Cause**: Running Python from wrong directory or `VocalTrack/` folder not in path.

**Solution**:
1. Ensure you're in the project root directory (where `vocaltrack.py` is located)
2. Run: `python vocaltrack.py` (not `python VocalTrack/vocaltrack.py`)

**Alternative**:
```bash
# From any directory
export PYTHONPATH=/path/to/VocalTrack
python -c "import VocalTrack; print('Success')"
```

### Permission denied when installing packages

**Problem**: `PermissionError` or `Access denied` when running `pip install`.

**Solution**:

**Option 1**: Install for current user only (recommended)
```bash
pip install --user -r requirements.txt
```

**Option 2**: Use virtual environment (best practice)
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

**Option 3**: Run as administrator (Windows only, not recommended)
- Right-click Command Prompt → "Run as administrator"
- Navigate to project directory
- Run: `pip install -r requirements.txt`

### Parselmouth installation fails

**Problem**: `pip install praat-parselmouth` fails with compilation errors.

**Cause**: Missing C++ compiler or incompatible Python version.

**Solution**:

**Windows:**
1. Install Visual C++ Build Tools: https://visualstudio.microsoft.com/downloads/ (select "Build Tools for Visual Studio")
2. Retry: `pip install praat-parselmouth`

**macOS:**
1. Install Xcode Command Line Tools: `xcode-select --install`
2. Retry: `pip install praat-parselmouth`

**Linux:**
```bash
sudo apt-get install build-essential
pip install praat-parselmouth
```

**Workaround**: Use native analysis methods instead
- In Analysis Settings dialog, select `formant_method='native'` and `pitch_method='native'`
- VocalTrack will work without Parselmouth (needed only for benchmarking)

---

## Audio Input Problems

### No microphone detected / Recording Settings shows no devices

**Problem**: "Recording Settings" dialog shows empty dropdown or "No devices found".

**Solution**:

1. **Verify microphone is connected**:
   - Check physical connection (USB or 3.5mm jack)
   - For USB mics, try different USB port
   - Check that mic is powered on (if applicable)

2. **Check OS recognizes device**:
   - **Windows**: Settings → Sound → Input → Select device
   - **macOS**: System Preferences → Sound → Input tab
   - **Linux**: `arecord -l` to list recording devices

3. **Verify PySide6 can see devices**:
   ```bash
   python -c "from PySide6.QtCore import QCoreApplication; from PySide6.QtMultimedia import QMediaDevices; app = QCoreApplication([]); print(f'{len(QMediaDevices.audioInputs())} input devices found'); [print(f\"{i}: {d.description()}\") for i, d in enumerate(QMediaDevices.audioInputs())]"
   ```

4. **Check OS permissions** (macOS/Windows):
   - **macOS**: System Preferences → Security & Privacy → Privacy → Microphone → Enable for Terminal/Python
   - **Windows**: Settings → Privacy → Microphone → Allow apps to access microphone, enable for desktop apps

5. **Troubleshoot QtMultimedia**:
   - Reinstall PySide6: `pip uninstall PySide6; pip install PySide6`
   - On Linux, make sure GStreamer libraries are installed (see installation issues above).

6. **Restart computer**: Sometimes audio drivers need refresh

### Audio input works but VocalTrack shows no response

**Problem**: Microphone is detected and selected, but no visualization appears when speaking.

**Solution**:

1. **Check RMS threshold**: `min_rms_db` may be too high (not negative enough)
   - Open Analysis Settings
   - Change `min_rms_db` from -60 to -70 or -80
   - Or press `-` key several times during recording to lower threshold

2. **Verify microphone volume**:
   - Check OS microphone volume settings (may be muted or too low)
   - Speak louder or move closer to microphone

3. **Test microphone in other apps**:
   - Record in Audacity, Voice Recorder, or similar
   - Verify mic is actually capturing audio
   - Check that correct mic is selected as system default

4. **Check audio device selection**:
   - Open Recording Settings in launcher
   - Try selecting a different device
   - Default device may not be the one you expect

5. **Verify analysis parameters**:
   - For LivePitch: Check that voice is within `min_f0` to `max_f0` range
   - For LiveVowel: Ensure you pressed `Ctrl+R` or hid the help overlay (`Ctrl+?`) to start recording

### Crackling, popping, or distorted audio

**Problem**: Audio contains artifacts, clicks, pops, or distortion.

**Possible causes and solutions**:

1. **Buffer underrun** (CPU can't keep up):
   - Solution: Increase `chunk_ms` (e.g., from 20 to 30 ms) in Analysis Settings
   - Close other CPU-intensive applications
   - Reduce FPS in visualization settings

2. **Microphone gain too high**:
   - Solution: Reduce microphone input volume in OS settings
   - Move farther from microphone or speak more quietly

3. **USB audio interface issue**:
   - Solution: Try different USB port (prefer USB 2.0 over USB 3.0 for audio)
   - Use powered USB hub if multiple devices on same bus

4. **Sample rate mismatch**:
   - Solution: Check that microphone supports VocalTrack's sample rate (typically 10000 Hz)
   - Some devices may resample poorly—try setting `max_formant=8000` to use 16000 Hz sample rate

### Echo or feedback in recordings

**Problem**: Recorded audio contains echo or feedback loop.

**Cause**: System audio output is being picked up by microphone.

**Solution**:
1. Use headphones instead of speakers during recording
2. Mute system audio output during recording
3. Reduce speaker/output volume
4. Move microphone farther from speakers

---

## Visualization Issues

### Pygame window is blank or frozen

**Problem**: Visualization mode window opens but shows only black/white screen.

**Possible causes and solutions**:

1. **Graphics driver issue**:
   - Solution: Update graphics drivers
   - Try running on primary display if using multiple monitors

2. **Pygame not initialized properly**:
   - Solution: Reinstall pygame: `pip uninstall pygame; pip install pygame==2.5.0`

3. **Window too small**:
   - Solution: Resize window by dragging edges
   - Or adjust `gui_width` and `gui_height` in settings

4. **Display on wrong monitor** (multi-monitor setup):
   - Solution: Move window to primary display
   - Or press Windows+Shift+Left/Right arrow to move between monitors

5. **Python/Pygame rendering issue**:
   - Solution: Try running with different Python version
   - Check terminal for error messages

### Display is too compressed / formants appear off-screen

**Problem**: LiveVowel formant points appear outside visible area or bunched in corner.

**Cause**: F1/F2 ranges don't match speaker's formant values.

**Solution**:

1. **Widen formant ranges** (Formant Plot Settings):
   - F1: Increase upper bound (e.g., 200-1200 → 200-1500)
   - F2: Increase upper/lower bounds (e.g., 500-2700 → 400-3000)

2. **Check for speaker type**:
   - Child voices need higher formant ranges (F1: 250-1500, F2: 700-3500)
   - Male voices may need narrower ranges (F1: 200-1000, F2: 500-2300)

3. **Toggle frequency scale**:
   - Press `Ctrl+L` to switch between log and linear scale
   - Logarithmic scale may provide better spread

4. **Examine CSV output** to see actual formant values:
   ```bash
   # Check F1/F2 ranges in data
   python -c "import pandas as pd; df = pd.read_csv('recordings/speaker_*.csv'); print(df[['f1', 'f2']].describe())"
   ```

### LivePitch contour is choppy or jumpy

**Problem**: Pitch contour shows discontinuous jumps instead of smooth curve.

**Possible causes and solutions**:

1. **Pitch jumps between octaves** (octave errors):
   - Solution: Adjust `min_f0` and `max_f0` to tighter range around expected voice
   - Switch pitch_method from 'native' to 'parselmouth' if available

2. **Insufficient smoothing**:
   - Solution in Smoother Settings:
     - Increase `memory_n` from 3 to 5
     - Decrease `euro_min_cutoff` from 0.05 to 0.02
     - Decrease `euro_beta` from 1.5 to 1.0

3. **Voicing detection issues**:
   - Solution: Lower `min_rms_db` threshold
   - Ensure voice is loud enough, speak more clearly

4. **Time resolution too coarse**:
   - Solution: Reduce `chunk_ms` (e.g., from 20 to 15 ms) in Analysis Settings
   - This provides more frequent pitch updates

### LiveSpectrogram looks washed out or too dark

**Problem**: Spectrogram is too bright (everything looks white) or too dark (hard to see detail).

**Solution**:

**If too bright:**
- Press `-` key several times to increase dynamic range
- Press `Ctrl+-` several times to decrease gain
- Reduce microphone input volume in OS settings

**If too dark:**
- Press `+` key several times to decrease dynamic range
- Press `Ctrl++` several times to increase gain
- Increase microphone input volume in OS settings
- Lower `min_rms_db` threshold in Analysis Settings

**Optimal settings**:
- Dynamic range: 30-50 dB (lower for more detail, higher for more contrast)
- Gain: Adjust so formants are clearly visible but noise floor is not saturated

### LiveSpectrum line is too noisy/jittery

**Problem**: Spectrum plot jumps erratically between frames.

**Solution**:

1. **Increase smoothing** (Spectrum Settings):
   - Change `smoothing` from 0.7 to 0.8 or 0.9
   - Higher values = more stable but slower response

2. **Increase analysis window**:
   - Increase `chunk_ms` (e.g., 20 → 30 ms)
   - Increase `number_of_chunks` (e.g., 3 → 5)
   - Longer window = smoother spectrum, worse time resolution

3. **Increase zero-padding**:
   - Increase `padding_length_ms` (e.g., 20 → 40 ms) in Spectrum Settings
   - More padding = smoother frequency axis

---

## Export and File Output Problems

### No files generated after recording

**Problem**: Recorded session but cannot find WAV/CSV files in `recordings/` folder.

**Possible causes and solutions**:

1. **Wrong visualization mode** (LiveSpectrogram/LiveSpectrum don't export by default):
   - Solution: Use LiveVowel or LivePitch for automatic export

2. **Recording not started**:
   - LiveVowel: Must press `Ctrl+R` or hide the help overlay with `Ctrl+?` to enter recording state before speaking
   - LivePitch: Must hold `Space` key while speaking
   - Solution: Check that recording control was activated

3. **No voiced frames** (all data filtered out):
   - Solution: Produce voiced sounds (vowels, /m/, /n/, /v/, /z/)
   - Check that f0 is within configured range (`min_f0` to `max_f0`)
   - Lower `min_rms_db` threshold

4. **Export disabled in config**:
   - Check `config.py` → `EXPORT_CONFIG`
   - Ensure `save_wav: True` and `save_csv: True`

5. **Write permissions issue**:
   - Check that `recordings/` folder exists and is writable
   - Try running with elevated permissions
   - Or change `output_dir` in `EXPORT_CONFIG` to a different location

6. **Files saved to unexpected location**:
   - Check if `output_dir` in `EXPORT_CONFIG` was modified
   - Search entire project directory for `*.wav` and `*.csv` files

### CSV file is empty (header only, no rows)

**Problem**: CSV file exists but contains only column names with no data rows.

**Cause**: All frames were filtered out due to voicing/f0 criteria.

**Solution**:

1. **Check f0 range**:
   - Verify your voice f0 is within configured `min_f0` to `max_f0` range
   - Test by producing sustained vowel and checking expected pitch
   - Widen f0 range in Analysis Settings (e.g., min_f0=40, max_f0=600)

2. **Check voicing detection**:
   - Ensure you're producing voiced sounds (vowels, not whisper)
   - Lower `min_rms_db` threshold (make more negative, e.g., -70 dB)
   - Speak louder or closer to microphone

3. **Verify formant extraction**:
   - Switch `formant_method` from 'native' to 'parselmouth' (or vice versa)
   - Check terminal for error messages during recording

4. **Examine pre-filter data**:
   - Temporarily disable filtering by modifying `exporter.py`:
     ```python
     # Comment out filtering logic in save_formants_csv()
     # Always write all rows instead of filtering
     ```

### WAV file is present but CSV is missing

**Problem**: WAV file exported successfully but corresponding CSV file not found.

**Possible causes and solutions**:

1. **CSV export disabled**:
   - Check `config.py` → `EXPORT_CONFIG` → `save_csv` is `True`

2. **All data filtered out**:
   - Same as "CSV file is empty" above
   - CSV may not be created if no rows would be written

3. **File extension issue**:
   - Check for `*.csv` vs `*.CSV` (case-sensitive on Linux/macOS)
   - Search for files ending in `_formants.*` or `_pitch.*`

4. **CSV write error**:
   - Check terminal for error messages during export
   - Verify write permissions on `recordings/` folder

---

## Performance Issues

### Display is laggy or stuttering

**Problem**: Visualization updates slowly or skips frames.

**Possible causes and solutions**:

1. **FPS too high for system**:
   - Solution: Reduce FPS (e.g., from 60 to 30) in mode-specific settings
   - Lower FPS = less CPU usage, still usable for most applications

2. **CPU overload**:
   - Solution: Close other applications
   - Reduce background processes
   - Run VocalTrack on dedicated display (not screen sharing/remote desktop)

3. **Spectrogram/Spectrum: max_freq too high**:
   - Solution: Reduce `max_freq` (e.g., from 8000 to 5000 Hz)
   - Lower frequency range = smaller FFT = faster computation

4. **Spectrogram/Spectrum: too much zero-padding**:
   - Solution: Reduce `padding_length_ms` (e.g., from 40 to 10 ms)
   - Less padding = faster FFT

5. **Analysis method too slow**:
   - Solution: Switch `formant_method` and `pitch_method` to 'native' instead of 'parselmouth'
   - Native methods are generally faster

6. **Python running in interpreted mode**:
   - Solution: Ensure numpy/other packages are using compiled extensions
   - Reinstall numpy: `pip uninstall numpy; pip install numpy`

### Audio dropouts or gaps

**Problem**: Audio recording contains silent gaps or dropped frames.

**Cause**: CPU cannot keep up with real-time audio processing.

**Solution**:

1. **Increase chunk size**:
   - In Analysis Settings, increase `chunk_ms` (e.g., 20 → 30 ms)
   - Larger chunks = fewer processing calls per second = less CPU load

2. **Reduce processing load**:
   - Disable formant analysis if only pitch is needed (set `formants=False` in code)
   - Reduce FPS in visualization settings
   - Close other applications

3. **Improve audio buffer settings**:
   - Modify `AudioProcessor` to use larger internal buffers (requires code change)

4. **Use dedicated audio hardware**:
   - External USB audio interface often has better buffering than built-in mic
   - ASIO drivers (Windows) may improve latency

### High CPU usage during idle periods

**Problem**: VocalTrack uses significant CPU even when not speaking.

**Cause**: Visualization and analysis run continuously regardless of input.

**Solution**:

1. **Reduce FPS when not actively using**:
   - Before speaking, temporarily set FPS to 15 or 30
   - Increase back to 60 during active use

2. **Implement voice activity detection** (code modification):
   - Skip analysis when RMS is below threshold
   - Requires modifying main loop logic

3. **Close unused visualization windows**:
   - Only run one mode at a time

---

## Analysis Quality Issues

### Noisy or unstable formant tracking

**Problem**: Formant points jump erratically even during sustained vowels.

**Possible causes and solutions**:

1. **Background noise**:
   - Solution: Record in quieter environment
   - Increase `min_rms_db` (less negative, e.g., -50 → -40 dB)
   - Use close-mic technique

2. **Insufficient smoothing**:
   - Solution in Smoother Settings:
     - Increase `memory_n` (3 → 5)
     - Decrease `euro_min_cutoff` (0.05 → 0.02)
     - Decrease `stability_threshold` (0.15 → 0.10) to accept more data points

3. **Low-quality microphone**:
   - Solution: Use better microphone
   - Condenser mic or USB headset usually better than built-in laptop mic

4. **Speaker characteristics**:
   - Solution: Adjust `max_formant` for speaker type
   - Female/child speakers may need higher max_formant (5500-7000 Hz)

5. **Analysis method**:
   - Solution: Try switching between 'native' and 'parselmouth' methods
   - Different algorithms may work better for different voices

### Pitch detection fails or is erratic

**Problem**: Pitch contour shows frequent octave jumps or missing segments.

**Possible causes and solutions**:

1. **Octave errors** (doubling/halving):
   - Solution: Narrow `min_f0` and `max_f0` range to expected voice range
   - Male: 60-250 Hz, Female: 120-400 Hz, Child: 180-500 Hz

2. **Breathy voice / low SNR**:
   - Solution: Speak with more modal voice quality
   - Increase microphone gain
   - Use `pitch_method='parselmouth'` if available (more robust to noise)

3. **Creaky voice / vocal fry**:
   - Solution: Lower `min_f0` (e.g., to 40 Hz) to capture creaky phonation
   - Or avoid vocal fry in recordings

4. **Analysis parameters**:
   - Solution: Increase `window_length` for more stable f0
     - Increase `chunk_ms` or `number_of_chunks` in Analysis Settings
     - Longer window = more stable but slower time response

### Formants appear at wrong frequencies

**Problem**: Formant estimates are consistently too high or too low.

**Possible causes and solutions**:

1. **Sample rate mismatch**:
   - Solution: Verify `max_formant` is set correctly
   - Sample rate = 2 × max_formant (Nyquist theorem)
   - For adult speakers, max_formant=5000 gives sample_rate=10000 Hz

2. **Wrong `n_formants` setting**:
   - Solution: For most adult speakers, `n_formants=5.5` is correct
   - Children may need `n_formants=6.0` or higher

3. **Pre-emphasis too strong/weak**:
   - Solution: Adjust `pre_emphasis_coeff` in `ANALYSIS_CONFIG` (code-level)
   - Default 0.97 is standard for speech

4. **Formant analysis method**:
   - Solution: Try switching between 'native' and 'parselmouth'
   - Cross-validate using benchmarking tool

5. **Microphone frequency response**:
   - Solution: Use microphone with flat frequency response
   - Some mics boost/attenuate certain frequencies

---

## Settings and Configuration Issues

### Settings are not saved between sessions

**Problem**: Changes made in launcher dialogs are not persisted when VocalTrack is restarted.

**Possible causes and solutions**:

1. **Write permissions issue**:
   - Solution: Verify `.VocalTrack_settings.json` file is created in project root
   - Check file permissions (should be writable by current user)
   - Try running with elevated permissions

2. **Settings file corrupted**:
   - Solution: Delete `.VocalTrack_settings.json` and recreate settings

3. **Settings not applied**:
   - Solution: Click "OK" button in settings dialogs (not just X to close)
   - Changes are only saved when OK is pressed

4. **JSON syntax error**:
   - Solution: Manually inspect `.VocalTrack_settings.json` for syntax errors
   - Fix or delete file to reset

### Settings file is corrupted

**Problem**: VocalTrack fails to load with JSON parsing error.

**Symptoms**: Error message mentioning `.VocalTrack_settings.json` and JSON decode error.

**Solution**:

1. **Delete corrupted file**:
   ```bash
   # From project root
   rm .VocalTrack_settings.json  # Linux/macOS
   del .VocalTrack_settings.json  # Windows
   ```

2. **Or manually fix JSON**:
   - Open `.VocalTrack_settings.json` in text editor
   - Look for syntax errors (missing commas, unmatched brackets)
   - Fix or restore from backup

3. **Prevent future corruption**:
   - Don't manually edit settings file while VocalTrack is running
   - Use UTF-8 encoding if editing manually

### Cannot select preferred microphone

**Problem**: Desired microphone not appearing in Recording Settings dropdown.

**Possible causes and solutions**:

1. **Device not connected**:
   - Solution: Plug in microphone and restart VocalTrack

2. **QtMultimedia doesn't see device**:
   - Solution: Test with: `python -c "from PySide6.QtCore import QCoreApplication; from PySide6.QtMultimedia import QMediaDevices; app = QCoreApplication([]); [print(d.description()) for d in QMediaDevices.audioInputs()]"`
   - Verify device appears in list

3. **Device is output-only**:
   - Solution: Ensure device has input channels (not just output)

4. **Driver issue**:
   - Solution: Update audio drivers
   - Try different USB port for USB microphones
   - Reinstall PySide6

---

## Platform-Specific Issues

### Windows: DLL load failed

**Problem**: `ImportError: DLL load failed` when importing PySide6 or other packages.

**Solution**:

1. **Install Visual C++ Redistributable**:
   - Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Install and restart computer

2. **Reinstall problematic package**:
   ```bash
   pip uninstall PySide6
   pip install PySide6
   ```

### macOS: Permission denied for microphone

**Problem**: VocalTrack launches but shows no audio input even though microphone is connected.

**Cause**: macOS requires explicit permission for apps to access microphone.

**Solution**:

1. **Grant microphone permission**:
   - System Preferences → Security & Privacy → Privacy tab
   - Select "Microphone" from left sidebar
   - Check box next to "Terminal" (or your Python app)
   - Restart Terminal and VocalTrack

2. **If permission checkbox is grayed out**:
   - Click padlock icon at bottom-left to unlock
   - Enter admin password
   - Enable permission

### Linux: ALSA errors or warnings

**Problem**: Terminal shows ALSA error messages when running VocalTrack.

**Typical errors**:
```
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.rear
ALSA lib pcm.c:2495:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.center_lfe
...
```

**Cause**: ALSA configuration issues (usually harmless but annoying).

**Solution**:

**Option 1**: Suppress warnings (quick fix)
```bash
export ALSA_CARD=0
python vocaltrack.py 2>/dev/null  # Suppress stderr
```

**Option 2**: Fix ALSA configuration (permanent fix)
```bash
# Edit ALSA config
sudo nano /etc/asound.conf

# Add or modify default device:
defaults.pcm.card 0
defaults.ctl.card 0
```

**Option 3**: Use PulseAudio instead of ALSA
```bash
# Ensure PulseAudio is running
pulseaudio --check
pulseaudio --start

# VocalTrack should automatically use PulseAudio through QtMultimedia
```

---

## Known Limitations

### Current limitations in VocalTrack:

1. **Mono audio only**: Multi-channel input not supported
   - Workaround: Use mono mic or modify code to split channels

2. **Fixed speaker ID**: Cannot customize speaker name in GUI
   - Workaround: Manually rename files after export or modify `exporter.py`

3. **LiveSpectrogram/LiveSpectrum no CSV export**: Visualization-only by default
   - Workaround: Modify source code to enable audio buffer export

4. **No real-time CSV streaming**: CSV written only on exit
   - Workaround: Modify exporter to write rows incrementally

5. **No Praat TextGrid export**: Only CSV format available
   - Workaround: Convert CSV to TextGrid using Praat script or Python

6. **No pitch tracking in LiveVowel**: Displays f0 but doesn't track pitch contour
   - Workaround: Use LivePitch for dedicated pitch tracking

7. **No simultaneous modes**: Can only run one visualization at a time
   - Workaround: Run in separate Python processes (advanced)

8. **Limited formant analysis**: Only F1-F3 written to CSV
   - Note: F4-F5 are analyzed but not exported (can be added in code)

9. **No database integration**: Files only, no SQL/NoSQL support
   - Workaround: Write custom import scripts for your database

10. **No cloud sync**: All files stored locally
    - Workaround: Use Dropbox, Google Drive, or similar for project folder

---

## Getting Further Help

If you've tried the solutions above and still have issues:

1. **Check terminal output**:
   - Run VocalTrack from terminal/command prompt to see error messages
   - Look for Python tracebacks or warning messages

2. **Enable debug logging**:
   - Edit `config.py` → `PERFORMANCE_CONFIG` → `logging_level` set to `10`
   - Restart VocalTrack and check terminal for detailed logs

3. **Test components individually**:
   ```python
    # Test QtMultimedia
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtMultimedia import QMediaDevices
    app = QCoreApplication([])
    print(f"{len(QMediaDevices.audioInputs())} devices")
    
    # Test formant analysis
    from VocalTrack.Sound import Sound
    # ... (advanced testing)
    ```

4. **Check Python and package versions**:
   ```bash
   python --version
   pip list | grep -E "parselmouth|pygame|numpy|PySide6"
   ```

5. **Search GitHub Issues**:
   - https://github.com/santiagobarreda/VocalTrack/issues
   - Search for similar problems and solutions

6. **Open a new issue**:
   - If problem persists, open GitHub issue with:
     - Operating system and version
     - Python version
     - Package versions (`pip list`)
     - Full error message and traceback
     - Steps to reproduce

7. **Community support**:
   - Check project wiki and documentation
   - Ask on relevant speech processing forums

---

## Diagnostic Checklist

Use this checklist to systematically diagnose problems:

- [ ] Python version >= 3.9 and < 3.14.4 installed
- [ ] All requirements installed (`pip install -r requirements.txt`)
- [ ] Virtual environment activated (if using)
- [ ] Running from project root directory
- [ ] Microphone connected and recognized by OS
- [ ] OS microphone permissions granted
- [ ] QtMultimedia can detect audio devices
- [ ] Audio input works in other applications
- [ ] Settings are saved in `.VocalTrack_settings.json`
- [ ] `recordings/` folder exists and is writable
- [ ] No conflicting Python packages installed
- [ ] Graphics drivers up to date
- [ ] Terminal shows no critical error messages

If all items are checked and issue persists, problem is likely configuration-specific or a bug—see "Getting Further Help" above.
