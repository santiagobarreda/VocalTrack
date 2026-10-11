# Formant Tracking Troubleshooting & Calibration

Formant estimates depend on analysis settings that suit the speaker: vocal tract length, f0 and vowel quality all affect them. When the settings do not suit the voice, the estimates in [LiveVowel](Mode-Guides#livevowel) jump, go missing or merge, and many are rejected by the smoother, so points appear late or not at all.

LiveVowel shows only the resulting F1/F2 point, not why an estimate went wrong. The LPC overlay in [LiveSpectrum](Mode-Guides#livespectrum) shows the analysis itself, drawn over the spectrum, for the same settings that LiveVowel uses.

## What the overlay shows

- **The FFT spectrum** (blue line): the harmonics of the voice, whose peaks outline the formants.
- **The LPC envelope** (red curve, `Ctrl/Cmd+L`): the vocal tract filter estimated by the formant analysis.
- **Formant markers**: a labeled triangle on the envelope at each formant found (F1 to F5).

The analysis is working when the peaks of the envelope sit on the groups of strong harmonics, with one marker on each peak.

## Procedure

1. In Spectrum Settings, check **Max Frequency** (default 8000 Hz, enough for adults and most children). `]` cannot raise the maximum formant above it. For young children, raise it and relaunch LiveSpectrum.
2. Launch LiveSpectrum and press `Ctrl/Cmd+L`.
3. Have the speaker sustain a vowel, and press `Space` to freeze the display.
4. Compare the envelope with the harmonics. If they do not match, press `Space` to resume and adjust the maximum formant with `[` and `]` (50 Hz per press) while the speaker sustains the vowel, until they do. If that is not enough, see [Problems](#problems) below.
5. Optionally press `Ctrl/Cmd+S` while frozen to keep the spectrum on screen as a colored trace, so that several vowels can be compared on one frequency axis.
6. Repeat for /i/, /u/ and /ɑ/ at least.
7. Close LiveSpectrum. The maximum formant is saved to Analysis Settings, and LiveVowel uses it the next time it is launched.

If the maximum formant in Analysis Settings is already above the Spectrum Settings max frequency when LiveSpectrum opens, LiveSpectrum lowers it to that limit and shows an alert, because the overlay would otherwise not match what LiveVowel uses.

## Vowels to test

| Vowel | F1 | F2 | Check that |
|-------|----|----|------------|
| /i/ ("beet") | ~250–350 Hz | ~2100–2800 Hz | The low F1 peak is found and not confused with f0, and F2 and F3 (often close together near 2500–3000 Hz) are separate |
| /ɑ/ ("father") | ~700–900 Hz | ~1100–1400 Hz | The envelope has two peaks, not one broad one |
| /u/ ("boot") | ~300–400 Hz | ~800–1100 Hz | F1 and F2, which are close, have not merged into one peak |
| /æ/ ("bat") | ~650–850 Hz | ~1700–2100 Hz | |

## Problems

### The maximum formant does not suit the speaker

- **Seen as**: the peaks of the envelope sit consistently above or below the groups of harmonics, or the formant numbers are shifted (e.g. F2 labeled as F1, or higher formants missing).
- **Cause**: the analysis looks for a fixed number of formants below `max_formant`, which assumes a vocal tract of a certain length (about 17 cm for adult males, 14.5 cm for adult females, 10–12 cm for children).
- **Fix**: `[` lowers `max_formant` by 50 Hz (longer vocal tracts) and `]` raises it (shorter vocal tracts), between 3000 Hz and the Spectrum Settings **Max Frequency**; an alert appears at either end. Starting values: 5000 Hz for adult males (the default), 5500 Hz for adult females, 6500–7500 Hz for children.

### The envelope follows individual harmonics (high-pitched voices)

- **Seen as**: sharp peaks in the envelope that line up with single harmonics (f0, 2f0, 3f0), and formant estimates that jump from one harmonic to the next as pitch changes.
- **Cause**: at high f0 (above about 250 Hz) the harmonics are widely spaced, and LPC can be drawn to the strongest harmonic instead of the formant.
- **Fix**: in Analysis Settings, change the formant method from `lpc` to `wlp` (weighted linear prediction), which is less prone to this (see [Analysis methods](Settings-Reference#analysis-methods)). Adjusting `max_formant` with `[` / `]`, or trying the `parselmouth` method, may also help.

### F1 and F2 merge into one peak (back vowels)

- **Seen as**: on /u/ or /o/, one large low-frequency peak instead of two. The analysis labels it F1 and labels F3 (around 2200–2600 Hz) as F2, which makes the point jump in LiveVowel.
- **Fix**: adjust `max_formant` with `[` / `]` in 50 Hz steps while the speaker sustains /u/; the peak often splits in two at a particular value. Otherwise increase `n_formants` in Analysis Settings (e.g. from 5.5 to 6.0). The LPC order is 2 × `n_formants`, so this adds a pole.

### Extra formants where there is no peak

- **Seen as**: a formant marker in a trough of the spectrum, for example between F1 and F2 of /i/.
- **Fix**: decrease `n_formants` in Analysis Settings (e.g. from 5.5 to 5.0), or check `max_formant`: if it is too low for the speaker, the analysis has more poles than there are formants below it.

### Points drop out in quiet speech

- **Seen as**: points drop out in LiveVowel during soft vowels or near consonants.
- **Fix**: in LiveVowel (or LivePitch), press `-` to lower `min_rms_db` (e.g. to -65 or -70 dB), or lower **Min RMS** in Analysis Settings. In LiveSpectrum, `+`/`-` only shift the display, and the threshold is not applied to the formant markers. Also check that the input level in the operating system's sound settings is adequate and not clipping.

### "Maximum analysis frequency reached"

`max_formant` has reached the Spectrum Settings **Max Frequency**. Raise **Max Frequency** and relaunch LiveSpectrum.
