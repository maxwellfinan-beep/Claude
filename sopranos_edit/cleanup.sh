#!/bin/bash
# cleanup.sh — Delete all dead media files from the LeBron fancam project.
# Run this once to free ~2.5 GB of disk space.
# KEEPS: lebron_career_hd.mp4, lebron_taco_tuesday_original.mp4,
#        nba_youngboy_shot_callin.mp3, beat_map_shot_callin.json,
#        timeline_raw.mp4, lebron_fancam_v12.mp4

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Cleaning dead clips (~1.6 GB) ==="
rm -fv "$DIR/assets/clips/Happy backyard ducks swimming in fresh water.mp4"
rm -fv "$DIR/assets/clips/The Sopranos - Greatest Scenes.mp4"
rm -fv "$DIR/assets/clips/larry_bird_hd.mp4"
rm -fv "$DIR/assets/clips/lebron_funny_moments.mp4"
rm -fv "$DIR/assets/clips/lebron_hd.mp4"
rm -fv "$DIR/assets/clips/lebron_lying_compilation.mp4"
rm -fv "$DIR/assets/clips/lebron_taco_tuesday_bubble.mp4"
rm -fv "$DIR/assets/clips/lebron_taco_tuesday_v2.mp4"
rm -fv "$DIR/assets/clips/lebron_washed_king_LeBron James    WASHED KING ｜  Motivational Tribute Motivational Video ｜ Reallife Achiever.mp4"
rm -fv "$DIR/assets/clips/lebron_washed_king_Lebron James Mix - ＂WASHED KING＂ (2020 Highlights) ᴴᴰ.mp4"
rm -fv "$DIR/assets/clips/movies_iconic_hd.mp4"
rm -fv "$DIR/assets/clips/sports_hype_hd.mp4"
rm -fv "$DIR/assets/clips/tom_brady_hd.mp4"
rm -fv "$DIR/assets/clips/tony_solo_hd.mp4"
rm -fv "$DIR/assets/clips/tony_soprano_hd.mp4"

echo ""
echo "=== Cleaning dead music (~130 MB) ==="
# Keep only nba_youngboy_shot_callin.mp3
find "$DIR/assets/music/" -type f ! -name "nba_youngboy_shot_callin.mp3" -exec rm -fv {} \;

echo ""
echo "=== Cleaning dead beat maps ==="
# Keep only beat_map_shot_callin.json
find "$DIR/assets/" -maxdepth 1 -name "beat_map_*.json" ! -name "beat_map_shot_callin.json" -exec rm -fv {} \;

echo ""
echo "=== Cleaning old intermediates ==="
# Keep only timeline_raw.mp4
find "$DIR/assets/intermediates/" -type f ! -name "timeline_raw.mp4" -exec rm -fv {} \;

echo ""
echo "=== Cleaning old outputs ==="
# Keep only lebron_fancam_v12.mp4
find "$DIR/output/" -type f ! -name "lebron_fancam_v12.mp4" -exec rm -fv {} \;
# Remove debug frame directories
rm -rf "$DIR/output/frames_bubble" "$DIR/output/frames_orig" "$DIR/output/frames_orig_t10" "$DIR/output/frames_v11"

echo ""
echo "Done. Freed ~2.5 GB."
echo "Active files:"
echo "  clips:       lebron_career_hd.mp4, lebron_taco_tuesday_original.mp4"
echo "  music:       nba_youngboy_shot_callin.mp3"
echo "  beat map:    beat_map_shot_callin.json"
echo "  intermediate: timeline_raw.mp4"
echo "  output:      lebron_fancam_v12.mp4"
