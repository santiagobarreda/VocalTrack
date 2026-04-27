![VocalTrack Logo](VocalTrack/images/VocalTrackLogo_.png)

# VocalTrack

Real-time speech visualization toolkit with four specialized modes for acoustic analysis. Features a user-friendly GUI launcher, configurable analysis parameters, and automated data export for research,  clinical, and pedagogical applications.

For a detailed description of the **VocalTrack** architecture and signal processing pipeline, please refer to the [methods article](https://github.com/santiagobarreda/VocalTrack/releases/download/v1.0.0-beta/Barreda_2026_VocalTrack_underreview.pdf), currently under review, or check out the comprehensive documentation available in the [wiki](https://github.com/santiagobarreda/VocalTrack/wiki).

## Features

- **Four Visualization Modes**:
  - **LiveVowel**: Real-time vowel space tracking (F1/F2 formant display)
  - **LivePitch**: Fundamental frequency (f0) contour visualization
  - **LiveSpectrogram**: Scrolling wideband spectrogram
  - **LiveSpectrum**: Real-time FFT spectrum analyzer
- **GUI Launcher**: PySide6 interface with comprehensive settings dialogs
- **Advanced Smoothing**: 1-Euro filter for responsive yet stable tracking
- **Flexible Analysis**: Native or Parselmouth backend for formant/pitch extraction
- **Automated Export**: WAV audio + CSV data logs for vowel and pitch modes
- **Benchmarking Tools**: Built-in accuracy and timing benchmarks

## How It Works

1. **Audio Capture**: `AudioProcessor` continuously reads microphone input in small chunks via PyAudio
2. **Windowing**: Chunks are combined to form analysis windows (configurable duration)
3. **Acoustic Analysis**: `Sound` objects compute formants, pitch, or spectra depending on mode
4. **Smoothing**: Adaptive `Smoother` maintains a memory applies 1-Euro filtering for stable trajectories
5. **Visualization**: Real-time Pygame rendering with configurable scales and ranges
6. **Export**: Automatic WAV + CSV export on exit (LiveVowel and LivePitch modes)

## Installation

### Requirements

- Python 3.7 or higher
- Microphone/audio input device (head-mounted microphones are require for proper function)
- OS audio permissions enabled

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/santiagobarreda/VocalTrack.git
cd VocalTrack
```
Or download from GitHub and unzip into local directory. 

2. Install dependencies:
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

3. Launch the GUI:

```bash
python vocaltrack.py
```

### Settings Dialogs

Configure parameters before launching a mode:

- **Analysis Settings**: Window duration, formant/pitch bounds, analysis method
- **Smoother Settings**: 1-Euro filter parameters, memory, stability thresholds
- **Recording Settings**: Select audio input device, and whether to save audio
- **Formant Plot Settings**: F1/F2 ranges, display mode, frequency scale
- **Pitch Plot Settings**: f0 display range, plot mode (fixed/continuous)
- **Spectrogram Settings**: Frequency range, colormap, dynamic range, padding
- **Spectrum Settings**: FFT parameters, display range, smoothing

### Launch a Mode

Click one of the four launch buttons:

1. **LiveVowel** (green): Vowel space tracking with F1/F2 display
2. **LivePitch** (blue): Pitch contour visualization
3. **LiveSpectrogram** (purple): Scrolling spectrogram
4. **LiveSpectrum** (orange): Real-time spectrum analyzer

### Keyboard Controls

**Common (all modes where implemented):**
- `ESC`: Quit and save (if applicable)
- `G`: Toggle grid overlay
- `H`: Toggle help overlay
- `+`/`-`: Adjust threshold/gain/dynamic range

**LiveVowel:**
- `Ctrl+V`: Toggle recording state
- `Ctrl+T`: Toggle vowel template display
- `L`: Toggle log/linear frequency scale
- `Backspace`: Undo last track (in track mode)
- `Delete`: Clear all tracks (in track mode)

**LivePitch:**
- `Space`: Push-to-talk recording (hold to record)
- `Backspace`: Remove last track
- `Delete`: Clear all tracks

**LiveSpectrogram:**
- `Ctrl +`/`Ctrl -`: Adjust gain

**LiveSpectrum:**
- `+`/`-`: Adjust gain offset

## Data Export

Files are automatically saved to `recordings/` on exit:

**LiveVowel:**
- `speaker_YYYY-MM-DD_HHMMSS.wav`: Audio recording
- `speaker_YYYY-MM-DD_HHMMSS_formants.csv`: Timestamped F1/F2/F3 data (voiced frames only)

**LivePitch:**
- `speaker_YYYY-MM-DD_HHMMSS_pitch.wav`: Audio recording
- `speaker_YYYY-MM-DD_HHMMSS_pitch.csv`: Timestamped f0 data (voiced frames only)

**Note:** LiveSpectrogram and LiveSpectrum are visualization-only modes and do not export CSV files by default.

## Architecture

**Core Components:**
- `AudioProcessor`: Background thread for real-time audio capture
- `Sound`: Acoustic analysis engine (formants, pitch, spectrum)
- `Smoother`: Adaptive 1-Euro filter for trajectory smoothing
- `BaseAudioVisualizer`: Shared pygame rendering and event handling
- `LiveVowel`, `LivePitch`, `LiveSpectrogram`, `LiveSpectrum`: Mode-specific visualizers

**Configuration:**
- `config.py`: Default parameters for all modes
- `.VocalTrack_settings.json`: Persistent user settings (auto-saved)

## Benchmarking

Run accuracy and timing benchmarks from the launcher:

1. Click **Benchmarking** button
2. Select benchmark comparison (Parselmouth vs. 'native' or 'custom')
3. Follow on-screen recording instructions
4. Results saved to `benchmarking/` folder

## Troubleshooting

**No audio input:**
- Open Recording Settings and verify input device
- Check OS microphone permissions
- Test: `python -c "import pyaudio; print(pyaudio.PyAudio().get_device_count())"`

**Poor tracking quality:**
- Adjust min/max f0 for your voice in Analysis Settings
- Increase `min_rms_db` (less negative) to ignore background noise
- Tune smoother parameters for your use case
- Use a quieter environment and speak closer to microphone
- Use a good microphone! Any USB headmounted microphone is probably good enough. Miscrophones on laptop screens or on webcams may result is very poor performance.

**GUI launcher issues:**
- Verify PySide6: `pip install PySide6>=6.5.0`
- Check `.VocalTrack_settings.json` for corruption

**Formant/pitch extraction errors:**
- Switch between `native` and `parselmouth` methods in Analysis Settings
- Install Parselmouth if needed: `pip install praat-parselmouth`

## Citation

TBD

## License

See [LICENSE](LICENSE) file for details.
