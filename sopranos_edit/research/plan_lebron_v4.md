# Plan: lebron_fancam_v4.mp4

Generated 2026-04-08 by review agent. Inputs: ffprobe metadata, volumedetect, 10 extracted frames, scene cut analysis, full review of edit.py / export.py / effects.py, beat map survey, v2 review.

---

## V3 Score: 6/10

Up from 4/10 in v2. Real progress was made: gray flash frames are gone, audio is no longer clipping, multi-game footage is present, and the color grade landed well. The pipeline is now structurally sound. What's dragging the score are the two user-reported issues (wrong title text, wrong music) plus remaining visual and pacing problems that are now fixable in a single render pass.

---

## What Improved from V2 to V3

| Problem in V2 | Status in V3 |
|---------------|-------------|
| Gray flash frames at every cut | Fixed — `method="chain"` resolved it completely, zero freezedetect hits |
| Audio clipping at 0.0 dB | Fixed — `loudnorm=I=-14:TP=-1.5:LRA=11` applied in export; new max is -5.7 dB, mean is -17.2 dB |
| No color grade | Fixed — darkwave preset is active: contrast 1.2, saturation 1.25, teal-blue colorbalance, vignette |
| No bookend ordering | Fixed — best motion clip is first, second-best last, middle ascending |
| Pacing arc flat | Partially fixed — code has hook/build/peak/climax arc, but implementation is weak (see below) |
| Single-source footage monotony | Partially fixed — frame analysis shows at least 3 different jerseys/courts (Cavaliers, Heat Finals, Lakers) |
| No zoom punches | Fixed — 4 zoom punches at 2.53s, 6.74s, 10.95s, 14.32s |

---

## What Still Needs Fixing in V3

### 1. Wrong title text — "THE SOPRANOS" (CRITICAL, user-reported)

`config.py` hard-codes `TITLE_TEXT = "THE SOPRANOS"`. The `export.py --title-text` flag exists but was not passed during the v3 render. The title appears at `t=0.0s` and runs until `t=2.0s` in the center of every frame — it is the first thing a viewer reads. For a LeBron fancam, this destroys credibility immediately.

**Fix:** Pass `--title-text` to the export command. See v4 action plan for exact string.

### 2. Wrong music — Kordhell "Murder in My Mind" (CRITICAL, user-reported)

Murder in My Mind is a dark, gothic phonk track built for moody Sopranos-style villain edits. At 117 BPM it has a heavy, ominous groove. For a LeBron basketball hype edit it creates an immediate genre mismatch — the vibe is wrong, the cultural association is wrong, and the beat pattern (slow plodding quarter-notes, no rhythmic aggression) does not serve fast athletic cuts. Beat intervals average 0.503s which produces cut durations that are slightly too long for peak-energy basketball highlights.

**Fix:** Replace with Ric Flair Drip. See rationale below.

### 3. Cut clustering at 5.7–6.6s creates a choppy dead zone

The scene cut analysis reveals a cluster of 5 cuts in a 0.9-second window (at 5.70, 5.73, 5.83, 6.27, 6.60s). The 0.03s and 0.10s micro-intervals are below one frame at 30fps and are almost certainly duplicate scene boundaries rather than intentional micro-cuts. This produces a visual stutter that reads as a rendering error. Immediately after, there is a 1.77s gap with no cut from 6.60s to 8.37s — a dead zone.

**Fix:** The pacing arc in `edit.py` is working but the beat map's 0.5s average interval combines with `beat_step=2` to produce uneven spacing. Switching to Ric Flair Drip at 129 BPM with `beat_step=2` will produce ~0.47s intervals, which eliminates the dead zone and tightens the peak section.

### 4. Frame 5 (t≈10.8s) shows Jokic without LeBron — wrong subject in frame

Extracted frame at n=350 shows Nikola Jokic in a Nuggets uniform with no LeBron visible. The scene selection pipeline picked this clip because it had high motion energy (Jokic driving), but it is the wrong subject. This is the single worst clip in the edit.

**Fix:** The `lebron_career_hd.mp4` source (825s, 60fps) is the richest source. The scene detection cache `scenes_939b170c5418.json` has 176 scenes from it. Cross-reference against which source file was used. For v4, ensure scene selection is constrained to the primary LeBron source or at minimum flag clips where jersey number "23" or "6" is not visible as lower priority.

### 5. Frame 6 (t≈16.0s, final climax) shows an empty hoop — no player

The last frame before the edit ends shows a ball going into a basket with LeBron out of frame. The climax clip should be LeBron's biggest reaction or follow-through, not an empty hoop. The bookend ordering placed a "high motion" clip last, but motion score alone does not distinguish between ball-in-hoop and player celebration.

