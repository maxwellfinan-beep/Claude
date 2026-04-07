import os

# ── Output format ────────────────────────────────────────────────────────────
TIKTOK_WIDTH = 1080
TIKTOK_HEIGHT = 1920
FPS = 30
TARGET_DURATION_MIN = 30   # seconds
TARGET_DURATION_MAX = 60   # seconds

# ── Editing style ────────────────────────────────────────────────────────────
SLOW_MO_FACTOR = 0.4        # 40% speed on drop moments
BEAT_SUBDIVISION = 2        # cut every Nth beat (2 = every other beat)
ZOOM_FACTOR = 1.08          # subtle push-in on regular clips
ZOOM_FACTOR_SLOWMO = 1.15   # stronger push-in on slow-mo clips
FLASH_DURATION = 0.07       # seconds (≈2 frames at 30fps)
FILM_GRAIN_INTENSITY = 0.025

# ── Color grade ──────────────────────────────────────────────────────────────
COLOR_PRESET = "cinematic"   # currently only "cinematic" is implemented
VIGNETTE_STRENGTH = 0.4

# ── Text overlays ────────────────────────────────────────────────────────────
PLAYER_NAME = "JOHN WALL"
HYPE_TEXTS = [
    "WALL STREET!",
    "THE WIZARD!",
    "TOO FAST!",
    "AND ONE!",
    "POSTER!",
    "HANDLES ON FIRE!",
]
STATS_LINES = [
    "5× NBA All-Star",
    "Career: 19.0 PPG  8.8 APG",
    "#2 Pick · 2010 NBA Draft",
]
FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "BebasNeue-Regular.ttf")
NAMEPLATE_FONTSIZE = 110
HYPE_FONTSIZE = 130
STATS_FONTSIZE = 36

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "john_wall_tiktok.mp4")

# ── YouTube highlight URLs ────────────────────────────────────────────────────
# Add or replace with fresh URLs before running.
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=9zkcPraU6-s",  # John Wall Highlights
]

# ── Music ─────────────────────────────────────────────────────────────────────
# Song: "Do the John Wall" by Troop 41
# Source: https://www.youtube.com/watch?v=meYIbAt2iaQ
