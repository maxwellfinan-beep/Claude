"""Download John Wall highlight clips from YouTube via yt-dlp."""

import os
import yt_dlp


def get_clip_metadata(url: str) -> dict:
    """Fetch title and duration for a URL without downloading."""
    opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),  # seconds
        "url": url,
    }


def download_clips(urls: list[str], output_dir: str) -> list[str]:
    """
    Download each URL to output_dir as MP4.

    Returns a list of local file paths that were successfully downloaded.
    Skips URLs whose output file already exists (idempotent).
    """
    os.makedirs(output_dir, exist_ok=True)

    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(output_dir, "%(id)s.mp4"),
        "quiet": False,
        "no_warnings": False,
        "ignoreerrors": True,   # skip unavailable videos instead of aborting
    }

    downloaded: list[str] = []

    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls:
            print(f"[downloader] Downloading: {url}")
            try:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    print(f"[downloader] Skipping (unavailable): {url}")
                    continue
                video_id = info.get("id")
                path = os.path.join(output_dir, f"{video_id}.mp4")
                if os.path.exists(path):
                    downloaded.append(path)
                    print(f"[downloader] Saved: {path}")
                else:
                    # yt-dlp may use a different extension after merge
                    for fname in os.listdir(output_dir):
                        if fname.startswith(video_id):
                            full = os.path.join(output_dir, fname)
                            downloaded.append(full)
                            print(f"[downloader] Saved: {full}")
                            break
            except Exception as exc:
                print(f"[downloader] Error downloading {url}: {exc}")

    return downloaded


def collect_existing_clips(downloads_dir: str) -> list[str]:
    """Return all MP4 files already in downloads_dir (skip re-downloading)."""
    if not os.path.isdir(downloads_dir):
        return []
    return [
        os.path.join(downloads_dir, f)
        for f in sorted(os.listdir(downloads_dir))
        if f.lower().endswith(".mp4")
    ]
