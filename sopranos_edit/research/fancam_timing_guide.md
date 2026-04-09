# Fancam / Athlete Edit Timing Guide: Fixing Cut Timing, Subject Focus, and Highlight Preservation

Compiled April 2026. Focused on actionable, codeable rules for our automated pipeline.

---

## The Three Problems We Are Solving

| Problem | Root Cause in Current Pipeline | Fix |
|---------|-------------------------------|-----|
| **Timing is off** | Cuts placed exactly on beat boundaries without anticipation offset; no distinction between beat types | Apply pre-beat offset; classify beats by strength; vary cut placement |
| **Focusing on others** | `jump_points` are random positions in the source video with no subject validation | Add scene detection + face/subject filtering before clip selection |
| **Cutting off highlights** | `cut_dur` is derived purely from beat intervals, ignoring what is happening on screen | Extend clips through action completion; use motion analysis to find natural endpoints |

---

## 1. Beat-Sync Timing: On the Beat vs. Before the Beat

### The Rule

**Place visual cuts 2-3 frames BEFORE the audio beat, not exactly on it.**

When the eye sees the new image slightly before the ear hears the beat, the brain perceives them as perfectly synchronized. This is because visual processing is ~30-50ms slower than auditory processing. If you cut exactly on the beat, viewers perceive the visual as slightly late.

### Specific Numbers (at 30 fps)

| Scenario | Offset | Frames at 30fps | Milliseconds |
|----------|--------|-----------------|--------------|
| Standard pre-beat cut | Before beat | 2 frames | ~67ms |
| Aggressive/punchy feel | Before beat | 3 frames | ~100ms |
| Relaxed/breathing feel | On beat exactly | 0 frames | 0ms |
| Delayed impact (dramatic weight) | After beat | 1-2 frames | 33-67ms |

### Implementation

```python
PRE_BEAT_OFFSET_FRAMES = 2  # default: 2 frames early
PRE_BEAT_OFFSET_SEC = PRE_BEAT_OFFSET_FRAMES / 30.0  # 0.067s at 30fps

def adjust_beat_times(beat_times, offset=PRE_BEAT_OFFSET_SEC):
    """Shift all beat timestamps earlier by offset for visual anticipation."""
    return [max(0, t - offset) for t in beat_times]
```

### When to Skip Pre-Beat Offset

- During the calm intro section (no cuts happening anyway)
- On the very first beat drop (the drop itself IS the surprise -- cut exactly on it)
- When using a white/black flash transition (the flash provides the anticipation)

---

## 2. Beat Classification: Not Every Beat Deserves a Cut

### The Problem

Current pipeline treats all beats equally. Real editors skip many beats and only cut on strong ones. Over-cutting to every single beat creates a monotonous machine-gun effect that feels robotic.

### Beat Hierarchy

| Beat Type | Description | Action |
|-----------|-------------|--------|
| **Downbeat (1)** | First beat of each bar | ALWAYS cut here |
| **Snare/Backbeat (3)** | Third beat of each bar in 4/4 | Cut here for high energy sections |
| **Off-beats (2, 4)** | Weaker beats | Skip these for most sections; use for rapid-fire climax only |
| **Sub-beats (hi-hats, 8ths)** | Fastest transients from onset detection | Reserve for 2-7 frame micro-cuts in peak sections only |
| **Bass drops / big hits** | Detected by onset strength | Slow-mo or freeze frame here |

### Implementation: Onset Strength Filtering

```python
import librosa
import numpy as np

def classify_beats(audio_path, sr=22050):
    """Classify beats by strength to determine cut importance."""
    y, sr = librosa.load(audio_path, sr=sr)

    # Get onset strength envelope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    # Beat tracking
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Score each beat by its onset strength
    beat_strengths = onset_env[beat_frames]

    # Normalize to 0-1
    if beat_strengths.max() > 0:
        beat_strengths = beat_strengths / beat_strengths.max()

    # Classify
    strong_beats = []    # strength >= 0.6 -- always cut
    medium_beats = []    # strength 0.3-0.6 -- cut in high-energy sections
    weak_beats = []      # strength < 0.3 -- skip or use for micro-cuts only

    for t, s in zip(beat_times, beat_strengths):
        if s >= 0.6:
            strong_beats.append(t)
        elif s >= 0.3:
            medium_beats.append(t)
        else:
            weak_beats.append(t)

    return {
        "strong": strong_beats,
        "medium": medium_beats,
        "weak": weak_beats,
        "all": beat_times.tolist(),
        "strengths": beat_strengths.tolist(),
    }
```

