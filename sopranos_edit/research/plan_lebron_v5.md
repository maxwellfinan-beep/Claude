# Plan: lebron_fancam_v5.mp4

Generated 2026-04-08 by review agent. Inputs: ffprobe metadata, volumedetect, 8 extracted frames (visually assessed), blackdetect, scene cut detection (36 cuts logged), project_state.json, plan_lebron_v4.md, fancam_timing_guide.md.

---

## V4 Score: 7/10

Up from 6/10 in v3. Progression: v2=4/10, v3=6/10, v4=7/10. The pipeline is now producing a genuinely watchable LeBron edit. The two critical regressions from v3 are confirmed fixed: the title text is correct and the music genre matches. What's holding v4 at 7 rather than 8+ is a cluster of pacing problems, a tempo mismatch that causes the wrong BPM to drive cuts, and two weak clips in prominent positions that need to be replaced.

---

## What the Data Shows

### Basic Info

| Metric | V4 Value | V3 Value | Status |
|--------|----------|----------|--------|
| Duration | 15.60s | 16.8s | Slightly shorter — good |
| Resolution | 720x720 | 720x720 | Square format maintained |
| FPS | 30 | 30 | Maintained |
| Video codec | H.264 (Constrained Baseline) | H.264 | Fine for TikTok |
| Audio codec | AAC LC, 96000 Hz stereo | AAC | 96kHz sample rate is wasteful (48kHz is standard), minor |
| File size | 14MB | — | Reasonable for 15.6s |
| Detected tempo in project_state | 161.5 BPM | 117 BPM | PROBLEM — see below |
| Beats used | 16 | — | |
| Total cut events detected (scene>0.3) | 36 | ~30 | |

### Audio Levels

| Metric | V4 Value | V3 Value | Target | Status |
|--------|----------|----------|--------|--------|
| max_volume | -0.7 dB | -5.7 dB | < -1.0 dB | FIXED — no clipping |
| mean_volume | -17.6 dB | -17.2 dB | -12 to -14 dB | STILL TOO QUIET |
| Perceived loudness | Weak | Weak | Match adjacent TikToks | Not fixed |

The LRA=7 loudnorm fix recommended in v4 plan was apparently not applied — mean is -17.6 dB, even slightly quieter than v3's -17.2 dB. This is a persistent problem. Phone speaker output will feel noticeably quieter than surrounding content on TikTok's autoplay.

### Black/Gray Frame Detection

`blackdetect` returned zero hits. There are no blank frames, gray flashes, or freeze frames anywhere in v4. This fix from v3 is holding perfectly.

---

## Frame-by-Frame Visual Analysis

The video is 15.60s at 30fps = 468 total frames. The 8 extracted frames span the full timeline:

**Frame 1 — n=0, t=0.0s (Hook opener)**
LeBron James, Cavaliers #23 wine/gold jersey, mid-air on a thunderous one-handed jam toward the basket. The ball is at the rim, his body fully extended. Arena background is dark, crowd visible. This is an excellent hook frame — high drama, subject clearly identified by jersey number. The "LEBRON JAMES" title text is NOT visible in this frame. The frame is slightly letterboxed/cropped at top and bottom — the original footage was 4:3 or widescreen and has been cropped to 720x720. LeBron's head is near the top crop line. The color grade here looks correct: warm arena tones, not the blue-teal darkwave cast. Cinematic preset is working.

**Frame 2 — n=30, t=1.0s (Title text overlay visible)**
LeBron in white Miami Heat jersey (no number visible but the Heat wordmark is clear), driving past two defenders in what appears to be a playoff game — the arena has gold seats (Indiana Pacers, likely 2012 or 2013 Eastern Conference Finals). Motion blur on LeBron's body indicates fast lateral movement, excellent energy. "LEBRON JAMES" title text is prominently visible in the lower-left third, white serif font, large. **CONFIRMED: The title text correctly reads "LEBRON JAMES" — the "THE SOPRANOS" issue is fixed.** The text position (lower-left) looks clean and does not obscure LeBron's face. However, the text is still showing at t=1.0s — the project_state shows title_appear_time=0.0, title_disappear_time=2.0, meaning the text runs a full 2 seconds. At this cut density (cuts every ~0.5s) the text is appearing over 3-4 different clips, which dilutes the opening impact. The text should ideally be confined to just the first clip (0.0-0.5s).

