# Scene Detection and Smart Clip Selection: Implementation Guide

Technical reference for replacing random clip selection in our TikTok edit pipeline with intelligent, scene-aware segment picking. Compiled April 2026.

---

## The Problem

In `edit.py`, lines 138-149 generate jump points with uniform spacing + random jitter, then shuffle them:

```python
jump_points = []
spacing = (safe_end - safe_start) / (num_segments + 1)
for idx in range(num_segments):
    base = safe_start + spacing * (idx + 1)
    jitter = random.uniform(-spacing * 0.25, spacing * 0.25)
    point = max(safe_start, min(safe_end - 2.0, base + jitter))
    jump_points.append(point)
random.shuffle(jump_points)
```

This causes three concrete failures:
1. Cuts land mid-action (a punch lands, a glass breaks, a character turns -- we cut away before the payoff)
2. Segments start on the wrong person or an empty frame (camera is panning, we grab the transition)
3. No preference for high-energy moments -- a static dialogue wide shot gets the same weight as Tony flipping a table

---

## Solution Architecture

Replace random jump points with a three-stage pipeline:

```
Source Video
    |
    v
[Stage 1] Scene Boundary Detection  -->  list of natural cut points (timestamps)
    |
    v
[Stage 2] Segment Scoring           -->  each segment gets a motion/energy score
    |
    v
[Stage 3] Smart Selection           -->  pick top-scoring segments that align with beats
    |
    v
build_timeline() uses these instead of random jump_points
```

---

## Stage 1: Detect Natural Scene Boundaries

Scene boundaries are the timestamps where the source video already has a cut, fade, or significant visual change. These are the ONLY safe places to start or end our clips because the original editor already chose them as transition points.

### Option A: PySceneDetect (Recommended for Python-native pipeline)

PySceneDetect is the standard Python library for shot boundary detection. It returns frame-accurate scene start/end times.

**Install:**

```bash
pip install scenedetect[opencv]
```

**Basic detection -- get all scene boundaries:**

```python
from scenedetect import detect, ContentDetector, AdaptiveDetector

def detect_scene_boundaries(video_path, method="adaptive"):
    """
    Detect natural scene boundaries in a video.

    Returns list of (start_sec, end_sec) tuples for each scene.
    """
    if method == "adaptive":
        # AdaptiveDetector uses a rolling average threshold instead of fixed.
        # Handles fast camera movement better -- important for action scenes.
        # adaptive_threshold=3.0 means a frame must be 3x the rolling average
        # to trigger a cut. Lower = more sensitive.
        detector = AdaptiveDetector(
            adaptive_threshold=3.0,
            min_scene_len=15,       # minimum 15 frames (0.5s at 30fps) per scene
            window_width=2,         # rolling average window
            min_content_val=15.0,   # ignore very small changes
        )
    else:
        # ContentDetector uses a fixed threshold.
        # threshold=27.0 is the default -- lower catches more cuts.
        # For Sopranos footage with lots of dark scenes, try 20-25.
        detector = ContentDetector(
            threshold=27.0,
            min_scene_len=15,
        )

    scene_list = detect(video_path, detector)

    # Convert to simple (start_seconds, end_seconds) tuples
    boundaries = []
    for start_tc, end_tc in scene_list:
        boundaries.append((
            start_tc.get_seconds(),
            end_tc.get_seconds(),
        ))

    return boundaries
```

**ContentDetector vs AdaptiveDetector:**

| Detector | How It Works | Best For |
|---|---|---|
| `ContentDetector` | Compares weighted HSV differences between adjacent frames against a fixed threshold (default 27.0). Score 0-255. | Clean, well-lit footage with obvious hard cuts |
| `AdaptiveDetector` | Same HSV comparison but threshold is a rolling average of nearby frame scores. A frame must exceed `adaptive_threshold` * rolling_avg to trigger. | Footage with fast camera motion, varying lighting (Sopranos has both) |
| `ThresholdDetector` | Triggers on absolute brightness crossing a threshold. | Detecting fade-to-black / fade-from-black transitions |

**Constructor parameters that matter for our use case:**

- `min_scene_len=15`: Prevents detecting "scenes" shorter than 15 frames (0.5s). Since our montage cuts are 0.3-1.5s, this keeps source scene detection reasonable without fragmenting.
- `weights=Components(delta_hue=1.0, delta_sat=1.0, delta_lum=1.0, delta_edges=0.0)`: Default weights. For dark Sopranos footage, increasing `delta_lum` weight can help catch cuts in dimly-lit scenes.
- `luma_only=False`: Set to `True` if color grading in the source causes false positives.

**Advanced: get per-frame content scores for later use in Stage 2:**

```python
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.stats_manager import StatsManager

def detect_scenes_with_scores(video_path):
    """
    Detect scenes AND return per-frame content scores.

    The scores are useful for Stage 2 (ranking segments by visual change).
    """
    video = open_video(video_path)
    stats = StatsManager()
    scene_manager = SceneManager(stats_manager=stats)
    scene_manager.add_detector(ContentDetector(threshold=27.0))

    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    # Extract per-frame content_val scores
    # These represent how different each frame is from the previous one.
    # Higher score = more visual change = more "interesting" moment.
    frame_scores = {}
    if stats is not None:
        frame_count = stats._registered_metrics  # internal, but stable
        for frame_num in range(video.scene_manager.get_num_frames()):
            score = stats.get_metrics(frame_num, ["content_val"])
            if score and score[0] is not None:
                frame_scores[frame_num] = score[0]

    boundaries = []
    for start_tc, end_tc in scene_list:
        boundaries.append((start_tc.get_seconds(), end_tc.get_seconds()))

    return boundaries, frame_scores
```

