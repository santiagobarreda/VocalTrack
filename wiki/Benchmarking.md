# Benchmarking

VocalTrack includes a built-in benchmarking tool accessible from the launcher. This tool compares analysis methods (native or custom vs. Parselmouth) for accuracy and timing performance. The system implements separate specialized functions for each analysis backend: the native implementations use standard signal processing algorithms (LPC for formants, autocorrelation for pitch), while the Parselmouth backend delegates to Praat's well-established algorithms. Benchmarking is useful for validating measurement accuracy and optimizing analysis settings for your use case. Don't assume that 'errors' mean that Parselmouth is right and the alternate implementations are 'wrong'. Differences require further inspection but in initial testing, I found plenty of cases where Parselmouth was wrong. It all depends on the specific recording and the settings used. 

## Quick Start

1. Launch VocalTrack:
   ```bash
   python vocaltrack.py
   ```

2. Click the **Benchmarking** button in the launcher

3. Select comparison method:
   - `native`: Built-in formant/pitch extraction
   - `custom`: Custom analysis backend (if implemented)
   - Note: Parselmouth is automatically used as the reference standard

4. Click **Run** to start the benchmark

5. Speak continuously during the recording period

6. Results are automatically saved to `benchmarking/` folder

## Benchmark

VocalTrack runs a single combined benchmark that measures both accuracy and timing by comparing the selected method against Parselmouth on the same recording.

**What It Measures:**
- Formant accuracy: correlation, RMSE, MAE, and relative error (%) for F1, F2, F3
- Pitch accuracy: correlation, RMSE, MAE, and relative error (%) for f0
- Timing: mean ms/frame and 95% confidence intervals for both the selected method and Parselmouth (reported separately for formant and pitch)
- Frame counts: number of voiced frames used in each comparison

**Output Files:**
- `benchmarking/formant_raw_comparison.csv`: Per-frame formant values (`timestamp, nF1, nF2, nF3, pF1, pF2, pF3`)
- `benchmarking/pitch_raw_comparison.csv`: Per-frame pitch values (`timestamp, native_f0, praat_f0`)
- `benchmarking/comprehensive_benchmark.md`: Full statistical report (accuracy tables, timing with 95% CIs)
- `benchmarking/benchmark_{timestamp}.wav`: Recorded audio used for the benchmark

**Duration:** ~15 seconds of recording

**Reference Standard:** Parselmouth/Praat is used as the gold standard for comparison. However, it makes plenty of mistakes too so check the audio!

**Use This When:**
- Validating formant/pitch accuracy against Praat
- Comparing native or custom methods against Parselmouth
- Optimizing for real-time performance
- Determining if analysis settings are appropriate for your use case
- Publishing research requiring method validation

## Requirements

### Software Dependencies

**Required:**
- `praat-parselmouth` must be installed for benchmarking, but this is installed when initial setup is run.
   ```bash
   pip install praat-parselmouth
   ```
  
**Check Installation:**
```bash
python -c "import parselmouth; print('Parselmouth installed successfully')"
```

If not installed, the launcher will show a warning and disable benchmarking.

### Hardware Requirements

- Working microphone
- Sufficient disk space (~1 MB per benchmark)
- Quiet recording environment (for accurate measurements)

### Recording Guidelines

For valid benchmarks:
1. **Produce vowels continuously** during the entire recording period
2. **Use natural speech** with varied vowels and pitch
3. **Minimize background noise** (affects accuracy measurements)
4. **Stay at consistent distance** from microphone
5. **Avoid silence** (reduces number of valid comparison frames)

## Interpreting Results

### Correlation Coefficients

**Interpretation:**
- **0.95-1.00**: Excellent agreement
- **0.90-0.95**: Good agreement
- **0.80-0.90**: Acceptable
- **<0.80**: Poor agreement (investigate audio)

**Expected Values:**
- f0: >0.95 (pitch is typically most reliable)
- F1: >0.90 (first formant is stable)
- F2: >0.90 (second formant is stable)
- F3: >0.80 (third formant is more variable)

### Error Metrics

**Root Mean Square Error (RMSE):**
- Measures average magnitude of errors
- Units are Hz (formants/pitch)
- Lower is better

**Meaningful Thresholds:**
- f0: <10 Hz (excellent), <20 Hz (good), <50 Hz (acceptable)
- F1/F2: <30 Hz (excellent), <50 Hz (good), <100 Hz (acceptable)
- F3: <100 Hz (acceptable for high formants)

**Relative Error (%):**
- Average absolute percentage difference from Parselmouth
- Scale-independent: useful for comparing across formants with different Hz ranges
- Lower is better

### Timing Metrics

**Mean Latency (ms/frame):**
- Time to process one analysis frame
- Reported separately for formant and pitch extraction, for both the selected method and Parselmouth
- 95% confidence intervals (2.5th–97.5th percentiles) are provided for each method
- Target: well under <16.67 ms for 60 FPS real-time visualization
- Native method is typically faster than Parselmouth

## Best Practices

1. **Run benchmarks in quiet environment** for accurate measurements
2. **Use natural, varied speech** to cover range of phonemes and f0
3. **Document analysis settings** used for each benchmark
4. **Compare multiple recording sessions** to assess variability
5. **Archive benchmark results** as validation for publications
6. **Re-run after code changes** to detect regressions
7. **Share benchmark CSVs** with collaborators for reproducibility
