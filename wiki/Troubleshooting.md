# Troubleshooting

Run VocalTrack from a terminal so that warnings and error messages are visible. For formant tracking problems, see also [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting).

## Installation

**`No module named 'PySide6'`, or another package is missing.** Activate the virtual environment, if one is used, and run `pip install -r requirements.txt` again. Check that `python --version` is 3.9 or newer.

**`No module named 'VocalTrack'`.** Run `python vocaltrack.py` from the project folder (the one that contains `vocaltrack.py`).

**Permission errors from `pip`.** Use a virtual environment (see [Installation](Installation-and-Launch#installation)), or install for the current user with `pip install --user -r requirements.txt`.

**`praat-parselmouth` fails to install.** A C++ compiler is missing: install the Visual C++ Build Tools (Windows), run `xcode-select --install` (macOS), or `sudo apt-get install build-essential` (Linux), then retry. VocalTrack runs without Parselmouth, which is needed only for the `parselmouth` methods and for benchmarking.

**Windows: `ImportError: DLL load failed`.** Install the Visual C++ Redistributable (https://aka.ms/vs/17/release/vc_redist.x64.exe), restart, and reinstall the package named in the error.

**Linux: no audio, or QtMultimedia errors.** Install the GStreamer packages listed under [Installation](Installation-and-Launch#installation).

**Linux: ALSA messages in the terminal** (e.g. `ALSA lib pcm.c ... Unknown PCM cards.pcm.rear`). These are usually harmless.

## Audio input

### No devices are listed in Data Settings

1. Check that the microphone is connected and that the operating system lists it as an input device.
2. Check the [microphone permissions](Installation-and-Launch#microphone-permissions).
3. Check what QtMultimedia can see:
   ```bash
   python -c "from PySide6.QtCore import QCoreApplication; from PySide6.QtMultimedia import QMediaDevices; app = QCoreApplication([]); [print(d.description()) for d in QMediaDevices.audioInputs()]"
   ```
4. Reopen Data Settings. The device list is refreshed each time the dialog opens.

### The microphone is selected but nothing is plotted

- LiveVowel and LivePitch open paused: press `Space` to start recording.
- `min_rms_db` may be too high for the signal: press `-` several times, or lower **Min RMS** in Analysis Settings (e.g. from -60 to -70).
- The voice may be outside the `min_f0` to `max_f0` range in Analysis Settings.
- Check the input level in the operating system's sound settings, and that the microphone works in another application.
- An on-screen message of the form "'<your microphone>' unavailable - using '<another device>'" means the selected microphone is not connected and another device is in use.

### The microphone disconnects during a session

- **A disconnect ends the recording.** The recording stops at that moment and its files are saved; they end at the dropout, with correct sample rate and timestamps. A banner stays on screen saying when the recording stopped, and the display pauses. Press `Space` to start a new recording, which goes into new files. Audio from a different or reconnected device is never joined onto an existing recording.
- Between recordings, VocalTrack falls back to any available device if the selected one is missing, checks every 2 seconds or so for the selected device to come back, and switches back to it when it does, with an on-screen notification. It never switches devices while a recording is running.
- A device that stops delivering audio is treated as disconnected even if the system still lists it and reports no error (after about 1 second without audio, or 2 seconds for a device that has just been opened). If that happens before anything has been recorded, the recording starts on the next working device, and a notification says which device is in use.
- If no input device is working, a "No working audio input device" notification is shown and VocalTrack keeps trying every few seconds, so recording can resume once a microphone is plugged in.
- The selected device is saved by name, so it is used again at the next launch. If the operating system lists it under a new name after reconnection, select it again in Data Settings.

### Crackling or distorted audio

- Listen to the `_original.wav` file. If the crackles are in it, the problem is upstream of VocalTrack: check the device's sample rate and buffer settings in the operating system's sound settings (or the interface's control panel), and test the microphone in another recording application.
- Lower the input level if the signal is clipping.
- VocalTrack opens the microphone at its own preferred rate (typically 44100 or 48000 Hz) and resamples to the analysis rate in software, so the device does not need to support the analysis rate.

## Display

**Formant points are off screen or bunched together (LiveVowel).** Widen `f1_range` and `f2_range` in [Formant Plot Settings](Settings-Reference#formant-plot-settings), or switch between log and linear scales with `Ctrl/Cmd+L`.

**The pitch contour jumps (LivePitch).** For octave jumps, narrow `min_f0` and `max_f0` around the speaker's range, or try another pitch method (`yin` or `parselmouth`). For jitter, see [smoother tuning](Settings-Reference#tuning).

**The spectrogram is too dark.** Raise the gain (`Ctrl/Cmd++`) or widen the dynamic range (`-`).

**The spectrogram is washed out.** Narrow the dynamic range (`+`) or lower the gain (`Ctrl/Cmd+-`).

**The spectrum line is jittery (LiveSpectrum).** Lower `smoothing` in Spectrum Settings (e.g. from 0.7 to 0.5; 1.0 is no smoothing), or lengthen `window_ms`.

**The window is blank or frozen.** Check the terminal for error messages. Reinstall pygame-ce: `pip uninstall pygame pygame-ce`, then `pip install -r requirements.txt`.

## Files

### No files after recording

- LiveSpectrogram and LiveSpectrum save WAV audio only. Formant and pitch CSVs come from LiveVowel and LivePitch.
- LiveVowel and LivePitch open paused. Nothing is recorded until `Space` is pressed (the `[REC]` badge is shown while recording).
- Check which file types are ticked in **Data Settings** (CSV, original audio, downsampled audio).
- If a subject/data folder is selected in Data Settings, files go to that folder's `recordings/` subfolder, not the project's.
- Check that the `recordings/` folder can be written to.

### The CSV has no rows, or has gaps

Only voiced frames accepted by the smoother, with f0 in range, are written (see [Which frames are in the CSV](Outputs-and-File-Formats#which-frames-are-in-the-csv)). Gaps in `time_ms` at silences and voiceless consonants are normal. If there are no rows at all:

- Check that the voice is within the `min_f0` to `max_f0` range, and widen the range if not.
- Lower `min_rms_db` (e.g. to -70), or speak louder or closer to the microphone.
- Try another `formant_method`, and check the terminal for error messages.

### The WAV is too quiet or clipped

Files are normalized on export, so the level of the file does not reflect the input level. A noisy or clipped file means the input level was too low or too high: change it in the operating system's sound settings.

## Performance

Turn on the performance monitor (`Ctrl/Cmd+P`) to see which part is falling behind: the display, the audio capture, or the analysis (see [Performance monitor](Benchmarking-and-Performance#performance-monitor)).

### The display lags, or tracks and CSV rows have gaps

When the analysis cannot keep up with the audio, chunks waiting to be analyzed are dropped. The WAV recording is not affected.

- Lower `fps` in the mode's plot settings (e.g. from 60 to 30). One analysis is made per display frame, so this halves the analysis load as well as the drawing.
- In LiveSpectrogram, increase `time_step_ms` instead (e.g. from 6 to 10 ms).
- Use the built-in methods (`lpc`, `autocorrelation`) instead of `parselmouth`.
- In LiveSpectrogram and LiveSpectrum, lower `max_freq` or `padding_length_ms`.
- Close other applications.

### High CPU use when nobody is speaking

While a mode is recording, audio is captured and the display is redrawn continuously, whether or not anyone is speaking. (In LiveVowel and LivePitch, pitch and formant analysis is skipped for frames below the minimum RMS threshold.) Press `Space` to pause: in LiveVowel and LivePitch this stops audio capture and analysis until `Space` is pressed again.

### Memory use in long sessions

VocalTrack keeps each recording in memory until it is saved. At a typical microphone rate of 48 kHz this is about 6 MB per minute, or roughly 350 MB per hour of continuous recording. LiveSpectrogram and LiveSpectrum record from the moment the window opens, so a window left running keeps growing until it is paused or closed.

- **Pause now and then.** `Space` saves the recording to disk and frees its memory; `Space` again starts a new recording in a new file.
- **Clear points that are no longer needed** (LiveVowel and LivePitch). Plotted points stay in memory until they are cleared; `Delete` clears the finished tracks.
- **Turn off audio that is not needed.** If only the display (or only the CSV) is wanted, untick the audio options in **Data Settings**. No audio is then kept in memory.

## Analysis quality

**Formants are at the wrong frequencies, or jump.** The most common cause is a `max_formant` that does not suit the speaker. Follow [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting).

**Tracks are noisy, slow, or break up.** See [smoother tuning](Settings-Reference#tuning). Background noise can be excluded by raising `min_rms_db` (e.g. from -50 to -40).

**Octave errors in pitch.** Narrow `min_f0` and `max_f0` to the speaker's range (see [starting values by speaker](Settings-Reference#starting-values-by-speaker)), or try another pitch method.

**Creaky voice is not tracked.** Lower `min_f0` (e.g. to 40 Hz). If a warning says the analysis window is too short for that f0, lengthen `window_ms`: with `parselmouth`, 40 Hz needs a 75 ms window.

**A method behaves unexpectedly.** Compare it against Parselmouth on a recording with the [Benchmarking](Benchmarking-and-Performance#benchmarking) tool.

## Settings

**Settings are not kept.** Dialogs save only when closed with **OK**. If a subject/data folder is selected, the settings file is in that folder. Check that the file can be written to.

**The settings file is ignored.** A warning "Could not load settings from ... .VocalTrack_settings.json" at startup means the file could not be read. VocalTrack carries on with the defaults and replaces the file the next time settings are saved. To start again, delete the file. See [Settings file](Settings-Reference#settings-file).

## Known limitations

1. **Mono only.** With a multi-channel input device, only the first channel is used.
2. **Fixed speaker ID.** File names always begin with `speaker` (see [File names](Outputs-and-File-Formats#file-names)). Use a separate subject/data folder for each speaker, or rename the files.
3. **No CSV from LiveSpectrogram or LiveSpectrum.** These modes save WAV audio only.
4. **CSV files are written when recording stops**, not continuously.
5. **F1–F3 only in the CSV.** Higher formants are estimated but not exported.
6. **No pitch contour in LiveVowel.** f0 is saved in the CSV but not drawn.
7. **One mode at a time.**

## Reporting a problem

Debug messages are printed when `logging_level` in `PERFORMANCE_CONFIG` (`config.py`) is set to `10`.

Issues can be searched and opened at https://github.com/santiagobarreda/VocalTrack/issues. Include the operating system and version, the Python version, the package versions (`pip list`), the full error message, and the steps that produce it.
