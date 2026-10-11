# Benchmarking and Performance

Two tools: a benchmark that compares analysis methods on a recording, and a monitor that shows real-time performance while a mode is running.

## Benchmarking

The benchmark records about 15 seconds of speech and runs a chosen formant method and pitch method (built-in or custom) and Parselmouth on the same frames. It reports how closely they agree and how long each takes.

Parselmouth is the reference, not ground truth. It also makes errors, and which method is right depends on the recording and the settings, so check the audio where the methods disagree.

### Running it

1. Click **Benchmarking** in the launcher.
2. Select the methods to compare. The dialog preselects those chosen in Analysis Settings.
   - Formants: `lpc`, `wlp`, or `custom` (if implemented)
   - Pitch: `autocorrelation`, `yin`, or `custom` (if implemented)
3. Click **Run** and produce vowels continuously for the whole recording. Silences reduce the number of frames that can be compared.

The benchmark uses the microphone selected in Data Settings and the current Analysis Settings (max formant, number of formants, window length, f0 range, min RMS and min confidence). The audio is analyzed at the analysis sample rate (2 × max formant) in frames one analysis window long. `praat-parselmouth` must be installed.

### What is reported

- **Agreement**: correlation, RMSE, MAE and relative error (%) for F1, F2, F3 and f0.
- **Timing**: mean ms per frame and the range of the central 95% of per-frame times (2.5th to 97.5th percentiles), for the selected method and for Parselmouth, separately for formants and pitch.
- **Frame counts**: frames recorded, frames judged voiced, and frames used in each comparison.

Formants are compared on voiced frames only, with voicing decided by Parselmouth's pitch tracker (using the Analysis Settings f0 range and min RMS), so the formant frames are the same whichever pitch method is benchmarked. Pitch is compared on frames that both methods judge voiced.

### Output files

Saved to `benchmarking/` in the project folder.

| File | Contents |
|------|----------|
| `comprehensive_benchmark.md` | The report: settings used, agreement tables, and timing |
| `formant_raw_comparison.csv` | Per-frame formant values, with columns named after the method (e.g. `timestamp, lpc_F1, lpc_F2, lpc_F3, praat_F1, praat_F2, praat_F3`) |
| `pitch_raw_comparison.csv` | Per-frame pitch values, with columns named after the method (e.g. `timestamp, autocorrelation_f0, praat_f0`) |
| `benchmark_{timestamp}.wav` | The recorded audio, at the analysis sample rate |

### Reading the results

| Measure | Rough guide |
|---------|-------------|
| Correlation | 0.95–1.00 excellent, 0.90–0.95 good, 0.80–0.90 acceptable, below 0.80 poor (inspect the audio) |
| RMSE, f0 | Below 10 Hz excellent, below 20 Hz good, below 50 Hz acceptable |
| RMSE, F1 and F2 | Below 30 Hz excellent, below 50 Hz good, below 100 Hz acceptable |
| Mean time per frame | Should be well under the time step: 16.67 ms at 60 fps |

## Performance monitor

`Ctrl/Cmd+P` in any mode shows the actual rate of each stage of the pipeline next to its target.

| Line | What it measures | Target | If it is low |
|------|------------------|--------|--------------|
| GUI FPS | How often the screen is redrawn | The mode's `fps` setting (60 by default) | Drawing is the bottleneck |
| Audio In | Audio chunks read from the microphone and queued for analysis, per second | One chunk per display frame, so the `fps` setting (60.0 ch/s at 60 fps). In LiveSpectrogram a chunk is one time step, so 1000 / `time_step_ms` (166.7 ch/s for a 6 ms step) | The microphone or its driver is not delivering audio at the expected rate |
| Analysis | Analysis windows completed and queued for plotting, per second | The same as Audio In, since each chunk triggers one analysis | The analysis takes longer than one chunk; the queue fills and chunks are dropped |
| Queue | Chunks waiting to be analyzed | 0 to 5 | (If high) the analysis is falling behind; an early warning before chunks are dropped |

Each rate is followed by its percentage of the target. The text is green at 90% of the target or more, yellow from 75% to 90%, and red below 75%. The Queue line is green for 0–5 chunks, yellow for 6–25, and red for 26 or more.

**Dropped chunks.** The recording (WAV) is not affected, since it is written before the queue. Analysis windows are never joined across a dropped chunk: after a drop, no windows are analyzed until a full window of continuous audio has arrived again, so the CSV has no rows for that stretch. The same applies to the first window after recording starts.

What to do when a rate is low: [Troubleshooting](Troubleshooting#performance).
