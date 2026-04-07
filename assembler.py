"""Assemble processed clips and overlays into the final TikTok video."""

import numpy as np
from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
)
from moviepy.video.fx import all as vfx
from PIL import Image, ImageFilter

import config
from color_grader import apply_grade_to_clip
from effects import (
    apply_slow_motion,
    apply_zoom_punch,
    make_flash_transition,
    apply_film_grain,
)


# ── Vertical crop helpers ────────────────────────────────────────────────────

def _make_blurred_background(clip: VideoFileClip) -> ImageClip:
    """
    Generate a static blurred background from the first frame of a clip,
    scaled to fill 1080×1920.
    """
    frame = clip.get_frame(0)  # H×W×3 uint8
    img = Image.fromarray(frame)

    # Scale to fill height (1920), let width overflow, then crop to 1080
    orig_w, orig_h = img.size
    scale = config.TIKTOK_HEIGHT / orig_h
    new_w = int(orig_w * scale)
    img = img.resize((new_w, config.TIKTOK_HEIGHT), Image.LANCZOS)

    # Crop to target width
    x_off = (new_w - config.TIKTOK_WIDTH) // 2
    img = img.crop((x_off, 0, x_off + config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT))

    # Heavy blur
    img = img.filter(ImageFilter.GaussianBlur(radius=30))

    # Darken so subject pops
    arr = np.array(img).astype(np.float32) * 0.45
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    return ImageClip(arr, duration=clip.duration)


def crop_to_vertical(clip: VideoFileClip) -> CompositeVideoClip:
    """
    Convert a 16:9 landscape clip to 9:16 vertical using the blur-pad technique:
      - Background: blurred, darkened, full-bleed version of the same clip
      - Foreground: original clip scaled to fit width (letterboxed if needed)
        centered vertically

    Returns a CompositeVideoClip of size (TIKTOK_WIDTH, TIKTOK_HEIGHT).
    """
    target_w, target_h = config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT

    # ── Background: blurred static image tiled for clip duration ────────────
    bg = _make_blurred_background(clip).set_duration(clip.duration)

    # ── Foreground: scale clip to fit width ──────────────────────────────────
    orig_w, orig_h = clip.size
    scale = target_w / orig_w
    scaled_h = int(orig_h * scale)
    fg = clip.resize(width=target_w)

    # Center vertically
    y_pos = (target_h - scaled_h) // 2
    fg = fg.set_position(("center", y_pos))

    return CompositeVideoClip(
        [bg, fg],
        size=(target_w, target_h),
    ).set_duration(clip.duration)


# ── Main sequence builder ────────────────────────────────────────────────────

def build_sequence(
    assignments: list[dict],
    add_flash: bool = True,
) -> list:
    """
    Process each clip assignment and build a list of positioned clips
    ready for final compositing.

    For each assignment:
      1. Trim source clip to the correct window
         (shorter for slow-mo so speedx produces the right output duration)
      2. Apply color grade
      3. Apply slow-mo + stronger zoom, OR regular zoom
      4. Apply film grain
      5. Crop to 9:16 vertical
      6. set_start() to the beat timestamp
      7. Optionally insert a white flash clip between beats

    Returns flat list of clips (all with .start set).
    """
    output_clips = []
    flash_size = (config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT)

    for i, a in enumerate(assignments):
        src_clip: VideoFileClip = a["clip"]
        slot_dur: float = a["slot_duration"]
        slot_start: float = a["slot_start"]
        is_slow: bool = a["slow_mo"]

        # ── Trim source window ───────────────────────────────────────────────
        if is_slow:
            # Pre-shorten: extract only (slot_dur * factor) seconds of source
            # so after speedx the output is exactly slot_dur long
            src_window = slot_dur * config.SLOW_MO_FACTOR
        else:
            src_window = slot_dur

        src_start = a["src_start"]
        src_end = min(src_start + src_window, src_clip.duration)
        # Guard: if clip is too short, take what's available
        if src_end <= src_start:
            src_start = max(0.0, src_clip.duration - src_window)
            src_end = src_clip.duration

        trimmed = src_clip.subclip(src_start, src_end)

        # ── Color grade ──────────────────────────────────────────────────────
        graded = apply_grade_to_clip(trimmed, strength=config.VIGNETTE_STRENGTH)

        # ── Speed / zoom effects ─────────────────────────────────────────────
        if is_slow:
            effected = apply_slow_motion(graded, slot_dur, config.SLOW_MO_FACTOR)
            effected = apply_zoom_punch(effected, config.ZOOM_FACTOR_SLOWMO)
        else:
            effected = apply_zoom_punch(graded, config.ZOOM_FACTOR)

        # ── Film grain ───────────────────────────────────────────────────────
        effected = apply_film_grain(effected, config.FILM_GRAIN_INTENSITY, seed=i)

        # ── Crop to 9:16 ─────────────────────────────────────────────────────
        vertical = crop_to_vertical(effected)

        # ── Position on timeline ─────────────────────────────────────────────
        vertical = vertical.set_start(slot_start)
        output_clips.append(vertical)

        # ── Flash transition (between clips, not after last) ──────────────────
        if add_flash and i < len(assignments) - 1:
            flash_start = a["slot_end"] - config.FLASH_DURATION / 2
            flash = (
                make_flash_transition(size=flash_size, duration=config.FLASH_DURATION)
                .set_start(max(0.0, flash_start))
            )
            output_clips.append(flash)

    return output_clips


# ── Final composite + export ─────────────────────────────────────────────────

def composite_with_overlays(
    sequence: list,
    overlays: list,
    audio: AudioFileClip,
    total_duration: float,
) -> CompositeVideoClip:
    """
    Merge video sequence, flash transitions, and text overlays.
    Z-order: background clips → flashes → text overlays (top).
    """
    all_clips = sequence + overlays
    final = CompositeVideoClip(
        all_clips,
        size=(config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT),
    )
    final = final.set_audio(audio.subclip(0, total_duration))
    final = final.set_duration(total_duration)
    return final


def export(final_clip: CompositeVideoClip, output_path: str) -> None:
    """Write the final clip to disk as a TikTok-compatible MP4."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"[assembler] Exporting to {output_path} ...")
    final_clip.write_videofile(
        output_path,
        fps=config.FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        ffmpeg_params=["-crf", "18"],
        preset="fast",
        threads=4,
        logger="bar",
    )
    print(f"[assembler] Done: {output_path}")
