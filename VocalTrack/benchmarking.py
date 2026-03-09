"""
Benchmarking utilities for VocalTrack analysis methods.
Consolidated accuracy and timing reports with raw data CSV exports.
"""

import time
import os
import sys
import numpy as np
import statistics
import logging
import csv
from scipy.io import wavfile
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

def record_speech_samples(duration_seconds=15.0, sample_rate=10000, 
                          window_length=0.06, progress_callback=None, status_callback=None):  
    analysis_config = config.ANALYSIS_CONFIG.copy()
    analysis_config.update({'max_formant': 5000, 'formants': False, 'chunk_ms': 20, 'number_of_chunks': 3}) 
    
    processor = AudioProcessor(
        chunk_ms=20, number_of_chunks=3, analysis_config=analysis_config,
        raw_queue_maxsize=2000, analyzed_queue_maxsize=2000
    )
    
    processor.start()    
    processor.start_recording()    
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < duration_seconds:
        if progress_callback:
            progress_callback(min((time.perf_counter() - start_time) / duration_seconds, 1.0))
        time.sleep(0.01)
    
    processor.stop_recording()
    recording = processor.get_recording()
    processor.stop()
    
    if recording is None or recording.size == 0: return [], sample_rate, None
    
    sr = processor.sample_rate
    frame_len = int(sr * float(window_length))
    samples_list = []
    for i in range(recording.shape[0] // frame_len):
        start, end = i * frame_len, (i + 1) * frame_len
        samples_list.append((recording[start:end].astype(np.float32) / 32768.0, i * (frame_len / float(sr))))
    return samples_list, sr, recording

def compare_formant_methods(samples_list, sample_rate, analysis_params, base_method="native"):
    raw_rows, n1, n2, n3, p1, p2, p3 = [], [], [], [], [], [], []
    nt, pt = [], []
    
    for _, (samples, ts) in enumerate(samples_list):
        samples_int = (samples * 32768.0).astype(np.int16)
        
        t0 = time.perf_counter()
        nr = get_formants(samples_int, sample_rate, method=base_method)
        nt.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        pr = get_formants(samples_int, sample_rate, method='parselmouth')
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
    
    # Calculate 95% confidence intervals using percentiles
    nt_array = np.array(nt)
    pt_array = np.array(pt)
    n_ci = (np.percentile(nt_array, 2.5), np.percentile(nt_array, 97.5))
    p_ci = (np.percentile(pt_array, 2.5), np.percentile(pt_array, 97.5))
    
    res = {
        'n_frames': len(n1),
        'timing': {
            'native_mean_ms': statistics.mean(nt),
            'native_ci_95': n_ci,
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
            'native_mean_hz': np.mean(na), 'praat_mean_hz': np.mean(pa), 'n_samples': len(na)
        }
    return res, raw_rows

def compare_pitch_methods(samples_list, sample_rate, analysis_params, base_method="native"):
    raw_rows, nf0, pf0, nt, pt = [], [], [], [], []
    
    for _, (samples, ts) in enumerate(samples_list):
        samples_int = (samples * 32768.0).astype(np.int16)
        
        t0 = time.perf_counter()
        nr = get_pitch(samples_int, sample_rate, method=base_method)
        nt.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        pr = get_pitch(samples_int, sample_rate, method='parselmouth')
        pt.append((time.perf_counter() - t0) * 1000)
        
        p_meth = pr.get('method') or pr.get('method_used')
        n_meth = nr.get('method') or nr.get('method_used')

        if p_meth == 'parselmouth' and n_meth != 'parselmouth':
            if nr.get('voiced') and pr.get('voiced') and nr.get('f0') and pr.get('f0'):
                nf0.append(nr['f0']); pf0.append(pr['f0'])
                raw_rows.append([ts, nr['f0'], pr['f0']])
    
    if not nf0: return None, None
    
    # Calculate 95% confidence intervals using percentiles
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
        'native_mean_hz': np.mean(na), 'praat_mean_hz': np.mean(pa), 'n_samples': len(na),
        'timing': {
            'native_mean_ms': statistics.mean(nt),
            'native_ci_95': n_ci,
            'praat_mean_ms': statistics.mean(pt),
            'praat_ci_95': p_ci
        }
    }
    return res, raw_rows

def run_comprehensive_benchmark(base_method="native", output_dir=None, duration_seconds=15.0, progress_callback=None, status_callback=None):
    """Run comprehensive benchmark comparing native/custom methods against Parselmouth.
    Includes both accuracy metrics and timing information, saves audio used for benchmarking.
    """
    if not _HAS_PARSELMOUTH: return None
    
    samples_list, sample_rate, recording = record_speech_samples(duration_seconds, progress_callback=progress_callback, status_callback=status_callback)
    if not samples_list: return None

    f_res, f_raw = compare_formant_methods(samples_list, sample_rate, {}, base_method)
    p_res, p_raw = compare_pitch_methods(samples_list, sample_rate, {}, base_method)
    
    out = _resolve_output_dir(output_dir)
    
    # Save the recorded audio for verification
    if recording is not None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        audio_filename = f"benchmark_{timestamp}.wav"
        wavfile.write(os.path.join(out, audio_filename), sample_rate, recording)
        if status_callback: status_callback(f"Saved audio: {audio_filename}")
    
    if f_raw:
        with open(os.path.join(out, "formant_raw_comparison.csv"), "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "nF1", "nF2", "nF3", "pF1", "pF2", "pF3"])
            csv.writer(f).writerows(f_raw)

    if p_raw:
        with open(os.path.join(out, "pitch_raw_comparison.csv"), "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "native_f0", "praat_f0"])
            csv.writer(f).writerows(p_raw)

    report = ["# Comprehensive Benchmark Results\n\n"]
    report.append(f"**Duration:** {duration_seconds}s | **Method:** {base_method} vs Parselmouth | **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    if f_res:
        report.append("## Formant Estimation Agreement\n\n")
        report.append(f"**Number of frames analyzed:** {f_res.get('n_frames', 'N/A')}\n\n")
        report.append("| Formant | Correlation | RMSE (Hz) | MAE (Hz) | Rel. Error (%) |\n|---|---|---|---|---|\n")
        for f in ['F1', 'F2', 'F3']:
            r = f_res[f]
            report.append(f"| {f} | {r['correlation']:.4f} | {r['rmse_hz']:.1f} | {r['mae_hz']:.1f} | {r['mean_rel_error_pct']:.2f} |\n")
        report.append("\n")

    if p_res:
        report.append(f"## Pitch ($F_0$) Estimation Agreement\n\n")
        report.append(f"**Number of frames analyzed:** {p_res.get('n_frames', 'N/A')}\n\n")
        report.append("| Metric | Value |\n|---|---|\n| Correlation | {:.4f} |\n| RMSE | {:.1f} Hz |\n| MAE | {:.1f} Hz |\n| Rel. Error | {:.2f}% |\n\n".format(
            p_res['correlation'], p_res['rmse_hz'], p_res['mae_hz'], p_res['mean_rel_error_pct']))

    report.append("## Processing Speed Comparison\n\n")
    if f_res:
        f_ci = f_res['timing']['native_ci_95']
        p_ci = f_res['timing']['praat_ci_95']
        report.append(f"**Formant ({base_method}):** {f_res['timing']['native_mean_ms']:.2f}ms (95% CI: [{f_ci[0]:.2f}, {f_ci[1]:.2f}] ms)\n\n")
        report.append(f"**Formant (Parselmouth):** {f_res['timing']['praat_mean_ms']:.2f}ms (95% CI: [{p_ci[0]:.2f}, {p_ci[1]:.2f}] ms)\n\n")
    if p_res:
        f_ci = p_res['timing']['native_ci_95']
        p_ci = p_res['timing']['praat_ci_95']
        report.append(f"**Pitch ({base_method}):** {p_res['timing']['native_mean_ms']:.2f}ms (95% CI: [{f_ci[0]:.2f}, {f_ci[1]:.2f}] ms)\n\n")
        report.append(f"**Pitch (Parselmouth):** {p_res['timing']['praat_mean_ms']:.2f}ms (95% CI: [{p_ci[0]:.2f}, {p_ci[1]:.2f}] ms)\n")

    with open(os.path.join(out, "comprehensive_benchmark.md"), 'w', encoding='utf-8') as f: f.writelines(report)
    if status_callback: status_callback(f"Done. Analyzed {len(f_raw) if f_raw else 0} formant frames and {len(p_raw) if p_raw else 0} pitch frames.")
    return os.path.join(out, "comprehensive_benchmark.md")