### Option B: ffmpeg select filter (Recommended for speed / no extra deps)

ffmpeg has a built-in scene detection score available through the `select` filter. The `scene` value ranges from 0.0 to 1.0, where higher values indicate a greater probability that the current frame starts a new scene.

**Get scene change timestamps with ffmpeg:**

```bash
# Detect frames where scene score > 0.4 (moderate sensitivity)
# Lower threshold (0.3) = more detected cuts, higher (0.5) = only obvious cuts
ffmpeg -i source.mp4 \
  -filter:v "select='gt(scene,0.4)',showinfo" \
  -f null - 2>&1 | grep showinfo

# Output includes lines like:
# [Parsed_showinfo_1 @ 0x...] n:  42 pts:   1401 pts_time:1.401 ...
# Parse pts_time values to get scene change timestamps.
```

**Extract timestamps as JSON with ffprobe:**

```bash
# Get scene scores for ALL frames (we filter in Python)
ffprobe -show_frames -of json \
  -f lavfi "movie=source.mp4,select=gt(scene\,0.3)" \
  source.mp4 2>/dev/null
```

**Python wrapper using subprocess:**

```python
import subprocess
import json
import re

def detect_scenes_ffmpeg(video_path, threshold=0.4):
    """
    Detect scene changes using ffmpeg's select filter.

    Returns list of timestamps (seconds) where scene changes occur.
    Fast -- uses ffmpeg directly, no Python frame processing.
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-an", "-f", "null", "-"
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300
    )

    # Parse timestamps from metadata output
    timestamps = []
    for line in result.stderr.split("\n"):
        # Look for pts_time in showinfo output
        match = re.search(r"pts_time:(\d+\.?\d*)", line)
        if match:
            timestamps.append(float(match.group(1)))

    return sorted(set(timestamps))


def detect_scenes_ffprobe(video_path, threshold=0.4):
    """
    Alternative: use ffprobe to get scene scores with timestamps.

    Returns list of dicts: [{"time": 1.234, "score": 0.85}, ...]
    """
    cmd = [
        "ffprobe",
        "-show_frames",
        "-of", "compact=p=0",
        "-f", "lavfi",
        f"movie={video_path},select=gt(scene\\,{threshold})",
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=300
    )

    scenes = []
    for line in result.stdout.split("\n"):
        if "media_type=video" not in line:
            continue

        time_match = re.search(r"pkt_pts_time=([0-9.]+)", line)
        score_match = re.search(r"tag:lavfi\.scene_score=([0-9.]+)", line)

        if time_match:
            entry = {"time": float(time_match.group(1))}
            if score_match:
                entry["score"] = float(score_match.group(1))
            scenes.append(entry)

    return scenes
```

**Threshold tuning guide:**

| Threshold | Sensitivity | Use Case |
|---|---|---|
| 0.2 - 0.3 | High -- catches subtle changes, camera pans, lighting shifts | When you need EVERY possible cut point |
| 0.3 - 0.4 | Medium -- catches most hard cuts, some dissolves | General purpose (start here) |
| 0.4 - 0.5 | Low -- only obvious hard cuts | Clean footage with clear scene transitions |
| 0.5+ | Very low -- only dramatic scene changes | When source has lots of fast motion causing false positives |

For Sopranos compilation footage, **start at 0.35** since the show has many dark scenes where cuts are less visually dramatic.

### Option C: scenecut-extractor (Convenience wrapper)

A lightweight pip package that wraps ffmpeg's scene detection into a clean JSON output.

```bash
pip install scenecut-extractor
```

```bash
# CLI usage -- outputs JSON array of scene cuts
scenecut-extractor source.mp4 -t 0.4

# Output:
# [
#   {"frame": 42, "pts": 1401, "pts_time": 1.401, "score": 0.85},
#   {"frame": 128, "pts": 4270, "pts_time": 4.270, "score": 0.72},
#   ...
# ]
```

```python
# Python API
from scenecut_extractor import extract

scenes = extract("source.mp4", threshold=0.4)
# Returns same JSON structure as CLI
```

---

## Stage 2: Score Segments by Visual Interest

Once we have scene boundaries, we need to rank them. Not all scenes are equal -- a close-up of Tony at the dinner table is more visually dynamic than a static wide shot of the Bada Bing parking lot.

### Method A: Motion Energy via Optical Flow (Most Accurate)

Compute dense optical flow between consecutive frames and sum the magnitude. High motion energy = action, camera movement, gestures. Low motion energy = static shot, talking heads.

