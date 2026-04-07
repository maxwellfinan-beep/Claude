"""Analyze a music track and return beat timestamps for edit synchronization."""

import numpy as np
import librosa


def analyze_beats(audio_path: str) -> dict:
    """
    Load audio and detect beat positions.

    Returns:
        {
            "tempo": float,           BPM
            "beat_times": np.ndarray, seconds for each beat
            "duration": float,        total track length in seconds
        }
    """
    print(f"[beat_detector] Analyzing beats: {audio_path}")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    duration = librosa.get_duration(y=y, sr=sr)

    # tempo may be a 0-d array in newer librosa versions
    tempo_val = float(np.atleast_1d(tempo)[0])
    print(f"[beat_detector] Tempo: {tempo_val:.1f} BPM, {len(beat_times)} beats, {duration:.1f}s total")

    return {"tempo": tempo_val, "beat_times": beat_times, "duration": duration}


def get_cut_points(beat_times: np.ndarray, subdivision: int, target_duration: float) -> list[float]:
    """
    Subsample beat_times by `subdivision` and trim to fit target_duration.

    subdivision=1 → cut on every beat  (fast, energetic)
    subdivision=2 → cut every 2nd beat (balanced, default)
    subdivision=4 → cut every 4th beat (slow, cinematic)

    Returns a list of absolute timestamps in seconds where cuts should occur,
    always starting at 0.0.
    """
    subsampled = beat_times[::subdivision]

    # Ensure we start from 0
    if len(subsampled) == 0 or subsampled[0] > 0.1:
        subsampled = np.concatenate([[0.0], subsampled])

    # Trim to target_duration
    subsampled = subsampled[subsampled <= target_duration]

    # Append the target end time as the final boundary
    if len(subsampled) == 0 or subsampled[-1] < target_duration:
        subsampled = np.append(subsampled, target_duration)

    return subsampled.tolist()


def get_drop_regions(audio_path: str, beat_times: np.ndarray) -> list[tuple[float, float]]:
    """
    Identify high-energy regions (chorus / drop) in the track.

    Uses onset strength envelope: windows with the highest density of strong
    onsets are treated as drop regions where slow-mo and extra FX fire.

    Returns a list of (start_sec, end_sec) tuples.
    """
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    times = librosa.times_like(onset_env, sr=sr)

    # Smooth envelope with a 1-second window
    window = int(sr / 512)  # ~1s of frames at hop_length=512
    kernel = np.ones(window) / window
    smoothed = np.convolve(onset_env, kernel, mode="same")

    threshold = np.percentile(smoothed, 80)  # top 20% energy = drop
    in_drop = smoothed >= threshold

    # Convert boolean mask to (start, end) intervals
    regions: list[tuple[float, float]] = []
    start_idx = None
    for i, val in enumerate(in_drop):
        if val and start_idx is None:
            start_idx = i
        elif not val and start_idx is not None:
            regions.append((float(times[start_idx]), float(times[i - 1])))
            start_idx = None
    if start_idx is not None:
        regions.append((float(times[start_idx]), float(times[-1])))

    # Merge regions that are closer than 2 beats apart
    if len(beat_times) >= 2:
        min_gap = float(np.median(np.diff(beat_times)) * 2)
    else:
        min_gap = 1.0

    merged: list[tuple[float, float]] = []
    for start, end in regions:
        if merged and start - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    print(f"[beat_detector] Found {len(merged)} drop region(s)")
    return merged
