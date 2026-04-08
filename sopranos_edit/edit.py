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
                   zoom_times, intro_duration=3.0, max_montage_seconds=12,
                   flash_every_n=0, duration_ramp=False, output_name="timeline_raw",
                   beat_step=2, music_start_offset=0.0):
    """
    Assemble edit matching TikTok reference style.

    Args:
        flash_every_n: Insert white flash every N cuts (0=disabled)
        duration_ramp: If True, start with shorter cuts and ramp up
        output_name: Base name for output file
        beat_step: Use every Nth beat (1=every beat, 2=every other, etc)
        music_start_offset: Start music from this offset in the track (seconds)
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

    print(f"\nBuilding timeline ({output_name})...")

    # --- Phase 1: Calm intro ---
    actual_intro_dur = min(intro_duration, intro_source.duration - intro_start)
    intro_seg = intro_source.subclipped(intro_start, intro_start + actual_intro_dur)
    intro_seg = fit_to_square(intro_seg)
    print(f"  Phase 1: Calm intro ({actual_intro_dur:.1f}s)")

    # --- Phase 2: Brief black flash ---
    black_flash = ColorClip(
        size=(720, 720),
        color=(0, 0, 0),
        duration=0.15,
    ).with_fps(config.FPS)

    # --- Phase 3: Rapid montage ---
    beat_drop_in_timeline = actual_intro_dur + 0.15

    # Build cut durations from beats using beat_step
    montage_durations = []
    elapsed = 0.0
    i = 0
    while i < len(beats) - beat_step and elapsed < max_montage_seconds:
        next_i = min(i + beat_step, len(beats) - 1)
        cut_dur = beats[next_i] - beats[i]
        if cut_dur < 0.1:
            i += beat_step
            continue
        montage_durations.append(cut_dur)
        elapsed += cut_dur
        i += beat_step

    # Apply duration ramp if enabled (shorter cuts early, longer cuts later)
    if duration_ramp and len(montage_durations) > 4:
        n = len(montage_durations)
        for j in range(n):
            # Scale from 0.7x at start to 1.3x at end
            scale = 0.7 + 0.6 * (j / (n - 1))
            montage_durations[j] *= scale

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

    # Build segments with optional flash transitions
    white_flash = None
    if flash_every_n > 0:
        white_flash = ColorClip(
            size=(720, 720),
            color=(255, 255, 255),
            duration=0.08,
        ).with_fps(config.FPS)

    montage_clips = []
    for seg_idx, (jump_pt, cut_dur) in enumerate(zip(jump_points, montage_durations)):
        seg_end = min(jump_pt + cut_dur + 0.05, src_duration - 0.1)
        seg = sopranos_clip.subclipped(jump_pt, seg_end)
        seg = fit_to_square(seg)
        montage_clips.append(seg)

        # Insert white flash between cuts
        if flash_every_n > 0 and (seg_idx + 1) % flash_every_n == 0 and seg_idx < num_segments - 1:
            montage_clips.append(white_flash)

    total_sopranos_dur = sum(s.duration for s in montage_clips if hasattr(s, 'duration'))
    print(f"  Phase 2: {num_segments} rapid-cut segments ({total_sopranos_dur:.1f}s)")
    print(f"  Beat drop at: {beat_drop_in_timeline:.1f}s")
    print(f"  Avg cut length: {total_sopranos_dur/num_segments:.2f}s")
    if flash_every_n > 0:
        flash_count = sum(1 for i in range(num_segments - 1) if (i + 1) % flash_every_n == 0)
        print(f"  Flash transitions: {flash_count}")

    sopranos_assembly = concatenate_videoclips(montage_clips, method="compose")
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

    music_end = min(music.duration, music_start_offset + total_sopranos_dur)
    music_trimmed = music.subclipped(music_start_offset, music_end).with_start(beat_drop_in_timeline)
    audio_clips.append(music_trimmed)

    if audio_clips:
        combined_audio = CompositeAudioClip(audio_clips)
        full_video = full_video.with_audio(combined_audio)

    total_duration = full_video.duration
    print(f"\n  Total duration: {total_duration:.1f}s")

    # --- Write intermediate ---
    os.makedirs(config.INTERMEDIATES_DIR, exist_ok=True)
    output_path = os.path.join(config.INTERMEDIATES_DIR, f"{output_name}.mp4")

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
        for frac in [0.15, 0.4, 0.65, 0.85]
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
