"""Map downloaded video clips onto the beat-grid cut schedule."""

import random
from moviepy.editor import VideoFileClip


def load_clips(file_paths: list[str]) -> list[VideoFileClip]:
    """
    Open each MP4 without its audio track (music track is used instead).
    Returns a list of VideoFileClip objects.
    """
    clips = []
    for path in file_paths:
        try:
            clip = VideoFileClip(path, audio=False)
            clips.append(clip)
            print(f"[clip_selector] Loaded ({clip.duration:.1f}s): {path}")
        except Exception as exc:
            print(f"[clip_selector] Could not open {path}: {exc}")
    return clips


def assign_clips_to_beats(
    clips: list[VideoFileClip],
    cut_points: list[float],
    seed: int = 42,
) -> list[dict]:
    """
    Assign a source clip and a window within it to each beat slot.

    Each slot spans cut_points[i] → cut_points[i+1].
    Clips are shuffled and assigned in round-robin order.
    A random start offset is chosen so different parts of each clip are used.

    Returns a list of dicts:
        {
            "clip":          VideoFileClip,
            "src_start":     float,   offset into source clip
            "src_end":       float,
            "slot_start":    float,   absolute position in the final edit
            "slot_end":      float,
            "slot_duration": float,
            "slow_mo":       bool,    filled in by mark_slowmo_clips()
        }
    """
    if not clips:
        raise ValueError("No clips loaded — check downloads/ directory.")

    rng = random.Random(seed)
    shuffled = clips[:]
    rng.shuffle(shuffled)

    assignments = []
    clip_index = 0

    for i in range(len(cut_points) - 1):
        slot_start = cut_points[i]
        slot_end = cut_points[i + 1]
        slot_duration = slot_end - slot_start

        clip = shuffled[clip_index % len(shuffled)]
        clip_index += 1

        # Pick a random window inside the source clip for variety
        max_offset = max(0.0, clip.duration - slot_duration)
        src_start = rng.uniform(0, max_offset) if max_offset > 0 else 0.0
        src_end = src_start + slot_duration

        assignments.append({
            "clip": clip,
            "src_start": src_start,
            "src_end": src_end,
            "slot_start": slot_start,
            "slot_end": slot_end,
            "slot_duration": slot_duration,
            "slow_mo": False,
        })

    return assignments


def mark_slowmo_clips(
    assignments: list[dict],
    drop_regions: list[tuple[float, float]],
) -> list[dict]:
    """
    Flag assignments whose slot overlaps with a drop region.
    These will receive slow-motion + extra zoom treatment.
    """
    for a in assignments:
        mid = (a["slot_start"] + a["slot_end"]) / 2
        for drop_start, drop_end in drop_regions:
            if drop_start <= mid <= drop_end:
                a["slow_mo"] = True
                break
    n_slowmo = sum(1 for a in assignments if a["slow_mo"])
    print(f"[clip_selector] {n_slowmo}/{len(assignments)} slots marked for slow-mo")
    return assignments
