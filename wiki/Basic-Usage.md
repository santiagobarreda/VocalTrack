# Basic Usage

A session has two stages: settings are chosen in the launcher, and then a mode runs in its own window. A [video](https://www.youtube.com/watch?v=kgjn3Xq4zgI) shows an example of usage.

## Steps

1. **Start the launcher**: `python vocaltrack.py` (see [Installation and Launch](Installation-and-Launch)).
2. **Choose settings.** They are saved automatically, so this is needed only the first time or when the speaker changes.
   - **Data Settings**: the microphone and, optionally, a subject/data folder.
   - **Analysis Settings**: the f0 range and maximum formant for the speaker (see [starting values by speaker](Settings-Reference#starting-values-by-speaker)).
   - The plot settings of the mode to be used. The defaults are usually adequate.
3. **Click a mode button.** The launcher is hidden and the mode's window opens, with a help overlay listing its keys (`Ctrl/Cmd+?` hides and shows it).
4. **Record.** `Space` starts and pauses recording in every mode. LiveVowel and LivePitch open paused; LiveSpectrogram and LiveSpectrum start recording when the window opens. While paused, the display is frozen and values can be read off it with `Shift` + click.
5. **Close the window** with `Esc`. The launcher reappears.

Files are written to `recordings/` each time recording is paused and when the window is closed (see [Outputs and File Formats](Outputs-and-File-Formats)).

## Modes

| Mode | Shows | Saves |
|------|-------|-------|
| [LiveVowel](Mode-Guides#livevowel) | F1 against F2 in a vowel space | WAV, CSV (formants) |
| [LivePitch](Mode-Guides#livepitch) | f0 over time | WAV, CSV (f0) |
| [LiveSpectrogram](Mode-Guides#livespectrogram) | A scrolling spectrogram | WAV |
| [LiveSpectrum](Mode-Guides#livespectrum) | The power spectrum of the current frame, with an optional LPC envelope and formant markers | WAV |

## Further information

| For | See |
|-----|-----|
| Keys and mouse controls | [Mode Guides](Mode-Guides#controls-common-to-all-modes) |
| What each setting does | [Settings Reference](Settings-Reference) |
| Finding formant settings that suit a speaker | [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting) |
| Keeping each participant's settings, templates and recordings in a separate folder | [Data Settings](Settings-Reference#data-settings) |
| File names and CSV columns | [Outputs and File Formats](Outputs-and-File-Formats) |
| Comparing analysis methods, and checking real-time performance | [Benchmarking and Performance](Benchmarking-and-Performance) |
| Problems | [Troubleshooting](Troubleshooting) |
