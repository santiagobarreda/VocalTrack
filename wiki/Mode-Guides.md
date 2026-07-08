# Mode Guides

This guide provides detailed documentation for each of VocalTrack's four visualization modes.

---

## Analysis Methods

VocalTrack uses specialized analysis functions for each supported backend. When you select a formant or pitch analysis method in Settings, the software automatically delegates to the appropriate function:

- **Native methods** (`formant_method='native'`, `pitch_method='native'`): Fast, built-in implementations using standard signal processing (LPC for formants, autocorrelation for pitch)
- **Parselmouth methods** (`formant_method='parselmouth'`, `pitch_method='parselmouth'`): Praat-based algorithms via the Parselmouth library. Also pretty standard (LPC for formants, autocorrelation for pitch)
- **Custom methods** (`formant_method='custom'`, `pitch_method='custom'`): User-defined (that's you) analysis functions for advanced users. These are not implemented by default

There is not much difference between the native methods and Parselmouth in either accuracy or latency. 

---

## LiveVowel - Formant Space Tracking

### Purpose

LiveVowel provides real-time visualization of vowel formants in F1/F2 acoustic space. It's designed for vowel quality analysis, pronunciation training, dialect studies, and speech therapy applications.

### Visual Display

The display shows a 2D plot in the style of the IPA vowel quadrilateral:

- **Horizontal axis (X)**: Inverted F2 formant frequency (typically 500-2700 Hz), i.e. vowel frontness
- **Vertical axis (Y)**: Inverted F1 formant frequency (typically 200-1200 Hz), i.e. vowel height
- **Axes reversed**: Higher frequencies appear toward the left and bottom (matching conventional vowel chart orientation)
- **Optional overlays**: 
  - Pre-loaded vowel templates (toggle with `Ctrl/Cmd+T`). These come in the 'templates' folder. If you rename one to 'vowel_template.csv', that file will be used. If not such file exists templates will not work
  - Menu to toggle IPA symbols on/off (toggle with `Ctrl/Cmd+V`). The IPA symbols can be dragged aroundto provide markers or targets for speakers
  - Grid lines (toggle with `Ctrl/Cmd+G`)
  - Performance monitor overlay (toggle with `Ctrl/Cmd+P`)
  - Help overlay (toggle with `Ctrl/Cmd+?`)

### Display Modes

Three visualization modes are available (configure in Formant Plot Settings):

1. **Single**: Shows only the most recent formant point
   - Best for: Real-time feedback without visual clutter
   - Use case: Pronunciation training, target vowel practice

2. **Track**: Shows the current trajectory as a connected path. Gaps in voicing or sufficients intensity will 'break' trajectories
   - Best for: Visualizing vowel transitions and diphthongs
   - Use case: Analyzing vowel dynamics, studying formant movement

3. **All**: Shows all recorded trajectories
   - Best for: Comparing multiple vowel productions. Other stuff?
   - Use case: Before/after comparisons, vowel inventory analysis

### Interaction and Controls

| Key | Action |
|-----|--------|
| `Ctrl/Cmd+V` | Toggle IPA chooser menu |
| `Ctrl/Cmd+R` | Toggle recording state |
| `Ctrl/Cmd+?` | Toggle help overlay (stops recording when shown, starts when hidden) |
| `Ctrl/Cmd+T` | Toggle vowel template overlay (IPA symbols) |
| `Ctrl/Cmd+G` | Toggle grid overlay |
| `Ctrl/Cmd+P` | Toggle performance monitor overlay |
| `+` | Increase minimum RMS threshold (filter out more noise) |
| `-` | Decrease minimum RMS threshold (capture quieter sounds) |
| `Backspace` | Undo last finished track |
| `Delete` | Clear all finished tracks |
| `Esc` | Quit and save WAV + CSV files |

### Workflow

1. **Launch**: Click "LiveVowel" button in launcher
2. **Disable help overlay**: Use `Ctrl/Cmd+?` key after display initializes
3. **Speak**: Produce vowels or continuous speech
4. **Monitor**: Watch formant points appear in real-time
5. **Adjust threshold**: Use `+`/`-` to filter background noise if needed
6. **Manage tracks**: Use `Backspace` to undo last track, `Delete` to clear all
7. **Export**: Press `Esc` to quit and save files to `recordings/`

### Recording Behavior

- **Continuous recording**: Audio is captured continuously while in recording state
- **Trajectory segmentation**: Formant tracks are automatically segmented when:
  - Voicing drops (unvoiced segments separate tracks)
  - Formants become unstable (beyond stability threshold)
  - Recording stops and restarts
- **Track numbering**: Each trajectory segment receives a unique `track_number` in CSV output

### Output Files

**WAV file**: `recordings/speaker_YYYY-MM-DD_HHMMSS_vowel_original.wav` (and/or `recordings/speaker_YYYY-MM-DD_HHMMSS_vowel_downsampled.wav`)
- Mono, 16-bit
- Sample rate: device sample rate (original) or 2 × max_formant (typically 10000 Hz, downsampled)
- Normalized amplitude

**CSV file**: `recordings/speaker_YYYY-MM-DD_HHMMSS_formants.csv`

Columns:
- `time_ms`: Timestamp in milliseconds
- `f0`: Fundamental frequency (Hz)
- `f1`: First formant (Hz)
- `f2`: Second formant (Hz)
- `f3`: Third formant (Hz)
- `voicing`: Boolean (True for voiced frames)
- `track_number`: Trajectory segment identifier

**Filter behavior**: Only voiced frames with f0 within configured range (`min_f0` to `max_f0`) and minimal intensity are written to CSV.

### Configuration Tips

**For optimal formant tracking:**

1. Set `max_formant` appropriately. General guidelines are below but it's really more about height than gender or age:
   - Adult male: 5000 Hz
   - Adult female: 5500 Hz
   - Child: 6500-8000 Hz

2. Adjust F1/F2 display ranges (Formant Plot Settings) to maximally use the plot space:
   - Default F1: 200-1200 Hz (good for most speakers)
   - Default F2: 500-2700 Hz (good for most speakers)
   - Narrow ranges for detailed view of specific vowel regions
   - Widen ranges if vowels appear cut off

3. Tune smoothing (Smoother Settings):
   - Increase `memory_n` (3-5) for stabler, smoother tracks
   - Change `1euro` parameters for faster response, and to reduce jitter for consistent productions
   - Increase `stability_threshold` (0.15-0.25) to filter erratic jumps, decrease to exlucde more noise

4. Control noise:
   - Increase `min_rms_db` (-50 to -40 dB) to ignore background noise
   - Use `+`/`-` keys during recording for real-time adjustment

### Frequency Scale Options

**Logarithmic (log)**: 
- Mimics perceptual spacing of formants
- Low formants spread out, high formants compressed
- Better matches traditional vowel charts

**Linear**:
- Uniform Hz spacing across entire range
- Better for measuring exact frequency differences
- Easier to read absolute values from axes

Toggle between scales in formant plot menu

---

## LivePitch - f0 Contour Tracking

### Purpose

LivePitch visualizes fundamental frequency (f0) over time in a scrolling pitch contour display. It's designed for intonation training, tone language learning, singing practice, and prosody analysis.

### Visual Display

The display shows:

- **Horizontal axis (X)**: Time (configured window duration, default 5 seconds)
- **Vertical axis (Y)**: f0 frequency (Hz), configurable range
- **Frequency scale**: Logarithmic or linear (matches perception vs. linear Hz)
- **Pitch contour**: Connected line showing f0 trajectory
- **Optional overlays**:
  - Grid lines (toggle with `Ctrl/Cmd+G`)
  - Performance monitor overlay (toggle with `Ctrl/Cmd+P`)
  - Help overlay (toggle with `Ctrl/Cmd+?`)

### Plot Modes

Two scrolling modes are available (configure in Pitch Plot Settings):

1. **Fixed**: Fixed-width time window (default 5 seconds)
   - Display window remains constant width
   - Older data scrolls off the left edge
   - Best for: Real-time monitoring with consistent temporal context

2. **Continuous**: Expanding timeline
   - Display window expands as recording progresses
   - All data remains visible (compressed over time)
   - Best for: Recording complete utterances for later review

### Interaction and Controls

| Key | Action |
|-----|--------|
| `Space` (hold) | Start recording pitch segment (push-to-talk) |
| `Space` (release) | Stop recording and export segment |
| `Ctrl/Cmd+G` | Toggle grid overlay |
| `Ctrl/Cmd+P` | Toggle performance monitor overlay |
| `Ctrl/Cmd+?` | Toggle help overlay |
| `+` | Increase minimum RMS threshold |
| `-` | Decrease minimum RMS threshold |
| `Backspace` | Remove most recent finished track |
| `Delete` | Clear all finished tracks |
| `Esc` | Quit (file already saved when Space released) |

### Workflow

1. **Launch**: Click "LivePitch" button in launcher
2. **Disable help overlay**: Use `Ctrl/Cmd+?` key after display initializes
3. **Hold Space**: Press and hold Space key to start recording
4. **Speak/sing**: Produce target intonation or melody
5. **Monitor**: Watch f0 contour appear in real-time
6. **Release Space**: Let go of Space to stop and automatically export
7. **Review**: Pitch data is immediately saved to `recordings/`
8. **Record more**: Hold Space again for additional segments
9. **Quit**: Press `Esc` to close window

### Recording Behavior

- **Push-to-talk**: Recording only occurs while Space is held down
- **Immediate export**: WAV + CSV files are saved automatically when Space is released
- **Multiple segments**: Each Space down/up cycle creates a new timestamped file pair
- **Track isolation**: Each recording is independent (no cross-contamination)

### Output Files

**WAV file**: `recordings/speaker_YYYY-MM-DD_HHMMSS_pitch_original.wav` (and/or `recordings/speaker_YYYY-MM-DD_HHMMSS_pitch_downsampled.wav`)
- Mono, 16-bit
- Sample rate: device sample rate (original) or 2 × max_formant (typically 10000 Hz, downsampled)
- Normalized amplitude

**CSV file**: `recordings/speaker_YYYY-MM-DD_HHMMSS_pitch.csv`

Columns:
- `track`: Track number (if multiple segments)
- `time_ms`: Timestamp in milliseconds
- `f0`: Fundamental frequency (Hz)
- `voicing`: Boolean (True for voiced frames)

**Filter behavior**: Only voiced frames with f0 within configured range (`min_f0` to `max_f0`) are written to CSV.

### Configuration Tips

**For optimal pitch tracking:**

1. Set analysis f0 range (Analysis Settings):
   - Male voice: `min_f0=60`, `max_f0=250`
   - Female voice: `min_f0=120`, `max_f0=400`
   - Child voice: `min_f0=180`, `max_f0=500`
   - Singing: Expand range to cover your full vocal range

2. Set display f0 range (Pitch Plot Settings):
   - Can differ from analysis range
   - Narrow display range for detailed intonation work
   - Wide display range to capture full contour variation

3. Adjust display window (Pitch Plot Settings):
   - `pitch_display_seconds=3.0`: Short utterances, quick feedback
   - `pitch_display_seconds=5.0`: Default, good for sentences
   - `pitch_display_seconds=10.0`: Long utterances, extended phonation

4. Tune smoothing (Smoother Settings):
   - Increase `euro_beta` (1.0-2.0) for more reactive tracking
   - Decrease `euro_min_cutoff` (0.01-0.05) for smoother contours
   - Adjust `stability_threshold` to filter pitch jumps

### Frequency Scale Options

**Logarithmic (log)**:
- Matches perceptual pitch spacing
- Octaves appear equally spaced
- Better represents musical intervals
- Default for most users

**Linear**:
- Uniform Hz spacing
- Better for measuring absolute Hz differences
- Less intuitive for musical applications

### Common Use Cases

**Intonation training (L2 pronunciation):**
1. Set fixed plot mode with 3-5 second window
2. Record model utterance, then repeat
3. Compare your contour shape to target

**Tone language learning:**
1. Use narrow f0 range to zoom in on tone contrasts
2. Record each tone in isolation
3. Practice matching contour shapes

**Singing pitch accuracy:**
1. Expand f0 range to cover your vocal range
2. Use continuous plot mode to see full phrase
3. Record scales or melodies and check for drift

**Prosody research:**
1. Use fixed mode for standardized recording windows
2. Export CSV for statistical analysis of f0 contours
3. Analyze peak alignment, slope, and range

---

## LiveSpectrogram - Scrolling Wideband Display

### Purpose

LiveSpectrogram provides a scrolling wideband spectrogram for real-time phonetic analysis, formant visualization, and acoustic detail examination. It displays frequency content over time using color-coded intensity.

### Visual Display

The display shows:

- **Horizontal axis (X)**: Time (scrolls right to left)
- **Vertical axis (Y)**: Frequency (0 to max_freq, typically 5000 Hz)
- **Color-coding**: Intensity mapped to colormap (bright = high energy, dark = low energy)
- **Scrolling behavior**: New spectrum appended on right, old data shifts left
- **Optional overlays**:
  - Performance monitor overlay (toggle with `Ctrl/Cmd+P`)
  - Help overlay (toggle with `Ctrl/Cmd+?`)

### Colormap Options

Choose from matplotlib colormaps (configure in Spectrogram Settings):

- **plasma** (default): Perceptually uniform, good for detail
- **viridis**: Perceptually uniform, blue-green-yellow
- **magma**: Perceptually uniform, dark purple to bright yellow
- **inferno**: Perceptually uniform, dark to bright red
- **hot**: Traditional hot metal color scale
- **jet**: Rainbow colors (not perceptually uniform, but familiar)

### Interaction and Controls

| Key | Action |
|-----|--------|
| `+` | Decrease dynamic range (show more detail in quiet regions) |
| `-` | Increase dynamic range (increase contrast) |
| `Ctrl/Cmd++` / `Ctrl/Cmd+=` | Increase gain (make brighter overall) |
| `Ctrl/Cmd+-` / `Ctrl/Cmd+_` | Decrease gain (make darker overall) |
| `Ctrl/Cmd+P` | Toggle performance monitor overlay |
| `Ctrl/Cmd+?` | Toggle help overlay |
| `Esc` | Quit |

**Note**: Grid toggle (`Ctrl/Cmd+G`) is not implemented in LiveSpectrogram.

### Workflow

1. **Launch**: Click "LiveSpectrogram" button in launcher
2. **Wait**: Display initializes and audio begins flowing automatically
3. **Speak**: Spectrogram appears immediately as you speak
4. **Adjust display**:
   - Use `+`/`-` to adjust dynamic range (detail vs. contrast)
   - Use `Ctrl/Cmd++`/`Ctrl/Cmd+-` to adjust gain (brightness)
5. **Monitor**: Observe formants, voicing, fricatives, stops, etc.
6. **Quit**: Press `Esc` to close (no automatic export)

### Recording Behavior

- **Automatic visualization**: Spectrogram begins updating as soon as window opens
- **No recording control**: Visualization is always active (no start/stop toggle)
- **No automatic export**: Display-focused mode (does not save WAV/CSV by default)
- **Use case**: Real-time visual feedback during speech production or analysis

### Output Files

**Default**: None (visualization-only mode)

To capture data from LiveSpectrogram:
- Use screen recording software to save visual output
- Modify source code to enable audio buffer export if needed

### Configuration Tips

**For optimal spectral visualization:**

1. Set max frequency (Spectrogram Settings):
   - `max_freq=5000`: Standard for speech (default)
   - `max_freq=8000`: Extended range for fricatives and sibilants
   - `max_freq=3000`: Focus on lower formants and voicing

2. Adjust dynamic range (in-window `+`/`-`):
   - Smaller range (20-30 dB): More detail in quiet regions
   - Larger range (50-60 dB): More contrast, clearer formant bars
   - Default (40 dB): Balanced detail and contrast

3. Adjust gain (in-window `Ctrl/Cmd++`/`Ctrl/Cmd+-`):
   - Increase gain if spectrogram appears too dark
   - Decrease gain if everything appears saturated/bright
   - Find balance where formants are visible without noise floor dominating

4. Set time window (Spectrogram Settings):
   - `display_seconds=1.0`: Fast scrolling, good for real-time feedback (default)
   - `display_seconds=3.0`: Slower scrolling, see more context
   - `display_seconds=0.5`: Very fast scrolling for immediate feedback

5. Choose colormap (Spectrogram Settings):
   - Perceptually uniform maps (plasma, viridis) avoid visual artifacts
   - Hot/jet colormaps may be more familiar but can mislead perception

6. Adjust FFT parameters (Spectrogram Settings):
   - Reduce `padding_length_ms` for faster computation (less smooth)
   - Increase `padding_length_ms` for smoother frequency axis (more computation)
   - Adjust `chunk_ms` to balance time/frequency resolution

### Understanding Spectrographic Features

**Formants**: Horizontal dark bars (resonances of the vocal tract)
- F1: Lowest horizontal bar (200-1200 Hz)
- F2: Second bar (500-3000 Hz)
- F3: Third bar (1500-4000 Hz)

**Voicing**: Regular vertical striations (glottal pulses)
- Spacing between striations = 1/f0
- Presence indicates voiced sound

**Fricatives**: High-frequency diffuse energy
- /s/, /ʃ/: Strong energy above 4000 Hz
- /f/, /θ/: Weaker, more diffuse high-frequency energy

**Stops**: Silent gaps followed by bursts
- /p/, /t/, /k/: Gap (closure) then brief burst of noise
- Burst frequency indicates place of articulation

### Common Use Cases

**Phonetic transcription:**
1. Use default settings (5000 Hz, plasma colormap)
2. Monitor formant transitions to identify vowels
3. Look for voicing, bursts, and frication to identify consonants

**Formant analysis:**
1. Reduce max_freq to 3000-4000 Hz to focus on formants
2. Adjust dynamic range to make formant bars stand out
3. Observe formant movement during speech

**Voice quality assessment:**
1. Look for regular vs. irregular voicing patterns
2. Check for breathiness (increased high-frequency noise)
3. Assess spectral tilt (relative energy in high vs. low frequencies)

---

## LiveSpectrum - Real-Time FFT Display

### Purpose

LiveSpectrum displays the real-time power spectrum as a static line plot, showing the distribution of acoustic energy across frequency bins. It's designed for spectral envelope analysis, resonance visualization, and harmonic structure examination.

### Visual Display

The display shows:

- **Horizontal axis (X)**: Frequency (0 to max_freq, typically 5000 Hz)
- **Vertical axis (Y)**: Power (dB)
- **Line plot**: Single continuous line showing spectrum magnitude
- **Averaging**: Spectrum is averaged across multiple audio frames for stability
  - Grid lines (toggle with `Ctrl/Cmd+G`)
  - Performance monitor overlay (toggle with `Ctrl/Cmd+P`)
  - Help overlay (toggle with `Ctrl/Cmd+?`)

### Interaction and Controls

| Key | Action |
|-----|--------|
| `+` | Increase gain offset (shift spectrum up) |
| `-` | Decrease gain offset (shift spectrum down) |
| `Ctrl/Cmd+G` | Toggle grid overlay |
| `Ctrl/Cmd+P` | Toggle performance monitor overlay |
| `Ctrl/Cmd+?` | Toggle help overlay |
| `Esc` | Quit |

### Workflow

1. **Launch**: Click "LiveSpectrum" button in launcher
2. **Wait**: Display initializes and spectrum begins updating automatically
3. **Speak**: Spectrum responds immediately to acoustic input
4. **Adjust gain**: Use `+`/`-` to shift spectrum vertically for optimal display
5. **Monitor**: Observe spectral peaks, harmonics, formants
6. **Quit**: Press `Esc` to close (no automatic export)

### Recording Behavior

- **Automatic visualization**: Spectrum updates continuously as soon as window opens
- **No recording control**: Visualization is always active
- **No automatic export**: Display-focused mode (does not save WAV/CSV by default)
- **Use case**: Real-time spectral monitoring and analysis

### Output Files

**Default**: None (visualization-only mode)

### Configuration Tips

**For optimal spectrum display:**

1. Set max frequency (Spectrum Settings):
   - `max_freq=5000`: Standard for speech (default)
   - `max_freq=8000`: Extended range for fricatives
   - `max_freq=3000`: Focus on fundamental and low harmonics

2. Adjust smoothing (Spectrum Settings):
   - Higher smoothing (0.8-0.9): Very stable, slow to respond
   - Medium smoothing (0.7): Default, balanced
   - Lower smoothing (0.3-0.5): Faster response, more jitter
   - No smoothing (0.0): Instantaneous, very noisy

3. Set dynamic range (Spectrum Settings):
   - Smaller range (30 dB): Compress vertical scale, see detail at all levels
   - Larger range (50 dB): Expand vertical scale, more contrast
   - Default (40 dB): Standard speech analysis range

4. Adjust gain offset (in-window `+`/`-`):
   - Increase to shift spectrum up if it's too low on screen
   - Decrease to shift spectrum down if it's saturating at top
   - Find balance where peaks are visible without clipping

5. Tune FFT parameters (Spectrum Settings):
   - Increase `padding_length_ms` for smoother frequency axis
   - Increase `chunk_ms` for better frequency resolution (slower time response)
   - Increase `number_of_chunks` for longer analysis window

### Understanding Spectral Features

**Harmonics**: Evenly spaced peaks in voiced sounds
- First peak: Fundamental frequency (f0)
- Subsequent peaks: Integer multiples of f0 (2×f0, 3×f0, etc.)
- Spacing between peaks = f0

**Formants**: Broader peaks/envelopes grouping harmonics
- F1, F2, F3 appear as broad resonance peaks
- Multiple harmonics cluster under each formant peak

**Spectral tilt**: Overall decrease in energy with increasing frequency
- Steeper tilt: Modal voice
- Flatter tilt: Breathy voice or voiceless sounds

**Noise vs. Tone**:
- Voiced sounds: Clear harmonic peaks
- Voiceless sounds: Flat or diffuse spectrum (no peaks)

### Common Use Cases

**Resonance training (singing/speech):**
1. Look for formant peaks in spectrum
2. Adjust articulators to shift formant frequencies
3. Monitor spectral envelope changes in real-time

**Harmonic analysis:**
1. Identify f0 as the first (lowest) peak
2. Count harmonics and check spacing
3. Assess harmonic-to-noise ratio

**Voice quality assessment:**
1. Compare spectral tilt between productions
2. Look for breathiness (increased noise floor)
3. Check for hyper/hypo-nasality (formant bandwidth changes)

**Formant frequency estimation:**
1. Identify broad peaks in spectrum envelope
2. Read approximate formant frequencies from X-axis
3. Use grid (`Ctrl/Cmd+G`) for easier frequency reading

---

## Comparing the Four Modes

| Feature | LiveVowel | LivePitch | LiveSpectrogram | LiveSpectrum |
|---------|-----------|-----------|-----------------|--------------|
| **Primary display** | F1/F2 scatter plot | f0 contour line | Scrolling spectrogram | Static spectrum line |
| **Recording control** | Ctrl/Cmd+R or Ctrl/Cmd+? (toggle) | Space (push-to-talk) | None (always on) | None (always on) |
| **Exports WAV** | Yes | Yes | No (by default) | No (by default) |
| **Exports CSV** | Yes (formants) | Yes (pitch) | No (by default) | No (by default) |
| **Best for** | Vowel analysis | Intonation training | Phonetic transcription | Spectral analysis |
| **Key advantage** | Direct vowel space visualization | Simple push-to-talk workflow | Rich acoustic detail | Harmonic structure |
| **Typical use case** | Pronunciation training | Tone language learning | Formant transitions | Resonance monitoring |

All modes share common controls (`Ctrl/Cmd+G` for grid, `Ctrl/Cmd+?` for help, `Esc` to quit) and support real-time parameter adjustment.
