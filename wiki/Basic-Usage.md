# Basic Usage

## Overview

VocalTrack is a real-time speech visualization toolkit with four specialized modes for acoustic analysis. The application runs in two stages:

1. **Configure** in the PySide6 launcher (`python vocaltrack.py`)
2. **Run** a visualization mode in a Pygame window with real-time feedback

## Complete Workflow

### 1. Launch the Application

```bash
python vocaltrack.py
```

The launcher window appears with settings dialogs on the top and mode launch buttons on the bottom.

### 2. Configure Settings (First-Time Setup)

**Recommended order for first-time users:**

1. **Recording Settings**: Select your microphone from the available input devices
2. **Analysis Settings**: Set f0 range (min/max) appropriate for your voice
3. **Mode-Specific Settings**: Configure the visualization you plan to use

**You can skip this step if you've used VocalTrack before** - settings are automatically saved to `.VocalTrack_settings.json` and restored on launch.

### 3. Launch a Visualization Mode

Click one of four mode buttons:

- **LiveVowel** (green): F1/F2 vowel space tracking
- **LivePitch** (blue): f0 pitch contour visualization  
- **LiveSpectrogram** (purple): Scrolling wideband spectrogram
- **LiveSpectrum** (orange): Real-time FFT spectrum analyzer

A Pygame window opens showing the visualization.

### 4. Record and Visualize

**LiveVowel:**
- Press `Ctrl+R` to toggle recording state, or `Ctrl+H` to hide help and start recording
- Speak naturally to see your vowel formants plotted in F1/F2 space
- Visual feedback shows current formant position and trajectory tracks

**LivePitch:**
- Hold `Space` to record pitch contour (push-to-talk)
- Release `Space` to stop recording segment
- Visual feedback shows f0 over time with configurable display window

**LiveSpectrogram:**
- Automatically displays audio as soon as the window opens
- No recording control needed - visualization is always active
- Adjust dynamic range and gain for optimal display

**LiveSpectrum:**
- Automatically displays spectrum as soon as the window opens
- Shows averaged power spectrum across frequency bins
- Adjust gain offset for optimal display

### 5. Adjust Parameters During Recording

All modes support real-time parameter adjustment:

- **Minimum RMS threshold** (`+`/`-`): Filter out background noise
- **Grid visibility** (`G`): Toggle reference grid overlay
- **Help overlay** (`H` or `Ctrl+H`): Show keyboard shortcuts

Mode-specific adjustments:
- **LiveSpectrogram**: Gain (`Ctrl++`/`Ctrl+-`), Dynamic range (`+`/`-`)
- **LiveSpectrum**: Gain offset (`+`/`-`)

### 6. Save and Exit

**LiveVowel and LivePitch:**
- Press `Esc` to quit and automatically export WAV + CSV files (if enabled in Recording Settings)
- Files are saved to `recordings/` directory with timestamp
- Format: `speaker_YYYY-MM-DD_HHMMSS.wav` and `speaker_YYYY-MM-DD_HHMMSS_formants.csv` (or `_pitch.csv`)

**LiveSpectrogram and LiveSpectrum:**
- Press `Esc` to quit (these are visualization-only modes)
- No automatic export by default

### 7. Review Exported Data

Navigate to the `recordings/` folder to find:

- **WAV files**: Normalized mono audio (16-bit, sample rate matches analysis settings)
- **CSV files**: Timestamped formant or pitch data (voiced frames only, filtered by f0 range)

## Choosing a Visualization Mode

### LiveVowel - Formant Space Tracking

**Best for:**
- Vowel quality analysis and training
- Dialect/accent studies
- Speech therapy and pronunciation training
- Real-time formant feedback

**Features:**
- F1/F2 formant space display with configurable ranges
- Three display modes: `single` (latest point), `track` (current trajectory), `all` (all tracks)
- Optional vowel template overlay (Ctrl+T)
- Continuous recording with trajectory segmentation
- Exports: WAV + CSV with f0, F1, F2, F3, voicing, track_number

**Key controls:**
- `Ctrl+V`: Toggle IPA vowel display overlay
- `Ctrl+T`: Toggle display of pre-loaded dialect template
- `Backspace`: Undo last finished track (in track mode)
- `Delete`: Clear all finished tracks (in track mode)

### LivePitch - Pitch Contour Tracking

