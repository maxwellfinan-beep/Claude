"""Video effects: slow motion, zoom punch, flash transitions, film grain."""

import numpy as np
from moviepy import VideoFileClip, ColorClip, vfx


def apply_slow_motion(
    clip: VideoFileClip,
    factor: float = 0.4,
) -> VideoFileClip:
    """
    Slow the clip to `factor` speed.
    The caller must pre-trim the source to (slot_duration * factor) seconds
    so the output is exactly slot_duration long after this call.
    """
    return clip.with_effects([vfx.MultiplySpeed(factor)])


def apply_zoom_punch(
    clip: VideoFileClip,
    zoom_to: float = 1.08,
) -> VideoFileClip:
    """Slow push-in zoom from 1.0× to zoom_to× over the clip's duration."""
    duration = clip.duration

    def resize_over_time(t: float):
        return 1.0 + (zoom_to - 1.0) * (t / duration)

    return clip.with_effects([vfx.Resize(resize_over_time)])


def make_flash_transition(
    size: tuple[int, int] = (1080, 1920),
    duration: float = 0.07,
) -> ColorClip:
    """Pure-white flash ColorClip inserted between cuts."""
    return ColorClip(size=size, color=[255, 255, 255], duration=duration)


def apply_film_grain(
    clip: VideoFileClip,
    intensity: float = 0.025,
    seed: int = 0,
) -> VideoFileClip:
    """Add subtle film grain via per-frame numpy noise."""
    rng = np.random.default_rng(seed)

    def add_grain(frame: np.ndarray) -> np.ndarray:
        noise = rng.normal(0, intensity * 255, frame.shape)
        return np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return clip.image_transform(add_grain)
