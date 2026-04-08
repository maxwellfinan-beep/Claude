#!/usr/bin/env python3
"""ffmpeg filter chain builders for color grading, vignette, zoom punch, and text overlay.

All effects are applied in a single ffmpeg pass during export — no per-frame Python processing.
Supports 3 style presets: darkwave, cinematic, atmospheric.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# --- Style presets ---
STYLES = {
    "darkwave": {
        "contrast": 1.2,
        "brightness": -0.03,
        "saturation": 1.25,
        "colorbalance": "rs=-0.08:gs=-0.04:bs=0.12:rm=0.06:gm=0.02:bm=-0.08",
        "vignette_angle": "PI/4.5",
        "text_fade_in": 0.08,
        "text_hold": 1.5,
        "text_fade_out": 0.08,
        "text_border": 4,
        "zoom_factor": 1.3,
        "punch_duration": 0.2,
    },
    "cinematic": {
        "contrast": 1.15,
        "brightness": 0.02,
        "saturation": 1.1,
        "colorbalance": "rs=0.05:gs=0.02:bs=-0.03:rm=0.04:gm=0.01:bm=-0.05:rh=0.06:gh=0.03:bh=-0.04",
        "vignette_angle": "PI/5",
        "text_fade_in": 0.4,
        "text_hold": 2.0,
        "text_fade_out": 0.5,
        "text_border": 3,
        "zoom_factor": 1.2,
        "punch_duration": 0.3,
    },
    "atmospheric": {
        "contrast": 1.25,
        "brightness": -0.04,
        "saturation": 1.3,
        "colorbalance": "rs=-0.12:gs=-0.06:bs=0.18:rm=0.02:gm=-0.02:bm=0.04",
        "vignette_angle": "PI/4",
        "text_fade_in": 0.15,
        "text_hold": 1.2,
        "text_fade_out": 0.3,
        "text_border": 5,
        "zoom_factor": 1.35,
        "punch_duration": 0.2,
    },
}


def build_color_grade_filter(beat_drop_time, style="darkwave"):
    """Color grade with style presets. Activates at beat_drop_time."""
    t = beat_drop_time
    s = STYLES[style]
    c, b, sat = s["contrast"], s["brightness"], s["saturation"]
    cb = s["colorbalance"]

    eq_filter = (
        f"eq="
        f"contrast='if(gte(t\\,{t})\\,{c}\\,1.0)':"
        f"brightness='if(gte(t\\,{t})\\,{b}\\,0.0)':"
        f"saturation='if(gte(t\\,{t})\\,{sat}\\,1.0)'"
    )
    cb_filter = f"colorbalance={cb}:enable='gte(t\\,{t})'"

    return f"{eq_filter},{cb_filter}"


def build_vignette_filter(beat_drop_time, style="darkwave"):
    """Vignette with style-specific intensity. Only after beat drop."""
    angle = STYLES[style]["vignette_angle"]
    return f"vignette={angle}:enable='gte(t\\,{beat_drop_time})'"


def build_zoom_punch_filter(zoom_times, style="darkwave"):
    """Zoom punch at beat timestamps using crop+scale."""
    if not zoom_times:
        return None

    s = STYLES[style]
    zoom_factor = s["zoom_factor"]
    punch_duration = s["punch_duration"]

    w, h = config.WIDTH, config.HEIGHT
    crop_w = int(w / zoom_factor)
    crop_h = int(h / zoom_factor)
    x_off = (w - crop_w) // 2
    y_off = (h - crop_h) // 2

    between_exprs = [f"between(t\\,{t}\\,{t + punch_duration})" for t in zoom_times]
    any_active = "+".join(between_exprs)

    crop_filter = (
        f"crop="
        f"w='if({any_active}\\,{crop_w}\\,{w})':"
        f"h='if({any_active}\\,{crop_h}\\,{h})':"
        f"x='if({any_active}\\,{x_off}\\,0)':"
        f"y='if({any_active}\\,{y_off}\\,0)'"
    )
    scale_filter = f"scale={w}:{h}"

    return f"{crop_filter},{scale_filter}"


def build_text_overlay_filter(appear_time, style="darkwave"):
    """'THE SOPRANOS' — serif, center frame. Style controls fade timing."""
    s = STYLES[style]
    fade_in = s["text_fade_in"]
    hold = s["text_hold"]
    fade_out = s["text_fade_out"]
    border = s["text_border"]

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
        f"borderw={border}:bordercolor=black@0.6:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2:"
        f"alpha='{alpha_expr}':"
        f"enable='between(t\\,{t_start}\\,{t_end})'"
    )


def build_full_filter_chain(project_state, style="darkwave"):
    """
    Combine all filters into a single -vf string.
    Order: color grade -> vignette -> zoom punch -> text overlay
    """
    beat_drop = project_state["beat_drop_time"]
    zoom_times = project_state.get("zoom_punch_times", [])
    title_time = project_state.get("title_appear_time", beat_drop)

    filters = [
        build_color_grade_filter(beat_drop, style),
        build_vignette_filter(beat_drop, style),
    ]

    zoom_filter = build_zoom_punch_filter(zoom_times, style)
    if zoom_filter:
        filters.append(zoom_filter)

    filters.append(build_text_overlay_filter(title_time, style))

    return ",".join(filters)