```python
import cv2
import numpy as np

def compute_motion_scores(video_path, scene_boundaries, sample_fps=5):
    """
    Score each scene segment by average motion energy.

    Uses Farneback dense optical flow -- computes motion vectors for every pixel,
    then averages the magnitude across the frame.

    Args:
        video_path: path to source video
        scene_boundaries: list of (start_sec, end_sec) from Stage 1
        sample_fps: how many frames per second to sample (lower = faster)

    Returns:
        list of dicts: [{"start": 1.0, "end": 5.2, "motion_score": 1847.3}, ...]
    """
    cap = cv2.VideoCapture(video_path)
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_skip = max(1, int(source_fps / sample_fps))

    scored_segments = []

    for start_sec, end_sec in scene_boundaries:
        start_frame = int(start_sec * source_fps)
        end_frame = int(end_sec * source_fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        prev_gray = None
        motion_values = []
        frame_idx = start_frame

        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (frame_idx - start_frame) % frame_skip != 0:
                frame_idx += 1
                continue

            # Downscale for speed -- we only need relative scores, not precision
            small = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                # Farneback dense optical flow
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray,
                    None,             # output flow
                    pyr_scale=0.5,    # pyramid scale
                    levels=3,         # pyramid levels
                    winsize=15,       # averaging window
                    iterations=3,     # iterations at each level
                    poly_n=5,         # pixel neighborhood size
                    poly_sigma=1.2,   # gaussian std for polynomial
                    flags=0,
                )
                # Magnitude of motion vectors
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_values.append(float(np.mean(mag)))

            prev_gray = gray
            frame_idx += 1

        avg_motion = np.mean(motion_values) if motion_values else 0.0
        peak_motion = np.max(motion_values) if motion_values else 0.0

        scored_segments.append({
            "start": start_sec,
            "end": end_sec,
            "duration": end_sec - start_sec,
            "motion_score": float(avg_motion),
            "peak_motion": float(peak_motion),
        })

    cap.release()
    return scored_segments
```

**Performance note:** At 320x240 resolution with sample_fps=5, this processes a 10-minute source video in ~15-30 seconds. Good enough for our pipeline since we run it once per source clip, not per edit.

### Method B: Frame Difference Energy (Faster, simpler)

Instead of full optical flow, just compute the absolute difference between consecutive frames. Less accurate but 3-5x faster.

```python
def compute_frame_diff_scores(video_path, scene_boundaries, sample_fps=5):
    """
    Score segments by average frame-to-frame pixel difference.

    Faster than optical flow but less precise -- captures brightness/color
    changes and large motion but misses subtle movement direction.
    """
    cap = cv2.VideoCapture(video_path)
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_skip = max(1, int(source_fps / sample_fps))

    scored_segments = []

    for start_sec, end_sec in scene_boundaries:
        start_frame = int(start_sec * source_fps)
        end_frame = int(end_sec * source_fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        prev_gray = None
        diff_values = []
        frame_idx = start_frame

        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (frame_idx - start_frame) % frame_skip != 0:
                frame_idx += 1
                continue

            small = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                diff_values.append(float(np.mean(diff)))

            prev_gray = gray
            frame_idx += 1

        avg_diff = np.mean(diff_values) if diff_values else 0.0

        scored_segments.append({
            "start": start_sec,
            "end": end_sec,
            "duration": end_sec - start_sec,
            "energy_score": float(avg_diff),
        })

    cap.release()
    return scored_segments
```

### Method C: ffmpeg-only Motion Scoring (No OpenCV needed)

Use ffmpeg's built-in filters to approximate motion energy without any Python frame processing. This aligns with our MEMORY.md directive to move processing to ffmpeg filters and skip numpy per-frame processing.

```python
import subprocess
import re

def compute_motion_scores_ffmpeg(video_path, scene_boundaries):
    """
    Score segments using ffmpeg's signalstats filter.

    Uses HUEAVG (hue average) and SATAVG (saturation average) variance
    as a proxy for visual dynamism. Not true motion detection, but
    fast and dependency-free.
    """
    scored_segments = []

    for start_sec, end_sec in scene_boundaries:
        duration = end_sec - start_sec

        # Use the blend filter to compute frame differences natively in ffmpeg
        cmd = [
            "ffmpeg",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", video_path,
            "-vf", (
                "scale=160:120,"            # downscale for speed
                "tblend=all_mode=difference," # frame difference
                "blackframe=amount=0"        # outputs frame stats
            ),
            "-an", "-f", "null", "-"
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )

        # Parse blackframe output for average brightness of the diff frames.
        # Higher brightness in diff = more motion between frames.
        pblack_values = []
        for line in result.stderr.split("\n"):
            match = re.search(r"pblack:(\d+)", line)
            if match:
                # pblack = percentage of black pixels in diff frame
                # Lower pblack = more pixels changed = more motion
                pblack_values.append(int(match.group(1)))

        if pblack_values:
            # Invert: 100 - pblack gives us a "motion percentage"
            motion_pct = 100.0 - np.mean(pblack_values)
        else:
            motion_pct = 0.0

        scored_segments.append({
            "start": start_sec,
            "end": end_sec,
            "duration": duration,
            "motion_score": motion_pct,
        })

    return scored_segments
```

### Composite Scoring

Combine multiple signals for a better ranking:

