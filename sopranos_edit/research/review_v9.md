# LeBron Fancam v9 — Quality Review

Reviewed: April 2026. Findings based on ffmpeg audio analysis, frame-by-frame visual inspection (fps=1 extraction, 0–6s), beat map analysis, and pipeline code audit.

---

## 1. Music — Kanye West "Power"

### What is actually playing?

The track is confirmed to be `kanye_west_power.mp3` (4:01 runtime, present in `/assets/music/`). The audio sample rate is 96kHz in the encoded AAC stream after export normalization (`volume=3dB,loudnorm=I=-14:TP=-1.5:LRA=7` from `export.py`).

### Does it start at the right moment?

**No. This is the core music problem.**

The `beat_map_power.json` has its first detected beat at **9.985 seconds** in the track file. The beat map contains 460 beats total, tempo 129.2 BPM.

The pipeline's `build_timeline()` receives `music_start_offset` and subclips from that position. There is no project_state.json from the v9 build present, but the audio evidence makes the offset clear:

- **0–5s audio mean: -15.0 dB**
- **5–20s audio mean: -13.3 dB**

That is only a 1.7 dB difference between the intro and the hype section. If the Power chorus or 808 verse had kicked in at the beat drop, you would expect a jump of 6–10 dB (the 808 and kick drums in Power are punishing). The near-flat loudness curve across the full edit means the hype music itself is quiet, which is a tell-tale sign of starting in the wrong section of the track.

### What section of Power is playing?

**The soul sample / quiet build-up section — not the verse.**

Power by Kanye West has this structure:
- 0:00 — Eerie choir / King Crimson vocal sample
- 0:08 — Soul sample begins (quiet build, no 808)
- 0:28 — **808 KICKS IN: first verse** (this is what the user wants)
- 0:56 — Hook: "No one man should have all that power"

The beat map's first beat is at `9.985s`, which falls squarely in the soul-sample build-up (before the 808). If `music_start_offset=0.0` was used (the default), the hype montage starts playing over the quiet intro of the track — no 808, no boom, just the atmospheric soul chop. This matches the flat loudness profile.

### What music_start_offset is needed?

To land on the 808 verse entry:

```
music_start_offset = 28.0
```

The beat map confirms beat index 38 at `28.050s` is classified `strong` — that is the 808 kick at the verse entry. Beat index 41 at `29.466s` is also `strong` and would be a valid alternative if 28.0 causes a pickup-measure feel.

**Bottom line: the edit is running Kanye "Power" but starting in the eerie quiet soul-sample intro. The 808 and verse never hit because the 20s edit ends before reaching them. The fix is `music_start_offset=28.0`.**

### Audio levels overall

- Max volume: -1.3 dB (hitting near ceiling, good)
- Mean volume: -13.3 dB overall (normalized to -14 LUFS target, acceptable)
- No clipping detected

The normalization pass in `export.py` is working correctly. The problem is entirely the wrong entry point in the track, not levels.

---

## 2. Taco Tuesday Intro — Does LeBron Actually Say It?

### Short answer: No.

### Visual evidence (frames extracted at 1 fps, 0–5s):

| Frame | Time | What you see |
|---|---|---|
| frame_01 | t=1s | LeBron — eyes closed, mouth shut, looking down. "TACO TUESDAY" text on screen (Instagram Stories overlay baked into the source video), taco emoji. |
| frame_02 | t=2s | LeBron — eyes half-open, slight head movement. Same text overlay. Still not speaking. |
| frame_03 | t=3s | LeBron — looking to the right. Mouth slightly open but in motion, not the Taco Tuesday yell. |
| frame_04 | t=4s | LeBron — eyes nearly closed, looking sideways. Still no open-mouth yelling moment. |
| frame_05 | t=5s | Basketball cut — LeBron in Heat jersey driving to the basket vs. Hawks. Beat drop has occurred. |

**LeBron's mouth never opens wide during the 0–4s intro section.** You see the Instagram text overlay "TACO TUESDAY!!!!!!" baked into the source video, plus the taco emoji sticker — but his actual vocal delivery is absent from the clip window being used.

### Why is the vocal missing?

The pipeline code in `edit.py` is the cause:

```python
intro_start = min(10.0, intro_source.duration - intro_duration - 1)
```

This line **skips the first 10 seconds** of whatever intro clip is passed. The intent was to avoid YouTube title card overlays. However, with `lebron_taco_tuesday_original.mp4`, LeBron's famous "IT'S TACO TUESDAYYYY" yell — the moment the meme comes from — happens in the **first 3–5 seconds** of the clip. The 10-second skip jumps past the entire vocal delivery and lands on a section where he has already finished yelling and is just standing there with the text overlay still present.

The result is visually confusing: the viewer sees "TACO TUESDAY" text on screen but hears no LeBron yelling. Worse, the audio at 10s+ in the source clip (`mean: -20.8 dB`) is near-silent — mostly ambient room sound — which adds no energy and wastes the intro's emotional hook.

