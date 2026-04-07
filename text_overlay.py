"""Build text and stats overlays for the TikTok edit."""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, TextClip, vfx

import config


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if os.path.exists(config.FONT_PATH):
        return ImageFont.truetype(config.FONT_PATH, size)
    return ImageFont.load_default()


def make_player_nameplate(
    name: str,
    clip_duration: float,
    position: tuple = ("center", 0.80),
) -> TextClip:
    """Large bold player name as a TextClip (moviepy 2.x API)."""
    font_arg = config.FONT_PATH if os.path.exists(config.FONT_PATH) else None
    tc = (
        TextClip(
            text=name,
            font=font_arg,
            font_size=config.NAMEPLATE_FONTSIZE,
            color="white",
            stroke_color="black",
            stroke_width=3,
            duration=clip_duration,
        )
        .with_position(position)
        .with_effects([vfx.FadeIn(0.15), vfx.FadeOut(0.15)])
    )
    return tc


def make_hype_text(
    text: str,
    start: float,
    duration: float,
) -> TextClip:
    """Centered hype text that pops on a beat."""
    font_arg = config.FONT_PATH if os.path.exists(config.FONT_PATH) else None
    tc = (
        TextClip(
            text=text,
            font=font_arg,
            font_size=config.HYPE_FONTSIZE,
            color="white",
            stroke_color="black",
            stroke_width=4,
            duration=duration,
        )
        .with_start(start)
        .with_position("center")
        .with_effects([vfx.FadeIn(0.08), vfx.FadeOut(0.08)])
    )
    return tc


def make_stats_card(
    stats: list[str],
    start: float,
    duration: float,
    canvas_size: tuple[int, int] = (config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT),
) -> ImageClip:
    """PIL-rendered stats card — no ImageMagick dependency."""
    font = _load_font(config.STATS_FONTSIZE)

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    line_heights = []
    max_w = 0
    for line in stats:
        bbox = draw.textbbox((0, 0), line, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        line_heights.append(h)
        max_w = max(max_w, w)

    pad = 24
    box_w = max_w + pad * 2
    box_h = sum(line_heights) + pad * 2 + 8 * (len(stats) - 1)

    card = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    bg = Image.new("RGBA", (box_w, box_h), (10, 10, 10, 190))
    card.paste(bg, (0, 0))

    draw = ImageDraw.Draw(card)
    y = pad
    for i, line in enumerate(stats):
        draw.text((pad, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_heights[i] + 8

    full = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    full.paste(card, (48, 160), mask=card)

    arr = np.array(full)
    clip = (
        ImageClip(arr, duration=duration)
        .with_start(start)
        .with_effects([vfx.FadeIn(0.2), vfx.FadeOut(0.2)])
    )
    return clip


def build_overlay_timeline(
    cut_points: list[float],
    total_duration: float,
    hype_texts: list[str],
    stats_lines: list[str],
    drop_regions: list[tuple[float, float]],
    use_imagemagick: bool = True,
) -> list:
    """Build all overlay clips timed to the beat grid."""
    overlays = []

    # ── Player nameplate ─────────────────────────────────────────────────────
    if use_imagemagick:
        try:
            overlays.append(make_player_nameplate(config.PLAYER_NAME, 2.5))
            end_plate = (
                make_player_nameplate(config.PLAYER_NAME, 3.0)
                .with_start(max(0.0, total_duration - 3.0))
            )
            overlays.append(end_plate)
        except Exception as exc:
            print(f"[text_overlay] Nameplate failed ({exc}), skipping")

    # ── Hype texts at drop regions ────────────────────────────────────────────
    hype_idx = 0
    for drop_start, _ in drop_regions:
        if hype_idx >= len(hype_texts):
            break
        nearest_beat = min(cut_points, key=lambda t: abs(t - drop_start))
        beat_dur = _slot_duration(cut_points, nearest_beat)
        if use_imagemagick:
            try:
                overlays.append(
                    make_hype_text(
                        hype_texts[hype_idx % len(hype_texts)],
                        start=nearest_beat,
                        duration=min(beat_dur * 2, 1.5),
                    )
                )
                hype_idx += 1
            except Exception as exc:
                print(f"[text_overlay] Hype text failed ({exc}), skipping")

    # ── Stats card ───────────────────────────────────────────────────────────
    stats_time = min(15.0, total_duration * 0.4)
    nearest_beat = min(cut_points, key=lambda t: abs(t - stats_time))
    overlays.append(make_stats_card(stats_lines, start=nearest_beat, duration=4.0))

    print(f"[text_overlay] Built {len(overlays)} overlay(s)")
    return overlays


def _slot_duration(cut_points: list[float], beat_time: float) -> float:
    try:
        idx = cut_points.index(beat_time)
        if idx + 1 < len(cut_points):
            return cut_points[idx + 1] - cut_points[idx]
    except ValueError:
        pass
    return 0.5