**Best for:**
- Pitch/intonation training
- Tone language learning
- Singing exercises
- Prosody analysis

**Features:**
- f0 contour display over time (configurable window: fixed or continuous scroll)
- Push-to-talk recording (Space key)
- Configurable f0 display range (independent of analysis range)
- Log or linear frequency scale
- Exports: WAV + CSV with f0, voicing, optional track numbers

**Key controls:**
- `Space` (hold): Start recording pitch segment
- `Space` (release): Stop recording and save segment
- `Backspace`: Remove most recent finished track
- `Delete`: Clear all finished tracks

### LiveSpectrogram - Wideband Scrolling Display

**Best for:**
- Formant transition visualization
- Spectral detail examination
- Pedagogy

**Features:**
- Scrolling spectrogram with configurable frequency range 
- Customizable colormap (plasma, viridis, magma, etc.)
- Adjustable dynamic range for detail vs. contrast
- Adjustable gain for overall brightness
- Pre-emphasis filtering for high-frequency visibility
- No export by default (visualization-focused)

**Key controls:**
- `+`/`-`: Decrease/increase dynamic range
- `Ctrl++`/`Ctrl+-`: Increase/decrease gain
- `Ctrl+H`: Toggle help overlay

### LiveSpectrum - Real-Time FFT Display

**Best for:**
- Spectral envelope analysis
- Resonance visualization
- Harmonic structure analysis

**Features:**
- Static (non-scrolling) spectrum line plot
- Averaged power spectrum across multiple audio frames
- Configurable smoothing parameter (0-1, default 0.7)
- Adjustable frequency range and dynamic range
- No export by default (visualization-focused)

**Key controls:**
- `+`/`-`: Adjust gain offset (dB)
- `G`: Toggle grid overlay
- `H`: Toggle help overlay

## Common Keyboard Controls

These controls work across all four modes:

| Key | Action |
|-----|--------|
| `Esc` | Quit mode and save (if applicable) |
| `G` | Toggle grid overlay |
| `H` or `Ctrl+H` | Toggle help overlay with keyboard shortcuts |
| `+` or `=` | Increase threshold/gain/dynamic range (mode-dependent) |
| `-` or `_` | Decrease threshold/gain/dynamic range (mode-dependent) |

## Mode-Specific Keyboard Controls

### LiveVowel Only

| Key | Action |
|-----|--------|
| `Ctrl+V` | Toggle IPA chooser menu |
| `Ctrl+R` | Toggle recording state |
| `Ctrl+H` | Toggle help overlay (stops recording when shown, starts when hidden) |
| `Ctrl+T` | Toggle vowel template overlay (IPA symbols) |
| `Backspace` | Undo last finished track |
| `Delete` | Clear all finished tracks |
| `+`/`-` | Adjust minimum RMS threshold |

### LivePitch Only

| Key | Action |
|-----|--------|
| `Space` (hold) | Start recording pitch segment (push-to-talk) |
| `Space` (release) | Stop recording segment and export |
| `Backspace` | Remove most recent finished track |
| `Delete` | Clear all finished tracks |
| `+`/`-` | Adjust minimum RMS threshold |

### LiveSpectrogram Only

| Key | Action |
|-----|--------|
| `+`/`-` | Decrease/increase dynamic range |
| `Ctrl++`/`Ctrl+-` | Increase/decrease gain (brightness) |
| `Ctrl+H` | Toggle help overlay |

### LiveSpectrum Only

| Key | Action |
|-----|--------|
| `+`/`-` | Adjust gain offset (dB) |
| `G` | Toggle grid overlay |
| `H` | Toggle help overlay |

## Recording and Export Behavior

### LiveVowel

- **Recording behavior**: Continuous recording while in recording state
- **Export trigger**: Automatic on quit (`Esc` or window close)
- **Output files**: WAV + CSV with formants (f0, F1, F2, F3, voicing, track_number)
- **Filter behavior**: Only voiced frames within configured f0 range are exported to CSV

### LivePitch

- **Recording trigger**: Hold `Space` key
- **Recording behavior**: Records while Space is held (push-to-talk)
- **Export trigger**: Automatic when Space is released (per segment)
- **Output files**: WAV + CSV with pitch data (track, time_ms, f0, voicing)
- **Filter behavior**: Only voiced frames within configured f0 range are exported to CSV

### LiveSpectrogram and LiveSpectrum