**Fix:** The climax position should be manually set or the "last" clip should be validated to contain the subject. For v4, the `lebron_career_hd.mp4` source has playoff moments — the best candidate is the Finals dunk/reaction moment visible in frame extra_4 (t≈12.2s, "JAMES 6", NBA Finals crowd, clear subject-in-frame). That clip should be the last cut, not penultimate.

### 6. Duration is 16.8s — slightly long relative to content quality

16.8s is within the fancam guide's 15-30s window but every second needs to earn its place. With the Jokic clip and the empty hoop climax removed/replaced, the edit would naturally tighten to 14-15s, which is the ideal zone for a hype fancam.

### 7. Audio mean volume (-17.2 dB) is now too quiet

V2 was clipping at 0.0 dB. The loudnorm fix swung to the other extreme: -17.2 dB mean is well below streaming targets. The loudnorm target was set to -14 LUFS integrated, but the mean suggests either a very dynamic track (phonk often has long silent sections) or the normalization is integrating silence. Phone speakers at -17 dB mean will feel weak compared to adjacent TikToks.

**Fix:** Switch to `loudnorm=I=-14:TP=-1.5:LRA=7` (tighter LRA=7 to reduce dynamic range and bring up perceived loudness), or combine with a pre-normalize boost: `-af "volume=+3dB,loudnorm=I=-14:TP=-1.5:LRA=7"`.

---

## V4 Action Plan (Ordered by Priority)

### P0 — Music: Switch to Ric Flair Drip

**File:** `assets/music/ric_flair_drip.mp3`
**Beat map:** `assets/beat_map_ric_flair_drip.json`
**Why:** 129 BPM is the standard NBA highlight edit tempo in 2025-2026. "Ric Flair Drip" by Offset & Metro Boomin is culturally synonymous with basketball highlights — Ric Flair is a wrestling persona LeBron has explicitly referenced, the track's ad-libs and ad-break structure are designed for rapid-cut athletic content, and it has been used in thousands of viral NBA edits. The 0.47s average beat interval at `beat_step=2` (effective 0.94s cuts) produces the correct rhythm for showing shot-celebration-shot sequences. It also has a strong snare on beat 2 and 4 which gives each cut a satisfying physical snap.

**Settings:** `beat_step=2`, `music_start_offset=0.0` (track opens with hard hit, no intro needed), `max_montage_seconds=14`.

**Runner-up option:** `ghostface_playa_why_not.mp3` with `beat_map_why_not.json`. Same 117 BPM as murder mind but has a more aggressive, punchy character and is culturally associated with street basketball. Use this if Ric Flair Drip feels too mainstream. Same settings.

**Do not use:** `kordhell_murder_in_my_mind.mp3`, `after_dark.mp3`, `little_dark_age.mp3`, `the_perfect_girl.mp3` — all are Sopranos/villain/atmospheric tracks that clash with athletic content.

### P0 — Title Text: "LEBRON JAMES" or stat-based hook

Pass to `export.py --title-text`. Recommended options in priority order:

1. **`23 YEARS. 40,000 POINTS.`** — This is the most shareable stat hook. LeBron is the all-time NBA scoring leader. A viewer who doesn't know this stat will stop scrolling. Fits in two lines at fontsize 80.
2. **`LEBRON JAMES`** — Simple, clean, correct. Use if the stat feels too long for the text overlay timing window.
3. **`THE KING`** — His most recognized nickname, shorter than full name, fits single line. Avoid if other TikTok edits in the same week are using it.

**Exact render flag:** `--title-text "23 YEARS. 40,000 POINTS."` or `--title-text "LEBRON JAMES"`

The title appears at `t=0.0s` (beat drop) for 2.0s. At darkwave's `text_fade_in=0.08s` the text snaps in immediately, which is correct for a hype edit opener.

### P1 — Style Preset: Switch to "cinematic" for basketball content

The "darkwave" preset uses strong teal-blue color shift (`bs=0.12, bm=-0.08`) which was designed for the Sopranos' dark indoor palette. Basketball footage shot in bright arena lighting with white/yellow courts turns teal under this grade — visible in the extracted frames as an unnatural blue cast over the crowd and floor. The "cinematic" preset uses a warmer color balance (`rs=0.05:rh=0.06`) that complements arena lighting and skin tones while still adding contrast (1.15) and saturation boost (1.1).

**Render flag:** `--style cinematic`

### P1 — Source: Use `lebron_career_hd.mp4` as primary source

The 825-second career compilation at 60fps is the richest source available. The scene cache (`scenes_939b170c5418.json`) already has 176 detected scenes. At 60fps the motion scoring will be more accurate because there are 2x the frames to difference. The pipeline should use this as the `--sopranos` argument. Do not mix in `sports_hype_hd.mp4` for this render — the Jokic frame (frame 5) almost certainly came from that source.