```python
def compute_composite_score(segment, weights=None):
    """
    Combine motion, duration, and scene-change scores into a single rank.

    weights dict controls relative importance:
      - motion:   high-motion segments are more visually interesting
      - duration: prefer segments that are long enough to be usable
      - change:   high scene-change score at boundaries = cleaner cuts
    """
    if weights is None:
        weights = {
            "motion": 0.5,
            "duration_fit": 0.3,
            "boundary_score": 0.2,
        }

    # Normalize motion to 0-1 (caller should normalize across all segments first)
    motion = segment.get("motion_score_normalized", 0.0)

    # Duration fitness: prefer 1-4 second segments (ideal for TikTok cuts)
    dur = segment["duration"]
    if 0.5 <= dur <= 4.0:
        dur_fit = 1.0
    elif dur < 0.5:
        dur_fit = dur / 0.5      # penalty for too short
    else:
        dur_fit = max(0.0, 1.0 - (dur - 4.0) / 10.0)  # gentle penalty for long

    # Boundary score from scene detection (if available)
    boundary = segment.get("boundary_score", 0.5)

    score = (
        weights["motion"] * motion +
        weights["duration_fit"] * dur_fit +
        weights["boundary_score"] * boundary
    )

    return score
```

---

## Stage 3: Smart Selection -- Integrating with build_timeline()

This is where we replace the random jump_points generation in `edit.py`.

### Complete integration function

```python
import os
import json
import hashlib

def get_smart_jump_points(video_path, num_segments, montage_durations,
                          cache_dir=None, method="pyscenedetect"):
    """
    Replace random jump_points with scene-aware, scored selections.

    This function:
      1. Detects scene boundaries (cached on disk after first run)
      2. Scores each scene by motion energy
      3. Selects top-scoring segments that match our needed durations
      4. Returns jump_points list compatible with build_timeline()

    Args:
        video_path: path to source video
        num_segments: how many segments we need
        montage_durations: list of desired durations for each segment
        cache_dir: where to store scene detection cache (default: same dir as video)
        method: "pyscenedetect" or "ffmpeg"

    Returns:
        list of float timestamps (jump points into source video)
    """
    # --- Cache key based on video file ---
    video_hash = hashlib.md5(
        f"{video_path}:{os.path.getsize(video_path)}".encode()
    ).hexdigest()[:12]

    if cache_dir is None:
        cache_dir = os.path.dirname(video_path)
    cache_path = os.path.join(cache_dir, f"scene_cache_{video_hash}.json")

    # --- Load or compute scene analysis ---
    if os.path.exists(cache_path):
        print(f"  Loading cached scene analysis...")
        with open(cache_path) as f:
            analysis = json.load(f)
        scored_segments = analysis["segments"]
    else:
        print(f"  Detecting scene boundaries ({method})...")

        if method == "pyscenedetect":
            from scenedetect import detect, AdaptiveDetector
            scene_list = detect(video_path, AdaptiveDetector(
                adaptive_threshold=3.0,
                min_scene_len=15,
            ))
            boundaries = [
                (s[0].get_seconds(), s[1].get_seconds())
                for s in scene_list
            ]
        else:
            boundaries_raw = detect_scenes_ffmpeg(video_path, threshold=0.35)
            # Convert cut points to scene ranges
            boundaries = []
            for i in range(len(boundaries_raw) - 1):
                boundaries.append((boundaries_raw[i], boundaries_raw[i + 1]))

        print(f"  Found {len(boundaries)} scenes. Scoring motion energy...")
        scored_segments = compute_motion_scores(
            video_path, boundaries, sample_fps=5
        )

        # Normalize motion scores to 0-1
        if scored_segments:
            max_motion = max(s["motion_score"] for s in scored_segments)
            if max_motion > 0:
                for s in scored_segments:
                    s["motion_score_normalized"] = s["motion_score"] / max_motion

        # Compute composite scores
        for s in scored_segments:
            s["composite_score"] = compute_composite_score(s)

        # Cache to disk
        analysis = {
            "video_path": video_path,
            "method": method,
            "num_scenes": len(boundaries),
            "segments": scored_segments,
        }
        with open(cache_path, "w") as f:
            json.dump(analysis, f, indent=2)
        print(f"  Cached to {cache_path}")

    # --- Select best segments ---
    # Sort by composite score (highest first)
    ranked = sorted(scored_segments, key=lambda s: s.get("composite_score", 0), reverse=True)

    # Filter out segments that are too short or too long
    viable = [
        s for s in ranked
        if s["duration"] >= 0.3 and s["start"] >= 3.0
    ]

    if len(viable) < num_segments:
        print(f"  WARNING: Only {len(viable)} viable segments, need {num_segments}. "
              f"Supplementing with lower-ranked segments.")
        viable = ranked  # fall back to all segments

    # Pick top N segments, trying to match requested durations
    jump_points = []
    used_ranges = []  # track used time ranges to avoid overlap

    for i in range(min(num_segments, len(viable))):
        target_dur = montage_durations[i] if i < len(montage_durations) else 1.0

        # Find best unused segment
        for seg in viable:
            seg_start = seg["start"]
            seg_end = seg["end"]

            # Check overlap with already-selected segments
            overlaps = any(
                seg_start < used_end and seg_end > used_start
                for used_start, used_end in used_ranges
            )
            if overlaps:
                continue

            # Check segment is long enough for our target duration
            if seg["duration"] >= target_dur * 0.5:
                jump_points.append(seg_start)
                used_ranges.append((seg_start, seg_start + target_dur + 0.1))
                break

    # If we still don't have enough, fill with evenly-spaced fallbacks
    if len(jump_points) < num_segments:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total_dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        spacing = (total_dur - 6.0) / (num_segments - len(jump_points) + 1)
        for j in range(num_segments - len(jump_points)):
            fallback = 3.0 + spacing * (j + 1)
            jump_points.append(fallback)

    return jump_points[:num_segments]
```

