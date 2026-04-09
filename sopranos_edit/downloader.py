#!/usr/bin/env python3
"""YouTube search and download using yt-dlp."""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

import yt_dlp


def search_youtube(query, n=3):
    """Search YouTube and return top n results with title, channel, URL."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch{n}:{query}", download=False)

    entries = result.get("entries", [])
    results = []
    for entry in entries:
        results.append({
            "title": entry.get("title", "Unknown"),
            "channel": entry.get("channel") or entry.get("uploader", "Unknown"),
            "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
            "duration": entry.get("duration"),
        })
    return results


def download_video(url, output_dir):
    """Download video at 720p, merge to mp4. Returns filepath."""
    ydl_opts = {
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "ffmpeg_location": config.BIN_DIR,
        "merge_output_format": "mp4",
        "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
        "quiet": False,
        "no_warnings": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Ensure .mp4 extension after merge
        base, _ = os.path.splitext(filename)
        return base + ".mp4"


def main():
    parser = argparse.ArgumentParser(description="Search and download YouTube videos")
    parser.add_argument("query", help="YouTube search query")
    parser.add_argument("--music", action="store_true", help="Save to music directory")
    parser.add_argument("--download-only", help="Skip search, download this URL directly")
    args = parser.parse_args()

    output_dir = config.MUSIC_DIR if args.music else config.CLIPS_DIR
    os.makedirs(output_dir, exist_ok=True)

    if args.download_only:
        print(f"Downloading: {args.download_only}")
        path = download_video(args.download_only, output_dir)
        print(f"\nSaved to: {path}")
        return

    print(f"Searching YouTube for: {args.query}\n")
    results = search_youtube(args.query)

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        duration = f" ({r['duration']}s)" if r.get("duration") else ""
        print(f"  {i}. [{r['channel']}] {r['title']}{duration}")
        print(f"     {r['url']}")
        print()

    choice = input("Pick a result (1-3), or 0 to skip: ").strip()
    if choice == "0":
        print("Skipped.")
        return

    try:
        idx = int(choice) - 1
        selected = results[idx]
    except (ValueError, IndexError):
        print("Invalid choice.")
        return

    print(f"\nDownloading: {selected['title']}")
    path = download_video(selected["url"], output_dir)
    print(f"\nSaved to: {path}")


if __name__ == "__main__":
    main()