### Pacing Rule: How Many Beats to Skip

| Edit Section | Which Beats to Cut On | Typical Interval at 140 BPM |
|-------------|----------------------|----------------------------|
| Calm intro | None | No cuts |
| Build-up | Strong beats only (every 4th) | ~1.7s between cuts |
| Main body | Strong + medium (every 2nd) | ~0.86s between cuts |
| Peak/climax | All beats | ~0.43s between cuts |
| Micro-burst (2-4s max) | Sub-beats / onsets | 2-7 frames per cut (~0.07-0.23s) |

---

## 3. Clip Duration: How Long to Hold Each Shot

### The Core Problem

Clips are too short when they cut off the action mid-play. Clips are too long when they linger on dead moments. The beat-driven duration ignores what is actually happening on screen.

### Duration Rules by Content Type

| Context | Minimum Clip Duration | Maximum Clip Duration | Notes |
|---------|----------------------|----------------------|-------|
| Rapid montage (hype) | 0.5s (15 frames) | 1.5s | Cut on every strong beat |
| Standard pacing | 1.0s (30 frames) | 3.0s | Most of the edit |
| Impact slow-mo | 1.5s (45 frames) | 4.0s | Let the moment land |
| Micro-burst | 0.07s (2 frames) | 0.23s (7 frames) | Stacking quick flashes |
| Breathing moment | 2.0s (60 frames) | 5.0s | After a peak, let viewer absorb |

### The "Action Completion" Rule

**Never cut in the middle of an action. Always let the action complete.**

An "action" in sports/fancam context means:
- A punch/hit/tackle landing and the reaction completing (~0.5-1.0s after impact)
- A celebration gesture finishing its arc (~1.0-2.0s)
- A facial expression reaching its peak (~0.5s after onset)
- A camera move completing (pan, zoom) (~0.3-0.5s)

### Implementation: Motion-Aware Cut Extension

```python
import subprocess
import json

def find_action_endpoint(video_path, proposed_cut_time, max_extension=1.0, fps=30):
    """
    Extend a cut point to find the natural end of the current action.

    Uses motion analysis: when motion drops significantly after a peak,
    the action has completed and it is safe to cut.
    """
    # Extract motion scores around the proposed cut point using ffmpeg
    # The 'mestimate' filter provides motion estimation
    start = proposed_cut_time
    end = proposed_cut_time + max_extension

    # Alternative: use frame differences as a proxy for motion
    # High diff = lots of motion (action happening)
    # Low diff = action settled (safe to cut)

    cmd = [
        'ffprobe', '-v', 'quiet',
        '-select_streams', 'v:0',
        '-show_frames',
        '-show_entries', 'frame=pts_time',
        '-read_intervals', f'{start}%{end}',
        '-of', 'json',
        video_path
    ]

    # In practice: compute per-frame luminance deltas
    # When delta drops below 30% of the local peak, the action has settled
    MOTION_SETTLE_THRESHOLD = 0.3  # 30% of peak motion

    # Return the adjusted cut time
    # If no clear settle point found, return original + 0.3s buffer
    return proposed_cut_time + 0.3  # fallback: add 0.3s buffer

# Simpler approach: minimum clip duration enforcement
MIN_CLIP_DURATION = 0.8  # seconds -- never shorter than this in standard sections
MIN_CLIP_FRAMES = 24     # at 30fps

def enforce_min_duration(cut_times, min_gap=MIN_CLIP_DURATION):
    """Remove cuts that are too close together, keeping the stronger beat."""
    if len(cut_times) < 2:
        return cut_times
    filtered = [cut_times[0]]
    for t in cut_times[1:]:
        if t - filtered[-1] >= min_gap:
            filtered.append(t)
    return filtered
```

---

## 4. Subject Focus: Keeping the Camera on Your Subject

### The Problem

Random `jump_points` in the source video have no awareness of WHO is on screen. The edit jumps to frames showing background characters, crowd shots, or empty scenery.

### Solution: Pre-Filter Clips with Scene/Subject Detection

#### Step 1: Scene Detection (Split Source into Usable Segments)

Use PySceneDetect to break the source video into individual shots/scenes first, rather than picking random timestamps.