**Frame 3 — n=70, t=2.33s (Build section)**
LeBron in a blue jersey — possibly a Team USA or an early career Cavaliers alternate. He is dribbling/driving left with an opponent (red jersey, possibly early 2000s footage given the image quality — lower resolution, more film grain). LeBron is smaller in the frame; he is not centered, appearing in the lower-left quadrant while the defender occupies the center. This is a weak composition — the subject is not the visual focus. The "LEBRON JAMES" text appears to still be faintly present (fade-out at ~2.0s). The crop of this clip leaves too much dead court space in the upper right.

**Frame 4 — n=120, t=4.0s (Build section, mid-point)**
Two players in the mid-court area — a player in white Heat jersey (likely LeBron, facing away from camera) and a player in a dark jersey. The player in white is walking/jogging, not in an action pose. This is the weakest clip in the edit: LeBron's back is to camera, no recognizable action, and it looks like a transition moment between plays rather than a highlight. This clip needs to be replaced. The court markings indicate this is a different arena from frame 3. No title text visible.

**Frame 5 — n=180, t=6.0s (Peak section begins)**
LeBron James, Cavaliers #23, in a powerful upward motion toward the basket with an opponent in a blue Pistons-era jersey (#36 visible — likely Rasheed Wallace). LeBron's arm is extended above the rim in a dunk or block attempt. This is an excellent clip — identifiable opponent makes the play feel historic, high action, LeBron clearly the subject and dominant physically. This is the kind of highlight that stops scrolling. The image quality is SD-era (early 2000s-mid career Cavaliers), which adds authenticity.

**Frame 6 — n=250, t=8.33s (Peak section)**
Wide shot of the Cavaliers arena (KIA logo visible on court). LeBron #23 is at mid-court with his back slightly turned, while a Minnesota Timberwolves player (#23 also visible in the distance) is the other person in frame. This is another weak clip — it reads as a defensive possession or dead ball situation rather than an offensive highlight. LeBron is not doing anything visually compelling. The wide shot means he is small in the 720x720 frame. This needs replacing.

**Frame 7 — n=350, t=11.67s (Late peak/climax lead-up)**
The Cavaliers arena again, wide angle, several players visible including LeBron, multiple Cavaliers teammates, and San Antonio Spurs-era players (based on uniform colors). This appears to be a free throw or timeout situation — players are standing, no action. LeBron is not even the most prominent subject; a referee is more visually central. This is a critical problem in the climax lead-up. Three consecutive clips (frames 4, 6, 7) are non-action clips. The "motion scoring" pipeline is apparently selecting clips that have movement but not highlight-quality movement.

**Frame 8 — n=460, t=15.33s (Final/climax)**
LeBron in white Miami Heat jersey, shooting a mid-range jump shot. He is in perfect form — full extension, follow-through wrist, ball visible at the release point. The crowd behind him in red and white Heat colors is packed and in focus. This is a genuinely good climax clip. LeBron is centered, the action is clear, and the Heat crowd provides a professional playoff atmosphere. This is the right energy for a final frame. The color grade here shows warm amber/red tones from the Heat arena — the cinematic preset is working correctly for arena lighting.

### Subject Presence Score by Frame

