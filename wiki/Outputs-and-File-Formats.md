# Outputs and File Formats

## Where files are saved

Recordings are saved to `recordings/` in the project folder. If a subject/data folder is selected in [Data Settings](Settings-Reference#data-settings), that folder is used instead, and holds everything belonging to the subject or project:

```
<data_dir>/
├── .VocalTrack_settings.json   # Settings for this subject/project
├── templates/                  # Vowel templates
└── recordings/                 # Audio and CSV files
```

Benchmark files are saved to `benchmarking/` in the project folder (see [Benchmarking and Performance](Benchmarking-and-Performance#output-files)).

## File names

```
speaker_YYYY-MM-DD_HHMMSS_NN_[mode]_[type].[ext]
```

| Part | Meaning |
|------|---------|
| `speaker` | Fixed speaker ID. To change it, change the `'speaker'` argument passed to `exporter.create_session_name()` in `BaseAudioVisualizer.__init__` (`VocalTrack/BaseAudioVisualizer.py`) |
| `YYYY-MM-DD_HHMMSS` | Date and time (24-hour) at which the display window was opened |
| `NN` | Number of the recording within that window (`01`, `02`, ...), counting up each time a new recording starts |
| `[mode]`, `[type]` | `vowel`, `pitch`, `spectrogram` or `spectrum`, followed by `original` or `downsampled` for audio. The CSV files end in `formants` (LiveVowel) or `pitch` (LivePitch) |

Example: two recordings from one LiveVowel window, then one each from LivePitch and LiveSpectrogram.

```
speaker_2026-03-04_102534_01_vowel_original.wav
speaker_2026-03-04_102534_01_formants.csv
speaker_2026-03-04_102534_02_vowel_original.wav
speaker_2026-03-04_102534_02_formants.csv
speaker_2026-03-04_102539_01_pitch_original.wav
speaker_2026-03-04_102539_01_pitch.csv
speaker_2026-03-04_102545_01_spectrogram_original.wav
```

## When files are written

Which files are saved (CSV, original audio, downsampled audio) is chosen in Data Settings; the three options are independent.

| Mode | A new set of files is written |
|------|-------------------------------|
| LiveVowel | Each time recording stops (`Space`, opening the IPA picker with `Ctrl/Cmd+V`, or opening help), and on exit |
| LivePitch | Each time recording stops (`Space`, or reaching the right edge in fixed mode), and on exit |
| LiveSpectrogram, LiveSpectrum | Each time the display is paused with `Space`, and on exit (WAV only) |

In every mode, a microphone disconnect during a recording also ends the recording and saves its files.

## WAV files

All modes can save two versions of the audio:

| File | Default | Contents |
|------|---------|----------|
| `_original.wav` | On | The microphone stream at the device's own sample rate (typically 44100 or 48000 Hz) |
| `_downsampled.wav` | Off | The stream that is analyzed, at the analysis sample rate: 2 × max formant in LiveVowel and LivePitch (e.g. 10000 Hz for a 5000 Hz max formant), 2 × max frequency in LiveSpectrogram and LiveSpectrum |

- Format: PCM, 16-bit signed integer, mono, little-endian.
- The audio is normalized on export so that its peak is at 97% of full scale: `samples = samples × (32767 × 0.97 / max_abs_value)`.
- Size: about 5.8 MB per minute at 48000 Hz, and 1.2 MB per minute at 10000 Hz.

## LiveVowel CSV

`speaker_YYYY-MM-DD_HHMMSS_NN_formants.csv`, UTF-8 with a header row.

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `time_ms` | int | milliseconds | Center of the analysis window, measured from the start of the accompanying WAV file |
| `f0` | float | Hz | Fundamental frequency, raw, to 2 decimal places |
| `f1` | int | Hz | First formant, raw |
| `f1_smoothed` | int | Hz | First formant after smoothing (the value plotted) |
| `f2` | int | Hz | Second formant, raw |
| `f2_smoothed` | int | Hz | Second formant after smoothing (the value plotted) |
| `f3` | int | Hz | Third formant, raw (not smoothed) |
| `voicing` | int | 0/1 | Always 1, since only voiced frames are written |
| `track_number` | int | — | Number of the track the frame belongs to |

```csv
time_ms,f0,f1,f1_smoothed,f2,f2_smoothed,f3,voicing,track_number
1233,123.41,567,565,1234,1231,2345,1,1
1250,125.02,570,567,1240,1235,2350,1,1
1267,126.87,575,570,1245,1239,2355,1,1
```

A new `track_number` starts when the track breaks for longer than the smoother's Skip Tolerance (see [LiveVowel tracks](Mode-Guides#tracks-and-recording)). The tracks drawn on screen follow the same rule, so one track on screen corresponds to one `track_number`.

## LivePitch CSV

`speaker_YYYY-MM-DD_HHMMSS_NN_pitch.csv`, UTF-8 with a header row.

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `track` | int | — | Pitch track number (a track ends after 3 unvoiced frames, when recording stops, or when the fixed-mode window fills) |
| `time_ms` | int | milliseconds | Center of the analysis window, measured from the start of the accompanying WAV file |
| `f0` | float | Hz | Fundamental frequency, raw, to 2 decimal places |
| `f0_smoothed` | float | Hz | f0 after smoothing (the value plotted), written unrounded |
| `voicing` | int | 0/1 | Always 1, since only voiced frames are written |

```csv
track,time_ms,f0,f0_smoothed,voicing
1,1233,123.41,122.80341176470588,1
1,1250,125.02,124.1190273556231,1
1,1267,126.87,125.93458110516934,1
```

Track numbers keep counting up across the files written from one LivePitch window.

## Which frames are in the CSV

A frame is written only if all of the following hold:

1. The smoother accepted it as stable. These are the same frames that are plotted, so the smoother's warm-up frames and frames with large frame-to-frame jumps are left out.
2. It is voiced.
3. Its f0 is within range: the Analysis Settings range (`min_f0` to `max_f0`) in LiveVowel, and the Pitch Plot Settings display range in LivePitch.

Gaps in `time_ms` are therefore normal: they are silences, voiceless consonants and rejected frames. The WAV file contains the complete recording, including those stretches.

**Timing.**
- One analysis is made per display frame, so rows are spaced by 1000 / `fps` ms (16.7 ms at the default 60 fps) where no frames are missing.
- `time_ms` comes from the number of audio samples captured, so it lines up with the WAV file saved alongside the CSV.
- Changing `fps` changes the spacing (e.g. 30 fps → 33.3 ms), so keep it fixed across recordings that are to be compared.

## Vowel templates

A template is a JSON file in the `templates/` folder that defines reference vowels shown in LiveVowel. It is chosen from the **Vowel Template** dropdown in [Formant Plot Settings](Settings-Reference#formant-plot-settings); the choice is saved and used on later launches. When a subject/data folder is active, its own `templates/` subfolder is used instead.

### Format

An excerpt from the bundled `Michigan_English.json`:

```json
{
  "name": "American English Vowels (Hillenbrand et al., 1995)",
  "description": "Acoustic characteristics of American English vowels produced in /hVd/ syllables, averaged across 45 men, 48 women, and 46 children at steady state.",
  "language": "American English",
  "source": "Hillenbrand, J., Getty, L. A., Clark, M. J., & Wheeler, K. (1995). Acoustic characteristics of American English vowels. The Journal of the Acoustical Society of America, 97(5), 3099-3111.",
  "vowels": [
    {
      "symbol": "i",
      "name": "Close front unrounded",
      "description": "Close front unrounded vowel (e.g., 'heed')",
      "f1": 410.33,
      "f2": 2721.33
    },
    {
      "symbol": "æ",
      "name": "Near-open front unrounded",
      "description": "Near-open front unrounded vowel (e.g., 'had')",
      "f1": 658.0,
      "f2": 2267.33
    }
  ]
}
```

The header fields (`name`, `description`, `language`, `source`) are optional and record where the values come from. Fields of each vowel:

| Field | Type | Description |
|---|---|---|
| `symbol` / `ipa` | `string` | IPA vowel character, drawn with the matching IPA glyph image. One of the 28 symbols in the IPA vowel chart (`i y ɨ ʉ ɯ u ɪ ʏ ʊ e ø ɘ ɵ ɤ o ə ɛ œ ɜ ɞ ʌ ɔ æ ɐ a ɶ ɑ ɒ`) or the two r-colored vowels (`ɚ ɝ`). Any other symbol is skipped with a warning in the log, as is a second vowel with the same symbol. |
| `f1` | `float` | First formant in Hz. |
| `f2` | `float` | Second formant in Hz. |
| `name` / `keyword` | `string` | (Optional) Common name or Wells lexical keyword (e.g. `"fleece"`, `"trap"`, `"goose"`). |
| `description` | `string` | (Optional) Phonetic description (e.g. `"Close front unrounded vowel"`). |
| `f3` | `float` | (Optional) Third formant in Hz. Kept for reference only: VocalTrack does not read or display it. |
| `image_num` | `int` | (Optional) Number of the symbol's image (1–30). Written by `Ctrl/Cmd+S`; when present it selects the symbol shown. Leave it out of hand-written templates and use `symbol`. |

### Bundled templates

| File | Contents | Source |
|---|---|---|
| `IPA_all_vowels.json` (default) | All 28 IPA vowels in an idealized layout of the IPA vowel chart (not measured data) | *Handbook of the International Phonetic Association* (1999) |
| `Michigan_English.json` | American English (Michigan): 12 vowels in /hVd/ syllables, averaged over men, women and children | Hillenbrand, Getty, Clark, & Wheeler (1995), *JASA* 97(5), 3099–3111 |
| `Texas_English.json` | American English (Texas): 12 vowels in /hVd/ syllables, averaged over adult male and female talkers | Assmann & Katz (2000), *JASA* 108(4), 1856–1866 |
| `Spanish.json` | Spanish: 5 vowels | Bradlow (1995), *JASA* 97(3), 1916–1924 |

Each file records its source in its `source` field. Because the measured templates are averages across talkers, a template usually has to be scaled to an individual speaker with the mouse wheel in LiveVowel.

### Making a template

- **By hand**: put a `.json` file in `templates/` and select it in Formant Plot Settings. `IPA_all_vowels.json` can be copied as a starting point.
- **In LiveVowel**: open the IPA picker (`Ctrl/Cmd+V`), click symbols to show or hide them, drag the labels into position, and press `Ctrl/Cmd+S`. The labels shown are saved as `custom_template_YYYY-MM-DD_HHMMSS.json` in the templates folder, which becomes the active template. Existing templates are never overwritten. Positions scaled with the mouse wheel are saved as scaled.
