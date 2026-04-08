#!/usr/bin/env python3
"""
Timeline assembly for 'You Never See It Coming' Sopranos edit.

Matches the @_klowy TikTok reference style:
  - Intro: calm Sopranos scene (from the show itself), ~3s
  - Beat drops: rapid cuts every ~0.5-1s jumping between iconic scenes
  - Hard cut to black at the end
  - Total: ~14-18s
  - Minimal effects, natural look

Output: assets/intermediates/timeline_raw.mp4 + project_state.json
"""

import sys
import os
import json
import argparse
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

os.environ["IMAGEIO_FFMPEG_EXE"] = config.FFMPEG_BIN

from moviepy import (
    VideoFileClip, AudioFileClip, ColorClip,
    concatenate_videoclips, CompositeAudioClip, vfx,
)


def fit_to_square(clip, size=720):
    """Scale and crop any clip to square (720x720) like TikTok reference."""
    clip_aspect = clip.w / clip.h

    if clip_aspect > 1.0:
        # Wider than tall — scale by height, crop sides
        new_h = size
        new_w = int(clip_aspect * new_h)
    else:
        # Taller than wide — scale by width, crop top/bottom
        new_w = size
        new_h = int(new_w / clip_aspect)

    clip = clip.resized((new_w, new_h))
    x1 = (new_w - size) // 2
    y1 = (new_h - size) // 2
    clip = clip.cropped(x1=x1, y1=y1, x2=x1 + size, y2=y1 + size)
    return clip


