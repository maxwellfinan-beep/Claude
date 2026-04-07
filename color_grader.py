"""Per-frame cinematic color grade using numpy (no pixel loops)."""

import numpy as np
from moviepy import VideoFileClip

import config


def _build_vignette_mask(height: int, width: int, strength: float) -> np.ndarray:
    """
    Pre-compute a float32 vignette mask of shape (H, W, 1).
    strength=0 → no darkening; strength=1 → edges go black.
    """
    cy, cx = height / 2, width / 2
    y, x = np.ogrid[:height, :width]
    dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    mask = np.exp(-dist ** 2 / (2 * (0.7 ** 2)))
    mask = 1 - strength * (1 - mask)
    return mask[:, :, np.newaxis].astype(np.float32)


def cinematic_grade(
    frame: np.ndarray,
    vignette_mask: np.ndarray,
) -> np.ndarray:
    """
    Apply a teal-and-orange cinematic look to a single frame.
    frame: uint8 H×W×3 RGB
    """
    f = frame.astype(np.float32) / 255.0

    # S-curve contrast
    f = np.where(f < 0.5,
                 0.5 * (2 * f) ** 0.85,
                 1 - 0.5 * (2 * (1 - f)) ** 0.85)

    # Shadow warmth: boost reds in dark pixels
    luma = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
    shadow_mask = np.clip(1 - luma * 2, 0, 1)[..., np.newaxis]
    f[..., 0] = np.clip(f[..., 0] + 0.06 * shadow_mask[..., 0], 0, 1)

    # Midtone cyan
    mid_mask = np.clip(1 - np.abs(luma - 0.5) * 4, 0, 1)[..., np.newaxis]
    f[..., 1] = np.clip(f[..., 1] + 0.03 * mid_mask[..., 0], 0, 1)
    f[..., 2] = np.clip(f[..., 2] + 0.05 * mid_mask[..., 0], 0, 1)

    # Slight desaturation
    gray = luma[..., np.newaxis]
    f = f * 0.88 + gray * 0.12

    # Vignette
    f = f * vignette_mask

    return np.clip(f * 255, 0, 255).astype(np.uint8)


def apply_grade_to_clip(clip: VideoFileClip, strength: float = 0.4) -> VideoFileClip:
    """Wrap a VideoFileClip with per-frame cinematic grading (moviepy 2.x)."""
    h, w = clip.size[1], clip.size[0]
    vignette_mask = _build_vignette_mask(h, w, strength)

    def grade_frame(frame: np.ndarray) -> np.ndarray:
        return cinematic_grade(frame, vignette_mask)

    return clip.image_transform(grade_frame)
