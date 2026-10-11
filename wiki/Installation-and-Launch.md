# Installation and Launch

## Requirements

- Python 3.9 or newer (developed with Python 3.14)
- Windows, macOS or Linux
- A microphone. A head-mounted USB microphone is recommended; microphones built into laptop screens or webcams can give very poor results
- A display of at least 1024×768
- About 100 MB of disk space, mostly for the dependencies

No special hardware is needed: an ordinary laptop or desktop computer is enough for real-time use.

## Installation

Video walkthroughs: [Windows](https://www.youtube.com/watch?v=q6jthenlhmk) · [macOS](https://www.youtube.com/watch?v=eYVnYBIRWhQ) · [Linux](https://www.youtube.com/watch?v=NdjsXgo6ZyE)

### 1. Get the code

```bash
git clone https://github.com/santiagobarreda/VocalTrack.git
cd VocalTrack
```

Or download the ZIP from the repository page (**Code** → **Download ZIP**) and extract it.

### 2. Install the dependencies

A virtual environment is recommended, so that VocalTrack's packages do not conflict with others on the system.

| Step | Windows | macOS / Linux |
|------|---------|---------------|
| Create | `python -m venv vocaltrack-env` | `python3 -m venv vocaltrack-env` |
| Activate | `vocaltrack-env\Scripts\activate.bat` (Command Prompt) or `.\vocaltrack-env\Scripts\Activate.ps1` (PowerShell) | `source vocaltrack-env/bin/activate` |

With the environment active:

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

- On Windows the first command must be run as `python -m pip`, not bare `pip`, to avoid file-locking errors during the upgrade.
- The environment has to be activated each time before VocalTrack is run. `deactivate` leaves it.
- To install without a virtual environment, run the same two commands. On macOS/Linux use `python3 -m pip` and `pip3`, and add `--user` if there are permission errors.

Packages installed:

| Package | Used for |
|---------|----------|
| PySide6 (≥6.5.0) | The launcher, and audio input through QtMultimedia |
| praat-parselmouth (≥0.4.0) | The `parselmouth` analysis methods and benchmarking |
| pygame-ce (≥2.5.0) | The display windows (the community edition of pygame, imported as `pygame`) |
| numpy (≥1.20.0) | Numerical operations |

`pygame` and `pygame-ce` cannot be installed in the same environment. If `pygame` is already installed, run `pip uninstall pygame` and then `pip install --force-reinstall pygame-ce`.

On Linux, QtMultimedia also needs GStreamer:

```bash
sudo apt-get install libqt6multimedia6 libqt6multimediawidgets6 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

### 3. Check the installation

```bash
python -c "import parselmouth, pygame, numpy, PySide6; print('All dependencies installed successfully!')"
```

## Microphone permissions

- **Windows**: Settings → Privacy & Security → Microphone. Enable "Allow apps to access your microphone" and "Allow desktop apps to access your microphone".
- **macOS**: System Settings → Privacy & Security → Microphone (on older macOS: System Preferences → Security & Privacy → Privacy tab → Microphone). Enable Terminal or your Python executable.
- **Linux**: normally none required.

## Starting VocalTrack

From the project folder, with the virtual environment active if one is used:

```bash
python vocaltrack.py        # python3 on macOS/Linux
```

The launcher opens. It has:

- **Settings buttons**: Analysis Settings, Smoother Settings, Data Settings, and a plot settings dialog for each mode (Formant Plot, Pitch Plot, Spectrogram, Spectrum). See [Settings Reference](Settings-Reference).
- **Benchmarking**. See [Benchmarking and Performance](Benchmarking-and-Performance).
- **Four mode buttons**: LiveVowel, LivePitch, LiveSpectrogram, LiveSpectrum. See [Mode Guides](Mode-Guides).

The launcher is hidden while a mode is running and reappears when the mode is closed. Closing the launcher quits VocalTrack. Settings are saved automatically (see [Settings file](Settings-Reference#settings-file)).

The steps of a first session are in [Basic Usage](Basic-Usage).

## Starting a mode from Python

A mode can be started without the launcher, from the project folder:

```python
from VocalTrack.LiveVowel import LiveVowel
app = LiveVowel()
```

The other modes are started the same way (`VocalTrack.LivePitch.LivePitch`, `VocalTrack.LiveSpectrogram.LiveSpectrogram`, `VocalTrack.LiveSpectrum.LiveSpectrum`). A mode started this way uses the defaults in `config.py`: settings saved by the launcher in `.VocalTrack_settings.json` are not applied. Settings can be passed in code:

```python
from VocalTrack import config
from VocalTrack.LivePitch import LivePitch

custom_config = config.LIVEPITCH_CONFIG.copy()
custom_config['min_f0'] = 100
custom_config['max_f0'] = 400

app = LivePitch(pitch_config=custom_config)
```

The launcher itself takes no command-line arguments.

## Updating

```bash
git pull origin main
pip install --upgrade -r requirements.txt
```

## Problems

See [Troubleshooting](Troubleshooting#installation).
