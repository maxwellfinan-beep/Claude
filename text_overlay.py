"""Build text and stats overlays for the TikTok edit."""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, TextClip

import config


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the project font; fall back to PIL default if TTF not found."""
    if os.path.exists(config.FONT_PATH):
        return ImageFont.truetype(config.FONT_PATH, size)
    return ImageFont.load_default()


def make_player_nameplate(
    name: str,
    clip_duration: float,
    position: tuple = ("center", 0.80),
) -> TextClip:
    """
    Large bold player name rendered as a TextClip.
    Requires ImageMagick; callers should catch ImportError/OSError and
    fall back to make_pil_text_clip().
    """
    tc = (
        TextClip(
            name,
            fontsize=config.NAMEPLATE_FONTSIZE,
            font=config.FONT_PATH if os.path.exists(config.FONT_PATH) else "Impact",
            color="white",
            stroke_color="black",
            stroke_width=3,
        )
        .set_duration(clip_duration)
        .set_position(position)
        .fadein(0.15)
        .fadeout(0.15)
    )
    return tc


def make_hype_text(
    text: str,
    start: float,
    duration: float,
) -> TextClip:
    """Centered hype text that pops on a beat and fades quickly."""
    tc = (
        TextClip(
            text,
            fontsize=config.HYPE_FONTSIZE,
            font=config.FONT_PATH if os.path.exists(config.FONT_PATH) else "Impact",
            color="white",
            stroke_color="black",
            stroke_width=4,
        )
        .set_start(start)
        .set_duration(duration)
        .set_position("center")
        .fadein(0.08)
        .fadeout(0.08)
    )
    return tc


def make_stats_card(
    stats: list[str],
    start: float,
    duration: float,
    canvas_size: tuple[int, int] = (config.TIKTOK_WIDTH, config.TIKTOK_HEIGHT),
) -> ImageClip:
    """
    PIL-rendered stats card (no ImageMagick dependency).

    Draws semi-transparent dark box with white text lines,
    positioned in the upper-left area of the frame.
    """
    font = _load_font(config.STATS_FONTSIZE)

    # Measure text to size the box
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

    # Draw box + text on RGBA canvas
    card = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    bg = Image.new("RGBA", (box_w, box_h), (10, 10, 10, 190))
    card.paste(bg, (0, 0))

    draw = ImageDraw.Draw(card)
    y = pad
    for i, line in enumerate(stats):
        draw.text((pad, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_heights[i] + 8

    # Paste onto a full-frame transparent canvas so position is embedded
    full = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x_pos = 48
    y_pos = 160   # upper area, below TikTok UI safe zone
    full.paste(card, (x_pos, y_pos), mask=card)

    arr = np.array(full)
    # MoviePy ImageClip expects RGB or RGBA
    clip = (
        ImageClip(arr, ismask=False)
        .set_start(start)
        .set_duration(duration)
        .fadein(0.2)
        .fadeout(0.2)
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
    """
    Build the complete list of text/image overlay clips timed to the beat grid.

    Layout:
      - Player nameplate: first 2.5s and last 3s of the edit
      - Hype texts: one per drop region (at the drop start beat)
      - Stats card: once, ~15s into the edit (or midpoint if shorter)
    """
    overlays = []
    hype_cycle = list(hype_texts)

    # ── Player nameplate ─────────────────────────────────────────────────────
    if use_imagemagick:
        try:
            overlays.append(make_player_nameplate(config.PLAYER_NAME, 2.5))
            # End nameplate
            end_plate = (
                make_player_nameplate(config.PLAYER_NAME, 3.0)
                .set_start(max(0, total_duration - 3.0))
            )
            overlays.append(end_plate)
        except Exception as exc:
            print(f"[text_overlay] ImageMagick nameplate failed ({exc}), skipping")

    # ── Hype texts at drop regions ────────────────────────────────────────────
    hype_idx = 0
    for drop_start, drop_end in drop_regions:
        if hype_idx >= len(hype_cycle):
            break
        # Find the nearest beat to drop_start
        nearest_beat = min(cut_points, key=lambda t: abs(t - drop_start))
        beat_duration = _slot_duration(cut_points, nearest_beat)

        if use_imagemagick:
            try:
                overlays.append(
                    make_hype_text(
                        hype_cycle[hype_idx % len(hype_cycle)],
                        start=nearest_beat,
                        duration=min(beat_duration * 2, 1.5),
                    )
                )
                hype_idx += 1
            except Exception as exc:
                print(f"[text_overlay] Hype text failed ({exc}), skipping")

    # ── Stats card ───────────────────────────────────────────────────────────
    stats_time = min(15.0, total_duration * 0.4)
    nearest_beat = min(cut_points, key=lambda t: abs(t - stats_time))
    overlays.append(
        make_stats_card(stats_lines, start=nearest_beat, duration=4.0)
    )

    print(f"[text_overlay] Built {len(overlays)} overlay(s)")
    return overlays


def _slot_duration(cut_points: list[float], beat_time: float) -> float:
    """Return the duration of the slot that starts at beat_time."""
    try:
        idx = cut_points.index(beat_time)
        if idx + 1 < len(cut_points):
            return cut_points[idx + 1] - cut_points[idx]
    except ValueError:
        pass
    return 0.5
