#!/usr/bin/env python3
"""Beat detection from music track using librosa, or manual timestamps."""

import sys
import os
import json
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

import librosa
import numpy as np


PRE_BEAT_OFFSET_FRAMES = 2  # Cut 2 frames early for perceived sync
PRE_BEAT_OFFSET_SEC = PRE_BEAT_OFFSET_FRAMES / 30.0  # ~0.067s at 30fps


def detect_beats(audio_path):
    """Extract audio, detect beats and onsets with strength classification."""
    os.makedirs(config.INTERMEDIATES_DIR, exist_ok=True)
    wav_path = os.path.join(config.INTERMEDIATES_DIR, "music_temp.wav")

    # Extract audio to WAV via ffmpeg
    print("Extracting audio...")
    subprocess.run([
        config.FFMPEG_BIN, "-y", "-i", audio_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
        wav_path,
    ], check=True, capture_output=True)

    # Load with librosa
    print("Loading audio...")
    y, sr = librosa.load(wav_path, sr=22050)

    # Beat tracking
    print("Detecting beats...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Onset detection (finer transients — hi-hats, snares)
    print("Detecting onsets...")
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, onset_envelope=onset_env)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

    # Beat strength classification
    print("Classifying beat strengths...")
    beat_strengths = []
    for bf in beat_frames:
        if bf < len(onset_env):
            beat_strengths.append(float(onset_env[bf]))
        else:
            beat_strengths.append(0.0)

    # Normalize strengths to 0-1
    max_strength = max(beat_strengths) if beat_strengths else 1.0
    if max_strength > 0:
        beat_strengths = [s / max_strength for s in beat_strengths]

    # Classify: strong (top 40%), medium (next 30%), weak (bottom 30%)
    if beat_strengths:
        sorted_s = sorted(beat_strengths, reverse=True)
        strong_thresh = sorted_s[int(len(sorted_s) * 0.4)] if len(sorted_s) > 2 else 0.5
        medium_thresh = sorted_s[int(len(sorted_s) * 0.7)] if len(sorted_s) > 2 else 0.25
    else:
        strong_thresh, medium_thresh = 0.5, 0.25

    beat_classes = []
    for s in beat_strengths:
        if s >= strong_thresh:
            beat_classes.append("strong")
        elif s >= medium_thresh:
            beat_classes.append("medium")
        else:
            beat_classes.append("weak")

    # Pre-beat adjusted times (2 frames early for visual anticipation)
    adjusted_beats = [max(0, t - PRE_BEAT_OFFSET_SEC) for t in beat_times]

    # Clean up temp file
    if os.path.exists(wav_path):
        os.remove(wav_path)

    tempo_val = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
    print(f"  Strong beats: {beat_classes.count('strong')}, Medium: {beat_classes.count('medium')}, Weak: {beat_classes.count('weak')}")
    return {
        "tempo": tempo_val,
        "beats": [round(t, 3) for t in beat_times],
        "beats_adjusted": [round(t, 3) for t in adjusted_beats],
        "beat_strengths": [round(s, 3) for s in beat_strengths],
        "beat_classes": beat_classes,
        "onsets": [round(t, 3) for t in onset_times],
        "source": "auto",
        "audio_file": os.path.basename(audio_path),
    }


def manual_beats(timestamps):
    """Create beat map from manually provided timestamps."""
    times = [float(t) for t in timestamps]
    if len(times) >= 2:
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        avg_interval = sum(intervals) / len(intervals)
        tempo = 60.0 / avg_interval if avg_interval > 0 else 0
    else:
        tempo = 0

    return {
        "tempo": round(tempo, 1),
        "beats": [round(t, 3) for t in times],
        "onsets": [round(t, 3) for t in times],
        "source": "manual",
    }


def main():
    parser = argparse.ArgumentParser(description="Detect beats in music track")
    parser.add_argument("audio", nargs="?", help="Path to audio/video file")
    parser.add_argument("--manual", nargs="+", type=float,
                        help="Manual beat timestamps in seconds")
    parser.add_argument("--output", default=os.path.join(config.ASSETS_DIR, "beat_map.json"),
                        help="Output JSON path")
    args = parser.parse_args()

    if args.manual:
        print(f"Using {len(args.manual)} manual beat timestamps")
        beat_map = manual_beats(args.manual)
    elif args.audio:
        print(f"Analyzing: {args.audio}")
        beat_map = detect_beats(args.audio)
    else:
        parser.error("Provide an audio file or --manual timestamps")
        return

    with open(args.output, "w") as f:
        json.dump(beat_map, f, indent=2)

    print(f"\nTempo: ~{beat_map['tempo']:.0f} BPM")
    print(f"Beats: {len(beat_map['beats'])} timestamps")
    print(f"Onsets: {len(beat_map['onsets'])} timestamps")
    print(f"Saved beat map to: {args.output}")


if __name__ == "__main__":
    main()
