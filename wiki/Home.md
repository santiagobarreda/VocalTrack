
![VocalTrack Logo](https://github.com/santiagobarreda/VocalTrack/raw/main/VocalTrack/images/VocalTrackLogo_.png)

# VocalTrack Wiki

Welcome to the VocalTrack documentation. This wiki provides comprehensive guides for installation, configuration, usage, and troubleshooting of VocalTrack's real-time speech visualization toolkit.

## Documentation Pages

- [Installation and Launch](Installation-and-Launch) - Setup instructions and first-time launch
- [Basic Usage](Basic-Usage) - Workflow overview and common tasks
- [Mode Guides](Mode-Guides) - Detailed guides for each visualization mode
- [Settings Reference](Settings-Reference) - Complete parameter documentation
- [Outputs and File Formats](Outputs-and-File-Formats) - Export file specifications
- [Benchmarking](Benchmarking) - Accuracy and timing benchmarks
- [Troubleshooting](Troubleshooting) - Common issues and solutions

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Launch the GUI:**
   ```bash
   python vocaltrack.py
   ```

3. **Configure settings:**
   - Open **Recording Settings** and select your microphone
   - Open **Analysis Settings** and adjust f0 range for your voice
   - Configure mode-specific settings as needed

4. **Launch a visualization mode:**
   - **LiveVowel**: Real-time F1/F2 vowel space tracking
   - **LivePitch**: f0 pitch contour visualization
   - **LiveSpectrogram**: Scrolling wideband spectrogram
   - **LiveSpectrum**: Real-time FFT spectrum analyzer

## What VocalTrack Produces

**Audio + Data (Exported on Exit):**
- LiveVowel: original and/or downsampled WAV audio + CSV with timestamped F1/F2/F3 formants
- LivePitch: original and/or downsampled WAV audio + CSV with timestamped f0 pitch values

**Visualization Only:**
- LiveSpectrogram: Real-time spectrogram display
- LiveSpectrum: Real-time spectrum display

**Benchmarking Output:**
- Accuracy reports: CSV comparisons and markdown summaries
- Timing reports: Performance metrics for different analysis methods
- Audio used for benchmarking saved as WAV file
- All saved to `benchmarking/` folder

## Settings Persistence

User settings are automatically saved to:

```
.VocalTrack_settings.json
```

This file stores:
- Analysis parameters (f0 range, max formant, window size)
- Smoother configuration (1-Euro filter parameters)
- Display settings for all modes (ranges, scales, colors)
- Audio input device selection

Settings are loaded on startup and applied to both launcher dialogs and runtime configuration.

## System Requirements

- Python >=3.9 and <3.15
- Working (preferably head mounted) microphone/audio input
- OS audio permissions enabled
- ~100MB disk space for installation (mostly of dependencies)
- Real-time processing requires modern CPU (2GHz+ recommended)

## Key Features

✓ Four specialized visualization modes for different analysis needs  
✓ Adaptive 1-Euro smoothing for stable yet responsive tracking  
✓ Native and Parselmouth analysis backends  
✓ Configurable frequency scales (log/linear)  
✓ Built-in benchmarking tools  
✓ Automated CSV + WAV export  
✓ Persistent settings across sessions
