#!/usr/bin/env python3
"""Final render — applies all effects via a single ffmpeg command."""

import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from effects import build_full_filter_chain


def export_final(draft=False, output_name=None, style="darkwave", state=None,
                 title_text=None, stat_overlays=None):
    """Export final video with color grade, vignette, zoom punches, and text."""
    if state is None:
        state = config.load_state()
    input_path = state["intermediate_path"]
    crf = config.CRF_DRAFT if draft else config.CRF_FINAL

    if output_name:
        output_path = os.path.join(config.OUTPUT_DIR, f"{output_name}.mp4")
    else:
        suffix = "_draft" if draft else "_final"
        output_path = os.path.join(config.OUTPUT_DIR, f"sopranos{suffix}.mp4")

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(input_path):
        print(f"Error: intermediate file not found: {input_path}")
        print("Run edit.py first to assemble the timeline.")
        sys.exit(1)

    filter_chain = build_full_filter_chain(state, style=style, title_text=title_text,
                                           stat_overlays=stat_overlays)

    # Audio: boost intro vocal section (+8dB for first 3.5s so LeBron voice cuts through),
    # then overall +3dB boost, then normalize to -14 LUFS
    beat_drop = state.get("beat_drop_time", 3.5)
    audio_filter = (
        f"volume=8dB:enable='lt(t,{beat_drop})',"
        f"volume=3dB,"
        f"loudnorm=I=-14:TP=-1.5:LRA=7"
    )

    cmd = [
        config.FFMPEG_BIN,
        "-y",
        "-i", input_path,
        "-vf", filter_chain,
        "-af", audio_filter,
        "-c:v", config.CODEC,
        "-preset", config.PRESET,
        "-crf", str(crf),
        "-pix_fmt", config.PIXEL_FORMAT,
        "-r", str(config.FPS),
        "-threads", str(config.THREADS),
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"Exporting {'draft' if draft else 'final'} (CRF {crf}, style={style})...")
    print(f"Filter chain preview: {filter_chain[:120]}...")
    print(f"Running ffmpeg...\n")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nffmpeg failed with code {result.returncode}")
        sys.exit(1)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone! Output: {output_path} ({size_mb:.1f} MB)")
    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export final video with effects")
    parser.add_argument("--draft", action="store_true", help="Draft quality (CRF 23)")
    parser.add_argument("--output-name", help="Output filename (without extension)")
    parser.add_argument("--style", default="darkwave",
                        choices=["darkwave", "cinematic", "atmospheric"],
                        help="Effect style preset")
    parser.add_argument("--title-text", default=None,
                        help="Title text overlay (default: THE SOPRANOS from config)")
    args = parser.parse_args()
    export_final(draft=args.draft, output_name=args.output_name, style=args.style,
                 title_text=args.title_text)


if __name__ == "__main__":
    main()
