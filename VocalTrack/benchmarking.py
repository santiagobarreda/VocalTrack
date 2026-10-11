"""
Benchmarking utilities for VocalTrack analysis methods.
Consolidated accuracy and timing reports with raw data CSV exports.
"""

import time
import os
import sys
import numpy as np
import statistics
import csv
import wave
from datetime import datetime

try:
    from .utils.get_formants import get_formants, _HAS_PARSELMOUTH  
    from .utils.get_pitch import get_pitch
    from .AudioProcessor import AudioProcessor
    from . import config
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from VocalTrack.utils.get_formants import get_formants, _HAS_PARSELMOUTH
    from VocalTrack.utils.get_pitch import get_pitch
    from VocalTrack.AudioProcessor import AudioProcessor
    from VocalTrack import config

def _resolve_output_dir(output_dir=None):
    base_dir = output_dir or os.path.join(os.getcwd(), "benchmarking")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def _benchmark_params():
    """The analysis settings the app uses (Analysis Settings), so the benchmark tests the same configuration."""
    a = config.ANALYSIS_CONFIG
    # Audio chunk (time step) as in LiveVowel: one display frame
    chunk_ms = config.chunk_ms_for_fps(config.LIVEVOWEL_CONFIG.get('fps', 60))
    return {
        'max_formant': a.get('max_formant', 5000),
        'n_formants': a.get('n_formants', 5.5),
        'window_length': a.get('window_length', 0.05),
        'time_step': chunk_ms / 1000.0,
        'pre_emphasis_hz': a.get('pre_emphasis_hz', 50),
        'robust_formants': a.get('robust_formants', False),
        'min_f0': a.get('min_f0', 60),
        'max_f0': a.get('max_f0', 500),
        'min_rms_db': a.get('min_rms_db', -60.0),
        'min_confidence': a.get('min_confidence', 0.45),
        'chunk_ms': chunk_ms,
        'window_ms': config.AUDIO_CONFIG.get('window_ms', 50),
    }