### Minimal edit.py patch

The smallest change to `edit.py` that switches from random to smart selection. This replaces the random jump_points block (lines ~138-149):

```python
# --- BEFORE (random selection) ---
jump_points = []
spacing = (safe_end - safe_start) / (num_segments + 1)
for idx in range(num_segments):
    base = safe_start + spacing * (idx + 1)
    jitter = random.uniform(-spacing * 0.25, spacing * 0.25)
    point = max(safe_start, min(safe_end - 2.0, base + jitter))
    jump_points.append(point)
random.shuffle(jump_points)

# --- AFTER (smart selection) ---
try:
    from scene_detect import get_smart_jump_points
    jump_points = get_smart_jump_points(
        video_path=sopranos_path,
        num_segments=num_segments,
        montage_durations=montage_durations,
        cache_dir=config.ASSETS_DIR,
    )
    print(f"  Using smart clip selection ({len(jump_points)} scene-aware segments)")
except ImportError:
    print(f"  WARNING: scene_detect module not found, falling back to random selection")
    jump_points = []
    spacing = (safe_end - safe_start) / (num_segments + 1)
    for idx in range(num_segments):
        base = safe_start + spacing * (idx + 1)
        jitter = random.uniform(-spacing * 0.25, spacing * 0.25)
        point = max(safe_start, min(safe_end - 2.0, base + jitter))
        jump_points.append(point)
    random.shuffle(jump_points)
```

---

## Avoiding Mid-Action Cuts

This is the hardest problem. Scene detection tells us where cuts already exist, but within a scene, we might still cut mid-action. Three mitigation strategies:

### Strategy 1: Always start at scene boundaries

If we only use timestamps from scene detection as our jump points, we always start where the original editor intended a new shot to begin. This is the primary defense.

### Strategy 2: End buffer with motion drop-off detection

Instead of cutting exactly at `jump_pt + cut_dur`, detect when motion energy drops within the segment and cut there:

```python
def find_clean_end_point(video_path, start_sec, target_end_sec, fps=30):
    """
    Find a clean end point near target_end_sec where motion is decreasing.

    Looks in a window around the target end time for a local minimum
    in frame-to-frame difference. This avoids cutting at the peak of
    an action (mid-punch, mid-turn, etc).

    Args:
        start_sec: segment start (for context)
        target_end_sec: where we ideally want to end
        fps: video fps

    Returns:
        adjusted end time (seconds) near target_end_sec
    """
    cap = cv2.VideoCapture(video_path)
    source_fps = cap.get(cv2.CAP_PROP_FPS)

    # Search window: 0.3s before to 0.3s after target end
    window_start = max(start_sec + 0.3, target_end_sec - 0.3)
    window_end = target_end_sec + 0.3

    start_frame = int(window_start * source_fps)
    end_frame = int(window_end * source_fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    prev_gray = None
    diffs = []  # (frame_idx, diff_value)

    for frame_idx in range(start_frame, end_frame):
        ret, frame = cap.read()
        if not ret:
            break

        small = cv2.resize(frame, (160, 120))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if prev_gray is not None:
            diff = float(np.mean(cv2.absdiff(prev_gray, gray)))
            diffs.append((frame_idx, diff))

        prev_gray = gray

    cap.release()

    if not diffs:
        return target_end_sec

    # Find the frame with minimum motion (cleanest cut point)
    best_frame, best_diff = min(diffs, key=lambda x: x[1])
    clean_end = best_frame / source_fps

    return clean_end
```

### Strategy 3: Action completion heuristic

For very short cuts (under 1 second), ensure the full segment is used -- don't trim it. For longer segments where we only need a portion, prefer starting at the scene boundary and cutting at a motion trough:

```python
def smart_subclip(video_path, scene_start, scene_end, target_duration):
    """
    Extract a subclip of target_duration from a scene, avoiding mid-action cuts.

    Strategy:
      - Always start at scene_start (the natural cut point)
      - If scene is shorter than target_duration, use the whole scene
      - If scene is longer, find a clean end point near target_duration
    """
    scene_duration = scene_end - scene_start

    if scene_duration <= target_duration * 1.2:
        # Scene roughly matches target -- use it all
        return scene_start, scene_end

    # Scene is longer than needed -- find clean cut point
    target_end = scene_start + target_duration
    clean_end = find_clean_end_point(video_path, scene_start, target_end)

    return scene_start, clean_end
```

---

## Prioritizing High-Energy Segments

For TikTok edits, "high energy" means a combination of:
- **Motion**: camera movement, character movement, action
- **Visual contrast**: bright-to-dark transitions, color shifts
- **Facial close-ups**: more engaging than wide shots (this requires face detection)

### Simple energy ranking (no ML needed)

