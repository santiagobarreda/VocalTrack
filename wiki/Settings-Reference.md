# Settings Reference

All settings in the launcher dialogs, with the defaults from `VocalTrack/config.py`. A few settings are not in any dialog and are changed in `config.py`; these are marked "`config.py` only".

## Settings file

- Settings are saved to `.VocalTrack_settings.json` in the project folder when a dialog is closed with **OK**, and are loaded at startup. The file is created the first time VocalTrack is launched.
- If a subject/data folder is selected in [Data Settings](#data-settings), that folder has its own `.VocalTrack_settings.json`, which is used while the folder is active. The folder is reopened at the next startup.
- The file has one section per dialog: `analysis`, `smoother`, `plotting` (Formant Plot Settings), `pitch_plot`, `spectrogram`, `spectrum`, and `recording` (Data Settings).
- Values missing from the file take their defaults from `config.py`.
- Settings are applied when a mode is launched, so a change takes effect the next time a mode is opened.
- Window sizes are not in the dialogs. Resize a window by dragging its edges; its size is saved when it closes.
- Copying the file to another installation or folder transfers the settings.

**Resetting.** Every dialog has a **Defaults** button that resets its fields to the `config.py` defaults (click **OK** to save them). Deleting the file resets everything. Individual sections or keys can also be removed from the file in a text editor (do not set values to `null`).

**Unreadable file.** If the file cannot be read, a warning is printed in the terminal ("Could not load settings from ..."), the defaults are used, and the file is replaced the next time settings are saved.

**Precedence.** Values passed to a mode in code override saved settings, which override `config.py`. Saved settings are applied by the launcher: a mode [started directly from Python](Installation-and-Launch#starting-a-mode-from-python) uses `config.py` plus whatever is passed to it.

**Files from earlier versions** are converted when loaded: `chunk_ms` and `number_of_chunks` become `window_ms = chunk_ms × number_of_chunks`, and the method name `'native'` becomes `'lpc'` (formants) or `'autocorrelation'` (pitch).

---

## Analysis Settings

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `window_ms` | `50` | 20-100 ms | Length of each analysis window (LiveVowel and LivePitch; also the LPC overlay in LiveSpectrum). Longer = steadier estimates and lower trackable f0, shorter = faster response. Shown as "Window Length (ms)". |
| `max_formant` | `5000` | 4000-8000 Hz | Upper limit of the formant search. The analysis sample rate is 2 × this value. |
| `n_formants` | `5.5` | 3.0-7.0 | Number of formants to look for below `max_formant`. It sets the LPC order (2 × this value, rounded down), so 5.5 gives order 11. F1–F3 are plotted and exported whatever the value. |
| `min_f0` | `60` | 40-200 Hz | Minimum f0 for pitch analysis and data filtering. |
| `max_f0` | `500` | 200-800 Hz | Maximum f0 for pitch analysis and data filtering. |
| `min_rms_db` | `-60.0` | -90 to -20 dB | Minimum RMS amplitude (dBFS) for a frame to be analyzed. More negative = quieter sounds are analyzed; less negative = more noise is excluded. Adjustable with `+`/`-` in LiveVowel and LivePitch. |
| `formant_method` | `'lpc'` | `'lpc'`, `'wlp'`, `'parselmouth'`, `'custom'` | Formant method (see [Analysis methods](#analysis-methods)). |
| `pitch_method` | `'autocorrelation'` | `'autocorrelation'`, `'yin'`, `'parselmouth'`, `'custom'` | Pitch method (see [Analysis methods](#analysis-methods)). |
| `min_confidence` | `0.45` | 0.0-1.0 | Voicing threshold for the built-in pitch methods (1.0 = perfectly periodic). `autocorrelation`: the minimum height of the window-corrected autocorrelation peak (0.45 is Praat's default voicing threshold; values below ~0.3 let some noise frames through as voiced). `yin`: the minimum periodicity, 1 − YIN aperiodicity. Not used by `parselmouth`. |
| `robust_formants` | `False` | True/False | With `formant_method='parselmouth'`, use Praat's robust formant method instead of Burg. Ignored by the built-in methods. `config.py` only. |
| `pre_emphasis_coeff` | `0.97` | 0.0-1.0 | Pre-emphasis coefficient applied to the spectrum shown in LiveSpectrogram and LiveSpectrum (0 = none). The built-in LPC and WLP methods always use 0.97. `config.py` only. |
| `pre_emphasis_hz` | `50` | 0-200 Hz | Frequency above which Praat applies pre-emphasis; used with `formant_method='parselmouth'` only. `config.py` only. |

### Window length and refresh rate

- Audio is captured in chunks one display frame long (1000 / `fps` ms). Each new chunk triggers one analysis of the most recent `window_ms` of audio, so the display receives one new analysis per frame.
- The time step between analyses is therefore `1 / fps` (16.7 ms at 60 fps), using the `fps` of the mode being run, and consecutive windows overlap by `window_ms − time_step` (50 − 16.7 = 33.3 ms with the defaults).
- The window length does not need to be a multiple of the frame duration.
- Because the time step follows `fps`, the refresh rate also sets the spacing of the rows in the exported CSV files. Lowering `fps` from 60 to 30 doubles the spacing from 16.7 ms to 33.3 ms.
- If `fps` is so low that one frame is longer than the window, the audio between windows is not analyzed (it is still recorded).
- LiveSpectrogram is the exception: its time step is a setting of its own (see [Spectrogram Settings](#spectrogram-settings)).

### Starting values by speaker

| Speaker | `min_f0` | `max_f0` | `max_formant` |
|---------|----------|----------|---------------|
| Adult male | 60 | 250 | 5000 |
| Adult female | 120 | 400 | 5500 |
| Child | 180 | 500 | 6500-8000, depending on age |

These are starting points. The right `max_formant` depends on the length of the speaker's vocal tract (roughly, on height) more than on gender or age, and should be checked for each speaker: see [Formant Tracking Troubleshooting & Calibration](Formant-Tracking-Troubleshooting).

### Analysis methods

The built-in methods and the Parselmouth methods differ little in accuracy or speed. They can be compared on your own system with the [Benchmarking](Benchmarking-and-Performance) tool.

**`lpc`** (formants; default; built-in). `get_formants_lpc()` in `VocalTrack/utils/get_formants.py`.
- The frame is resampled to 2 × `max_formant`, pre-emphasized and Gaussian-windowed. Levinson-Durbin LPC (order 2 × `n_formants`) is followed by root-finding on the prediction polynomial.
- Poles between 50 Hz and `max_formant` with a bandwidth below 1600 Hz are formants (Praat applies no bandwidth limit).

**`wlp`** (formants; built-in). `get_formants_wlp()` in `VocalTrack/utils/get_formants.py`. Weighted Linear Prediction with Short-Time Energy weighting (Ma, Kamp & Willems 1993), recommended for high-pitched voices (Alku et al. 2013).
- Standard LPC weights the prediction error equally at every sample. WLP weights each sample's error by the energy of the 2 ms of signal before it. No glottal events are detected: the weighting itself down-weights the glottal excitations (the hardest samples to predict, since the signal just before them has decayed) and emphasizes the high-energy stretch that follows them, when the vocal tract rings freely. In high-pitched voices this makes it less prone than LPC to locking onto a harmonic instead of the formant.
- If a voice has no clear excitation-then-decay pattern (e.g. breathy voice), the weights become flatter and WLP behaves more like ordinary linear prediction. At very high f0 the period approaches the 2 ms energy window, so the weighting becomes less selective.
- Same pre-processing as `lpc`. Every sample of the zero-padded frame is predicted from the preceding 2 × `n_formants` samples, and the weighted least-squares problem is solved directly. Unlike Levinson-Durbin LPC this can produce poles outside the unit circle; they are reflected inside (keeping their frequency) rather than dropped.
- When F1 lies below f0 (e.g. /i/ or /u/ produced at 400 Hz) there is no harmonic near F1, and no method can recover it.

**`autocorrelation`** (pitch; default; built-in). `get_pitch_autocorrelation()` in `VocalTrack/utils/get_pitch.py`. Follows Boersma (1993) / Praat's "To Pitch (ac)".
- The frame is mean-removed and Hanning-windowed. Its autocorrelation is divided by the window's own autocorrelation, so that long lags (low voices) are not suppressed by the window. Peak lags and heights are refined by parabolic interpolation. Among the peaks, a small octave cost (0.05 per octave) favors the shortest lag, avoiding octave-down errors. The frame is voiced if the chosen peak exceeds `min_confidence`.
- The analysis window must hold about 1.8 periods of `min_f0` (a 50 ms window reaches down to about 36 Hz). If it doesn't, a warning is logged with the lowest f0 that can be tracked.
- Each frame is estimated on its own (no tracking across frames as in Praat); the smoother handles continuity.

**`yin`** (pitch; built-in). `get_pitch_yin()` in `VocalTrack/utils/get_pitch.py`. YIN (de Cheveigné & Kawahara 2002), steps 2–5 of the paper.
- The frame is mean-removed. The difference function d(τ) measures how much the frame differs from itself shifted by τ, and is normalized by its cumulative mean (d′). The period is the first dip of d′ below the absolute threshold (0.1, as in the paper), followed down to its local minimum, or the deepest dip if none falls below the threshold. Its lag is refined by parabolic interpolation.
- The frame is voiced if its periodicity (1 − d′ at the chosen dip) exceeds `min_confidence`.
- The analysis window must hold 2 periods of `min_f0` (a 50 ms window reaches down to about 40 Hz). If it doesn't, a warning is logged with the lowest f0 that can be tracked.
- Each frame is estimated on its own (the paper's step 6 is not used).

**`parselmouth`** (formants and pitch). `get_formants_parselmouth()` and `get_pitch_parselmouth()`. Praat's algorithms through the Parselmouth library (Burg LPC for formants, autocorrelation for pitch); also the reference in benchmarking. Requires the `praat-parselmouth` package.
- Praat needs three periods of `min_f0` in the analysis window (a 50 ms window reaches down to 60 Hz). If the window is shorter than that, the lowest f0 the window allows is used instead and a warning is logged.

**`custom`** (formants and pitch). User-defined functions `get_formants_custom()` in `VocalTrack/utils/get_formants.py` and `get_pitch_custom()` in `VocalTrack/utils/get_pitch.py`. Not implemented by default. Each must return a dictionary with the keys listed in its docstring.

---

## Smoother Settings

The smoother (LiveVowel and LivePitch) first decides which frames to accept, then filters the accepted ones.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `memory_n` | `3` | 1-10 frames | Number of consecutive voiced, stable frames required before a point is accepted (plotted and written to the CSV). Larger = fewer spurious points, but a longer delay at the start of each vowel. |
| `stability_threshold` | `0.15` | 0.05-0.50 | Largest frame-to-frame change allowed within those `memory_n` frames, in natural-log units (0.15 ≈ a 16% change). Lower = more frames rejected. |
| `skip_tolerance` | `2` | 0-10 frames | Number of rejected frames tolerated before a track ends (the display holds the last accepted value meanwhile). |
| `use_euro_filter` | `True` | True/False | Apply the 1-Euro filter to accepted frames. |
| `euro_min_cutoff` | `0.05` | 0.001-1.0 Hz | Cutoff frequency when the value is not changing. Lower = smoother but slower to respond. |
| `euro_beta` | `1.5` | 0.0-5.0 | How fast the cutoff rises with the speed of change. Higher = fast changes are followed more closely, with more noise let through. |
| `euro_dcutoff` | `0.5` | 0.1-2.0 Hz | Cutoff for smoothing the speed estimate itself. |
| `velocity_power` | `1.5` | 0.5-3.0 | Exponent applied to the speed. 1 = the standard 1-Euro filter; >1 = slow changes are smoothed more and fast changes are followed more closely. |

### The 1-Euro filter

The 1-Euro filter (Casiez, Roussel & Vogel 2012) is an exponential moving average whose cutoff frequency rises with the speed of the tracked value: steady values are smoothed heavily, and fast changes are followed with little delay. Formants and f0 are filtered in log space. For each accepted value $x_i$:

1. Time since the last accepted frame, where $dt_{\text{base}} = 1/\text{fps}$ and skipped frames are those that were unvoiced or rejected:

$$
dt = dt_{\text{base}} + (dt_{\text{base}} \times \text{skipped\_frames})
$$

2. Speed, from the previous output $\hat{x}_{i-1}$:

$$
dx_i = \frac{x_i - \hat{x}_{i-1}}{dt}
$$

3. Smoothed speed, with a fixed cutoff $f_{c, d}$ (`euro_dcutoff`):

$$
\alpha_d = \frac{1}{1 + \frac{\tau_d}{dt}}, \quad \tau_d = \frac{1}{2 \pi \cdot f_{c, d}}, \quad \hat{dx}_i = \alpha_d \cdot dx_i + (1 - \alpha_d) \cdot \hat{dx}_{i-1}
$$

4. Cutoff for the value, from `euro_min_cutoff` ($f_{c, \min}$), `euro_beta` ($\beta$) and `velocity_power` (never below $10^{-6}$):

$$
f_c = f_{c, \min} + \beta \cdot |\hat{dx}_i|^{\text{power}}
$$

5. Output:

$$
\alpha = \frac{1}{1 + \frac{\tau}{dt}}, \quad \tau = \frac{1}{2 \pi \cdot f_c}, \quad \hat{x}_i = \alpha \cdot x_i + (1 - \alpha) \cdot \hat{x}_{i-1}
$$

### Tuning

| Problem | Change |
|---------|--------|
| Tracks are jittery | Raise `memory_n` (3 → 5), lower `euro_min_cutoff` (0.05 → 0.02), lower `euro_beta` (1.5 → 1.0) |
| Tracks respond slowly | Lower `memory_n` (3 → 2), raise `euro_min_cutoff` (0.05 → 0.1), raise `euro_beta` (1.5 → 2.0) |
| Tracks jump between values | Lower `stability_threshold` (0.15 → 0.10), lower `skip_tolerance` (2 → 1) |
| Tracks break up during normal speech | Raise `skip_tolerance` (2 → 3), raise `stability_threshold` (0.15 → 0.25) |

---

## Formant Plot Settings

For LiveVowel.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `template_file` | `'IPA_all_vowels.json'` | Any `.json` in `templates/`, or `None` | Active [vowel template](Outputs-and-File-Formats#vowel-templates). If the selected file is missing, the default is used, or else the first template in alphabetical order. |
| `f1_range` | `(200, 1200)` | (100, 1500) Hz | Range of the vertical (F1) axis. |
| `f2_range` | `(500, 3000)` | (300, 3500) Hz | Range of the horizontal (F2) axis. |
| `fps` | `60` | 15-120 | Display refresh rate. One analysis is made per frame, so this also sets the analysis time step (1000 / fps ms) and the spacing of CSV rows. |
| `display_mode` | `'single'` | `'single'`, `'track'`, `'all'` | See [LiveVowel display modes](Mode-Guides#display-modes). |
| `freq_scale` | `'log'` | `'log'`, `'linear'` | Scale of both axes. Toggle with `Ctrl/Cmd+L` during use. |
| `show_vowel_template` | `False` | True/False | Whether the template is shown when LiveVowel opens. Toggle with `Ctrl/Cmd+T` during use. `config.py` only. |
| `gui_size` | `(900, 650)` | — | Window size in pixels. Set by resizing the window. |

The default ranges suit most adult speakers. Children may need wider ranges (e.g. F1 250-1500 Hz, F2 700-3500 Hz).

---

## Pitch Plot Settings

For LivePitch.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `min_f0` | `75` | 40-200 Hz | Lower limit of the f0 axis. |
| `max_f0` | `500` | 200-800 Hz | Upper limit of the f0 axis. |
| `fps` | `60` | 15-120 | Display refresh rate. One analysis is made per frame, so this also sets the analysis time step (1000 / fps ms) and the spacing of CSV rows. |
| `pitch_plot_mode` | `'fixed'` | `'fixed'`, `'continuous'` | See [LivePitch time modes](Mode-Guides#time-modes). |
| `pitch_display_seconds` | `5.0` | 1.0-20.0 s | Duration shown across the window. |
| `freq_scale` | `'log'` | `'log'`, `'linear'` | Scale of the f0 axis. Toggle with `Ctrl/Cmd+L` during use. |
| `gui_width`, `gui_height` | `1200`, `650` | — | Window size in pixels. Set by resizing the window. |

The display range here is independent of the analysis range in Analysis Settings: the analysis range limits which f0 values can be estimated, and the display range limits which are shown. The LivePitch CSV contains only frames within the display range.

---

## Spectrogram Settings

For LiveSpectrogram.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_freq` | `5000` | 1000-10000 Hz | Top of the frequency axis. The audio is analyzed at twice this value. |
| `display_seconds` | `3.0` | 0.5-5.0 s | Duration shown across the window. Smaller = faster scrolling. |
| `colormap` | `'plasma'` | `viridis`, `plasma`, `inferno`, `magma`, `cividis`, `twilight`, `turbo` | Bundled copies of the matplotlib colormaps of the same names. `twilight` is cyclic (light at both ends) and less suited to spectrograms. |
| `dynamic_range` | `40` | 20-80 dB | The top `dynamic_range` dB below full scale are shown; weaker energy is drawn in the darkest color. Adjustable with `+`/`-` during use. |
| `gain_db` | `0.0` | 0-80 dB | Gain added before display (brightness). Adjustable with `Ctrl/Cmd++`/`Ctrl/Cmd+-` during use; the value in use when the window closes is saved. |
| `fps` | `60` | 15-120 | How often the screen is redrawn. Here it does not set the analysis rate, which is set by `time_step_ms`. |
| `window_ms` | `6.0` | 3-50 ms | Length of each analysis window. Shown as "Window Length (ms)". |
| `time_step_ms` | `6.0` | 1-50 ms | Time between analyses. Each analysis is drawn as one column, and the step can be shorter than a display frame. Shown as "Time Step (ms)". |
| `padding_length_ms` | `20.0` | 0-100 ms | Zero-padding for the FFT. Adds interpolated frequency bins (a smoother frequency axis, more computation) without changing the true frequency resolution, which is set by the window length. |
| `gui_width`, `gui_height` | `1200`, `650` | — | Window size in pixels. Set by resizing the window. |

**Window length.** A short window (about 5 ms; the default is 6 ms) gives a wide-band spectrogram, which resolves individual glottal pulses and shows formants as broad bands. A long window (30-50 ms) gives a narrow-band spectrogram, which resolves individual harmonics.

**Time step.**
- Step equal to the window (the default, 6 ms and 6 ms): windows sit end to end with no overlap.
- Step shorter than the window (e.g. 40 ms window, 10 ms step): windows overlap by `window_ms − time_step_ms`, as needed for a smooth narrow-band display.
- Step longer than the window: the audio between windows is not analyzed (it is still recorded).
- A shorter step means more analyses per second and more CPU load.

---

## Spectrum Settings

For LiveSpectrum.

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `max_freq` | `8000` | 1000-10000 Hz | Top of the frequency axis. The audio is analyzed at twice this value. Also the highest max formant reachable with `[`/`]`, which is why the default is above the 5000 Hz typical for speech displays. |
| `dynamic_range` | `70` | 20-100 dB | Height of the dB axis, which runs from 0 dB at the top to −`dynamic_range` at the bottom. |
| `gain_offset_db` | `-30.0` | -100 to 100 dB | Shifts the spectrum up or down on the dB axis. Adjustable with `+`/`-` (3 dB per press) during use; the value in use when the window closes is saved. |
| `fps` | `60` | 15-120 | Display refresh rate. One spectrum is analyzed per frame, so this also sets the analysis time step (1000 / fps ms). |
| `window_ms` | `50.0` | 10-100 ms | Length of each FFT analysis window. Longer = better frequency resolution (roughly 1 / window duration). Shown as "Window Length (ms)". |
| `padding_length_ms` | `20.0` | 0-100 ms | Zero-padding for the FFT. Increases the density of frequency bins (a smoother line), not the true frequency resolution. Bin spacing = sample_rate / (window_samples + padding_samples). |
| `smoothing` | `0.7` | 0.0-1.0 | Response factor of the exponential smoothing across frames. 1.0 = no smoothing, 0.0 = frozen. |
| `gui_width`, `gui_height` | `1200`, `650` | — | Window size in pixels. Set by resizing the window. |

**Smoothing.** Each frame, `new_spectrum = (smoothing × current_spectrum) + ((1 - smoothing) × old_spectrum)`. With the LPC overlay on, the same factor smooths the LPC envelope and the formant markers.

**The LPC overlay uses two analysis windows.**
- The overlay's parameters (`window_ms`, `max_formant`, `n_formants`, `formant_method`) come from Analysis Settings, so that it shows the analysis LiveVowel would run. The spectrum's parameters (`window_ms`, `padding_length_ms`, `max_freq`) come from Spectrum Settings.
- `AudioProcessor` buffers enough audio for the longer of the two windows. The FFT uses the most recent part of the buffer, and the formant analysis receives the whole buffer.
- If the Spectrum window is the longer one, the formant analysis uses that longer window too. For an exact match with LiveVowel, keep the Spectrum window no longer than the Analysis Settings window (both are 50 ms by default).

**Changing the max formant with `[`/`]`** takes effect immediately. The audio is captured at 2 × max frequency and, as in Praat, each formant analysis window is resampled to 2 × max formant, so the envelope and formant markers change while the displayed spectrum does not. To use a max formant above the max frequency, raise the max frequency.

---

## Data Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `data_dir` | `'.'` | Subject/data folder. VocalTrack loads and saves `.VocalTrack_settings.json` here, looks for vowel templates in its `templates/` subfolder, and writes recordings to its `recordings/` subfolder. Chosen with **Browse...**, and can be changed during a session to switch between participants or projects. |
| `device_name` | System default | Microphone, selected by name (which does not change when other devices are plugged in or removed). |
| `input_device_index` | System default | Position of the device in the QtMultimedia device list. Used only as a fallback for settings saved without a name. |
| `save_csv` | `True` | Save CSV files (LiveVowel and LivePitch). |
| `save_original_audio` | `True` | Save the audio at the microphone's sample rate. |
| `save_downsampled_audio` | `False` | Save the audio at the analysis sample rate. |
| `output_dir` | `'recordings'` | Folder for recordings, relative to `data_dir`. `config.py` only (`EXPORT_CONFIG`). |

The three save options are independent of each other.

The device list shows all input devices found by QtMultimedia and is refreshed each time the dialog opens. The system default is marked `[DEFAULT]`. If the saved microphone is not connected, it stays selected and is marked `[NOT CONNECTED]`; VocalTrack then uses the system default (and says so on screen) until the microphone is available again. See [microphone disconnects](Troubleshooting#the-microphone-disconnects-during-a-session).

---

## Other values in `config.py`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PERFORMANCE_CONFIG['logging_level']` | `30` | Python logging level: 10 = DEBUG, 20 = INFO, 30 = WARNING, 40 = ERROR. |
| `COLORS['white']` | `(255, 255, 255)` | Plot background in LiveVowel, LivePitch and LiveSpectrum; label text in LiveSpectrogram. |
| `COLORS['black']` | `(0, 0, 0)` | Background in LiveSpectrogram. |

The colors of tracks, labels and overlays are set in the visualizer code (e.g. `LiveVowel.py`, `LivePitch.py`).