```python
from scenedetect import detect, ContentDetector, AdaptiveDetector

def detect_scenes(video_path):
    """
    Split source video into natural scene boundaries.

    ContentDetector params:
      threshold=27.0   (default; lower = more sensitive; range 0-255)
      min_scene_len=15 (minimum 15 frames between cuts = 0.5s at 30fps)
      weights=(hue=1.0, sat=1.0, lum=1.0, edges=0.0)

    AdaptiveDetector params (better for camera motion):
      adaptive_threshold=3.0
      min_scene_len=15
      window_width=2
      min_content_val=15.0
    """
    scene_list = detect(video_path, ContentDetector(threshold=27.0, min_scene_len=15))
    # Returns list of (start_timecode, end_timecode) tuples

    scenes = []
    for start, end in scene_list:
        scenes.append({
            "start": start.get_seconds(),
            "end": end.get_seconds(),
            "duration": end.get_seconds() - start.get_seconds(),
        })
    return scenes
```

#### Step 2: Score Each Scene for Subject Presence

```python
import cv2

def score_scene_for_subject(video_path, scene_start, scene_end, fps=30):
    """
    Score a scene segment for subject presence.

    Returns a dict with:
      - face_score: 0-1 (how much of the scene has faces visible)
      - face_size_score: 0-1 (how large the face is -- close-ups score higher)
      - motion_score: 0-1 (how much movement is in the scene)
      - center_score: 0-1 (whether the subject is centered)
    """
    cap = cv2.VideoCapture(video_path)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    cap.set(cv2.CAP_PROP_POS_MSEC, scene_start * 1000)

    face_frames = 0
    total_frames = 0
    max_face_area = 0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_area = frame_w * frame_h

    # Sample every 5th frame for speed
    sample_interval = 5

    while cap.get(cv2.CAP_PROP_POS_MSEC) / 1000 < scene_end:
        ret, frame = cap.read()
        if not ret:
            break
        total_frames += 1

        if total_frames % sample_interval != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            face_frames += 1
            for (x, y, w, h) in faces:
                area = w * h
                max_face_area = max(max_face_area, area)

    cap.release()
    sampled = total_frames // sample_interval

    face_score = face_frames / max(sampled, 1)
    face_size_score = min(max_face_area / (frame_area * 0.15), 1.0)  # 15% of frame = max score
    # Close-up: face is >10% of frame area
    # Medium: face is 3-10% of frame area
    # Wide: face is <3% of frame area

    return {
        "face_score": round(face_score, 3),
        "face_size_score": round(face_size_score, 3),
    }
```

#### Step 3: Rank and Select Best Scenes

```python
def select_best_scenes(scenes_with_scores, num_needed, subject_weight=0.7, variety_weight=0.3):
    """
    Select the best N scenes for the edit.

    Prioritizes:
    1. Subject presence (face visible, close-up preferred)
    2. Scene variety (don't pick 5 consecutive scenes from the same section)
    3. Motion/action (high-energy moments preferred)
    """
    for scene in scenes_with_scores:
        scene["composite_score"] = (
            subject_weight * (scene["face_score"] * 0.5 + scene["face_size_score"] * 0.5)
            # + variety_weight * scene["position_diversity"]
        )

    # Sort by composite score descending
    ranked = sorted(scenes_with_scores, key=lambda s: s["composite_score"], reverse=True)

    # Select top N but enforce spacing (don't pick scenes within 5s of each other)
    selected = []
    min_spacing = 5.0  # seconds apart in source

    for scene in ranked:
        if len(selected) >= num_needed:
            break
        too_close = any(abs(scene["start"] - s["start"]) < min_spacing for s in selected)
        if not too_close:
            selected.append(scene)

    return selected
```

### Minimum Subject Requirements

| Requirement | Threshold | Action if Not Met |
|------------|-----------|-------------------|
| Face visible in scene | face_score >= 0.3 (30% of sampled frames) | Skip this scene entirely |
| Face is close-up or medium | face_size_score >= 0.2 (face area >= 3% of frame) | Deprioritize; use only if no better options |
| Multiple people visible | Count > 1 face | Crop/zoom to isolate main subject if possible |

---

## 5. Velocity Edits: Speed Ramping for Impact

### What Velocity Edits Are

Speed manipulation within a single clip: slow down on impact moments, speed up between moments. This is THE most popular technique in 2026 fancam/athlete edits.

### Speed Values

