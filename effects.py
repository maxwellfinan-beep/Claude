"""Video effects: slow motion, zoom punch, flash transitions, film grain."""

import numpy as np
from moviepy.editor import VideoFileClip, ColorClip
from moviepy.video.fx import all as vfx


def apply_slow_motion(
    clip: VideoFileClip,
    slot_duration: float,
    factor: float = 0.4,
) -> VideoFileClip:
    """
    Slow the clip to `factor` speed while keeping output exactly slot_duration long.

    Strategy: take a shorter source window (slot_duration * factor seconds of
    source footage), then speedx by factor → result is slot_duration seconds.
    The clip must already be trimmed to at most (slot_duration * factor) long
    before this is called; assembler.py handles the trimming.
    """
    return clip.fx(vfx.speedx, factor)


def apply_zoom_punch(
    clip: VideoFileClip,
    zoom_to: float = 1.08,
) -> VideoFileClip:
    """
    Slow push-in zoom over the clip's full duration.
    zoom_to=1.08 adds an 8% zoom — subtle on normal cuts.
    Use 1.15 for slow-mo moments.
    """
    duration = clip.duration

    def resize_over_time(t: float):
        # Linear zoom from 1.0 to zoom_to
        return 1.0 + (zoom_to - 1.0) * (t / duration)

    return clip.resize(resize_over_time)


def make_flash_transition(
    size: tuple[int, int] = (1080, 1920),
    duration: float = 0.07,
) -> ColorClip:
    """
    Pure-white ColorClip used as a hard flash between cuts.
    Keep duration ≤ 3 frames (0.1s) so it reads as a flash, not a glitch.
    """
    return ColorClip(size=size, color=[255, 255, 255], duration=duration)


def apply_film_grain(
    clip: VideoFileClip,
    intensity: float = 0.025,
    seed: int = 0,
) -> VideoFileClip:
    """
    Add subtle film grain via per-frame numpy noise.
    intensity is the std-dev of the normal distribution (0–1 scale).
    """
    rng = np.random.default_rng(seed)

    def add_grain(frame: np.ndarray) -> np.ndarray:
        noise = rng.normal(0, intensity * 255, frame.shape)
        noisy = frame.astype(np.float32) + noise
        return np.clip(noisy, 0, 255).astype(np.uint8)

    return clip.fl_image(add_grain)
