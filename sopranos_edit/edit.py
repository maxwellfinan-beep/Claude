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
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

os.environ["IMAGEIO_FFMPEG_EXE"] = config.FFMPEG_BIN

from moviepy import (
    VideoFileClip, AudioFileClip, ColorClip,
    concatenate_videoclips, CompositeAudioClip, vfx,
)

# --- Scene Detection & Smart Clip Selection ---

def _video_hash(path):
    """Quick hash of first 64KB for cache keying."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    h.update(str(os.path.getsize(path)).encode())
    return h.hexdigest()[:12]


def detect_scenes(video_path):
    """Detect natural scene boundaries using PySceneDetect."""
    cache_path = os.path.join(config.ASSETS_DIR, f"scenes_{_video_hash(video_path)}.json")
    if os.path.exists(cache_path):
        print(f"  Using cached scene data: {cache_path}")
        with open(cache_path) as f:
            return json.load(f)

    try:
        from scenedetect import detect, AdaptiveDetector
        print(f"  Running scene detection on {os.path.basename(video_path)}...")
        scene_list = detect(video_path, AdaptiveDetector(adaptive_threshold=4.5))
        scenes = []
        for scene in scene_list:
            start = scene[0].get_seconds()
            end = scene[1].get_seconds()
            scenes.append({"start": round(start, 3), "end": round(end, 3),
                           "duration": round(end - start, 3)})
        print(f"  Found {len(scenes)} scenes")
        with open(cache_path, "w") as f:
            json.dump(scenes, f, indent=2)
        return scenes
    except ImportError:
        print("  PySceneDetect not available, falling back to ffmpeg scene detection...")
        return detect_scenes_ffmpeg(video_path, cache_path)
    except Exception as e:
        print(f"  Scene detection failed ({e}), falling back to ffmpeg...")
        return detect_scenes_ffmpeg(video_path, cache_path)


def detect_scenes_ffmpeg(video_path, cache_path=None, max_analyze_sec=300):
    """Fallback scene detection using ffmpeg select filter.

    Limits analysis to max_analyze_sec to avoid timeouts on long clips.
    """
    import subprocess
    cmd = [
        config.FFMPEG_BIN, "-i", video_path,
        "-t", str(max_analyze_sec),  # limit analysis duration for long clips
        "-vf", "select='gt(scene,0.35)',showinfo",
        "-vsync", "vfr", "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    timestamps = [0.0]
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts = float(line.split("pts_time:")[1].split()[0])
                timestamps.append(pts)
            except (ValueError, IndexError):
                continue

    scenes = []
    for i in range(len(timestamps) - 1):
        s, e = timestamps[i], timestamps[i + 1]
        scenes.append({"start": round(s, 3), "end": round(e, 3),
                        "duration": round(e - s, 3)})
    if cache_path:
        with open(cache_path, "w") as f:
            json.dump(scenes, f, indent=2)
    return scenes


def score_segments_motion(video_path, scenes):
    """Score each scene by motion energy using frame differencing."""
    import subprocess
    import struct

    print(f"  Scoring {len(scenes)} segments by motion energy...")
    scored = []
    for scene in scenes:
        dur = scene["duration"]
        if dur < 0.3 or dur > 10.0:
            scored.append({**scene, "motion_score": 0.0})
            continue

        # Sample 3 frames from the segment using ffmpeg
        mid = scene["start"] + dur / 2
        cmd = [
            config.FFMPEG_BIN, "-ss", str(scene["start"]),
            "-i", video_path, "-t", str(min(dur, 3.0)),
            "-vf", "tblend=all_mode=difference,blackframe=amount=0:threshold=32",
            "-f", "null", "-"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # Count non-black frames as motion indicator
            motion_frames = result.stderr.count("Parsed_blackframe")
            total_lines = max(1, result.stderr.count("frame="))
            # Invert: fewer blackframes = more motion
            motion_score = 1.0 - (motion_frames / max(total_lines, 1))
        except Exception:
            motion_score = 0.5

        # Duration fitness: prefer 0.5-3s segments
        if 0.5 <= dur <= 3.0:
            dur_score = 1.0
        elif dur < 0.5:
            dur_score = dur / 0.5
        else:
            dur_score = max(0, 1.0 - (dur - 3.0) / 7.0)

        composite = motion_score * 0.6 + dur_score * 0.4
        scored.append({**scene, "motion_score": round(composite, 3)})

    return scored


def get_smart_jump_points(video_path, num_segments, montage_durations):
    """Replace random jump points with scene-aware, motion-scored selection."""
    scenes = detect_scenes(video_path)

    if not scenes or len(scenes) < 3:
        print("  Not enough scenes detected, falling back to spread selection")
        return _fallback_jump_points(video_path, num_segments)

    scored = score_segments_motion(video_path, scenes)

    # Filter out very low motion (likely dead-ball, timeouts, camera pans on empty court)
    # Also filter scenes < 0.6s — too short to show a complete highlight moment
    high_action = [s for s in scored if s["motion_score"] >= 0.50 and s["duration"] >= 0.6]
    if len(high_action) < num_segments:
        high_action = scored  # fallback if too few pass threshold

    # Sort by motion score, pick top segments
    high_action.sort(key=lambda s: s["motion_score"], reverse=True)

    # Pick top 3x candidates, then select num_segments with good spacing
    candidates = high_action[:num_segments * 3]
    if len(candidates) < num_segments:
        candidates = high_action

    # Greedy selection: pick highest scored, ensure minimum spacing
    # Store (start, end, score) tuples so we can clamp highlights to scene boundaries
    selected = []  # list of (start, end, score)
    used_ranges = []
    min_gap = 1.0  # minimum 1s gap between selected segments

    for seg in candidates:
        if len(selected) >= num_segments:
            break
        # Check overlap with already selected
        overlap = False
        for used_start, used_end in used_ranges:
            if seg["start"] < used_end + min_gap and seg["end"] > used_start - min_gap:
                overlap = True
                break
        if not overlap:
            selected.append((seg["start"], seg["end"], seg.get("motion_score", 0.5)))
            used_ranges.append((seg["start"], seg["end"]))

    # If we didn't get enough, fill with fallback (use scene end = start + 2s estimate)
    if len(selected) < num_segments:
        remaining = num_segments - len(selected)
        fallback_pts = _fallback_jump_points_partial(video_path, remaining, used_ranges)
        for pt in fallback_pts:
            selected.append((pt, pt + 2.0, 0.5))

    # Bookend ordering: best motion first (hook), second-best last (climax),
    # middle in ascending score order for energy build
    if len(selected) >= 3:
        selected.sort(key=lambda x: x[2], reverse=True)
        best = selected[0]
        second_best = selected[1]
        middle = sorted(selected[2:], key=lambda x: x[2])  # ascending for build
        selected = [best] + middle + [second_best]
    else:
        random.shuffle(selected)

    selected = selected[:num_segments]
    print(f"  Smart selection: {len(selected)} segments (scene-aware, bookend ordered, scene-end clamped)")
    return selected  # list of (jump_pt, scene_end, score)


def _fallback_jump_points(video_path, num_segments):
    """Original random jump point generation as fallback."""
    from moviepy import VideoFileClip
    clip = VideoFileClip(video_path)
    src_duration = clip.duration
    clip.close()
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
    return jump_points


def _fallback_jump_points_partial(video_path, count, used_ranges):
    """Generate additional random points avoiding used ranges."""
    from moviepy import VideoFileClip
    clip = VideoFileClip(video_path)
    src_duration = clip.duration
    clip.close()
    safe_start = 3.0
    safe_end = src_duration - 3.0
    points = []
    attempts = 0
    while len(points) < count and attempts < count * 10:
        pt = random.uniform(safe_start, safe_end - 2.0)
        overlap = any(pt < ue + 1.0 and pt > us - 1.0 for us, ue in used_ranges)
        if not overlap:
            points.append(pt)
        attempts += 1
    return points


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
                   beat_step=2, music_start_offset=0.0, intro_clip_start=None):
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
        if intro_clip_start is not None:
            # Use explicitly provided start time
            intro_start = float(intro_clip_start)
        else:
            # Skip first 10s to avoid YouTube title overlays on downloaded clips
            intro_start = min(10.0, intro_source.duration - intro_duration - 1)
    else:
        intro_source = sopranos_clip
        intro_start = 0.0

    print(f"  sopranos: {os.path.basename(sopranos_path)} ({sopranos_clip.duration:.1f}s, {sopranos_clip.w}x{sopranos_clip.h})")
    print(f"  music: {os.path.basename(music_path)} ({music.duration:.1f}s)")

    # Use pre-beat adjusted times if available, else raw beats
    beats = beat_map.get("beats_adjusted", beat_map["beats"])
    beat_classes = beat_map.get("beat_classes", [])
    if len(beats) < 4:
        print("Error: need at least 4 beats in beat map")
        sys.exit(1)

    print(f"\nBuilding timeline ({output_name})...")

    # --- Phase 1: Calm intro (skip entirely when intro_duration <= 0) ---
    skip_intro = intro_duration <= 0.0
    if skip_intro:
        actual_intro_dur = 0.0
        intro_seg = None
        black_flash = None
        print(f"  Phase 1: Skipped (immediate start)")
    else:
        actual_intro_dur = min(intro_duration, intro_source.duration - intro_start)
        intro_seg = intro_source.subclipped(intro_start, intro_start + actual_intro_dur)
        intro_seg = fit_to_square(intro_seg)
        print(f"  Phase 1: Calm intro ({actual_intro_dur:.1f}s)")

        # --- Phase 2: Black card — 0.7s for "SAME GUY." title overlay tension ---
        black_flash = ColorClip(
            size=(720, 720),
            color=(0, 0, 0),
            duration=0.7,
        ).with_fps(config.FPS)

    # --- Phase 3: Rapid montage ---
    beat_drop_in_timeline = 0.0 if skip_intro else (actual_intro_dur + 0.15)

    # Build cut durations from beats using beat_step
    # Filter to strong/medium beats when classification is available
    if beat_classes:
        filtered_beats = [b for b, c in zip(beats, beat_classes) if c in ("strong", "medium")]
        if len(filtered_beats) < 6:
            filtered_beats = beats  # fallback if too few strong beats
        else:
            print(f"  Using {len(filtered_beats)} strong/medium beats (skipped {len(beats) - len(filtered_beats)} weak)")
    else:
        filtered_beats = beats

    montage_durations = []
    elapsed = 0.0
    i = 0
    while i < len(filtered_beats) - beat_step and elapsed < max_montage_seconds:
        next_i = min(i + beat_step, len(filtered_beats) - 1)
        cut_dur = filtered_beats[next_i] - filtered_beats[i]
        if cut_dur < 0.1:
            i += beat_step
            continue
        montage_durations.append(cut_dur)
        elapsed += cut_dur
        i += beat_step

    # Pacing arc: hook (fast) → build (medium) → peak (rapid-fire) → climax (one slow payoff)
    # Based on research: 0-3s hook, 3-10s build, 10-15s peak, 15-18s climax
    if len(montage_durations) > 6:
        n = len(montage_durations)
        hook_end = max(1, int(n * 0.15))      # ~15% hook
        build_end = max(hook_end + 1, int(n * 0.55))   # ~40% build
        peak_end = max(build_end + 1, int(n * 0.85))   # ~30% peak
        # Rest = climax (~15%)
        for j in range(n):
            if j < hook_end:
                # Hook: fast cuts (0.7x duration)
                montage_durations[j] *= 0.7
            elif j < build_end:
                # Build: normal pace with slight acceleration
                progress = (j - hook_end) / max(1, build_end - hook_end)
                montage_durations[j] *= (1.0 - 0.2 * progress)
            elif j < peak_end:
                # Peak: rapid-fire (0.5-0.6x duration)
                montage_durations[j] *= 0.55
            else:
                # Climax: slower payoff moment (1.4x duration)
                montage_durations[j] *= 1.4
        print(f"  Pacing arc: hook({hook_end}) → build({build_end-hook_end}) → peak({peak_end-build_end}) → climax({n-peak_end})")
    elif duration_ramp and len(montage_durations) > 4:
        n = len(montage_durations)
        for j in range(n):
            # Scale from 0.7x at start to 1.3x at end
            scale = 0.7 + 0.6 * (j / (n - 1))
            montage_durations[j] *= scale

    num_segments = len(montage_durations)

    # Smart clip selection: scene-aware, motion-scored jump points
    print("  Selecting clips (scene-aware)...")
    jump_points = get_smart_jump_points(sopranos_path, num_segments, montage_durations)
    src_duration = sopranos_clip.duration

    # Build segments with optional flash transitions
    white_flash = None
    if flash_every_n > 0:
        white_flash = ColorClip(
            size=(720, 720),
            color=(255, 255, 255),
            duration=0.08,
        ).with_fps(config.FPS)

    montage_clips = []
    for seg_idx, (jump_info, cut_dur) in enumerate(zip(jump_points, montage_durations)):
        # jump_points now returns (jump_pt, scene_end, score) tuples
        if isinstance(jump_info, (tuple, list)):
            jump_pt, scene_boundary = jump_info[0], jump_info[1]
        else:
            jump_pt, scene_boundary = jump_info, src_duration
        # Clamp to scene boundary to prevent highlights from cutting mid-action
        seg_end = min(jump_pt + cut_dur + 0.05, scene_boundary - 0.05, src_duration - 0.1)
        seg_end = max(jump_pt + 0.2, seg_end)  # ensure at least 0.2s per clip
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

    # Use method="chain" to avoid gray flash frame artifacts from mismatched clip properties
    sopranos_assembly = concatenate_videoclips(montage_clips, method="chain")
    sopranos_no_audio = sopranos_assembly.without_audio()

    # --- Assemble full video ---
    if skip_intro:
        full_video = sopranos_no_audio
    else:
        full_video = concatenate_videoclips(
            [intro_seg, black_flash, sopranos_no_audio],
            method="chain",
        )

    # --- Audio ---
    audio_clips = []
    if not skip_intro and intro_seg is not None and intro_seg.audio is not None:
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
    parser.add_argument("--intro-start", type=float, default=None,
                        help="Start offset within intro clip in seconds (default: auto-detect)")
    parser.add_argument("--montage-length", type=float, default=12,
                        help="Max montage section length in seconds (default: 12)")
    parser.add_argument("--music-offset", type=float, default=0.0,
                        help="Start music from this offset in seconds (e.g. 83 to start at chorus)")
    parser.add_argument("--beat-step", type=int, default=2,
                        help="Use every Nth beat for cuts (1=every beat, 2=every other, 3=every third — longer clips)")
    args = parser.parse_args()

    with open(args.beats) as f:
        beat_map = json.load(f)

    # If music offset given, trim beat map to beats >= offset so cut timing matches music
    if args.music_offset > 0:
        offset = args.music_offset
        for key in ("beats", "beats_adjusted"):
            if key in beat_map:
                beat_map[key] = [b - offset for b in beat_map[key] if b >= offset]
        if "beat_classes" in beat_map and "beats" in beat_map:
            orig_beats = json.load(open(args.beats))["beats"]
            orig_classes = orig_beats and beat_map.get("beat_classes", [])
            # Rebuild classes aligned to trimmed beats
            trimmed_indices = [i for i, b in enumerate(orig_beats) if b >= offset]
            all_classes = json.load(open(args.beats)).get("beat_classes", [])
            beat_map["beat_classes"] = [all_classes[i] for i in trimmed_indices if i < len(all_classes)]

    build_timeline(
        intro_clip_path=args.intro or args.sopranos,
        sopranos_path=args.sopranos,
        music_path=args.music,
        beat_map=beat_map,
        zoom_times=args.zoom_times,
        intro_duration=args.intro_duration,
        max_montage_seconds=args.montage_length,
        music_start_offset=args.music_offset,
        intro_clip_start=args.intro_start,
        beat_step=args.beat_step,
    )


if __name__ == "__main__":
    main()