| Moment Type | Speed Multiplier | Effect |
|-------------|-----------------|--------|
| Impact frame (hit, dunk, catch) | 0.2x - 0.3x | Dramatic slow-mo; viewer savors the moment |
| Peak expression / celebration | 0.3x - 0.5x | Slow enough to read the emotion |
| Transition between clips | 2.0x - 4.0x | Rapid bridging; keeps energy up |
| Approach to impact | 1.5x - 2.0x | Building anticipation |
| Recovery after impact | 0.5x gradually to 1.0x | Easing back to normal |

### The Classic Velocity Curve (per clip)

```
Speed
  ^
  |   2-3x        2-3x
  |  /    \      /    \
  | /      \    /      \
1x|/        \  /        \
  |          \/
  |        0.2-0.3x
  |     (impact moment)
  +-------------------------> Time
```

Shape: Fast approach --> dramatic slow-mo at impact --> fast exit

### Implementation with ffmpeg

```bash
# Velocity edit using setpts filter
# Slow-mo at 0.25x (multiply PTS by 4)
ffmpeg -i clip.mp4 -vf "setpts=4.0*PTS" -an slow.mp4

# Speed up at 3x (divide PTS by 3)
ffmpeg -i clip.mp4 -vf "setpts=PTS/3.0" -an fast.mp4

# Variable speed using sendcmd (advanced)
# Creates speed ramp: normal -> slow -> normal
ffmpeg -i clip.mp4 -vf "
  setpts='if(between(T,1.0,2.0), 4.0*PTS, if(between(T,0.5,1.0), 2.0*PTS, PTS))'
" -an velocity_edit.mp4
```

### Practical Speed Ramp Implementation

```python
def generate_velocity_segments(clip_path, impact_time, clip_duration, fps=30):
    """
    Generate speed-ramped segments for a velocity edit.

    Args:
        clip_path: source video path
        impact_time: time within clip where the key moment happens (seconds)
        clip_duration: total clip duration (seconds)
        fps: frame rate

    Returns:
        List of (start, end, speed_multiplier) tuples
    """
    # Define zones around the impact
    approach_start = max(0, impact_time - 0.8)
    slow_start = max(0, impact_time - 0.2)
    slow_end = min(clip_duration, impact_time + 0.5)
    recovery_end = min(clip_duration, impact_time + 1.0)

    segments = []

    # Pre-approach: normal or slightly fast
    if approach_start > 0.1:
        segments.append((0, approach_start, 2.0))

    # Approach: building speed
    segments.append((approach_start, slow_start, 1.5))

    # Impact zone: dramatic slow-mo
    segments.append((slow_start, slow_end, 0.25))

    # Recovery: ease back to normal
    segments.append((slow_end, recovery_end, 0.5))

    # Exit: fast to next clip
    if recovery_end < clip_duration:
        segments.append((recovery_end, clip_duration, 2.5))

    return segments
```

### Frame Rate Requirement for Smooth Slow-Mo

| Source FPS | Minimum Slow-Mo Speed | Reasoning |
|-----------|----------------------|-----------|
| 24 fps | 0.5x (= 12 fps effective) | Below this, visibly choppy |
| 30 fps | 0.3x (= 9 fps; marginal) | 0.5x preferred for smoothness |
| 60 fps | 0.15x (= 9 fps; marginal) | Sweet spot is 0.25x (15 fps) |
| 120 fps | 0.1x (= 12 fps) | True cinematic slow-mo |

**Rule: Effective FPS after slow-down should be >= 12 fps to avoid choppiness.** If source is 30 fps, do not go slower than 0.4x without frame interpolation.

### Frame Interpolation for Smoother Slow-Mo

```bash
# Use ffmpeg minterpolate filter to generate intermediate frames
ffmpeg -i clip.mp4 -vf "setpts=4.0*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" -an smooth_slow.mp4
```

---

## 6. Edit Structure: Where to Place the Best Moment

### The Rule: Best Moment First, Second-Best Last

The research consensus for TikTok/short-form is clear:

| Position | What Goes Here | Why |
|----------|---------------|-----|
| **First 1-3 seconds** | Your single most jaw-dropping clip | Stops the scroll; 80% of viewers decide to stay or leave in this window |
| **4-15 seconds** | Rising action; next-best moments | Building energy; viewer is now committed |
| **Final 2-3 seconds** | Second-best moment (climax) | Emotional payoff; drives shares/rewatches; sets up the loop |

### The "Bookend" Structure

```
[BEST MOMENT] -> [Build] -> [Build] -> [Build] -> [SECOND BEST / CLIMAX]
   1-3s           varies      varies     varies        2-3s
     ^                                                   |
     |_______________ seamless loop _____________________|
```

