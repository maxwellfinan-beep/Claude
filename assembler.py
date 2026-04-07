"""Assemble processed clips and overlays into the final TikTok video."""

import numpy as np
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    vfx,
)
from PIL import Image, ImageFilter

import config
from color_grader import apply_grade_to_clip
from effects import (
    apply_slow_motion,
    apply_zoom_punch,
    make_flash_transition,
    apply_film_grain,
)


def _make_blurred_background(clip: VideoFileClip) -> ImageClip:
    """Blurred, darkened first-frame background scaled to fill 1080×1920."""
    frame = clip.get_frame(0)
    img = Image.fromarray(frame)

    orig_w, orig_h = img.size
    scale = config.TIKTOK_HEIGHT / orig_h
    new_w = int(orig_w * scale)
    img = img.resize((new_w, config.TIKTOK_HEIGHT), Image.LANCZOS)

    x_off = (new_w - config.TIKTOK_WIDTH) // 2
    img = img.crop((x_off, 0, x_off + config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT))
    img = img.filter(ImageFilter.GaussianBlur(radius=30))

    arr = np.array(img).astype(np.float32) * 0.45
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    return ImageClip(arr, duration=clip.duration)


def crop_to_vertical(clip: VideoFileClip) -> CompositeVideoClip:
    """
    Convert a 16:9 clip to 9:16 using the blur-pad technique.
    Background: blurred static image. Foreground: clip scaled to fit width,
    centered vertically.
    """
    target_w, target_h = config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT

    bg = _make_blurred_background(clip).with_duration(clip.duration)

    orig_w, orig_h = clip.size
    scale = target_w / orig_w
    scaled_h = int(orig_h * scale)
    fg = clip.with_effects([vfx.Resize(width=target_w)])

    y_pos = (target_h - scaled_h) // 2
    fg = fg.with_position(("center", y_pos))

    return CompositeVideoClip(
        [bg, fg],
        size=(target_w, target_h),
    ).with_duration(clip.duration)


def build_sequence(
    assignments: list[dict],
    add_flash: bool = True,
) -> list:
    """
    Process each beat slot and return a list of positioned clips.

    Per slot: trim → color grade → slow-mo or zoom → grain → vertical crop → set_start
    """
    output_clips = []
    flash_size = (config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT)

    for i, a in enumerate(assignments):
        src_clip: VideoFileClip = a["clip"]
        slot_dur: float = a["slot_duration"]
        slot_start: float = a["slot_start"]
        is_slow: bool = a["slow_mo"]

        # Trim source — pre-shorten for slow-mo so output is exactly slot_dur
        src_window = slot_dur * config.SLOW_MO_FACTOR if is_slow else slot_dur
        src_start = a["src_start"]
        src_end = min(src_start + src_window, src_clip.duration)
        if src_end <= src_start:
            src_start = max(0.0, src_clip.duration - src_window)
            src_end = src_clip.duration

        trimmed = src_clip.subclipped(src_start, src_end)

        # Color grade
        graded = apply_grade_to_clip(trimmed, strength=config.VIGNETTE_STRENGTH)

        # Speed / zoom
        if is_slow:
            effected = apply_slow_motion(graded, config.SLOW_MO_FACTOR)
            effected = apply_zoom_punch(effected, config.ZOOM_FACTOR_SLOWMO)
        else:
            effected = apply_zoom_punch(graded, config.ZOOM_FACTOR)

        # Film grain
        effected = apply_film_grain(effected, config.FILM_GRAIN_INTENSITY, seed=i)

        # 9:16 vertical
        vertical = crop_to_vertical(effected)
        vertical = vertical.with_start(slot_start)
        output_clips.append(vertical)

        # Flash between clips
        if add_flash and i < len(assignments) - 1:
            flash_start = max(0.0, a["slot_end"] - config.FLASH_DURATION / 2)
            flash = (
                make_flash_transition(size=flash_size, duration=config.FLASH_DURATION)
                .with_start(flash_start)
            )
            output_clips.append(flash)

    return output_clips


def composite_with_overlays(
    sequence: list,
    overlays: list,
    audio: AudioFileClip,
    total_duration: float,
) -> CompositeVideoClip:
    """Merge video, flashes, and text overlays. Z-order: video → flashes → text."""
    all_clips = sequence + overlays
    final = CompositeVideoClip(
        all_clips,
        size=(config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT),
    )
    final = final.with_audio(audio.subclipped(0, total_duration))
    final = final.with_duration(total_duration)
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
