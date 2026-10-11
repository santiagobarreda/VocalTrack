# Import numpy for efficient array operations and statistical functions
import numpy  # NumPy handles array math for formant buffers
import math  # Math module for exponential and trigonometric calculations
from . import config  # Import configuration module for default audio settings


def _one_euro_step(x, x_prev, dx_prev, dt, min_cutoff, beta, dcutoff, velocity_power):
    """
    One step of the 1-Euro filter (Casiez, Roussel & Vogel 2012), with the velocity term raised
    to velocity_power (>1 snaps faster to fast changes).

    Args:
        x (float): New input value (log scale).
        x_prev (float): Previous filtered value.
        dx_prev (float): Previous filtered velocity.
        dt (float): Time since the previous value (s).

    Returns:
        tuple: (filtered value, filtered velocity)
    """
    def alpha(cutoff):
        # Exponential smoothing coefficient for a low-pass filter with this cutoff (Hz)
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    # Velocity (log Hz per second), smoothed with its own low-pass filter
    dx = (x - x_prev) / dt
    a_d = alpha(dcutoff)
    dx_hat = a_d * dx + (1.0 - a_d) * dx_prev
    # Cutoff rises with speed: little smoothing during fast changes, more when the value is steady
    cutoff = max(1e-6, min_cutoff + beta * (abs(dx_hat) ** velocity_power))
    a = alpha(cutoff)
    return a * x + (1.0 - a) * x_prev, dx_hat