This outperforms both "save the best for last" (loses viewers who never get there) and "all bangers no structure" (no narrative arc, feels flat).

### Implementation for the Pipeline

```python
def order_clips_for_edit(scored_clips):
    """
    Order clips for maximum engagement using bookend structure.

    scored_clips: list of dicts with 'composite_score' and clip data
    """
    ranked = sorted(scored_clips, key=lambda c: c["composite_score"], reverse=True)

    if len(ranked) < 3:
        return ranked

    best = ranked[0]          # Hook: first position
    second_best = ranked[1]   # Climax: last position
    rest = ranked[2:]         # Middle: ascending energy order

    # Sort middle clips by score ascending (weakest first, building up)
    rest.sort(key=lambda c: c["composite_score"])

    return [best] + rest + [second_best]
```

---

## 7. Pacing: Fast Cuts vs. Letting Moments Breathe

### The Contrast Principle

**The power of a fast cut comes from the slow moment before it.** Constant rapid cutting numbs the viewer. The contrast between pacing speeds is what creates impact.

### Pacing Map for a 30-Second Edit

| Timestamp | Section | Cuts/second | Clip Duration | Purpose |
|-----------|---------|-------------|---------------|---------|
| 0-3s | Hook | 1 clip | 2-3s | Best moment, held long enough to register |
| 3-8s | Build | 0.5-1 cuts/s | 1.0-2.0s | Rising energy, moderate pace |
| 8-12s | Push | 1-2 cuts/s | 0.5-1.0s | Faster, building toward peak |
| 12-16s | Peak | 2-4 cuts/s | 0.25-0.5s | Rapid-fire montage |
| 16-18s | Breathe | 0.5 cuts/s | 2.0-3.0s | One slow-mo moment to absorb |
| 18-25s | Second Push | 1-2 cuts/s | 0.5-1.0s | Building to climax |
| 25-28s | Climax | 1 clip slow-mo | 2-3s | Second-best moment, velocity edit |
| 28-30s | Exit | Cut to black or loop | 1-2s | Clean ending |

### The "Breathe After Peak" Rule

**After any sequence of 4+ rapid cuts (each < 0.5s), insert one longer clip (2-3s) before resuming.** This prevents fatigue and makes the next fast section feel fast again.

```python
def insert_breathing_room(cut_times, min_rapid_sequence=4, rapid_threshold=0.5, breath_duration=2.0):
    """
    After N consecutive rapid cuts, enforce a longer hold.

    Returns modified cut_times with breathing gaps inserted.
    """
    result = [cut_times[0]]
    rapid_count = 0

    for i in range(1, len(cut_times)):
        gap = cut_times[i] - cut_times[i-1]

        if gap < rapid_threshold:
            rapid_count += 1
        else:
            rapid_count = 0

        if rapid_count >= min_rapid_sequence:
            # Force next cut to be at least breath_duration away
            forced_time = result[-1] + breath_duration
            if forced_time < cut_times[i]:
                result.append(forced_time)
            rapid_count = 0

        result.append(cut_times[i])

    return result
```

### Do NOT Cut Every Single Beat

Let some beats pass without visual cuts. This builds anticipation. Professional editors typically cut on 30-60% of detected beats, reserving 100% beat-matching for climax moments only.

```python
def thin_beats(beat_times, keep_ratio=0.5, section="body"):
    """
    Keep only a fraction of beats for visual cuts.

    keep_ratio:
      0.25 = every 4th beat (calm build)
      0.5  = every other beat (standard)
      1.0  = every beat (climax only)
    """
    if section == "climax":
        return beat_times  # use all beats

    step = max(1, int(1.0 / keep_ratio))
    return beat_times[::step]
```

---

## 8. Scene Detection for Automated Editing

### Tools and Their Parameters

#### PySceneDetect (Recommended: Best Accuracy)

```bash
pip install scenedetect[opencv]
```

**Detectors and defaults:**

| Detector | Best For | Key Param | Default | Recommended Range |
|----------|----------|-----------|---------|-------------------|
| `ContentDetector` | Hard cuts | `threshold` | 27.0 | 20-35 (lower = more sensitive) |
| `AdaptiveDetector` | Camera motion, varying lighting | `adaptive_threshold` | 3.0 | 2.0-4.0 |
| `ThresholdDetector` | Fades to/from black | `threshold` | 12.0 | 8-16 |
| `HashDetector` | Perceptual changes | `threshold` | 0.395 | 0.3-0.5 |
| `HistogramDetector` | Color distribution shifts | `threshold` | 0.05 | 0.03-0.08 |