```python
def rank_segments_for_tiktok(scored_segments, style="darkwave"):
    """
    Rank segments for TikTok edit styles.

    Different styles prefer different segment characteristics:
      - darkwave: highest motion, dramatic moments
      - cinematic: medium motion, good composition (longer scenes)
      - atmospheric: varied -- mix of high and low energy
    """
    style_weights = {
        "darkwave": {"motion": 0.7, "duration_fit": 0.2, "boundary_score": 0.1},
        "cinematic": {"motion": 0.3, "duration_fit": 0.5, "boundary_score": 0.2},
        "atmospheric": {"motion": 0.5, "duration_fit": 0.3, "boundary_score": 0.2},
    }

    weights = style_weights.get(style, style_weights["darkwave"])

    for seg in scored_segments:
        seg["rank_score"] = compute_composite_score(seg, weights)

    return sorted(scored_segments, key=lambda s: s["rank_score"], reverse=True)
```

### Optional: Face detection boost

If a segment contains a close-up of a face, boost its score. This is optional and adds an OpenCV dependency for the Haar cascade, but dramatically improves subject selection for character-focused edits.

```python
def has_prominent_face(video_path, start_sec, end_sec):
    """
    Check if a segment contains a prominent face (close-up).

    Returns a boost factor: 1.0 (no face), 1.3 (face present), 1.5 (close-up face).
    """
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Sample 3 frames from the segment
    sample_times = [
        start_sec + (end_sec - start_sec) * frac
        for frac in [0.25, 0.5, 0.75]
    ]

    max_face_ratio = 0.0

    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        for (x, y, w, h) in faces:
            face_area = w * h
            frame_area = frame.shape[0] * frame.shape[1]
            ratio = face_area / frame_area
            max_face_ratio = max(max_face_ratio, ratio)

    cap.release()

    if max_face_ratio > 0.1:    # face takes up >10% of frame = close-up
        return 1.5
    elif max_face_ratio > 0.02:  # face visible but not dominant
        return 1.3
    else:
        return 1.0
```

---

## Complete New Module: scene_detect.py

Here is the full module that can be dropped into the `sopranos_edit/` directory:

