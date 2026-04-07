"""
John Wall TikTok Edit — main pipeline entry point.

Usage:
    1. Place a music track (.mp3 or .wav) in assets/music/
    2. (Optional) Edit config.py to update YOUTUBE_URLS and style constants
    3. Run:  python main.py

Output:  output/john_wall_tiktok.mp4
"""

import os
import glob
import shutil
import sys

import config
from downloader import download_clips, collect_existing_clips
from beat_detector import analyze_beats, get_cut_points, get_drop_regions
from clip_selector import load_clips, assign_clips_to_beats, mark_slowmo_clips
from text_overlay import build_overlay_timeline
from assembler import build_sequence, composite_with_overlays, export

from moviepy import AudioFileClip


# ── Pre-flight ────────────────────────────────────────────────────────────────

def preflight_checks() -> dict:
    """Verify system deps and locate the music file. Returns runtime flags."""
    flags = {"imagemagick": True}

    # ffmpeg is mandatory
    if not shutil.which("ffmpeg"):
        print("[main] ERROR: ffmpeg not found on PATH.")
        print("       Install ffmpeg: https://ffmpeg.org/download.html")
        sys.exit(1)

    # ImageMagick is optional (PIL fallback used for stats card)
    if not shutil.which("convert"):
        print("[main] WARNING: ImageMagick 'convert' not found — "
              "TextClip overlays disabled; PIL stats card still works.")
        flags["imagemagick"] = False

    # Create required directories
    for d in [config.DOWNLOADS_DIR, config.OUTPUT_DIR,
              config.MUSIC_DIR, config.FONTS_DIR]:
        os.makedirs(d, exist_ok=True)

    # Locate music file
    music_files = (
        glob.glob(os.path.join(config.MUSIC_DIR, "*.mp3")) +
        glob.glob(os.path.join(config.MUSIC_DIR, "*.wav")) +
        glob.glob(os.path.join(config.MUSIC_DIR, "*.m4a"))
    )
    if not music_files:
        print(f"[main] ERROR: No music file found in {config.MUSIC_DIR}")
        print("       Add an .mp3 or .wav file to assets/music/ and re-run.")
        sys.exit(1)

    flags["music_path"] = music_files[0]
    if len(music_files) > 1:
        print(f"[main] Multiple music files found, using: {flags['music_path']}")

    print(f"[main] Music: {flags['music_path']}")
    print(f"[main] ImageMagick: {'yes' if flags['imagemagick'] else 'no (PIL fallback)'}")
    return flags


# ── Pipeline ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  JOHN WALL TIKTOK EDIT")
    print("=" * 60)

    # 1. Pre-flight
    flags = preflight_checks()
    music_path: str = flags["music_path"]
    use_imagemagick: bool = flags["imagemagick"]

    # 2. Download / collect clips
    existing = collect_existing_clips(config.DOWNLOADS_DIR)
    if existing:
        print(f"[main] Found {len(existing)} existing clip(s) in downloads/ — skipping download.")
        clip_paths = existing
    else:
        print(f"[main] Downloading {len(config.YOUTUBE_URLS)} clip(s)...")
        clip_paths = download_clips(config.YOUTUBE_URLS, config.DOWNLOADS_DIR)

    if not clip_paths:
        print("[main] ERROR: No clips available. Check YOUTUBE_URLS in config.py.")
        sys.exit(1)

    # 3. Beat analysis
    beat_data = analyze_beats(music_path)
    beat_times = beat_data["beat_times"]
    track_duration = beat_data["duration"]

    target_duration = min(config.TARGET_DURATION_MAX, track_duration)
    target_duration = max(config.TARGET_DURATION_MIN, target_duration)

    cut_points = get_cut_points(beat_times, config.BEAT_SUBDIVISION, target_duration)
    drop_regions = get_drop_regions(music_path, beat_times)

    print(f"[main] {len(cut_points)-1} beat slots over {target_duration:.1f}s")

    # 4. Load and assign clips
    clips = load_clips(clip_paths)
    if not clips:
        print("[main] ERROR: Could not open any video files.")
        sys.exit(1)

    assignments = assign_clips_to_beats(clips, cut_points)
    assignments = mark_slowmo_clips(assignments, drop_regions)

    # 5. Build text overlays
    overlays = build_overlay_timeline(
        cut_points=cut_points,
        total_duration=target_duration,
        hype_texts=config.HYPE_TEXTS,
        stats_lines=config.STATS_LINES,
        drop_regions=drop_regions,
        use_imagemagick=use_imagemagick,
    )

    # 6. Build video sequence (color grade + effects + vertical crop)
    print("[main] Building video sequence (this may take a while)...")
    sequence = build_sequence(assignments, add_flash=True)

    # 7. Load audio
    audio = AudioFileClip(music_path)

    # 8. Composite
    print("[main] Compositing...")
    final = composite_with_overlays(sequence, overlays, audio, target_duration)

    # 9. Export
    export(final, config.OUTPUT_PATH)

    # 10. Cleanup
    for clip in clips:
        try:
            clip.close()
        except Exception:
            pass
    audio.close()

    print()
    print("=" * 60)
    print(f"  OUTPUT: {config.OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