All detectors share `min_scene_len=15` (frames) to prevent false positives from flashes/strobes.

**CLI usage:**
```bash
# Detect scenes and split video
scenedetect -i source.mp4 detect-content -t 27 split-video

# Export scene list as CSV
scenedetect -i source.mp4 detect-content -t 27 list-scenes -o scenes.csv

# With adaptive detector for sports footage (camera pans)
scenedetect -i source.mp4 detect-adaptive -t 3.0 --min-content-val 15 split-video
```

**Python API:**
```python
from scenedetect import detect, ContentDetector, AdaptiveDetector, split_video_ffmpeg

# Basic scene detection
scene_list = detect('source.mp4', ContentDetector(threshold=27.0, min_scene_len=15))

# For sports footage with lots of camera motion, use adaptive
scene_list = detect('source.mp4', AdaptiveDetector(
    adaptive_threshold=3.0,
    min_scene_len=15,
    window_width=2,
    min_content_val=15.0,
))

# Split into individual clips
split_video_ffmpeg('source.mp4', scene_list)

# Or get timestamps for pipeline use
for i, (start, end) in enumerate(scene_list):
    print(f"Scene {i}: {start.get_seconds():.2f}s - {end.get_seconds():.2f}s")
```

#### FFmpeg Native Scene Detection (Faster, Less Accurate)

```bash
# Using select filter (legacy, all FFmpeg versions)
ffmpeg -i source.mp4 -filter:v "select='gt(scene,0.4)',showinfo" -f null - 2>&1 | grep showinfo

# Using scdet filter (FFmpeg 7.0+, better)
# threshold range: 8.0-14.0 recommended (scale 0-100)
ffmpeg -i source.mp4 -vf "scdet=threshold=10:sc_pass=1" -f null -

# Extract keyframes at scene changes
ffmpeg -i source.mp4 -filter:v "select='gt(scene,0.4)'" -vsync vfr scene_%04d.png
```

**Performance comparison:**

| Method | Speed (1hr 1080p) | Accuracy |
|--------|-------------------|----------|
| PySceneDetect ContentDetector | 5-15 min | 94-99% |
| PySceneDetect AdaptiveDetector | 5-15 min | 96-99% (best for camera motion) |
| FFmpeg scdet filter | 2-5 min | 85-92% |
| FFmpeg select scene filter | 2-5 min | 80-90% |

#### librosa Beat Detection (Audio-Side)

```python
import librosa

y, sr = librosa.load('track.wav', sr=22050)

# Beat tracking
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
beat_times = librosa.frames_to_time(beat_frames, sr=sr)

# Onset detection (finer: snares, hi-hats, transients)
onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
onset_times = librosa.frames_to_time(onset_frames, sr=sr)

# Onset strength for each beat (for classification)
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
beat_strengths = onset_env[beat_frames]

# Spectral flux for detecting "drops" (big timbral shifts)
spectral_flux = librosa.onset.onset_strength(y=y, sr=sr, feature=librosa.feature.melspectrogram)
```

---

## 9. Specific Pipeline Fixes

These are the exact changes to make in the current `edit.py` to fix the three problems.

### Fix 1: Replace Random Jump Points with Scene-Based Selection

**Current code (edit.py lines 138-149):**
```python
# PROBLEM: random positions, no subject awareness
jump_points = []
spacing = (safe_end - safe_start) / (num_segments + 1)
for idx in range(num_segments):
    base = safe_start + spacing * (idx + 1)
    jitter = random.uniform(-spacing * 0.25, spacing * 0.25)
    point = max(safe_start, min(safe_end - 2.0, base + jitter))
    jump_points.append(point)
random.shuffle(jump_points)
```

