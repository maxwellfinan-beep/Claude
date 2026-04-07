"""Map downloaded video clips onto the beat-grid cut schedule."""

import random
from moviepy import VideoFileClip


def load_clips(file_paths: list[str]) -> list[VideoFileClip]:
    """Open each MP4 without its audio track."""
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
    Assign a source clip and window to each beat slot.

    Returns list of dicts with keys:
        clip, src_start, src_end, slot_start, slot_end, slot_duration, slow_mo
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
    """Flag assignments whose slot midpoint falls within a drop region."""
    for a in assignments:
        mid = (a["slot_start"] + a["slot_end"]) / 2
        for drop_start, drop_end in drop_regions:
            if drop_start <= mid <= drop_end:
                a["slow_mo"] = True
                break
    n_slowmo = sum(1 for a in assignments if a["slow_mo"])
    print(f"[clip_selector] {n_slowmo}/{len(assignments)} slots marked for slow-mo")
    return assignments
