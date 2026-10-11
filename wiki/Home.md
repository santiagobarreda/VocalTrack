
![VocalTrack Logo](https://github.com/santiagobarreda/VocalTrack/raw/main/VocalTrack/images/VocalTrackLogo_.png)

# VocalTrack Wiki

VocalTrack is a Python application for real-time speech visualization. It has four display modes: LiveVowel (F1/F2 vowel space), LivePitch (f0 contour), LiveSpectrogram (scrolling spectrogram) and LiveSpectrum (power spectrum).

## Pages

| Page | Contents |
|------|----------|
| [Installation and Launch](Installation-and-Launch) | Requirements, installation, microphone permissions, starting the launcher |
| [Basic Usage](Basic-Usage) | The steps of a session, from launch to saved files |
| [Mode Guides](Mode-Guides) | What each mode shows, its keyboard and mouse controls, and how it records |
| [Settings Reference](Settings-Reference) | Every setting with its default and effect, the settings file, and the analysis methods |
| [Outputs and File Formats](Outputs-and-File-Formats) | File names, WAV and CSV formats, and the vowel template format |
| [Benchmarking and Performance](Benchmarking-and-Performance) | Comparing analysis methods against Parselmouth, and the performance monitor |
| [Troubleshooting](Troubleshooting) | Problems and fixes, and known limitations |
| [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting) | Checking the formant settings for a speaker with the LPC overlay in LiveSpectrum |

## Quick start

```bash
python -m venv vocaltrack-env                      # python3 on macOS/Linux
vocaltrack-env\Scripts\activate                    # macOS/Linux: source vocaltrack-env/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python vocaltrack.py
```

Then select a microphone in **Data Settings** and click a mode button. See [Installation and Launch](Installation-and-Launch) and [Basic Usage](Basic-Usage).

Videos showing installation and usage are in a [YouTube playlist](https://www.youtube.com/playlist?list=PLcX__4_5WSTg).