**Replacement approach:**
```python
from scenedetect import detect, AdaptiveDetector

def get_subject_focused_clips(video_path, num_needed, min_duration=0.5):
    """
    Replace random jump points with scene-detected, subject-filtered clips.
    """
    # Step 1: Detect all scene boundaries
    scenes = detect(video_path, AdaptiveDetector(
        adaptive_threshold=3.0,
        min_scene_len=15,
    ))

    # Step 2: Score each scene for subject presence
    scored_scenes = []
    for start, end in scenes:
        s = start.get_seconds()
        e = end.get_seconds()
        dur = e - s

        if dur < min_duration:
            continue

        score = score_scene_for_subject(video_path, s, e)
        scored_scenes.append({
            "start": s, "end": e, "duration": dur,
            **score
        })

    # Step 3: Filter out scenes without subject
    valid_scenes = [s for s in scored_scenes if s["face_score"] >= 0.3]

    # Step 4: Rank and select
    selected = select_best_scenes(valid_scenes, num_needed)

    # Step 5: Order for engagement (bookend structure)
    ordered = order_clips_for_edit(selected)

    return [(s["start"], s["end"]) for s in ordered]
```

### Fix 2: Add Pre-Beat Offset to Cut Times

**Current code (edit.py line 123):**
```python
# PROBLEM: cuts land exactly on beat -- perceived as late
cut_dur = beats[next_i] - beats[i]
```

**Add offset:**
```python
PRE_BEAT_FRAMES = 2
PRE_BEAT_SEC = PRE_BEAT_FRAMES / config.FPS  # 0.067s at 30fps

# Apply offset to beat times before using them
adjusted_beats = [max(0, b - PRE_BEAT_SEC) for b in beats]

# Then use adjusted_beats for cut point calculation
cut_dur = adjusted_beats[next_i] - adjusted_beats[i]
```

### Fix 3: Enforce Minimum Clip Duration to Prevent Cut-Off Highlights

**Current code (edit.py lines 119-120):**
```python
# PROBLEM: only checks if cut_dur < 0.1, allows very short clips that chop action
if cut_dur < 0.1:
    i += beat_step
    continue
```

**Replace with action-aware minimum:**
```python
MIN_STANDARD_CLIP = 0.8   # seconds -- minimum for standard pacing
MIN_CLIMAX_CLIP = 0.3     # seconds -- minimum during peak sections

# Determine section (based on position in edit)
progress = elapsed / max_montage_seconds
if progress > 0.7:  # last 30% = peak section
    min_clip = MIN_CLIMAX_CLIP
else:
    min_clip = MIN_STANDARD_CLIP

if cut_dur < min_clip:
    # Instead of skipping, extend to the next beat that meets minimum
    extended_i = next_i
    while extended_i < len(beats) - 1:
        extended_i += 1
        extended_dur = beats[extended_i] - beats[i]
        if extended_dur >= min_clip:
            break
    cut_dur = beats[extended_i] - beats[i]
    i = extended_i
    continue
```

---

## 10. Quick Reference: Codeable Rules Summary

| Rule | Value | Where to Apply |
|------|-------|---------------|
| Pre-beat visual offset | 2 frames (67ms) at 30fps | All beat-synced cut points |
| Minimum clip duration (standard) | 0.8s (24 frames) | Body of edit |
| Minimum clip duration (climax) | 0.3s (9 frames) | Peak montage section only |
| Maximum clip duration | 3.0s (90 frames) | Anywhere; longer = viewer drifts |
| Breathing clip after rapid sequence | 2.0-3.0s after 4+ rapid cuts | After any burst of < 0.5s clips |
| Subject face requirement | >= 30% of frames in scene | Clip selection filter |
| Face close-up preference | Face area >= 3% of frame | Clip ranking score |
| Velocity slow-mo on impact | 0.25x - 0.3x | Impact frames; limited by source fps |
| Velocity fast transition | 2.0x - 3.0x | Between impact moments |
| Effective FPS floor for slow-mo | >= 12 fps after speed reduction | Determines minimum speed multiplier |
| Beat cut ratio (body) | 50% of detected beats | Skip weak beats |
| Beat cut ratio (climax) | 100% of detected beats | Use all beats |
| Beat cut ratio (build) | 25% of detected beats | Strong beats only |
| Best clip placement | Position 1 (hook) | First 1-3 seconds |
| Second-best clip placement | Last position (climax) | Final 2-3 seconds |
| Scene detection threshold | 27.0 (ContentDetector) | PySceneDetect |
| Scene detection min length | 15 frames (0.5s) | Prevents false positives |
| Hook window | First 3 seconds | Must contain best moment |
| Total edit length (fancam) | 30-60 seconds | Sweet spot for engagement |
| Total edit length (hype) | 15-30 seconds | Shorter = higher completion rate |
| Export: resolution | 1080x1920 (9:16) or 720x720 | TikTok format |
| Export: frame rate | 30fps standard, 60fps if slow-mo heavy | Match content needs |
| Export: codec | H.264, CRF 18, MP4 | TikTok-optimized |

