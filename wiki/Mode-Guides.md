# Mode Guides

What each of the four modes shows, how it is controlled, and how it records. Settings are described in the [Settings Reference](Settings-Reference), and the files each mode writes in [Outputs and File Formats](Outputs-and-File-Formats).

## Controls common to all modes

| Key | Action |
|-----|--------|
| `Space` | Start / pause recording. While paused, the display is frozen |
| `Shift` + left click | Read values off the frozen display (see [below](#inspecting-a-frozen-display)) |
| `Ctrl/Cmd+?` | Show / hide the help overlay, which lists the mode's keys |
| `Ctrl/Cmd+G` | Show / hide the grid |
| `Ctrl/Cmd+P` | Show / hide the [performance monitor](Benchmarking-and-Performance#performance-monitor) |
| `Esc`, or closing the window | Save any unsaved recording and return to the launcher |

On macOS, `Cmd` can be used wherever `Ctrl` is shown.

Every mode opens with the help overlay shown. LiveVowel and LivePitch open paused; LiveSpectrogram and LiveSpectrum start recording when the window opens. A badge in the upper right corner shows `[REC]` or `[PAUSED]`.

## Inspecting a frozen display

Press `Space` to pause, then hold `Shift` and left-click (or click and drag) anywhere on the plot. Crosshairs and a card of values appear at the cursor and follow it while the mouse button is held. Release `Shift` to hide them. This works only while the display is frozen; in LiveVowel it also works while the IPA picker (`Ctrl/Cmd+V`) is open.

| Mode | Values at the cursor | Extra values |
|------|----------------------|--------------|
| LiveVowel | F1 and F2 (Hz) | If a plotted point is within 25 px: its raw f0 ("Recorded f0") and its smoothed F1/F2 ("Track Formants") |
| LivePitch | Time (s) and f0 (Hz). In fixed mode the time is within the 0–T window; in continuous mode it is the position on the scrolling timeline | If a plotted point is within 25 px: its f0 (the smoothed, plotted value) |
| LiveSpectrogram | Time (s, from the left edge of the window), frequency (Hz), and the power (dB, including the current gain) stored for that column and frequency | — |
| LiveSpectrum | Frequency (Hz), the spectrum's level at that frequency, and the level of the cursor itself on the dB axis (both including the gain offset) | With the LPC overlay on: the level of the LPC envelope at that frequency (below the max formant), and the detected formant within 180 Hz of the cursor, with its level on the envelope |

The dB values in LiveSpectrogram and LiveSpectrum are on the same relative display scale as the plot (not calibrated to dBFS), so they are for comparing levels within a display.

---

## LiveVowel

Plots F1 against F2 in the layout of a vowel chart: F2 on the horizontal axis and F1 on the vertical axis, both reversed, so that front vowels are on the left and high vowels at the top. The axes can be log or linear.

### Display modes

Set with `display_mode` in [Formant Plot Settings](Settings-Reference#formant-plot-settings).

| Mode | Shows |
|------|-------|
| `single` | Only the most recent point |
| `track` | The current vocalization as a connected track, together with the finished tracks |
| `all` | All points recorded in the session |

### Colors

| Color | Meaning |
|-------|---------|
| Red | The vocalization being tracked now |
| Blue | Finished tracks from earlier vocalizations, kept on screen for comparison |
| Green | IPA labels and template vowels |

### Controls

In addition to the [common controls](#controls-common-to-all-modes):

| Key | Action |
|-----|--------|
| `Ctrl/Cmd+V` | Open / close the IPA symbol picker (click a symbol to show or hide its label). Recording stops while it is open |
| `Ctrl/Cmd+T` | Show / hide the vowel template |
| Left click + drag | Move an IPA or template label |
| Mouse wheel | Scale all labels up or down together in formant space, about 1% per step, to fit a template to a speaker with a shorter or longer vocal tract (in log scale this keeps the shape of the vowel space) |
| `Ctrl/Cmd+S` | Save the labels shown to a new timestamped template, which becomes the active template |
| `Ctrl/Cmd+L` | Switch between log and linear frequency scales |
| `+` / `-` | Raise / lower the minimum RMS threshold (`min_rms_db`) |
| `Backspace` | Remove the last finished track (`track` and `all` modes) |
| `Delete` | Remove all finished tracks (`track` and `all` modes) |

Showing the help overlay stops recording, and hiding it starts recording.

Templates are described under [Vowel templates](Outputs-and-File-Formats#vowel-templates).

### Tracks and recording

- A track ends when voicing drops or the formants become unstable (beyond the stability threshold) for longer than the Skip Tolerance ([Smoother Settings](Settings-Reference#smoother-settings), default 2 frames). Shorter interruptions continue the same track. Stopping recording also ends the current track.
- Each track has its own `track_number` in the CSV, matching the tracks drawn on screen.
- A new set of files (WAV and CSV) is written each time recording stops (`Space`, opening the IPA picker, or opening help) and on exit.

---

## LivePitch

Plots f0 against time. The f0 axis can be log or linear, and its range is set separately from the f0 range of the analysis (see [Pitch Plot Settings](Settings-Reference#pitch-plot-settings)).

### Time modes

Set with `pitch_plot_mode` in Pitch Plot Settings.

| Mode | Behavior |
|------|----------|
| `fixed` (default) | The window spans a fixed duration (0 to T seconds, 5 by default). Each track starts at the left edge and earlier tracks stay in place, so successive attempts are overlaid on each other and on any target contour. When the active track reaches the right edge it is finished and recording pauses; press `Space` to record the next one |
| `continuous` | The window scrolls while recording: new data enters on the right and older data leaves on the left. Pausing and resuming continues the same timeline |

### Colors

| Color | Meaning |
|-------|---------|
| Red | The vocalization being tracked now |
| Blue | Finished tracks from earlier vocalizations, kept on screen for comparison |
| Green | Target markers placed with a left click, joined by a line |

### Controls

In addition to the [common controls](#controls-common-to-all-modes):

| Key | Action |
|-----|--------|
| Left click | Place a target marker |
| Right click | Remove all target markers |
| `Ctrl/Cmd+L` | Switch between log and linear frequency scales |
| `+` / `-` | Raise / lower the minimum RMS threshold (`min_rms_db`) |
| `Backspace` | Remove the last finished track |
| `Delete` | Remove all finished tracks |

### Tracks and recording

- A track ends after 3 consecutive unvoiced frames, when recording is paused, or (in fixed mode) when it reaches the right edge.
- A new set of files (WAV and CSV) is written each time recording stops and on exit.

---

## LiveSpectrogram

Shows a scrolling spectrogram: time on the horizontal axis (new data enters on the right), frequency on the vertical axis (0 to `max_freq`, 5000 Hz by default), and level as color.

The window length and the time step are set separately in [Spectrogram Settings](Settings-Reference#spectrogram-settings), so both wide-band and narrow-band spectrograms can be shown.

### Controls

In addition to the [common controls](#controls-common-to-all-modes):

| Key | Action |
|-----|--------|
| `+` / `-` | Narrow / widen the dynamic range by 5 dB |
| `Ctrl/Cmd++` / `Ctrl/Cmd+-` | Raise / lower the gain by 5 dB (`Ctrl/Cmd+=` and `Ctrl/Cmd+_` also work) |

The picture shows the top `dynamic_range` dB below full scale, after the gain has been added. Anything weaker is drawn in the darkest color. A narrower range hides weak energy and spreads the colors over the strong energy; a wider range brings weaker energy into view. Gain brightens the whole picture.

### Recording

Recording starts when the window opens. `Space` freezes the picture and saves the audio recorded so far; `Space` again resumes, and starts a new file. Audio is also saved on exit. No CSV is written.

---

## LiveSpectrum

Plots the power spectrum of the current analysis window: frequency on the horizontal axis (0 to `max_freq`, 8000 Hz by default) and level on the vertical axis in relative dB (a display scale shifted by the gain offset, not calibrated to dBFS). The spectrum is smoothed across frames (`smoothing` in [Spectrum Settings](Settings-Reference#spectrum-settings)).

### LPC overlay

`Ctrl/Cmd+L` adds two things to the spectrum (drawn in blue):

- the spectral envelope of the formant analysis (a red curve), and
- a labeled triangle on the envelope at each detected formant (F1 to F5).

The overlay uses the formant method and settings from Analysis Settings, so it shows the formants that LiveVowel would report for the same audio. `[` and `]` lower and raise the maximum formant in 50 Hz steps, from 3000 Hz up to the max frequency in Spectrum Settings; an alert appears at either end. The value is saved to Analysis Settings when the window closes, and LiveVowel uses it the next time it is launched.

How to use the overlay to find settings for a speaker is described in [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting). How the overlay's analysis window relates to the spectrum's is described under [Spectrum Settings](Settings-Reference#spectrum-settings).

### Controls

In addition to the [common controls](#controls-common-to-all-modes):

| Key | Action |
|-----|--------|
| `Ctrl/Cmd+L` | Show / hide the LPC overlay |
| `[` / `]` | Lower / raise the maximum formant by 50 Hz |
| `1`–`5` + click | Place or move the arrow marker for F1–F5 at the cursor frequency (hold the number key and click, or press the number while the mouse is over the plot) |
| Right click | Remove the arrow markers |
| `Ctrl/Cmd+S` | Keep the current frozen spectrum on screen as a colored trace, for comparison with later ones |
| `Backspace` | Remove the last saved trace, or the last arrow marker if no traces are saved |
| `Delete` | Remove all saved traces and arrow markers |
| `+` / `-` | Raise / lower the gain offset by 3 dB, which shifts the spectrum up or down on the dB axis |

### Recording

As in LiveSpectrogram: recording starts when the window opens, `Space` freezes the display and saves the audio recorded so far, and no CSV is written.
