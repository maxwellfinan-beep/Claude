#!/usr/bin/env python3
"""
Batch editor — creates 3 distinct Sopranos TikTok edits.

Edit 1: "Darkwave Power" — After Dark by Mr.Kitty
  - Ducks intro (2.5s) → flash → aggressive rapid cuts
  - Flash transitions every 3rd cut, duration ramp
  - High contrast teal grade, snap-on text, zoom punches

Edit 2: "Cinematic" — Little Dark Age by MGMT
  - Ducks intro (3s) → black → deliberate medium-pace montage
  - No flash transitions, smoother cuts
  - Warm cinematic grade, gentle text fade, subtle zooms

Edit 3: "Atmospheric" — The Perfect Girl by Mareux
  - Ducks intro (2s) → flash → variable-rhythm montage
  - Flash transitions every 4th cut
  - Deep moody teal grade, quick text, aggressive zooms

Usage:
  python3 sopranos_edit/batch_edit.py
"""

import sys
import os
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

os.environ["IMAGEIO_FFMPEG_EXE"] = config.FFMPEG_BIN

from beats import detect_beats
from edit import build_timeline
from export import export_final


def find_music_file(pattern):
    """Find a music file matching a glob pattern in the music dir."""
    matches = glob.glob(os.path.join(config.MUSIC_DIR, pattern))
    if matches:
        return matches[0]
    return None


def find_asset(directory, pattern):
    """Find any file matching pattern in directory."""
    matches = glob.glob(os.path.join(directory, pattern))
    if matches:
        return matches[0]
    return None


# --- Edit configurations ---
EDITS = [
    {
        "name": "edit1_darkwave",
        "style": "darkwave",
        "music_pattern": "after_dark*",
        "intro_duration": 2.5,
        "max_montage": 12,
        "flash_every_n": 3,
        "duration_ramp": True,
        "beat_step": 2,
        "music_start_offset": 15.0,  # After Dark builds up ~15s
    },
    {
        "name": "edit2_cinematic",
        "style": "cinematic",
        "music_pattern": "little_dark_age*",
        "intro_duration": 3.0,
        "max_montage": 14,
        "flash_every_n": 0,
        "duration_ramp": False,
        "beat_step": 3,  # Longer cuts — every 3rd beat
        "music_start_offset": 30.0,  # LDA chorus starts ~30s
    },
    {
        "name": "edit3_atmospheric",
        "style": "atmospheric",
        "music_pattern": "the_perfect_girl*",
        "intro_duration": 2.0,
        "max_montage": 11,
        "flash_every_n": 4,
        "duration_ramp": True,
        "beat_step": 2,
        "music_start_offset": 10.0,  # TPG drops at ~10s
    },
]


def run_beat_detection(music_path, output_name):
    """Run beat detection and save to a named beat map file."""
    beat_map_path = os.path.join(config.ASSETS_DIR, f"beat_map_{output_name}.json")
    if os.path.exists(beat_map_path):
        print(f"  Beat map already exists: {beat_map_path}")
        with open(beat_map_path) as f:
            return json.load(f)

    print(f"  Detecting beats for {os.path.basename(music_path)}...")
    beat_map = detect_beats(music_path)
    with open(beat_map_path, "w") as f:
        json.dump(beat_map, f, indent=2)
    print(f"  Tempo: ~{beat_map['tempo']:.0f} BPM, {len(beat_map['beats'])} beats")
    return beat_map


def main():
    print("=" * 60)
    print("  SOPRANOS EDIT BATCH RENDERER")
    print("  Creating 3 distinct TikTok edits")
    print("=" * 60)

    # --- Find assets ---
    ducks_clip = find_asset(config.CLIPS_DIR, "*duck*")
    sopranos_clip = find_asset(config.CLIPS_DIR, "*Sopranos*")

    if not sopranos_clip:
        print("ERROR: No Sopranos clip found in assets/clips/")
        sys.exit(1)

    print(f"\nAssets:")
    print(f"  Sopranos: {os.path.basename(sopranos_clip) if sopranos_clip else 'MISSING'}")
    print(f"  Ducks:    {os.path.basename(ducks_clip) if ducks_clip else 'MISSING (will use Sopranos intro)'}")

    # --- Process each edit ---
    results = []
    for edit_cfg in EDITS:
        name = edit_cfg["name"]
        style = edit_cfg["style"]

        print(f"\n{'=' * 60}")
        print(f"  EDIT: {name} (style: {style})")
        print(f"{'=' * 60}")

        # Find music
        music_path = find_music_file(edit_cfg["music_pattern"])
        if not music_path:
            # Fallback to existing phonk track
            music_path = find_asset(config.MUSIC_DIR, "*Phonk*")
            if not music_path:
                music_path = find_asset(config.MUSIC_DIR, "*")
            if not music_path:
                print(f"  SKIPPING {name}: no music found matching '{edit_cfg['music_pattern']}'")
                continue
            print(f"  WARNING: Using fallback music: {os.path.basename(music_path)}")

        print(f"  Music: {os.path.basename(music_path)}")

        # Beat detection
        beat_map = run_beat_detection(music_path, name)

        # Build timeline
        intro_path = ducks_clip if ducks_clip else sopranos_clip
        print(f"\n  Assembling timeline...")
        timeline_path, state = build_timeline(
            intro_clip_path=intro_path,
            sopranos_path=sopranos_clip,
            music_path=music_path,
            beat_map=beat_map,
            zoom_times=[],  # Auto-generate
            intro_duration=edit_cfg["intro_duration"],
            max_montage_seconds=edit_cfg["max_montage"],
            flash_every_n=edit_cfg["flash_every_n"],
            duration_ramp=edit_cfg["duration_ramp"],
            output_name=name,
            beat_step=edit_cfg["beat_step"],
            music_start_offset=edit_cfg["music_start_offset"],
        )

        # Export with effects
        print(f"\n  Exporting with {style} effects...")
        output_path = export_final(
            draft=False,
            output_name=name,
            style=style,
            state=state,
        )

        results.append({
            "name": name,
            "style": style,
            "output": output_path,
            "duration": state["total_duration"],
            "beats_used": state["beats_used"],
            "music": os.path.basename(music_path),
        })

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"  BATCH COMPLETE — {len(results)} edits rendered")
    print(f"{'=' * 60}")
    for r in results:
        size_mb = os.path.getsize(r["output"]) / (1024 * 1024) if os.path.exists(r["output"]) else 0
        print(f"\n  {r['name']}:")
        print(f"    Style:    {r['style']}")
        print(f"    Music:    {r['music']}")
        print(f"    Duration: {r['duration']:.1f}s")
        print(f"    Cuts:     {r['beats_used']}")
        print(f"    Output:   {r['output']} ({size_mb:.1f} MB)")

    print(f"\nAll outputs in: {config.OUTPUT_DIR}")
    return results


if __name__ == "__main__":
    main()