---

## Sources

- [CapCut Beat Sync / Auto-Beat Tutorial](https://www.tiktok.com/@rvm_thecameraguy/video/7264195497269742881)
- [Graphed: How to Analyze TikTok Video Editing Techniques](https://www.graphed.com/blog/how-to-analyze-tiktok-video-editing-techniques)
- [Inside the Edit: Master Pacing in Video Editing](https://www.insidetheedit.com/blog/pacing-in-video-editing)
- [Film Editing Pro: Timing and Pacing for Dramatic Moments](https://www.filmeditingpro.com/film-editing-timing-and-pacing-how-to-edit-dramatic-moments/)
- [Sportico: What Is a Sports Edit -- How Viral TikTok NBA Edits Took Over](https://www.sportico.com/business/tech/2025/sports-edit-guide-viral-tiktok-nba-jordy-social-media-1234850152/)
- [Mob Film: How to Edit a Sports Video Like a Pro](https://wearemob.tv/blog/how-to-edit-a-sports-video-like-a-pro/)
- [FlexClip: Velocity TikTok Guide](https://www.flexclip.com/learn/velocity-tiktok.html)
- [FlexClip: Fancam Video Guide](https://www.flexclip.com/learn/fancam-video.html)
- [CapCut: How to Do Velocity on CapCut](https://www.capcut.com/resource/how-to-do-velocity-on-capcut)
- [MiniTool: What Is a Velocity Edit](https://moviemaker.minitool.com/moviemaker/velocity-edit.html)
- [Klap: How to Create a Highlight Video -- Pro Tips 2026](https://klap.app/blog/how-to-create-a-highlight-video)
- [Revid: How to Make a Highlight Reel](https://www.revid.ai/blog/how-to-make-a-highlight-reel)
- [Vimeo: How to Make a Highlight Video](https://vimeo.com/blog/post/how-to-make-a-highlight-video)
- [PySceneDetect Documentation: Detection Algorithms](https://www.scenedetect.com/docs/latest/api/detectors.html)
- [PySceneDetect Homepage](https://www.scenedetect.com/)
- [BrightCoding: Python & OpenCV Video Scene Cut Detection Guide](https://www.blog.brightcoding.dev/2025/12/09/the-ultimate-guide-to-python-opencv-video-scene-cut-detection-automate-your-video-editing-like-a-pro/)
- [FFmpeg Scene Detection Notes (GitHub Gist)](https://gist.github.com/dudewheresmycode/054c8de34762091b43530af248b369e7)
- [FFmpeg scdet Filter Documentation](https://ayosec.github.io/ffmpeg-filters-docs/6.0/Filters/Video/scdet.html)
- [librosa: beat_track Documentation](https://librosa.org/doc/main/generated/librosa.beat.beat_track.html)
- [GitHub: emjjkk/beat-detection (EDL markers for video editing)](https://github.com/emjjkk/beat-detection)
- [Vegas Creative Software: Edit to the Beat of the Music](https://www.vegascreativesoftware.com/us/post-production/how-to-edit-video-footage-to-the-beats-of-music/)
- [SociaLens Hub: How to Cut Scenes Precisely on Beat](https://www.unrealtexture.com/how-to-cut-scenes-precisely-on-beat-a-complete-guide-to-musical-video-editing/)
- [Big Shoulders: 3 Video Editing Techniques for Optimal Delivery](https://www.bigshoulders.com/from-good-to-great-3-video-editing-techniques-for-optimal-delivery/)
- [LucidLink: Sports Video Editing Complete Guide](https://www.lucidlink.com/blog/sports-video-editing)
- [Clipchamp: How to Make a Fancam Video Edit](https://clipchamp.com/en/blog/fancam-videos/)
- [CapCut: How to Make Highlight Videos](https://www.capcut.com/resource/how-to-make-highlight-videos)
- [Skillman Video Group: Rhythmic Editing](https://www.skillmanvideogroup.com/rhythmic-editing/)
- [Lwks: A Precise Cut -- Beginner Guide to Video Editing Cuts](https://lwks.com/blog/a-precise-cut-a-beginner-guide-to-video-editing-cuts-and-techniques)
- [Blackmagic Forum: Best Way to Edit to Beat of Music](https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=69346)
- [OpusClip: 12 Best AI Beat-Sync and Cut-to-Music Tools](https://www.opus.pro/blog/best-ai-beat-sync)