```python
#!/usr/bin/env python3
"""
Smart scene detection and clip selection for TikTok edit pipeline.

Replaces random jump_point generation in edit.py with scene-aware,
motion-scored segment selection.

Dependencies:
  - Required:  opencv-python (cv2), numpy
  - Optional:  scenedetect (pip install scenedetect[opencv])
  - Fallback:  ffmpeg CLI (always available in our pipeline)

Usage:
    from scene_detect import get_smart_jump_points

    jump_points = get_smart_jump_points(
        video_path="assets/clips/Sopranos.mp4",
        num_segments=20,
        montage_durations=[0.5, 0.5, 0.8, ...],
    )
"""

import os
import sys
import json
import hashlib
import subprocess
import re

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Stage 1: Scene boundary detection
# ---------------------------------------------------------------------------

def detect_scenes_pyscenedetect(video_path, threshold=3.0, min_scene_len=15):
    """Detect scene boundaries using PySceneDetect's AdaptiveDetector."""
    from scenedetect import detect, AdaptiveDetector

    scene_list = detect(video_path, AdaptiveDetector(
        adaptive_threshold=threshold,
        min_scene_len=min_scene_len,
    ))

    return [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list]


def detect_scenes_ffmpeg(video_path, threshold=0.35):
    """Detect scene boundaries using ffmpeg's select filter."""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-an", "-f", "null", "-"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    timestamps = [0.0]  # always include start
    for line in result.stderr.split("\n"):
        match = re.search(r"pts_time:\s*([0-9.]+)", line)
        if match:
            t = float(match.group(1))
            if t > 0:
                timestamps.append(t)

    timestamps = sorted(set(timestamps))

    # Get video duration
    cap = cv2.VideoCapture(video_path)
    total_dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    timestamps.append(total_dur)

    # Convert cut points to (start, end) ranges
    boundaries = []
    for i in range(len(timestamps) - 1):
        if timestamps[i + 1] - timestamps[i] >= 0.3:
            boundaries.append((timestamps[i], timestamps[i + 1]))

    return boundaries


def detect_scenes(video_path, method="auto", **kwargs):
    """
    Detect scene boundaries using best available method.

    method="auto" tries PySceneDetect first, falls back to ffmpeg.
    """
    if method == "auto":
        try:
            return detect_scenes_pyscenedetect(video_path, **kwargs)
        except ImportError:
            print("  PySceneDetect not installed, using ffmpeg fallback")
            return detect_scenes_ffmpeg(video_path, **kwargs)
    elif method == "pyscenedetect":
        return detect_scenes_pyscenedetect(video_path, **kwargs)
    else:
        return detect_scenes_ffmpeg(video_path, **kwargs)


# ---------------------------------------------------------------------------
# Stage 2: Motion/energy scoring
# ---------------------------------------------------------------------------

def compute_motion_scores(video_path, scene_boundaries, sample_fps=5):
    """
    Score each scene by average optical flow magnitude.

    Returns list of dicts with start, end, duration, motion_score, peak_motion.
    """
    cap = cv2.VideoCapture(video_path)
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_skip = max(1, int(source_fps / sample_fps))

    scored = []

    for start_sec, end_sec in scene_boundaries:
        start_frame = int(start_sec * source_fps)
        end_frame = int(end_sec * source_fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        prev_gray = None
        motion_vals = []
        frame_idx = start_frame

        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (frame_idx - start_frame) % frame_skip != 0:
                frame_idx += 1
                continue

            small = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            if prev_gray is not None:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None,
                    0.5, 3, 15, 3, 5, 1.2, 0
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                motion_vals.append(float(np.mean(mag)))

            prev_gray = gray
            frame_idx += 1

        avg_motion = float(np.mean(motion_vals)) if motion_vals else 0.0
        peak_motion = float(np.max(motion_vals)) if motion_vals else 0.0

        scored.append({
            "start": start_sec,
            "end": end_sec,
            "duration": end_sec - start_sec,
            "motion_score": avg_motion,
            "peak_motion": peak_motion,
        })

    cap.release()
    return scored


def normalize_scores(segments):
    """Normalize motion_score to 0-1 range across all segments."""
    if not segments:
        return segments

    max_motion = max(s["motion_score"] for s in segments)
    if max_motion > 0:
        for s in segments:
            s["motion_score_normalized"] = s["motion_score"] / max_motion
    else:
        for s in segments:
            s["motion_score_normalized"] = 0.0

    return segments


def compute_composite_score(segment, weights=None):
    """Combine motion and duration fitness into a single rank score."""
    if weights is None:
        weights = {"motion": 0.6, "duration_fit": 0.4}

    motion = segment.get("motion_score_normalized", 0.0)

    dur = segment["duration"]
    if 0.5 <= dur <= 4.0:
        dur_fit = 1.0
    elif dur < 0.5:
        dur_fit = dur / 0.5
    else:
        dur_fit = max(0.0, 1.0 - (dur - 4.0) / 10.0)

    return weights["motion"] * motion + weights["duration_fit"] * dur_fit


# ---------------------------------------------------------------------------
# Stage 3: Smart selection
# ---------------------------------------------------------------------------

def find_clean_end_point(cap, start_sec, target_end_sec, source_fps):
    """Find a low-motion frame near target_end_sec to cut on."""
    window_start = max(start_sec + 0.2, target_end_sec - 0.3)
    window_end = target_end_sec + 0.3

    start_frame = int(window_start * source_fps)
    end_frame = int(window_end * source_fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    prev_gray = None
    diffs = []

    for frame_idx in range(start_frame, end_frame):
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (160, 120))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff = float(np.mean(cv2.absdiff(prev_gray, gray)))
            diffs.append((frame_idx, diff))
        prev_gray = gray

    if not diffs:
        return target_end_sec

    best_frame, _ = min(diffs, key=lambda x: x[1])
    return best_frame / source_fps


def get_smart_jump_points(video_path, num_segments, montage_durations,
                          cache_dir=None, method="auto", style="darkwave"):
    """
    Main entry point: replace random jump_points with smart selection.

    Compatible with edit.py's build_timeline() -- returns a list of
    float timestamps into the source video.
    """
    # --- Cache key ---
    video_stat = f"{video_path}:{os.path.getsize(video_path)}"
    video_hash = hashlib.md5(video_stat.encode()).hexdigest()[:12]

    if cache_dir is None:
        cache_dir = os.path.dirname(video_path)
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"scene_cache_{video_hash}.json")

    # --- Load or compute ---
    if os.path.exists(cache_path):
        print(f"  Loading cached scene analysis...")
        with open(cache_path) as f:
            scored_segments = json.load(f)["segments"]
    else:
        print(f"  Detecting scene boundaries...")
        boundaries = detect_scenes(video_path, method=method)
        print(f"  Found {len(boundaries)} scenes. Scoring motion energy...")
        scored_segments = compute_motion_scores(video_path, boundaries)
        scored_segments = normalize_scores(scored_segments)

        for s in scored_segments:
            s["composite_score"] = compute_composite_score(s)

        with open(cache_path, "w") as f:
            json.dump({"segments": scored_segments}, f, indent=2)
        print(f"  Cached scene analysis to {cache_path}")

    # --- Style-based weights ---
    style_weights = {
        "darkwave":    {"motion": 0.7, "duration_fit": 0.3},
        "cinematic":   {"motion": 0.3, "duration_fit": 0.7},
        "atmospheric": {"motion": 0.5, "duration_fit": 0.5},
    }
    weights = style_weights.get(style, style_weights["darkwave"])

    for s in scored_segments:
        s["rank_score"] = compute_composite_score(s, weights)

    # --- Rank and select ---
    ranked = sorted(scored_segments, key=lambda s: s["rank_score"], reverse=True)
    viable = [s for s in ranked if s["duration"] >= 0.3 and s["start"] >= 2.0]

    if len(viable) < num_segments:
        viable = ranked

    jump_points = []
    used_ranges = []

    for i in range(min(num_segments, len(viable))):
        target_dur = montage_durations[i] if i < len(montage_durations) else 1.0

        for seg in viable:
            start = seg["start"]
            end = seg["end"]

            overlaps = any(
                start < ue and end > us for us, ue in used_ranges
            )
            if overlaps:
                continue

            if seg["duration"] >= target_dur * 0.5:
                jump_points.append(start)
                used_ranges.append((start, start + target_dur + 0.1))
                break

    # --- Fallback for remaining slots ---
    if len(jump_points) < num_segments:
        cap = cv2.VideoCapture(video_path)
        total_dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()

        remaining = num_segments - len(jump_points)
        spacing = (total_dur - 6.0) / (remaining + 1)
        for j in range(remaining):
            jump_points.append(3.0 + spacing * (j + 1))

    print(f"  Selected {len(jump_points)} smart jump points "
          f"(top motion scores: {[f'{s['rank_score']:.2f}' for s in viable[:5]]})")

    return jump_points[:num_segments]
```

