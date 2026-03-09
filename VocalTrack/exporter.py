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
    
    Args:
        filename (str): Output WAV filename
        samples (ndarray): Audio samples (int16)
        sample_rate (int): Sample rate in Hz
        normalize (bool): Scale audio to use full range. Defaults to True.
    """
    # Create output directory if it doesn't exist (mkdir -p behavior)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Convert samples to float64 for normalization calculations (prevents overflow)
    samples = samples.astype(np.float64)
    
    # Normalize to near-maximum amplitude
    # Check if normalization is enabled
    if normalize:
        # Find maximum absolute value in audio array
        max_val = np.abs(samples).max()
        # Only normalize if audio contains non-zero samples
        if max_val > 0:
            # Scale to 97% of max int16 range to avoid clipping
            # Calculate scaling factor (target amplitude / current max amplitude)
            scale_factor = (32767 * 0.97) / max_val
            # Apply scaling to all samples
            samples = samples * scale_factor
    
    # Clip values to int16 range and convert to int16 dtype for WAV format
    samples = np.clip(samples, -32768, 32767).astype(np.int16)
    
    # Open WAV file for writing in binary mode
    with wave.open(filename, 'wb') as wav_file:
        # Set number of audio channels (1 = mono)
        wav_file.setnchannels(1)  # Mono
        # Set sample width in bytes (2 bytes = 16-bit audio)
        wav_file.setsampwidth(2)  # 16-bit
        # Set sample rate (samples per second)
        wav_file.setframerate(sample_rate)
        # Write audio data as bytes to WAV file
        wav_file.writeframes(samples.tobytes())


def save_formants_csv(filename, formant_data):
    """Save timestamped formant analyses to CSV.
    
    Args:
        filename (str): Output CSV filename
        formant_data (list): List of dicts with keys:
            'time_ms', 'f0', 'f1', 'f2', 'f3', 'voicing', 'track_number'
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
        writer = csv.DictWriter(f, fieldnames=['time_ms', 'f0', 'f1', 'f2', 'f3', 'voicing', 'track_number'])
        # Write CSV header row with column names
        writer.writeheader()
        # Loop through each formant measurement dictionary
        for row in formant_data:
            # Extract f0 value from row dictionary (fixed: was 'f0_hz', should be 'f0')
            f0 = row.get('f0')
            # Extract voicing flag from row dictionary (True/False for voiced/unvoiced)
            voicing = row.get('voicing')
            # Only write voiced frames with valid f0 in acceptable range
            if voicing and f0 is not None and min_f0 <= f0 <= max_f0:
                # Write row dictionary as CSV line
                writer.writerow(row)


def save_pitch_csv(filename, pitch_data, min_f0=None, max_f0=None):
    """Save timestamped pitch analyses to CSV.

    Args:
        filename (str): Output CSV filename
        pitch_data (list): List of dicts with keys:
            'time_ms', 'f0', 'voicing', optionally 'track'
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

    # Determine columns: always include time_ms, f0, voicing; add 'track' if present in any row
    columns = ['time_ms', 'f0', 'voicing']
    if any('track' in row for row in pitch_data):
        columns = ['track'] + columns
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in pitch_data:
            f0 = row.get('f0')
            voicing = row.get('voicing')
            if voicing and f0 is not None and min_f0 <= f0 <= max_f0:
                writer.writerow(row)


def create_session_name(speaker_id='unknown'):
    """Generate session name with timestamp.
    
    Args:
        speaker_id (str): Speaker identifier
        
    Returns:
        str: Session name like "speaker_2026-01-29_143022"
    """
    # Get current time and format as YYYY-MM-DD_HHMMSS string
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    # Combine speaker ID with timestamp using underscore separator
    return f"{speaker_id}_{timestamp}"