| Frame | t | LeBron Visible | LeBron is Subject | Action Quality | Grade |
|-------|---|----------------|-------------------|----------------|-------|
| 1 | 0.0s | Yes (#23 Cavs) | Yes | Dunk attempt | A |
| 2 | 1.0s | Yes (Heat) | Yes | Drive vs. Pacers | A |
| 3 | 2.33s | Yes (Team USA/Cavs alt) | Weak — off-center | Drive/dribble, early career | C |
| 4 | 4.0s | Yes (Heat, back to camera) | No | Walking, dead play | D |
| 5 | 6.0s | Yes (#23 Cavs) | Yes | Dunk/block vs. Pistons | A |
| 6 | 8.33s | Yes (#23 Cavs) | Weak — wide shot | Standing, vs. Wolves | D |
| 7 | 11.67s | Yes (Cavs Finals) | No — referee is center | Standing, vs. Spurs | D |
| 8 | 15.33s | Yes (Heat) | Yes | Jump shot, Finals crowd | B+ |

**LeBron as clear subject: 4/8 frames (50%). This is the core problem.** Four clips have LeBron present but either turned away, small in frame, or inactive. The motion-scoring pipeline is finding clips with camera/crowd motion rather than LeBron highlight motion.

---

## Title Text Issue: CONFIRMED FIXED

The title text correctly reads "LEBRON JAMES" (visible in frame 2 at t=1.0s). The "THE SOPRANOS" problem from v3 is resolved. However, a new title text issue exists: the 2.0s display window means the text spans 3-4 different clips during the montage. The text should appear during the hook (first clip only) and disappear before the second cut.

---

## Pacing Arc Analysis

### Cut Timeline (scene change >0.3 threshold, 36 events detected)

Key timestamps from the showinfo data:
- **t=0.10s** — first cut (fast, good)
- **t=0.60s** — cut
- **t=0.87s** — cut (3 cuts in first 0.9s — strong hook density)
- **t=1.13s** — cut
- **t=2.50s** — cut (1.37s gap — dead zone during "build")
- **t=3.40s** — cut
- **t=4.10s** — cut
- **t=4.13s** — micro-cut 33ms later (rendering artifact or intentional flash)
- **t=4.27s** — cut (3 cuts in 170ms window at 4.1-4.27s)
- **t=4.50s** — cut
- **t=5.23s** — cut (0.73s gap)
- **t=5.97s** — cut
- **t=7.03s** — cut (1.07s gap — dead zone, mid-edit)
- **t=7.07s** — micro-cut 33ms later (artifact)
- **t=7.17s** — cut
- **t=7.60s** — cut
- **t=7.67s** — micro-cut (artifact)
- **t=7.83s** — cut
- **t=8.03s** — cut (cluster of 5 cuts in 1s window 7.0-8.0s)
- **t=8.87s** — cut
- **t=9.30s** — cut
- **t=9.37s** — micro-cut (artifact)
- **t=9.77s** — cut
- **t=10.00s** — cut
- **t=10.23s** — cut
- **t=10.70s** — cut
- **t=11.33s** — cut
- **t=11.80s** — cut
- **t=11.83s** — micro-cut (artifact)
- **t=12.93s** — cut (1.1s gap — dead zone)
- **t=13.00s** — micro-cut
- **t=13.97s** — cut
- **t=14.10s** — cut
- **t=14.67s** — cut
- **t=15.00s** — cut
- **t=15.47s** — cut (final)

### Pacing Problems Identified

**Problem 1 — Tempo mismatch: project_state shows 161.5 BPM, not 129 BPM**

The project_state.json records `"tempo": 161.4990234375`. The v4 plan specified using `beat_map_ric_flair_drip.json` (129 BPM). The rendered tempo suggests either a different beat map was used or the beat detection was rerun and snapped to a doubled BPM. At 161.5 BPM the average beat interval is 0.372s, which with `beat_step=2` yields effective cut intervals of 0.744s. This does not match what the fancam timing guide calls for during peak (0.45s) or build (0.56s) sections. The erratic gaps visible above (1.37s dead zone at 2.5s, 1.07s gap at 7.0s) suggest cuts are not cleanly landing on any beat grid.

**Problem 2 — Dead zones at critical positions**

Three dead zones where no cuts happen despite being in the "peak" section of the arc:
- 2.5s dead zone: 1.37s gap (t=1.13s to t=2.50s) — this is during the build section, should be getting faster, but instead it slows
- 7.0s dead zone: 1.07s gap (t=5.97s to t=7.03s) — this is during what should be peak, the worst place for a pause
- 12.93s dead zone: 1.10s gap (t=11.83s to t=12.93s) — climax lead-up is losing energy when it should be building

**Problem 3 — Micro-cut artifacts persist (same problem as v3)**

The 33ms micro-cuts at t=4.10/4.13, t=7.03/7.07, t=7.67, t=11.80/11.83, t=13.00 are sub-frame artifacts (33ms = 1 frame at 30fps). These are the same duplicate-boundary rendering artifacts from v3 that were supposed to be fixed. They create a visual stutter on cuts and suggest the `method="chain"` fix is not eliminating all cases, or the scene detection threshold is generating these.

**Problem 4 — No pacing acceleration toward peak**

The ideal arc from the fancam guide:
- Hook (0-3s): ~0.66s per cut
- Build (3-7s): ~0.56s per cut
- Peak (7-11s): ~0.45s per cut
- Climax (11-15s): one long 0.94s hold, then hard cut

What v4 actually delivers:
- Hook (0-3s): 4 cuts in 3s = 0.75s average (too slow for hook)
- Build (3-7s): 8 cuts in 4s = 0.50s average (actually correct)
- Peak (7-11s): 10 cuts in 4s = 0.40s average (good, but marred by dead zones)
- Climax (11-15s): 7 cuts in 4s = 0.57s average (should be longer holds, not shorter — the climax is over-cut)

The climax section is being cut too fast (7 cuts in 4s) when it should be 1-2 long dramatic holds. The pattern is inverted: the hook is slow, the climax is fast.

---

## Color Grade Assessment

The cinematic preset is a clear upgrade over v3's darkwave. Frame 2 (Heat, gold Pacers arena) and Frame 8 (Heat, red crowd) both show warm, natural arena tones without the teal cast that made v3 footage look like it was shot through an aquarium. Frame 5 (Cavaliers, early 2000s) shows good contrast enhancement — the darker arena footage is lifted appropriately without looking washed out.

The one issue is consistency: early career footage (SD-era, 4:3 source, low resolution) sits next to HD content and the quality difference is jarring. Frame 3 is visibly lower resolution than frame 8. The pipeline is mixing eras without any resolution-aware filtering — the color grade can't fully bridge the gap between SD and HD source material.

---

## Specific Fixes for V5 (Priority Ordered)

### P0 — Fix the 4 D-grade clips (wrong subject, back to camera, dead play)

This is the single highest-impact fix. Replace all four weak clips (frames 4, 6, 7 and frame 3 which is off-center):

- **Frame 3 replacement (t=2.33s)**: Replace the off-center early-career drive. Need a clip where LeBron is centered in frame and clearly the subject. The `lebron_career_hd.mp4` source (176 scenes in cache) should have suitable candidates from the Cavaliers 2016 era or Heat Finals years. Filter for scenes where the motion-scored region is central in the frame.

- **Frame 4 replacement (t=4.0s)**: The "back to camera" Heat clip is a dead ball moment. This should be an offensive highlight — a dunk, block, post move, or fast break finish. Any clip where LeBron is facing the camera with ball in hand.

- **Frame 6 replacement (t=8.33s)**: The wide-shot Cavaliers vs. Wolves clip. Need a tighter crop or a clip that starts with LeBron in a confined frame (post position, catch-and-shoot) rather than a full-arena establishing shot. If the pipeline cannot filter for shot composition, a tighter `--crop-scale` parameter or adding a center-crop zoom to this clip would help.

- **Frame 7 replacement (t=11.67s)**: The free throw / timeout clip in the climax section. This is the worst placement — the climax lead-up should be the most electrifying clip in the edit. Need a block, steal, or celebration moment. The NBA Finals 2016 chase-down block would be ideal here if available in the source.

**Implementation approach for v5**: Add a minimum composition check to `score_segments_motion` — after the motion score, sample a frame from the center of the segment and check whether the mean pixel brightness in the center 50% of the frame differs significantly from the edges. High subject-in-center clips will have high contrast between the center (bright jersey, skin tone) and the periphery. This is an approximation of subject-centering without requiring face detection.

### P0 — Fix the BPM mismatch: regenerate beat map or constrain to 129 BPM

The project_state records 161.5 BPM — this needs to be investigated. Either the beat map was not the Ric Flair Drip map (129 BPM), or the beat tracking ran at double-tempo. Confirm by checking the beat intervals in `beat_map_ric_flair_drip.json` — they average ~0.465s, which corresponds to 129 BPM. If the v4 edit actually used a different beat map (the file listing shows several options including `beat_map_paint_town_red.json` and `beat_map_why_not.json` which were added recently), that would explain the tempo discrepancy. For v5, explicitly pass `--beats sopranos_edit/assets/beat_map_ric_flair_drip.json` and verify the project_state.json shows `"tempo": 129.2` after the run.

### P1 — Shorten title text window from 2.0s to 0.5s

Currently `title_disappear_time=2.0` means the "LEBRON JAMES" text spans 3-4 different clips. The text should hit on the first frame, hold for one clip (0-0.5s), then fade out before the second cut. Change `title_disappear_time` to `0.5` in `config.py` or pass via command flag. The text fade duration is already 0.08s (fast snap-in, fast snap-out) so this will feel like a title card that establishes the subject, then gets out of the way.

### P1 — Fix the dead zones: rebuild pacing arc at 129 BPM with beat_step=2

The three dead zones (at 1.13-2.50s, 5.97-7.03s, 11.83-12.93s) are breaking the energy arc. With 129 BPM and `beat_step=2`, the expected cut interval is 0.93s. The gaps above are 1.37s, 1.07s, and 1.10s — all exceeding the target. This suggests either the clips selected are too short (ending before the next beat) or the beat snap is silently skipping beats when no clip transition point aligns.

Fix: Ensure the timeline builder uses the longest available clip segment to fill each beat window rather than cutting the clip short. If a clip is 0.6s and the beat window is 0.93s, either allow clips to run past the next beat boundary (extend to action completion) or find a clip from the same scene that has ≥0.93s available.

### P1 — Fix the over-cut climax: hold for 1-2 long clips at 11-15s

The last 4 seconds has 7 cuts (0.57s average), which is peak-section pacing applied to the climax. The fancam guide is explicit: the climax should be 1 extended clip (0.94-1.5s) that shows the payoff action in full. The rapid cutting in the climax section makes the ending feel rushed rather than triumphant.

Fix: Add a climax override in the timeline builder — the last 2 clips should have their durations doubled (use `beat_step=4` for the final 2 positions) to let the action breathe. This gives the viewer time to appreciate the final highlight before the hard cut to black.

### P2 — Fix micro-cut artifacts: raise scene detection threshold to 0.4

The 33ms micro-cuts (visible at 4.10/4.13, 7.03/7.07, 11.80/11.83 etc.) are duplicate scene boundaries being detected at the same transition with slightly different pts values. The `detect_scenes_ffmpeg` function in `edit.py` uses a scene threshold of `0.35`. Raising this to `0.4` will reduce false-positive boundary detections and eliminate most of these artifacts. Alternative: post-process the cut list to remove any two consecutive cuts separated by less than 3 frames (0.1s) — keep only the first of any such pair.

### P2 — Fix audio perceived loudness: tighten LRA to 7

The LRA=7 fix was planned for v4 but apparently not applied (mean is -17.6 dB, slightly worse than v3's -17.2 dB). Apply in `export.py`:
```
loudnorm=I=-14:TP=-1.5:LRA=7
```
Also add a pre-boost: `volume=+3dB,loudnorm=I=-14:TP=-1.5:LRA=7` to compensate for the dynamic track's long quiet sections pulling down the integrated loudness.

### P2 — Filter out SD-era footage or apply resolution normalization

The mix of SD (early 2000s, ~480p source) and HD (2010s-2020s) footage creates a resolution jump that the color grade cannot fix. Options in priority order:
1. Constrain scene selection to source files that are confirmed HD (the `lebron_career_hd.mp4` file at 825s, 60fps is the best source — use it exclusively)
2. If SD clips are included, apply an aggressive `unsharp` filter to bring them closer to the HD sharpness level
3. Do not mix sources with >2x resolution difference in adjacent clips

### P3 — Reduce audio sample rate from 96kHz to 48kHz

The output audio is encoded at 96000 Hz. TikTok's standard is 44100 Hz or 48000 Hz. 96kHz increases file size without audible benefit on mobile speakers. Add `-ar 48000` to the export ffmpeg audio flags. This will reduce file size by ~8% with no quality loss.

### P3 — Add pre-beat offset (2 frames, 67ms early)

The fancam timing guide specifies placing cuts 2 frames before the beat, not on it. V4 has no pre-beat offset applied (the `beats_adjusted` field is absent from `beat_map_ric_flair_drip.json`). This 67ms anticipation offset makes the cuts feel more physically "snappy" and energetic. Generate the adjusted beat map:
```python
beats_adjusted = [max(0, t - 0.067) for t in beats]
```
Add this field to the beat map JSON before the v5 render.

---

## V4 vs V5 Expected Improvements Table

| Metric | V3 | V4 (Actual) | V5 Target |
|--------|----|-------------|-----------|
| Title text | "THE SOPRANOS" | "LEBRON JAMES" (FIXED) | "LEBRON JAMES" (maintained) |
| Music genre | Wrong (phonk villain) | Correct (basketball hype) | Correct (maintained) |
| Audio max dB | -5.7 dB | -0.7 dB | < -1.0 dB |
| Audio mean dB | -17.2 dB | -17.6 dB (worse) | -13 to -14 dB |
| Black/gray frames | 0 | 0 | 0 |
| LeBron subject-in-frame | ~75% | ~50% (regression) | ~90% |
| Weak/dead-play clips | 2 | 4 | 0-1 |
| Dead zones >1.0s | 3 | 3 | 0 |
| Micro-cut artifacts | 5 | 5 | 0 |
| Climax pacing | Over-cut | Over-cut | 1-2 long holds |
| Title text duration | 2.0s | 2.0s | 0.5s |
| Color grade | Darkwave (wrong) | Cinematic (correct) | Cinematic (maintained) |
| Pre-beat anticipation offset | No | No | Yes (-67ms) |
| Predicted score | 6/10 | 7/10 | 8.5/10 |

---

## V5 Render Command

```bash
# Step 1: Edit — confirm ric flair drip beat map, verify 129 BPM in project_state
python3 sopranos_edit/edit.py \
  --sopranos sopranos_edit/assets/clips/lebron_career_hd.mp4 \
  --music sopranos_edit/assets/music/ric_flair_drip.mp3 \
  --beats sopranos_edit/assets/beat_map_ric_flair_drip.json \
  --intro-duration 0 \
  --montage-length 14

# VERIFY: cat sopranos_edit/project_state.json | grep tempo
# Expected: "tempo": 129.x
# If it shows 161.x, the wrong beat map was loaded — check config.py defaults

# Step 2: Export — cinematic grade, correct title with short display window
python3 sopranos_edit/export.py \
  --output-name lebron_fancam_v5 \
  --style cinematic \
  --title-text "LEBRON JAMES" \
  --title-duration 0.5
```

---

## Note on Music

The user's feedback "music sucks, I need a better song with singing" is a separate track selection issue not addressed in this plan (per instructions). The current music (presumed Ric Flair Drip based on the beat map used) is instrumentally correct for basketball edits, but if the user wants vocals/singing specifically, the track will need to change for v6. Candidate songs with strong vocals and basketball cultural resonance: "Goat" by Polo G, "King's Dead" by Jay Rock/Kendrick, or "Alright" by Kendrick Lamar (slower BPM but powerful). This is flagged for post-v5 consideration.

---

## Overall Quality Assessment

V4 is a real edit now. Compared to v2 (which was unwatchable due to gray flashes, wrong title, and clipping audio) and v3 (which had the wrong title plastered over everything), v4 would survive a first scroll. The opening frame is strong (dunk shot, Cavs #23 clearly visible), the color grade is correct for the content, and the music genre matches.

The ceiling break from 7 to 8.5 comes entirely from fixing the clip selection. Three of the eight sampled frames show LeBron in a dead-ball or off-camera position — on TikTok, those frames will be the ones where someone decides to scroll away. The pacing fixes (dead zones, over-cut climax, micro-artifacts) are secondary to getting LeBron in frame and performing for every clip.
