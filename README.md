![VocalTrack Logo](VocalTrack/images/VocalTrackLogo_.png)

# VocalTrack

VocalTrack is a Python application for real-time speech visualization. It has four display modes, a launcher for configuring the analysis, and automatic export of audio and measurements.

The architecture and signal processing pipeline are described in the [methods article](https://github.com/santiagobarreda/VocalTrack/releases/download/v1.0.0-beta/Barreda_2026_VocalTrack_underreview.pdf), currently under review. The documentation is in the [wiki](https://github.com/santiagobarreda/VocalTrack/wiki), and videos showing installation and usage are in a [YouTube playlist](https://www.youtube.com/playlist?list=PLcX__4_5WSTg).

## Features

- **Four display modes**:
  - **LiveVowel**: F1/F2 vowel space
  - **LivePitch**: fundamental frequency (f0) contour
  - **LiveSpectrogram**: scrolling spectrogram
  - **LiveSpectrum**: power spectrum, with an optional LPC envelope and formant markers
- **Launcher**: PySide6 interface with settings dialogs; settings are saved between sessions
- **Analysis methods**: built-in (LPC or WLP for formants, autocorrelation or YIN for pitch), Parselmouth (Praat), or your own
- **Smoothing**: a stability gate followed by a 1-Euro filter
- **Export**: WAV audio in all modes, plus CSV files of measurements in LiveVowel and LivePitch
- **Benchmarking**: compares any method against Parselmouth (Praat) for agreement and timing

## How it works

1. **Audio capture**: `AudioProcessor` reads microphone input through QtMultimedia (`QAudioSource`) in chunks, one chunk per display frame
2. **Windowing**: each new chunk triggers one analysis of the most recent window of audio (of configurable length), so consecutive windows overlap
3. **Analysis**: `Sound` objects compute formants, pitch, or spectra, depending on the mode
4. **Smoothing**: the `Smoother` accepts only stable, voiced frames and applies a 1-Euro filter
5. **Display**: the mode (`LiveVowel`, `LivePitch`, `LiveSpectrogram` or `LiveSpectrum`) draws the result with Pygame
6. **Export**: files are written when recording is paused and on exit

## Requirements

- Python 3.9 or newer (developed with Python 3.14)
- A microphone. A head-mounted USB microphone is recommended; microphones built into laptop screens or webcams can give very poor results
- Microphone permission granted by the operating system

## Quick start

1. Clone the repository (or download it from GitHub and unzip it):

```bash
git clone https://github.com/santiagobarreda/VocalTrack.git
cd VocalTrack
```

2. Install the dependencies. A virtual environment is recommended:

```bash
# Windows:     python -m venv vocaltrack-env && vocaltrack-env\Scripts\activate
# macOS/Linux: python3 -m venv vocaltrack-env && source vocaltrack-env/bin/activate

# python -m pip is required on Windows for this command, to avoid file-locking errors
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Without a virtual environment on macOS/Linux, use `pip3` instead of `pip`.

3. Start the launcher:

```bash
python vocaltrack.py
```

4. Select a microphone in **Data Settings**, then click a mode button. `Space` starts and pauses recording, and `Ctrl/Cmd+?` shows the keys for the mode. Files are saved to `recordings/`.

## Documentation

| Page | Contents |
|------|----------|
| [Installation and Launch](https://github.com/santiagobarreda/VocalTrack/wiki/Installation-and-Launch) | Requirements, installation, microphone permissions, starting the launcher |
| [Basic Usage](https://github.com/santiagobarreda/VocalTrack/wiki/Basic-Usage) | The steps of a session, from launch to saved files |
| [Mode Guides](https://github.com/santiagobarreda/VocalTrack/wiki/Mode-Guides) | What each mode shows, its keyboard and mouse controls, and how it records |
| [Settings Reference](https://github.com/santiagobarreda/VocalTrack/wiki/Settings-Reference) | Every setting with its default and effect, the settings file, and the analysis methods |
| [Outputs and File Formats](https://github.com/santiagobarreda/VocalTrack/wiki/Outputs-and-File-Formats) | File names, WAV and CSV formats, and the vowel template format |
| [Benchmarking and Performance](https://github.com/santiagobarreda/VocalTrack/wiki/Benchmarking-and-Performance) | Comparing analysis methods against Parselmouth, and the performance monitor |
| [Troubleshooting](https://github.com/santiagobarreda/VocalTrack/wiki/Troubleshooting) | Problems and fixes, and known limitations |
| [Formant Tracking Troubleshooting & Calibration](https://github.com/santiagobarreda/VocalTrack/wiki/Formant-Tracking-Troubleshooting) | Checking the formant settings for a speaker with the LPC overlay in LiveSpectrum |

## Citation

TBD

## License

See [LICENSE](LICENSE) file for details.