class Smoother:
    """Smooths formant values using temporal continuity constraints.
    
    Maintains a rolling buffer of formant measurements and only outputs points
    when stability criteria are met (values consistent across frames, voicing present).
    Useful for filtering noise in real-time audio analysis. Also includes a 1-Euro filter 
    for adaptive smoothing of formant trajectories.
    
    """
    
    def __init__(self, memory_n=3, stability_threshold=0.15, skip_tolerance=2,
                 use_euro_filter=True, euro_min_cutoff=0.05, euro_beta=1.5,
                 euro_dcutoff=0.5, velocity_power=1.5, chunk_ms=None):
        """Initialize the smoother with empty buffers.

        Args:
            memory_n (int, optional): Memory buffer size. Defaults to 3.
            stability_threshold (float, optional): Max log-scale delta allowed. Defaults to 0.15.
            skip_tolerance (int, optional): Unstable frames allowed before reset. Defaults to 2.
            euro_min_cutoff (float, optional): Baseline cutoff for 1-Euro. Defaults to 0.05.
            euro_beta (float, optional): Responsiveness multiplier for 1-Euro. Defaults to 1.5.
            euro_dcutoff (float, optional): Velocity smoothing cutoff for 1-Euro. Defaults to 0.5.
            use_euro_filter (bool, optional): Apply 1-Euro temporal smoothing. Defaults to True.
            velocity_power (float, optional): Non-linear exponent for adaptive snap. Defaults to 1.5.
            chunk_ms (float, optional): Time between analysis frames in ms (one display frame in
                LiveVowel and LivePitch). Falls back to one frame of a 60 Hz display if not provided.
        """
        # Initialize rolling buffers for F1, F2, and f0 with ones (avoid log(0) errors)
        self.f1_history = numpy.full(memory_n, 1)  # F1 buffer (first formant history in log space)
        self.f2_history = numpy.full(memory_n, 1)  # F2 buffer (second formant history in log space)
        self.f0_history = numpy.full(memory_n, 1)  # f0 buffer (fundamental frequency history in log space)
        
        # Flag indicating whether current frame passes stability criteria and should be displayed
        self.use = False  # Set to True when formant track is stable enough to display
        # Smoothed F1 value for plotting (after all filtering stages)
        self.plot_f1 = 1.0  # Current F1 value to display on screen (Hz)
        # Smoothed F2 value for plotting (after all filtering stages)
        self.plot_f2 = 1.0  # Current F2 value to display on screen (Hz)
        # Number of previous frames to keep in memory for stability checking
        self.memory_n = memory_n  # Size of rolling buffer (more frames = stricter stability requirement)

        # Last known valid formant values (used when holding during brief instabilities)
        self.last_valid_f1 = 1.0  # Last stable F1 value (Hz), used for hold-unvoiced behavior
        self.last_valid_f2 = 1.0  # Last stable F2 value (Hz), used for hold-unvoiced behavior
        self.last_valid_f0 = 1.0  # Last stable f0 value (Hz), used for hold-unvoiced behavior
        
        # Maximum allowed log-scale difference between consecutive frames (e.g., 0.15 ≈ 16% change)
        self.stability_threshold = stability_threshold  # Lower values = stricter stability requirement
        # Number of consecutive unstable frames allowed before resetting track
        self.skip_tolerance = skip_tolerance  # Allows brief gaps in voicing without breaking track
        # Chunk duration (ms) for timing calculations in 1-Euro filter; falls back to one frame of a 60 Hz display
        self.chunk_ms = chunk_ms if chunk_ms is not None else config.chunk_ms_for_fps(60)
        
        # Current track identifier (starts at 0, increments when new stable track begins)
        self.track_number = 0  # Increments each time track resets after instability
        # True once the current track has ended (skip tolerance exceeded); the next stable frame starts a new track
        self.track_ended = True
        
        # Isolated state variables for formants (separate from pitch state)
        self.skipped = 0  # Counter for consecutive unstable formant frames
        self.valid_frames = 0  # Counter for consecutive valid voiced formant frames (warm-up)
        self._euro_prev_time = None  # Last timestamp for 1-Euro filter (formants)
        self._euro_x_prev = [0, 0, 0]  # Previous filtered values [F1, F2, f0] in log space
        self._euro_dx_prev = [0, 0, 0]  # Previous velocity estimates [dF1/dt, dF2/dt, df0/dt]
        
        # Isolated state variables for pitch (independent from formant smoothing)
        self.pitch_use = False  # Flag indicating pitch value is stable enough to display
        self.plot_f0 = 1.0  # Current f0 value for pitch-only displays (Hz)
        self.pitch_skipped = 0  # Counter for consecutive unstable pitch frames
        self.valid_pitch_frames = 0  # Counter for consecutive valid voiced pitch frames (warm-up)
        self._pitch_euro_prev_time = None  # Last timestamp for 1-Euro filter (pitch only)
        self._pitch_euro_x_prev = 1.0  # Previous filtered pitch value in log space
        self._pitch_euro_dx_prev = 0.0  # Previous pitch velocity estimate (df0/dt)

        self.use_euro_filter = use_euro_filter  # When False, skip 1-Euro step and use raw stable values

        # Parameterized 1-Euro filter constants (tune responsiveness vs smoothness)
        self.euro_min_cutoff = euro_min_cutoff  # Baseline cutoff frequency (Hz) - lower = smoother
        self.euro_beta = euro_beta  # Responsiveness to velocity - higher = more adaptive
        self.euro_dcutoff = euro_dcutoff  # Cutoff for velocity smoothing - lower = smoother velocity
        self.velocity_power = velocity_power  # Exponent for non-linear velocity influence (>1 = snap to fast changes)

    def _apply_1euro_filter_scalar(self, value):
        """Apply the 1-Euro filter to one pitch value (log scale), keeping pitch-only filter state.

        Args:
            value (float): Input value in log space (log(Hz + 1))

        Returns:
            float: Filtered value in log space
        """
        # First call: initialize filter state and return input value unchanged
        if self._pitch_euro_prev_time is None:
            self._pitch_euro_prev_time = 0  # Marks the filter as started
            self._pitch_euro_x_prev = value
            self._pitch_euro_dx_prev = 0.0
            return value

        # Time since the last accepted frame: one chunk, plus one chunk per skipped frame
        base_dt = self.chunk_ms / 1000.0
        dt = base_dt + (base_dt * self.pitch_skipped)
        x_hat, dx_hat = _one_euro_step(value, self._pitch_euro_x_prev, self._pitch_euro_dx_prev, dt,
                                       self.euro_min_cutoff, self.euro_beta, self.euro_dcutoff, self.velocity_power)
        self._pitch_euro_x_prev = x_hat
        self._pitch_euro_dx_prev = dx_hat
        return x_hat

    def _apply_1euro_filter(self, values):
        """Apply the 1-Euro filter to [F1, F2, f0] (log scale), each channel with its own state.

        Args:
            values (list): 3-element list [log(F1+1), log(F2+1), log(f0+1)]

        Returns:
            list: Filtered 3-element list in log space
        """
        # First call: initialize filter state and return input values unchanged
        if self._euro_prev_time is None:
            self._euro_prev_time = 0  # Marks the filter as started
            self._euro_x_prev = values.copy()
            self._euro_dx_prev = [0.0, 0.0, 0.0]
            return values

        # Time since the last accepted frame: one chunk, plus one chunk per skipped frame
        base_dt = self.chunk_ms / 1000.0
        dt = base_dt + (base_dt * self.skipped)
        out_vals = []
        for i, x in enumerate(values):
            x_hat, dx_hat = _one_euro_step(x, self._euro_x_prev[i], self._euro_dx_prev[i], dt,
                                           self.euro_min_cutoff, self.euro_beta, self.euro_dcutoff, self.velocity_power)
            out_vals.append(x_hat)
            self._euro_x_prev[i] = x_hat
            self._euro_dx_prev[i] = dx_hat
        return out_vals

    def smooth_pitch(self, sound, min_f0=None, max_f0=None):
        """Smooth pitch (f0) values without formant stability tracking.
        
        Manages a rolling buffer of pitch values and applies stability checks + 1-Euro filtering.
        Handles unvoiced frames, out-of-range values, and buffer warm-up period.
        
        Args:
            sound (Sound): Sound object with .f0 (Hz) and .voicing (bool) attributes
            min_f0 (float, optional): Minimum acceptable f0 in Hz (values below are rejected)
            max_f0 (float, optional): Maximum acceptable f0 in Hz (values above are rejected)
        
        Updates:
            self.plot_f0: Filtered f0 value to display (in Hz, not log)
            self.pitch_use: Boolean flag indicating if current f0 is trustworthy
            self.last_valid_f0: Most recent accepted f0 (fallback for bad frames)
        """
        # Store old history buffer (used for rollback if frame is rejected)
        f0_old = self.f0_history.copy()  # Backup current buffer state before modification

        # Update rolling buffer: add new value (log scale), remove oldest value
        self.f0_history = numpy.append(self.f0_history, numpy.log(sound.f0 + 1))  # Append log(f0+1) to end
        self.f0_history = numpy.delete(self.f0_history, 0)  # Remove first (oldest) element
        self.plot_f0 = numpy.log(sound.f0 + 1)  # Store current unfiltered value (log scale) as candidate

        # Check if input f0 is within acceptable user-specified range
        f0_value = float(sound.f0)  # Extract raw f0 in Hz
        in_range = True  # Assume valid unless proven otherwise
        if min_f0 is not None and f0_value < min_f0:  # f0 is too low
            in_range = False  # Reject as out of range
        if max_f0 is not None and f0_value > max_f0:  # f0 is too high
            in_range = False  # Reject as out of range

        # Warm-up counter logic: track consecutive voiced frames within valid range
        if sound.voicing and in_range:  # Frame is voiced AND in valid f0 range
            self.valid_pitch_frames = min(self.memory_n, self.valid_pitch_frames + 1)  # Increment counter (capped at memory_n)
        else:  # Frame is unvoiced OR out of range
            self.valid_pitch_frames = 0  # Reset warm-up counter immediately

        # Stability check: count consecutive frame-to-frame jumps exceeding threshold
        errors = 0  # Error counter for stability violations
        # Only run the sequential sanity check if we have a full buffer of real voice
        if self.valid_pitch_frames == self.memory_n:  # Buffer is fully warmed up (all frames voiced+in-range)
            for j in range(self.memory_n - 1):  # Check each adjacent pair in buffer
                # Count as error if: (1) jump > threshold, or (2) frame is silent (log(0+1)=0)
                errors += abs(self.f0_history[j] - self.f0_history[j + 1]) > self.stability_threshold or self.f0_history[j] == 0

        # CASE 1: Frame is mathematically stable and buffer is fully warmed up (ACCEPT)
        if self.valid_pitch_frames == self.memory_n and errors == 0:  # All checks passed
            self.pitch_use = True  # Mark f0 as trustworthy for plotting/export

            # Optionally apply 1-Euro filter to smooth trajectory in log space
            if self.use_euro_filter:
                self.plot_f0 = self._apply_1euro_filter_scalar(self.plot_f0)
            self.plot_f0 = numpy.exp(self.plot_f0) - 1  # Convert back to linear Hz for display
            self.last_valid_f0 = self.plot_f0  # Store as fallback for future bad frames
            self.pitch_skipped = 0  # Reset skip counter (stability is good)

        # CASE 2: Frame is valid and voicing, but buffer is still warming up (HOLD)
        elif self.valid_pitch_frames > 0 and self.valid_pitch_frames < self.memory_n:  # Warm-up phase
            self.plot_f0 = self.last_valid_f0  # Use previous valid f0 (don't update yet)
            self.pitch_use = False  # Mark as not trustworthy (still warming up)

        # CASE 3: Frame is unstable, unvoiced, or out of range (SKIP/RESET)
        else:  # Frame failed stability or range checks
            if self.pitch_skipped < self.skip_tolerance:  # Still in grace period
                self.pitch_skipped += 1  # Increment skip counter (allow brief glitches)
                self.f0_history = f0_old  # Rollback buffer (reject this frame's data)

                self.plot_f0 = self.last_valid_f0  # Use previous valid f0 (hold stable output)
                self.pitch_use = False  # Mark as not trustworthy
            else:  # Exceeded skip tolerance (trajectory is truly broken)
                self.pitch_skipped = 0  # Reset skip counter
                # Reset 1-Euro filter state (start fresh on next stable segment)
                self._pitch_euro_prev_time = None  # Clear time tracker
                self._pitch_euro_x_prev = 1.0  # Reset position to log(0+1)=0 → exp-1=0 Hz
                self._pitch_euro_dx_prev = 0.0  # Reset velocity estimate
                self.pitch_use = False  # Mark as not trustworthy

    def smooth_formants(self, sound):
        """Analyze formant stability and output smoothed values if stable.
        
        Manages 3 rolling buffers (F1, F2, f0) and applies joint stability checks.
        All three formants must be stable simultaneously before accepting the frame.
        Uses 1-Euro filter for smooth trajectories and tracks contiguous segments.
        
        Args:
            sound (Sound): Sound object with .f1, .f2, .f0 (Hz) and .voicing (bool)
        
        Updates:
            self.plot_f1, self.plot_f2, self.plot_f0: Filtered formant values (Hz)
            self.use: Boolean flag indicating if current formants are trustworthy
            self.track_number: Increments each time a new stable segment begins
        """
        # Store old history buffers (used for rollback if frame is rejected)
        f1_old = self.f1_history.copy()  # Backup F1 buffer before modification
        f2_old = self.f2_history.copy()  # Backup F2 buffer before modification
        f0_old = self.f0_history.copy()  # Backup f0 buffer before modification
        
        # Update rolling buffers: add new values (log scale), remove oldest values
        self.f1_history = numpy.append(self.f1_history, numpy.log(sound.f1 + 1))  # Add log(F1+1)
        self.f2_history = numpy.append(self.f2_history, numpy.log(sound.f2 + 1))  # Add log(F2+1)
        self.f0_history = numpy.append(self.f0_history, numpy.log(sound.f0 + 1))  # Add log(f0+1)

        self.f1_history = numpy.delete(self.f1_history, 0)  # Remove oldest F1 value
        self.f2_history = numpy.delete(self.f2_history, 0)  # Remove oldest F2 value
        self.f0_history = numpy.delete(self.f0_history, 0)  # Remove oldest f0 value

        # Store current unfiltered values (log scale) as candidates for filtering
        self.plot_f1 = numpy.log(sound.f1 + 1)  # Current F1 in log space
        self.plot_f2 = numpy.log(sound.f2 + 1)  # Current F2 in log space
        self.plot_f0 = numpy.log(sound.f0 + 1)  # Current f0 in log space
        
        # Warm-up counter logic: track consecutive voiced frames
        if sound.voicing:  # Frame has detected voicing (f0 is valid)
            self.valid_frames = min(self.memory_n, self.valid_frames + 1)  # Increment counter (capped at memory_n)
        else:  # Frame is unvoiced (no detectable pitch)
            self.valid_frames = 0  # Reset warm-up counter immediately

        # Joint stability check: count violations across ALL THREE formants (F1, F2, f0)
        errors = 0  # Error counter for stability violations
        # Only run the sequential sanity check if we have a full buffer of real voice
        if self.valid_frames == self.memory_n:  # Buffer is fully warmed up (all frames voiced)
            for j in range(self.memory_n - 1):  # Check each adjacent pair in buffers
                # f0 stability: count as error if jump > threshold OR value is silent (log(0+1)=0)
                errors += abs(self.f0_history[j] - self.f0_history[j + 1]) > self.stability_threshold or self.f0_history[j] == 0
                # F1 stability: count as error if jump > threshold OR value is silent
                errors += abs(self.f1_history[j] - self.f1_history[j + 1]) > self.stability_threshold or self.f1_history[j] == 0
                # F2 stability: count as error if jump > threshold OR value is silent
                errors += abs(self.f2_history[j] - self.f2_history[j + 1]) > self.stability_threshold or self.f2_history[j] == 0
        
        # CASE 1: Frame is mathematically stable and buffer is fully warmed up (ACCEPT)
        if self.valid_frames == self.memory_n and errors == 0:  # All three formants are stable

            # Track segment boundaries: increment track ID when starting a new stable region.
            # A brief glitch within skip tolerance continues the same track; once the track has
            # ended (tolerance exceeded), the next stable frame always starts a new one.
            if not self.use and (self.skipped == 0 or self.track_ended):
                self.track_number += 1  # New contiguous vowel segment begins
                self.track_ended = False
             
            self.use = True  # Mark formants as trustworthy for plotting/export
      
            # Optionally apply 1-Euro filter to all three formants jointly (in log space)
            if self.use_euro_filter:
                values = [self.plot_f1, self.plot_f2, self.plot_f0]  # Bundle into list
                self.plot_f1, self.plot_f2, self.plot_f0 = self._apply_1euro_filter(values)

            # Convert from log space back to linear Hz for display and storage
            self.plot_f1 = numpy.exp(self.plot_f1) - 1  # log(F1+1) → F1 in Hz
            self.plot_f2 = numpy.exp(self.plot_f2) - 1  # log(F2+1) → F2 in Hz
            self.plot_f0 = numpy.exp(self.plot_f0) - 1  # log(f0+1) → f0 in Hz

            # Store as fallback values for future bad frames
            self.last_valid_f1 = self.plot_f1  # Most recent stable F1
            self.last_valid_f2 = self.plot_f2  # Most recent stable F2
            self.last_valid_f0 = self.plot_f0  # Most recent stable f0

            self.skipped = 0  # Reset skip counter (stability is good)

        # CASE 2: Frame is valid and voicing, but buffer is still warming up (HOLD)
        elif self.valid_frames > 0 and self.valid_frames < self.memory_n:  # Warm-up phase
            self.plot_f1 = self.last_valid_f1  # Use previous valid F1 (don't update yet)
            self.plot_f2 = self.last_valid_f2  # Use previous valid F2 (don't update yet)
            self.plot_f0 = self.last_valid_f0  # Use previous valid f0 (don't update yet)
            self.use = False  # Mark as not trustworthy (still warming up)

        # CASE 3: Frame is unstable or unvoiced (SKIP/RESET)
        else:  # Frame failed stability checks or voicing detection
            if self.skipped < self.skip_tolerance:  # Still in grace period
                self.skipped += 1  # Increment skip counter (allow brief glitches)
                # Rollback all three buffers (reject this frame's data)
                self.f1_history = f1_old  # Restore F1 buffer
                self.f2_history = f2_old  # Restore F2 buffer
                self.f0_history = f0_old  # Restore f0 buffer

                # Hold previous valid formants (don't change display)
                self.plot_f1 = self.last_valid_f1  # Use previous F1
                self.plot_f2 = self.last_valid_f2  # Use previous F2
                self.plot_f0 = self.last_valid_f0  # Use previous f0
                
                self.use = False  # Mark as not trustworthy
            else:  # Exceeded skip tolerance (trajectory is truly broken)
                self.skipped = 0  # Reset skip counter
                self.track_ended = True  # Next stable frame begins a new track

                # Reset 1-Euro filter state (start fresh on next stable segment)
                self._euro_prev_time = None  # Clear time tracker
                self._euro_x_prev = [0, 0, 0]  # Reset positions to log(0+1)=0
                self._euro_dx_prev = [0, 0, 0]  # Reset velocity estimates

                self.use = False  # Mark as not trustworthy