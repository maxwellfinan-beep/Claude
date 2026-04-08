import os
import json

# --- Paths ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
CLIPS_DIR = os.path.join(ASSETS_DIR, "clips")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
INTERMEDIATES_DIR = os.path.join(ASSETS_DIR, "intermediates")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
BIN_DIR = os.path.join(PROJECT_ROOT, "bin")

# ffmpeg via symlink (yt-dlp needs directory with 'ffmpeg' and 'ffprobe' names)
FFMPEG_BIN = os.path.join(BIN_DIR, "ffmpeg")

# --- Video settings ---
WIDTH = 720
HEIGHT = 720
FPS = 30
CODEC = "libx264"
PRESET = "ultrafast"
THREADS = 8
PIXEL_FORMAT = "yuv420p"
CRF_DRAFT = 23
CRF_FINAL = 18

# --- Text overlay ---
TITLE_TEXT = "THE SOPRANOS"  # default, overridden per edit
FONT_PATH = "/System/Library/Fonts/Times.ttc"
TITLE_FONTSIZE = 80

# --- Project state (shared between edit.py and export.py) ---
PROJECT_STATE_FILE = os.path.join(PROJECT_ROOT, "project_state.json")


def save_state(data):
    with open(PROJECT_STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Project state saved to: {PROJECT_STATE_FILE}")


def load_state():
    with open(PROJECT_STATE_FILE) as f:
        return json.load(f)