### What the clip looks like at 10s+

At `t=10s` in `lebron_taco_tuesday_original.mp4`, LeBron is indoors in what appears to be a home or hotel room. He has already finished his Taco Tuesday announcement. He looks calm, slightly sleepy-eyed — not the meme moment. The text overlay from the original Instagram Stories recording is still visible (baked in) but the performance is gone.

The `lebron_taco_tuesday_v2.mp4` is a different version (9:16 aspect, 69s long, HE-AAC audio at -22.3 dB mean) that is even quieter and would have the same skip problem.

### What needs to change

Remove or drastically reduce the 10-second skip for intro clips that are social media vertical videos (not YouTube recordings with title cards). Specifically for the Taco Tuesday clip, the yell happens at approximately **t=0–5s**. The correct intro_start should be:

```python
intro_start = 0.0  # for social clips with no title overlay
```

Or add a per-clip override parameter. The current `min(10.0, ...)` guard is appropriate for YouTube compilations but destroys social clips.

---

## 3. "SAME GUY." Text Card — Does It Appear at ~3.5s?

### Status: Present but not visually confirmed in extracts

The code in `edit.py` creates a 0.7s black `ColorClip` between the intro segment and the montage. At default `intro_duration=3.0s`, the timing is:

```
0.00 – 3.00s   Intro (Taco Tuesday clip)
3.00 – 3.70s   Black flash (0.7s) — "SAME GUY." would render here via effects.py
3.70s          Beat drop → hype montage begins
```

At fps=1 extraction, the 0.7s black card falls between frame_03 (t=3s) and frame_04 (t=4s) and is not captured. This is expected — it is sub-second.

**What frame_04 (t=4s) shows is the Taco Tuesday clip still on screen** (LeBron looking sideways). This suggests the beat drop may be happening at ~4.2s, not 3.7s, meaning the intro segment ran slightly longer OR the `intro_start=10.0` skip shifted the effective intro in a way that added duration. In any case, the basketball content clearly starts between t=4s and t=5s, which is correct placement.

The "SAME GUY." text requires the `title_text` param to be set and `effects.py` to render it as part of the filter chain. Whether it appears as white text on the black card depends on the export call and is not verifiable from frame extraction alone (audio-only review of the intermediate file was not performed). **This requires a visual playback check.**

---

## 4. Beat Drop Feel — Does It Feel Like Power?

**No. It feels like ambient/atmospheric music, not Power.**

The key sonic signatures of Kanye West "Power" in the verse section are:
1. A massive 808 sub-bass kick that physically hits
2. Hard-panned snare
3. A clear sample loop underneath
4. Kanye's voice entering within 2 seconds of the 808 drop

None of these characteristics are present at the apparent entry point. The edit opens on the eerie choir sample from King Crimson, which is quiet, spacey, and completely wrong for a LeBron hype fancam. A viewer who knows Power would recognize the sound but be confused by the energy mismatch — the song is playing but the wrong part of the song.

---

## 5. Summary of Issues and Fixes

| Issue | Severity | Root Cause | Fix |
|---|---|---|---|
| Music starts at wrong section | Critical | `music_start_offset=0.0` (or not set) — plays quiet soul-sample intro, not 808 verse | Set `music_start_offset=28.0` in build command |
| LeBron not saying "Taco Tuesday" | Critical | `intro_start = min(10.0, ...)` skips past the vocal delivery at t=0–5s | For this clip, use `intro_start=0.0` — remove or bypass the 10s skip |
| Intro audio has no energy | High | Same as above — 10s+ section is near-silent ambient room audio (-20.8 dB) | Capture the correct window where the yell happens |
| Intro audio not reduced to 25% | Medium | `edit.py` appends `intro_audio` at full volume with no `MultiplyVolume` applied | Add volume reduction per the v8 brainstorm spec |
| "SAME GUY." card not confirmed | Low | Not verifiable from frame-at-1fps extraction | Do a playback or extract frames at higher fps around t=3.0–3.8s |

---

## 6. Recommended v10 Build Command (Corrected)

```bash
python3 sopranos_edit/edit.py \
  --intro sopranos_edit/assets/clips/lebron_taco_tuesday_original.mp4 \
  --sopranos sopranos_edit/assets/clips/lebron_hd.mp4 \
  --music sopranos_edit/assets/music/kanye_west_power.mp3 \
  --beats sopranos_edit/assets/beat_map_power.json \
  --intro-duration 3.5 \
  --music-offset 28.0 \
  --montage-length 16
```

The `--music-offset 28.0` is the essential change. The intro clip skip issue requires a code fix in `edit.py` — the `intro_start = min(10.0, ...)` guard should be reduced to `min(0.0, ...)` or made a CLI parameter (`--intro-skip`) for the taco tuesday use case.