def build_timeline(intro_clip_path, sopranos_path, music_path, beat_map,
                   zoom_times, intro_duration=3.0, max_montage_seconds=12):
    """
    Assemble edit matching TikTok reference style.

    - Intro from the Sopranos clip itself (calm scene)
    - Then rapid cuts jumping around the compilation
    - Cuts every ~0.7-1s (not every single beat — every 2nd beat)
    - Hard cut to black at end
    """
    print("Loading clips...")
    sopranos_clip = VideoFileClip(sopranos_path)
    music = AudioFileClip(music_path)

    # Optionally load separate intro, or use start of Sopranos clip
    if intro_clip_path and intro_clip_path != sopranos_path:
        intro_source = VideoFileClip(intro_clip_path)
        # Skip first 10s to avoid YouTube title overlays
        intro_start = min(10.0, intro_source.duration - intro_duration - 1)
    else:
        intro_source = sopranos_clip
        intro_start = 0.0

    print(f"  sopranos: {os.path.basename(sopranos_path)} ({sopranos_clip.duration:.1f}s, {sopranos_clip.w}x{sopranos_clip.h})")
    print(f"  music: {os.path.basename(music_path)} ({music.duration:.1f}s)")

    beats = beat_map["beats"]
    if len(beats) < 4:
        print("Error: need at least 4 beats in beat map")
        sys.exit(1)

    print(f"\nBuilding timeline...")

    # --- Phase 1: Calm intro from the show (~3s) ---
    actual_intro_dur = min(intro_duration, intro_source.duration - intro_start)
    intro_seg = intro_source.subclipped(intro_start, intro_start + actual_intro_dur)
    intro_seg = fit_to_square(intro_seg)
    # Keep original audio for calm intro
    print(f"  Phase 1: Calm intro ({actual_intro_dur:.1f}s)")

    # --- Phase 2: Brief black flash (0.15s) ---
    black_flash = ColorClip(
        size=(720, 720),
        color=(0, 0, 0),
        duration=0.15,
    ).with_fps(config.FPS)

    # --- Phase 3: Rapid montage — every ~2nd beat for ~0.7-1s cuts ---
    beat_drop_in_timeline = actual_intro_dur + 0.15

    # Use every 2nd beat for slightly longer cuts (~0.8s at 144 BPM)
    montage_durations = []
    elapsed = 0.0
    i = 0
    while i < len(beats) - 2 and elapsed < max_montage_seconds:
        # Combine 2 beats into one cut duration
        cut_dur = beats[i + 2] - beats[i] if i + 2 < len(beats) else beats[i + 1] - beats[i]
        if cut_dur < 0.1:
            i += 2
            continue
        montage_durations.append(cut_dur)
        elapsed += cut_dur
        i += 2

    num_segments = len(montage_durations)

    # Generate jump points spread across the source
    src_duration = sopranos_clip.duration
    safe_start = 3.0
    safe_end = src_duration - 3.0

    jump_points = []
    spacing = (safe_end - safe_start) / (num_segments + 1)
    for idx in range(num_segments):
        base = safe_start + spacing * (idx + 1)
        jitter = random.uniform(-spacing * 0.25, spacing * 0.25)
        point = max(safe_start, min(safe_end - 2.0, base + jitter))
        jump_points.append(point)

    random.shuffle(jump_points)

    # Build segments
    sopranos_segments = []
    for jump_pt, cut_dur in zip(jump_points, montage_durations):
        seg_end = min(jump_pt + cut_dur + 0.05, src_duration - 0.1)
        seg = sopranos_clip.subclipped(jump_pt, seg_end)
        seg = fit_to_square(seg)
        sopranos_segments.append(seg)

    total_sopranos_dur = sum(s.duration for s in sopranos_segments)
    print(f"  Phase 2: {num_segments} rapid-cut segments ({total_sopranos_dur:.1f}s)")
    print(f"  Beat drop at: {beat_drop_in_timeline:.1f}s")
    print(f"  Avg cut length: {total_sopranos_dur/num_segments:.2f}s")

    sopranos_assembly = concatenate_videoclips(sopranos_segments, method="compose")
    sopranos_no_audio = sopranos_assembly.without_audio()

    # --- Assemble full video ---
    full_video = concatenate_videoclips(
        [intro_seg, black_flash, sopranos_no_audio],
        method="compose",
    )

    # --- Audio ---
    audio_clips = []
    if intro_seg.audio is not None:
        intro_audio = intro_seg.audio.with_start(0)
        audio_clips.append(intro_audio)

    music_dur = min(music.duration, total_sopranos_dur)
    music_trimmed = music.subclipped(0, music_dur).with_start(beat_drop_in_timeline)
    audio_clips.append(music_trimmed)

    if audio_clips:
        combined_audio = CompositeAudioClip(audio_clips)
        full_video = full_video.with_audio(combined_audio)

    total_duration = full_video.duration
    print(f"\n  Total duration: {total_duration:.1f}s")

    # --- Write intermediate ---
    os.makedirs(config.INTERMEDIATES_DIR, exist_ok=True)
    output_path = os.path.join(config.INTERMEDIATES_DIR, "timeline_raw.mp4")

    print(f"\nWriting intermediate...")
    full_video.write_videofile(
        output_path,
        fps=config.FPS,
        codec=config.CODEC,
        preset=config.PRESET,
        threads=config.THREADS,
        ffmpeg_params=["-crf", str(config.CRF_DRAFT)],
        logger="bar",
    )

    # --- Save project state ---
    auto_zoom_times = zoom_times if zoom_times else [
        round(beat_drop_in_timeline + total_sopranos_dur * frac, 2)
        for frac in [0.2, 0.5, 0.8]
    ]

    state = {
        "beat_drop_time": round(beat_drop_in_timeline, 3),
        "zoom_punch_times": auto_zoom_times,
        "title_appear_time": round(beat_drop_in_timeline, 3),
        "title_disappear_time": round(beat_drop_in_timeline + 2.0, 3),
        "total_duration": round(total_duration, 3),
        "intermediate_path": output_path,
        "beats_used": num_segments,
        "tempo": beat_map.get("tempo", 0),
    }
    config.save_state(state)

    # Cleanup
    if intro_source is not sopranos_clip:
        intro_source.close()
    sopranos_clip.close()
    music.close()

    print(f"\nSaved: {output_path}")
    return output_path, state


def main():
    parser = argparse.ArgumentParser(description="Assemble Sopranos edit timeline")
    parser.add_argument("--intro", default=None,
                        help="Path to intro clip (default: uses start of Sopranos clip)")
    parser.add_argument("--sopranos", required=True, help="Path to Sopranos compilation clip")
    parser.add_argument("--music", required=True, help="Path to music track")
    parser.add_argument("--beats", required=True, help="Path to beat_map.json")
    parser.add_argument("--zoom-times", nargs="*", type=float, default=[],
                        help="Timestamps for zoom punches (timeline-absolute)")
    parser.add_argument("--intro-duration", type=float, default=3.0,
                        help="Intro duration in seconds (default: 3.0)")
    parser.add_argument("--montage-length", type=float, default=12,
                        help="Max montage section length in seconds (default: 12)")
    args = parser.parse_args()

    with open(args.beats) as f:
        beat_map = json.load(f)

    build_timeline(
        intro_clip_path=args.intro or args.sopranos,
        sopranos_path=args.sopranos,
        music_path=args.music,
        beat_map=beat_map,
        zoom_times=args.zoom_times,
        intro_duration=args.intro_duration,
        max_montage_seconds=args.montage_length,
    )


if __name__ == "__main__":
    main()