---

## Quick Reference: ffmpeg Scene Detection Commands

```bash
# Detect scene changes and output timestamps (threshold 0.4)
ffmpeg -i input.mp4 -filter:v "select='gt(scene,0.4)',showinfo" -an -f null - 2>&1 | \
  grep "pts_time" | awk -F'pts_time:' '{print $2}' | awk '{print $1}'

# Generate thumbnail mosaic at scene changes
ffmpeg -i input.mp4 \
  -vf "select=gt(scene\,0.4),scale=160:-1,tile=6x20" \
  -frames:v 1 -qscale:v 3 scene_mosaic.jpg

# Extract individual frame at each scene change
ffmpeg -i input.mp4 \
  -vf "select=gt(scene\,0.4)" \
  -vsync vfr scene_%04d.jpg

# Get scene scores with ffprobe (JSON-like output)
ffprobe -show_frames -of compact=p=0 \
  -f lavfi "movie=input.mp4,select=gt(scene\,0.3)" 2>/dev/null | \
  head -20

# Use scdet filter for rich scene change metadata
ffmpeg -i input.mp4 \
  -vf "scdet=s=1:t=10" \
  -an -f null - 2>&1 | grep lavfi.scd

# Extract a 2-second clip starting at a scene change
ffmpeg -ss 14.234 -i input.mp4 -t 2.0 -c:v libx264 -crf 18 clip.mp4
```

---

## Dependencies and Installation

```bash
# Core (already in our pipeline)
pip install opencv-python numpy

# Recommended (much better scene detection than ffmpeg alone)
pip install scenedetect[opencv]

# Optional convenience wrapper
pip install scenecut-extractor
```

---

## Performance Expectations

| Operation | 5-min source | 30-min source | 2-hr source |
|---|---|---|---|
| PySceneDetect (AdaptiveDetector) | ~8s | ~45s | ~5min |
| ffmpeg select scene filter | ~3s | ~15s | ~2min |
| Motion scoring (optical flow, 5fps sample) | ~15s | ~90s | ~10min |
| Motion scoring (frame diff, 5fps sample) | ~5s | ~30s | ~3min |
| Total (first run, PySceneDetect + optical flow) | ~25s | ~2.5min | ~15min |
| Total (cached, second run) | <1s | <1s | <1s |

The caching strategy means we pay the cost once per source video. Every subsequent edit using the same source loads instantly from the JSON cache.

---

## Integration Checklist

1. Create `sopranos_edit/scene_detect.py` with the complete module above
2. In `edit.py`, replace the random jump_points block (lines ~138-149) with the smart selection call, keeping the random fallback
3. Add `scenedetect[opencv]` to requirements or install manually
4. Run once on each source video to generate the cache file
5. Verify: the first edit will be slower (scene analysis), subsequent edits will be instant
6. Tune: adjust `adaptive_threshold` (PySceneDetect) or ffmpeg threshold (0.3-0.5) based on results
7. Optional: add `--smart-clips` flag to `edit.py` argparse to toggle between random and smart selection

---

## Sources

- [PySceneDetect GitHub](https://github.com/Breakthrough/PySceneDetect)
- [PySceneDetect Documentation](https://www.scenedetect.com/)
- [PySceneDetect Detection Algorithms API](https://www.scenedetect.com/docs/latest/api/detectors.html)
- [PySceneDetect Python API](https://www.scenedetect.com/api/)
- [PySceneDetect Package API](https://www.scenedetect.com/docs/latest/api.html)
- [ffmpeg Scene Detection Notes (gist)](https://gist.github.com/dudewheresmycode/054c8de34762091b43530af248b369e7)
- [ffmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html)
- [GDELT: Using FFMPEG Scene Detection for TV News](https://blog.gdeltproject.org/using-ffmpegs-scene-detection-to-generate-a-visual-shot-summary-of-television-news/)
- [scenecut-extractor GitHub](https://github.com/slhck/scenecut-extractor)
- [scenecut-extractor on PyPI](https://pypi.org/project/scenecut-extractor/)
- [PyImageSearch: Scene Boundary Detection with OpenCV](https://pyimagesearch.com/2019/08/19/simple-scene-boundary-shot-transition-detection-with-opencv/)
- [Sports Highlight Detector (GitHub)](https://github.com/AkhilNam/Sports-Highlight-Detector)
- [OpenCV Optical Flow Tutorial](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html)
- [LearnOpenCV: Optical Flow in OpenCV](https://learnopencv.com/optical-flow-in-opencv/)
- [ffmpeg Scene Detection and Keyframes (bogotobogo)](https://www.bogotobogo.com/FFMpeg/ffmpeg_thumbnails_select_scene_iframe.html)
- [Split Videos by Scene Detection Using FFmpeg](https://copyprogramming.com/howto/split-up-a-video-using-ffmpeg-through-scene-detection)
- [Video Scene Detection with PySceneDetect (Vultr Docs)](https://docs.vultr.com/video-scene-transition-detection-and-split-video-using-pyscenedetect)
