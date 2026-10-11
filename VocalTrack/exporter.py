# Import os module for file and directory operations
import os
# Import csv module for writing CSV formatted data files
import csv
# Import wave module for writing WAV audio files
import wave
# Import numpy for array processing and data type conversions
import numpy as np
# Import datetime for generating timestamps in filenames
from datetime import datetime
# Import config module for accessing analysis parameters
from . import config


def save_wav(filename, samples, sample_rate, normalize=True):
    """Save audio samples to WAV file.

    The audio is scaled and written one block at a time, so saving a long recording needs
    little memory beyond the recording itself.

    Args:
        filename (str): Output WAV filename
        samples (ndarray or list of ndarray): Audio samples (int16). A list of arrays is written
            one after the other, as a single recording.
        sample_rate (int): Sample rate in Hz
        normalize (bool): Scale audio to use full range. Defaults to True.
    """
    # Create output directory if it doesn't exist (mkdir -p behavior)
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    arrays = [np.asarray(a) for a in (samples if isinstance(samples, (list, tuple)) else [samples])]

    # Normalize to near-maximum amplitude
    # Check if normalization is enabled
    scale_factor = None
    if normalize:
        # Find maximum absolute value in the audio
        max_val = max((max(float(a.max()), -float(a.min())) for a in arrays if a.size), default=0.0)
        # Only normalize if audio contains non-zero samples
        if max_val > 0:
            # Scale to 97% of max int16 range to avoid clipping
            # Calculate scaling factor (target amplitude / current max amplitude)
            scale_factor = (32767 * 0.97) / max_val

    # One second of audio is converted and written at a time
    block_size = max(int(sample_rate), 1)

    # Open WAV file for writing in binary mode
    with wave.open(filename, 'wb') as wav_file:
        # Set number of audio channels (1 = mono)
        wav_file.setnchannels(1)  # Mono
        # Set sample width in bytes (2 bytes = 16-bit audio)
        wav_file.setsampwidth(2)  # 16-bit
        # Set sample rate (samples per second)
        wav_file.setframerate(sample_rate)
        for a in arrays:
            for start in range(0, a.size, block_size):
                # Convert the block to float64 for the scaling (prevents overflow)
                block = a[start:start + block_size].astype(np.float64)
                if scale_factor is not None:
                    block *= scale_factor
                # Clip values to int16 range, convert to int16 for WAV format, and write the bytes
                wav_file.writeframes(np.clip(block, -32768, 32767, out=block).astype(np.int16).tobytes())


def save_formants_csv(filename, formant_data):
    """Save timestamped formant analyses to CSV.

    Args:
        filename (str): Output CSV filename
        formant_data (list): List of dicts with keys:
            'time_ms', 'f0', 'f1', 'f1_smoothed', 'f2', 'f2_smoothed', 'f3', 'voicing', 'track_number'
    """
    # Create output directory if it doesn't exist (mkdir -p behavior)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Return early if no data to save (empty list)
    if not formant_data:
        return
    
    # Get minimum f0 threshold from config (default 0 if not specified)
    min_f0 = config.ANALYSIS_CONFIG.get('min_f0', 0)
    # Get maximum f0 threshold from config (default infinity if not specified)
    max_f0 = config.ANALYSIS_CONFIG.get('max_f0', float('inf'))

    # Open CSV file for writing with UTF-8 encoding
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        # Create CSV dict writer with specified column names
        writer = csv.DictWriter(f, fieldnames=['time_ms', 'f0', 'f1', 'f1_smoothed', 'f2', 'f2_smoothed', 'f3', 'voicing', 'track_number'], extrasaction='ignore')
        # Write CSV header row with column names
        writer.writeheader()
        for row in formant_data:
            # Extract f0 value from row dictionary (fixed: was 'f0_hz', should be 'f0')
            f0 = row.get('f0')
            # Extract voicing flag from row dictionary (True/False for voiced/unvoiced)
            voicing = row.get('voicing')
            # Only write voiced frames with valid f0 in acceptable range
            if voicing and f0 is not None and min_f0 <= f0 <= max_f0:
                row_out = row.copy()
                if 'f1_smoothed' in row_out and row_out['f1_smoothed'] is not None:
                    row_out['f1_smoothed'] = int(round(row_out['f1_smoothed']))
                if 'f2_smoothed' in row_out and row_out['f2_smoothed'] is not None:
                    row_out['f2_smoothed'] = int(round(row_out['f2_smoothed']))
                # Write row dictionary as CSV line
                writer.writerow(row_out)


def save_pitch_csv(filename, pitch_data, min_f0=None, max_f0=None):
    """Save timestamped pitch analyses to CSV.

    Args:
        filename (str): Output CSV filename
        pitch_data (list): List of dicts with keys:
            'time_ms', 'f0', 'f0_smoothed', 'voicing', optionally 'track'
    """
    # Create output directory if it doesn't exist (mkdir -p behavior)
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Return early if no data to save (empty list)
    if not pitch_data:
        return

    # Use config value if min_f0 not provided as argument
    if min_f0 is None:
        # Get minimum f0 threshold from config (default 0 if not specified)
        min_f0 = config.ANALYSIS_CONFIG.get('min_f0', 0)
    # Use config value if max_f0 not provided as argument
    if max_f0 is None:
        # Get maximum f0 threshold from config (default infinity if not specified)
        max_f0 = config.ANALYSIS_CONFIG.get('max_f0', float('inf'))

    # Determine columns: always include time_ms, f0, f0_smoothed, voicing; add 'track' if present in any row
    columns = ['time_ms', 'f0', 'f0_smoothed', 'voicing']
    if any('track' in row for row in pitch_data):
        columns = ['track'] + columns
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for row in pitch_data:
            f0 = row.get('f0')
            voicing = row.get('voicing')
            if voicing and f0 is not None and min_f0 <= f0 <= max_f0:
                writer.writerow(row)


_issued_session_names = set()  # Names already handed out in this run


def create_session_name(speaker_id='unknown'):
    """Generate a unique session name with timestamp.

    Timestamps have 1-second resolution, so a second session started within the same second
    gets a numeric suffix instead of overwriting the first session's files.

    Args:
        speaker_id (str): Speaker identifier

    Returns:
        str: Session name like "speaker_2026-01-29_143022" (or "speaker_2026-01-29_143022_2")
    """
    # Get current time and format as YYYY-MM-DD_HHMMSS string
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    # Combine speaker ID with timestamp using underscore separator
    base_name = f"{speaker_id}_{timestamp}"
    name, suffix = base_name, 2
    while name in _issued_session_names:
        name = f"{base_name}_{suffix}"
        suffix += 1
    _issued_session_names.add(name)
    return name