def record_speech_samples(duration_seconds=15.0, window_length=None, progress_callback=None, params=None):
    params = params or _benchmark_params()
    if window_length is None:
        window_length = params['window_length']
    analysis_config = config.ANALYSIS_CONFIG.copy()
    analysis_config.update({'max_formant': params['max_formant'], 'formants': False, 'pitch': False})

    # Record from the input device chosen in Data Settings (by name; the index is only a fallback
    # for settings saved without a name), like the visualizers do
    processor = AudioProcessor(
        chunk_ms=params['chunk_ms'], window_ms=params['window_ms'], analysis_config=analysis_config,
        raw_queue_maxsize=2000, analyzed_queue_maxsize=2000,
        input_device_index=config.EXPORT_CONFIG.get('input_device_index'),
        input_device_name=config.EXPORT_CONFIG.get('device_name') or None
    )
    
    processor.start()
    # Record the analysis-rate (downsampled) stream: the device-rate stream is at the
    # hardware rate (e.g. 48 kHz), not the analysis rate the methods are compared at
    processor.start_recording(record_original=False, record_downsampled=True)
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < duration_seconds:
        if progress_callback:
            progress_callback(min((time.perf_counter() - start_time) / duration_seconds, 1.0))
        time.sleep(0.01)

    processor.stop_recording()
    recording = processor.get_downsampled_recording()
    sr = processor.get_downsampled_recording_sample_rate()
    processor.stop()

    if recording is None or recording.size == 0: return [], sr, None

    frame_len = int(sr * float(window_length))
    samples_list = []
    for i in range(recording.shape[0] // frame_len):
        start, end = i * frame_len, (i + 1) * frame_len
        samples_list.append((recording[start:end].astype(np.float32) / 32768.0, i * (frame_len / float(sr))))
    return samples_list, sr, recording

def voiced_frames(samples_list, sample_rate, analysis_params):
    """
    Voicing of each frame according to Parselmouth's pitch tracker, with the Analysis Settings
    f0 range and minimum RMS. Parselmouth (the reference) decides voicing so the formant comparison
    uses the same frames whichever pitch method is being benchmarked.
    """
    p = analysis_params or _benchmark_params()
    voiced = []
    for samples, _ in samples_list:
        res = get_pitch((samples * 32768.0).astype(np.int16), sample_rate, method='parselmouth',
                        min_f0=p['min_f0'], max_f0=p['max_f0'], min_rms_db=p['min_rms_db'],
                        min_confidence=p['min_confidence'])
        voiced.append(bool(res.get('voiced')))
    return voiced


def compare_formant_methods(samples_list, sample_rate, analysis_params, base_method="lpc", voiced=None):
    """
    Compare a formant method against Parselmouth on voiced frames only (as in LiveVowel, where
    formants are only measured in voiced frames). voiced: per-frame voicing from voiced_frames();
    computed here if not given.
    """
    raw_rows, n1, n2, n3, p1, p2, p3 = [], [], [], [], [], [], []
    nt, pt = [], []
    p = analysis_params or _benchmark_params()
    formant_kwargs = {
        'max_formant': int(p['max_formant']), 'n_formants_praat': p['n_formants'],
        'window_length': p['window_length'], 'time_step': p['time_step'],
        'pre_emphasis_hz': p['pre_emphasis_hz'], 'robust': p['robust_formants'],
    }
    if voiced is None:
        voiced = voiced_frames(samples_list, sample_rate, p)

    for (samples, ts), is_voiced in zip(samples_list, voiced):
        if not is_voiced:
            continue
        samples_int = (samples * 32768.0).astype(np.int16)

        t0 = time.perf_counter()
        nr = get_formants(samples_int, sample_rate, method=base_method, **formant_kwargs)
        nt.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        pr = get_formants(samples_int, sample_rate, method='parselmouth', **formant_kwargs)
        pt.append((time.perf_counter() - t0) * 1000)
        
        # Robust check for 'method' or 'method_used'
        p_meth = pr.get('method') or pr.get('method_used')
        n_meth = nr.get('method') or nr.get('method_used')

        if p_meth == 'parselmouth' and n_meth != 'parselmouth':
            nf, pf = nr.get('formants', [0,0,0]), pr.get('formants', [0,0,0])
            if nf[0] > 0 and pf[0] > 0:
                n1.append(nf[0]); n2.append(nf[1]); n3.append(nf[2])
                p1.append(pf[0]); p2.append(pf[1]); p3.append(pf[2])
                raw_rows.append([ts, nf[0], nf[1], nf[2], pf[0], pf[1], pf[2]])

    if not n1: return None, None
    
    # Range of the central 95% of per-frame times (2.5th to 97.5th percentiles)
    nt_array = np.array(nt)
    pt_array = np.array(pt)
    n_ci = (np.percentile(nt_array, 2.5), np.percentile(nt_array, 97.5))
    p_ci = (np.percentile(pt_array, 2.5), np.percentile(pt_array, 97.5))
    
    res = {
        'n_frames': len(n1),
        'timing': {
            'method_mean_ms': statistics.mean(nt),
            'method_ci_95': n_ci,
            'praat_mean_ms': statistics.mean(pt),
            'praat_ci_95': p_ci
        }
    }
    for i, (nv, pv) in enumerate([(n1, p1), (n2, p2), (n3, p3)], 1):
        na, pa = np.array(nv), np.array(pv)
        res[f'F{i}'] = {
            'correlation': np.corrcoef(na, pa)[0, 1] if len(na) > 1 else 0,
            'rmse_hz': np.sqrt(np.mean((na - pa)**2)),
            'mae_hz': np.mean(np.abs(na - pa)),
            'mean_rel_error_pct': np.mean(np.abs((na - pa) / pa)) * 100,
            'method_mean_hz': np.mean(na), 'praat_mean_hz': np.mean(pa), 'n_samples': len(na)
        }
    return res, raw_rows

def compare_pitch_methods(samples_list, sample_rate, analysis_params, base_method="autocorrelation"):
    raw_rows, nf0, pf0, nt, pt = [], [], [], [], []
    p = analysis_params or _benchmark_params()
    pitch_kwargs = {
        'min_f0': p['min_f0'], 'max_f0': p['max_f0'],
        'min_rms_db': p['min_rms_db'], 'min_confidence': p['min_confidence'],
    }

    for _, (samples, ts) in enumerate(samples_list):
        samples_int = (samples * 32768.0).astype(np.int16)

        t0 = time.perf_counter()
        nr = get_pitch(samples_int, sample_rate, method=base_method, **pitch_kwargs)
        nt.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        pr = get_pitch(samples_int, sample_rate, method='parselmouth', **pitch_kwargs)
        pt.append((time.perf_counter() - t0) * 1000)
        
        p_meth = pr.get('method') or pr.get('method_used')
        n_meth = nr.get('method') or nr.get('method_used')

        if p_meth == 'parselmouth' and n_meth != 'parselmouth':
            if nr.get('voiced') and pr.get('voiced') and nr.get('f0') and pr.get('f0'):
                nf0.append(nr['f0']); pf0.append(pr['f0'])
                raw_rows.append([ts, nr['f0'], pr['f0']])
    
    if not nf0: return None, None
    
    # Range of the central 95% of per-frame times (2.5th to 97.5th percentiles)
    nt_array = np.array(nt)
    pt_array = np.array(pt)
    n_ci = (np.percentile(nt_array, 2.5), np.percentile(nt_array, 97.5))
    p_ci = (np.percentile(pt_array, 2.5), np.percentile(pt_array, 97.5))
    
    na, pa = np.array(nf0), np.array(pf0)
    res = {
        'n_frames': len(nf0),
        'correlation': np.corrcoef(na, pa)[0, 1] if len(na) > 1 else 0,
        'rmse_hz': np.sqrt(np.mean((na - pa)**2)),
        'mae_hz': np.mean(np.abs(na - pa)),
        'mean_rel_error_pct': np.mean(np.abs((na - pa) / pa)) * 100,
        'method_mean_hz': np.mean(na), 'praat_mean_hz': np.mean(pa), 'n_samples': len(na),
        'timing': {
            'method_mean_ms': statistics.mean(nt),
            'method_ci_95': n_ci,
            'praat_mean_ms': statistics.mean(pt),
            'praat_ci_95': p_ci
        }
    }
    return res, raw_rows

def run_comprehensive_benchmark(formant_method="lpc", pitch_method="autocorrelation", output_dir=None,
                                duration_seconds=15.0, progress_callback=None, status_callback=None):
    """Run comprehensive benchmark comparing a formant method and a pitch method against Parselmouth.
    Includes both accuracy metrics and timing information, saves audio used for benchmarking.
    """
    if not _HAS_PARSELMOUTH: return None
    
    params = _benchmark_params()
    samples_list, sample_rate, recording = record_speech_samples(duration_seconds, progress_callback=progress_callback,
                                                                 params=params)
    if not samples_list: return None

    voiced = voiced_frames(samples_list, sample_rate, params)
    f_res, f_raw = compare_formant_methods(samples_list, sample_rate, params, formant_method, voiced=voiced)
    p_res, p_raw = compare_pitch_methods(samples_list, sample_rate, params, pitch_method)
    
    out = _resolve_output_dir(output_dir)
    
    # Save the recorded audio for verification
    if recording is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        audio_filename = f"benchmark_{timestamp}.wav"        
        
        with wave.open(os.path.join(out, audio_filename), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(recording.tobytes())

        if status_callback: status_callback(f"Saved audio: {audio_filename}")
    
    if f_raw:
        with open(os.path.join(out, "formant_raw_comparison.csv"), "w", newline="") as f:
            csv.writer(f).writerow(["timestamp"] + [f"{formant_method}_F{i}" for i in (1, 2, 3)]
                                   + ["praat_F1", "praat_F2", "praat_F3"])
            csv.writer(f).writerows(f_raw)

    if p_raw:
        with open(os.path.join(out, "pitch_raw_comparison.csv"), "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", f"{pitch_method}_f0", "praat_f0"])
            csv.writer(f).writerows(p_raw)

    report = ["# Comprehensive Benchmark Results\n\n"]
    report.append(f"**Duration:** {duration_seconds}s | **Methods:** formants {formant_method}, pitch {pitch_method}, each vs Parselmouth | **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    report.append(f"**Settings:** sample rate {sample_rate} Hz | frame {params['window_length'] * 1000:.0f} ms | "
                  f"max formant {params['max_formant']} Hz | formants {params['n_formants']} | "
                  f"f0 {params['min_f0']}-{params['max_f0']} Hz | min RMS {params['min_rms_db']} dB | "
                  f"min confidence {params['min_confidence']}\n\n")
    
    report.append(f"**Frames recorded:** {len(samples_list)} | **Voiced frames (Parselmouth voicing):** {sum(voiced)}\n\n")

    if f_res:
        report.append("## Formant Estimation Agreement\n\n")
        report.append("Voiced frames only (voicing decided by Parselmouth's pitch tracker with the f0 range and min RMS above), "
                      "excluding frames where either method found no F1.\n\n")
        report.append(f"**Number of frames analyzed:** {f_res.get('n_frames', 'N/A')}\n\n")
        report.append("| Formant | Correlation | RMSE (Hz) | MAE (Hz) | Rel. Error (%) |\n|---|---|---|---|---|\n")
        for f in ['F1', 'F2', 'F3']:
            r = f_res[f]
            report.append(f"| {f} | {r['correlation']:.4f} | {r['rmse_hz']:.1f} | {r['mae_hz']:.1f} | {r['mean_rel_error_pct']:.2f} |\n")
        report.append("\n")

    if p_res:
        report.append("## Pitch ($F_0$) Estimation Agreement\n\n")
        report.append(f"**Number of frames analyzed:** {p_res.get('n_frames', 'N/A')}\n\n")
        report.append("| Metric | Value |\n|---|---|\n| Correlation | {:.4f} |\n| RMSE | {:.1f} Hz |\n| MAE | {:.1f} Hz |\n| Rel. Error | {:.2f}% |\n\n".format(
            p_res['correlation'], p_res['rmse_hz'], p_res['mae_hz'], p_res['mean_rel_error_pct']))

    report.append("## Processing Speed Comparison\n\n")
    if f_res:
        f_ci = f_res['timing']['method_ci_95']
        p_ci = f_res['timing']['praat_ci_95']
        report.append(f"**Formant ({formant_method}):** {f_res['timing']['method_mean_ms']:.2f}ms (95% range: [{f_ci[0]:.2f}, {f_ci[1]:.2f}] ms)\n\n")
        report.append(f"**Formant (Parselmouth):** {f_res['timing']['praat_mean_ms']:.2f}ms (95% range: [{p_ci[0]:.2f}, {p_ci[1]:.2f}] ms)\n\n")
    if p_res:
        f_ci = p_res['timing']['method_ci_95']
        p_ci = p_res['timing']['praat_ci_95']
        report.append(f"**Pitch ({pitch_method}):** {p_res['timing']['method_mean_ms']:.2f}ms (95% range: [{f_ci[0]:.2f}, {f_ci[1]:.2f}] ms)\n\n")
        report.append(f"**Pitch (Parselmouth):** {p_res['timing']['praat_mean_ms']:.2f}ms (95% range: [{p_ci[0]:.2f}, {p_ci[1]:.2f}] ms)\n")

    with open(os.path.join(out, "comprehensive_benchmark.md"), 'w', encoding='utf-8') as f: f.writelines(report)
    if status_callback: status_callback(f"Done. Analyzed {len(f_raw) if f_raw else 0} formant frames and {len(p_raw) if p_raw else 0} pitch frames.")
    return os.path.join(out, "comprehensive_benchmark.md")