"""Generate a hip-hop beat track (~130 BPM, 45s) as a placeholder for 'Do the John Wall'."""

import numpy as np
import struct
import wave
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "assets", "music", "do_the_john_wall.wav")
SAMPLE_RATE = 44100
BPM = 130
DURATION = 45  # seconds
BEAT_SEC = 60.0 / BPM


def sine(freq, duration, sr=SAMPLE_RATE, amp=0.3):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return amp * np.sin(2 * np.pi * freq * t)


def decay_env(length, decay=0.15):
    t = np.linspace(0, 1, length, endpoint=False)
    return np.exp(-t / decay)


def kick(dur=0.15):
    sr = SAMPLE_RATE
    n = int(sr * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    # Pitch sweep from 150Hz down to 50Hz
    freq = 150 * np.exp(-t * 20) + 50
    phase = np.cumsum(2 * np.pi * freq / sr)
    sig = 0.7 * np.sin(phase) * decay_env(n, 0.08)
    return sig


def snare(dur=0.12):
    sr = SAMPLE_RATE
    n = int(sr * dur)
    noise = np.random.randn(n) * 0.3
    tone = sine(200, dur, amp=0.2)[:n]
    env = decay_env(n, 0.05)
    return (noise + tone) * env


def hihat(dur=0.05):
    n = int(SAMPLE_RATE * dur)
    noise = np.random.randn(n) * 0.15
    env = decay_env(n, 0.02)
    return noise * env


def bass_note(freq=55, dur=0.2):
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    sig = 0.4 * np.sin(2 * np.pi * freq * t)
    env = decay_env(n, 0.12)
    return sig * env


def place(output, sound, pos_samples):
    end = pos_samples + len(sound)
    if end > len(output):
        end = len(output)
        sound = sound[:end - pos_samples]
    output[pos_samples:end] += sound


def main():
    total_samples = int(SAMPLE_RATE * DURATION)
    track = np.zeros(total_samples, dtype=np.float64)
    beat_samples = int(BEAT_SEC * SAMPLE_RATE)
    total_beats = int(DURATION / BEAT_SEC)

    # Drop region: beats 32-48 and 64-80 (higher energy)
    drop_beats = set(range(32, 49)) | set(range(64, 81))

    for b in range(total_beats):
        pos = b * beat_samples
        # Kick on every beat
        place(track, kick(), pos)
        # Snare on beats 2 and 4 (of each 4-beat bar)
        if b % 4 in (1, 3):
            place(track, snare(), pos)
        # Hi-hat on every 8th note
        place(track, hihat(), pos)
        place(track, hihat(), pos + beat_samples // 2)
        # Bass on beat 1 of each bar
        if b % 4 == 0:
            place(track, bass_note(55, BEAT_SEC * 0.8), pos)
        # Extra energy in drop regions
        if b in drop_beats:
            place(track, bass_note(55, BEAT_SEC * 0.4), pos + beat_samples // 2)
            if b % 2 == 0:
                place(track, snare(0.08), pos + beat_samples // 4)

    # Normalize
    peak = np.max(np.abs(track))
    if peak > 0:
        track = track / peak * 0.9

    # Convert to 16-bit PCM
    pcm = (track * 32767).astype(np.int16)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with wave.open(OUTPUT, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())

    print(f"Generated beat track: {OUTPUT} ({DURATION}s, {BPM} BPM)")


if __name__ == "__main__":
    main()