- **Recording behavior**: Visualization only, no automatic recording
- **Export trigger**: None by default (display-focused modes)
- **Output files**: None by default
- **Use case**: Real-time visual feedback and analysis

## Practical Setup Tips

### Audio Quality and Analysis

1. **Set appropriate f0 range**: 
   - Male: `min_f0=60`, `max_f0=250`
   - Female: `min_f0=120`, `max_f0=400`
   - Child: `min_f0=180`, `max_f0=500`

2. **Adjust max_formant for speaker**:
   - Adult male: 5000 Hz (Praat-suggested default)
   - Adult female: 5500 Hz (Praat-suggested default)
   - Child: 6500-8000 Hz (It really depends on their age!)
   - *Note: Sample rate is automatically set to 2 × max_formant*

3. **Control background noise**:
   - Increase `min_rms_db` (less negative, e.g., -40 dB instead of -60 dB)
   - Use in-window `+`/`-` keys to adjust threshold in real-time
   - Record in a quiet environment

4. **Optimize tracking stability**:
   - If formants/pitch are too jittery: Increase `memory_n` (smoother memory)
   - If tracking is too sluggish OR too jittery: Adjust 1euro parameters. 
   - If formants jump around: Increase `stability_threshold` (stricter gating)
   - If formant tracks end suddenly: Decrease `stability_threshold` (stricter gating)

### Display Settings

1. **LiveVowel formant ranges**:
   - Default F1: 200-1200 Hz (good for most speakers)
   - Default F2: 500-2700 Hz (good for most speakers)
   - Adjust if vowels appear off-screen or too clustered

2. **LivePitch display window**:
   - `fixed` mode: Fixed time window (default 5 seconds)
   - `continuous` mode: Continuous scrolling as recording progresses
   - Adjust `pitch_display_seconds` to show more/less time context

3. **LiveSpectrogram settings**:
   - Reduce `dynamic_range` (e.g., 30 dB) for more detail in quiet sections
   - Increase `dynamic_range` (e.g., 50 dB) for more contrast in loud sections
   - Use `+`/`-` to adjust live during recording

4. **Frequency scale preference**:
   - Logarithmic (`log`): Better for perceptual uniformity, emphasizes low frequencies
   - Linear (`linear`): Better for measuring actual Hz distances

### Performance Optimization

1. **If display is laggy**:
   - Reduce FPS (e.g., from 60 to 40) in mode-specific settings
   - Close other applications to free up CPU
   - Reduce `max_freq` in spectral modes (less FFT computation)

2. **If analysis is slow**:
   - Use `native` formant/pitch methods instead of `parselmouth`
   - Reduce `padding_length_ms` in spectral modes
   - Reduce `number_of_chunks` (smaller analysis windows)

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| No microphone detected | Check Recording Settings, verify OS permissions |
| Noisy formants/pitch | Increase `min_rms_db`, adjust smoother settings |
| No CSV files generated | Check that f0 is within configured range, verify voicing detection |
| Display too compressed | Adjust mode-specific ranges (F1/F2, f0, max_freq) |
| Performance issues | Reduce FPS, close other apps, reduce max_freq |
| Settings not saved | Check write permissions, verify `.VocalTrack_settings.json` |

For detailed troubleshooting, see [Troubleshooting.md](Troubleshooting.md).

## Advanced Usage

### Multiple Recording Sessions

Each session generates unique timestamped files. To organize recordings:

```bash
# Recordings are automatically saved to recordings/ folder
ls recordings/
# speaker_2026-03-04_102534_formants.csv
# speaker_2026-03-04_102534.wav
# speaker_2026-03-04_102539_pitch.csv
# speaker_2026-03-04_102539_pitch.wav
```

### Custom Speaker IDs

Currently, all sessions use the default speaker ID "speaker". To customize, modify the `session_name` generation in the source code or rename files post-export.

### Integrating with Analysis Pipelines

CSV files are plain text and can be imported directly into:
- R/Python for statistical analysis
- Praat for acoustic phonetics
- Excel/LibreOffice for visualization
- Custom scripts for batch processing

### Benchmarking Analysis Quality

VocalTrack includes built-in benchmarking tools:

1. Click **Benchmarking** button in launcher
2. Select accuracy or timing benchmark
3. Follow recording instructions
4. Review results in `benchmarking/` folder

See [Benchmarking.md](../wiki/Benchmarking.md) for details.