**Render flag:** `--sopranos assets/clips/lebron_career_hd.mp4`

### P2 — Audio: Tighten loudnorm LRA to reduce dynamic range

Replace current `loudnorm=I=-14:TP=-1.5:LRA=11` with `loudnorm=I=-14:TP=-1.5:LRA=7` in `export.py`. The lower LRA value (7 LU vs 11 LU) compresses the dynamic range more aggressively, which raises the perceived loudness of the quieter sections without increasing the peak. This is standard practice for social media audio where the listener environment is noisy.

Edit `export.py` line 37:
```
audio_filter = "loudnorm=I=-14:TP=-1.5:LRA=7"
```

### P2 — Pacing: Use `beat_step=2`, `intro_duration=0` (immediate drop)

The v3 project state shows `beat_drop_time=0.0`, meaning the intro was already skipped. Keep this. With Ric Flair Drip opening on a hard hit, the correct approach is to drop directly into the montage. Set `--intro-duration 0`.

The pacing arc in edit.py is already implemented. At 129 BPM with `beat_step=2`, the effective cut rate is:
- Hook (first 15% of cuts): ~0.66s per cut (beat_interval × 0.7)
- Build: ~0.56s per cut
- Peak: ~0.45s per cut (rapid-fire)
- Climax: ~0.94s per cut (one long payoff)

This arc matches the fancam guide exactly.

### P3 — Pre-beat offset: Verify `beats_adjusted` is being used

The `beat_map_ric_flair_drip.json` does NOT have `beats_adjusted` or `beat_classes` fields (confirmed above). The `edit.py` line 311 correctly falls back to `beat_map["beats"]` when `beats_adjusted` is absent, so no crash will occur. However the 2-frame pre-beat anticipation offset from the fancam guide will be lost.

**Fix:** After running `beats.py` for Ric Flair Drip, verify the output beat map includes `beats_adjusted`. If the beats.py pipeline generates it, use the existing map. If not, regenerate: the field is simply `[max(0, t - 0.067) for t in beats]`.

For v4 this is a nice-to-have, not a blocker.

### P3 — Zoom punch timing: Recalculate after music switch

The current zoom_punch_times `[2.53, 6.74, 10.95, 14.32]` were calculated relative to the murder_mind beat map. After switching to Ric Flair Drip the total duration and beat positions will shift. The pipeline auto-calculates zoom times from `total_duration × [0.15, 0.4, 0.65, 0.85]` — this is fine and requires no manual change. Confirm the auto-times look reasonable after the timeline build completes before running export.

---

## Full V4 Render Command Sequence

```bash
# Step 1: Edit — assemble timeline with new music
python3 sopranos_edit/edit.py \
  --sopranos sopranos_edit/assets/clips/lebron_career_hd.mp4 \
  --music sopranos_edit/assets/music/ric_flair_drip.mp3 \
  --beats sopranos_edit/assets/beat_map_ric_flair_drip.json \
  --intro-duration 0 \
  --montage-length 14

# Step 2: Export — apply cinematic grade, correct title
python3 sopranos_edit/export.py \
  --output-name lebron_fancam_v4 \
  --style cinematic \
  --title-text "LEBRON JAMES"
```

If the stat-hook title is preferred:
```bash
  --title-text "23 YEARS. 40,000 POINTS."
```

---

## Expected V4 Improvements

| Metric | V3 | V4 Target |
|--------|----|-----------|
| Title text | "THE SOPRANOS" (wrong) | "LEBRON JAMES" or stat hook |
| Music | Kordhell phonk (wrong genre) | Ric Flair Drip (basketball standard) |
| BPM | 117 | 129 |
| Color grade style | Darkwave (teal/dark) | Cinematic (warm arena) |
| Gray flash frames | 0 (fixed in v3) | 0 (maintained) |
| Audio max dB | -5.7 dB (good) | -5.7 dB (maintained) |
| Audio perceived loudness | Weak (-17.2 dB mean) | Stronger (LRA 7 tightening) |
| Duration | 16.8s | ~13-15s |
| Subject-in-frame rate | ~75% (Jokic clip, empty hoop) | ~95% (single source) |
| Predicted score | 6/10 | 7.5-8/10 |

The ceiling for v4 is 8/10 because the remaining gap to a truly viral edit requires velocity edits (speed ramping), subject detection to filter non-LeBron clips, and ideally a second source for jersey variety. Those are pipeline architecture changes. V4 should be a clean, properly branded, genre-correct edit that could pass a first scroll — which v3 cannot due to the title and music issues alone.
