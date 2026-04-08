#!/usr/bin/env python3
"""ffmpeg filter chain builders for color grading, vignette, zoom punch, and text overlay.

All effects are applied in a single ffmpeg pass during export — no per-frame Python processing.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


def build_color_grade_filter(beat_drop_time):
    """
    Teal-orange look with crushed blacks. Activates at beat_drop_time.

    curves: teal in shadows (lifted blue), orange in highlights (pulled blue),
            crushed black point on R/G channels.
    eq: contrast 1.2, brightness -0.05, saturation 1.3
    colorbalance: teal shadows, orange midtones, teal-leaning highlights
    """
    t = beat_drop_time
    # Minimal grade — slight warmth and contrast boost, keep natural look
    return (
        f"eq="
        f"contrast='if(gte(t\\,{t})\\,1.1\\,1.0)':"
        f"brightness='if(gte(t\\,{t})\\,0.02\\,0.0)':"
        f"saturation='if(gte(t\\,{t})\\,1.15\\,1.0)'"
    )


def build_vignette_filter(beat_drop_time):
    """Subtle vignette — just enough edge darkening. Only after beat drop."""
    return f"vignette=PI/5:enable='gte(t\\,{beat_drop_time})'"


def build_zoom_punch_filter(zoom_times, zoom_factor=1.3, punch_duration=0.25):
    """
    Zoom punch at each eye-contact timestamp.

    Uses crop+scale instead of zoompan for simpler video passthrough:
    - Calculate crop region for zoom_factor centered on frame
    - Apply between() expressions for each timestamp
    """
    if not zoom_times:
        return None

    w, h = config.WIDTH, config.HEIGHT
    crop_w = int(w / zoom_factor)
    crop_h = int(h / zoom_factor)
    x_off = (w - crop_w) // 2
    y_off = (h - crop_h) // 2

    # Build enable expression: any of the zoom windows active
    between_exprs = [f"between(t\\,{t}\\,{t + punch_duration})" for t in zoom_times]
    any_active = "+".join(between_exprs)

    # Crop to center region when zoom is active, then scale back to full size
    crop_filter = (
        f"crop="
        f"w='if({any_active}\\,{crop_w}\\,{w})':"
        f"h='if({any_active}\\,{crop_h}\\,{h})':"
        f"x='if({any_active}\\,{x_off}\\,0)':"
        f"y='if({any_active}\\,{y_off}\\,0)'"
    )
    scale_filter = f"scale={w}:{h}"

    return f"{crop_filter},{scale_filter}"


def build_text_overlay_filter(appear_time, fade_in=0.5, hold=1.0, fade_out=0.5):
    """
    'THE SOPRANOS' — clean serif, center frame.
    Fades in at the drop, holds 1s, fades out. Total visible: 2.0s.
    """
    t_start = appear_time
    t_fade_in_end = t_start + fade_in
    t_hold_end = t_fade_in_end + hold
    t_end = t_hold_end + fade_out

    alpha_expr = (
        f"if(lt(t\\,{t_start})\\,0\\,"
        f"if(lt(t\\,{t_fade_in_end})\\,(t-{t_start})/{fade_in}\\,"
        f"if(lt(t\\,{t_hold_end})\\,1\\,"
        f"if(lt(t\\,{t_end})\\,({t_end}-t)/{fade_out}\\,0))))"
    )

    return (
        f"drawtext="
        f"text='{config.TITLE_TEXT}':"
        f"fontfile={config.FONT_PATH}:"
        f"fontsize={config.TITLE_FONTSIZE}:"
        f"fontcolor=white:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2:"
        f"alpha='{alpha_expr}':"
        f"enable='between(t\\,{t_start}\\,{t_end})'"
    )


def build_full_filter_chain(project_state):
    """
    Combine all filters into a single -vf string.
    Order: color grade -> vignette -> zoom punch -> text overlay
    """
    beat_drop = project_state["beat_drop_time"]
    zoom_times = project_state.get("zoom_punch_times", [])
    title_time = project_state.get("title_appear_time", beat_drop)

    filters = [
        build_color_grade_filter(beat_drop),
        build_vignette_filter(beat_drop),
    ]

    zoom_filter = build_zoom_punch_filter(zoom_times)
    if zoom_filter:
        filters.append(zoom_filter)

    filters.append(build_text_overlay_filter(title_time))

    return ",".join(filters)
