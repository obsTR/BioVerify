from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


DEFAULT_MAX_DIM = 480
DEFAULT_MAX_FRAMES = 600  # ~20s at 30fps


def read_video(
    path: str,
    max_dim: Optional[int] = DEFAULT_MAX_DIM,
    max_frames: Optional[int] = DEFAULT_MAX_FRAMES,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Read a video into frames and timestamps.

    For long videos, reads the first `max_frames` contiguous frames
    to preserve the temporal resolution required for rPPG analysis.
    Sparse/uniform sampling would destroy the signal.

    Args:
        path: Path to the video file.
        max_dim: Max height/width in pixels. Resized proportionally.
        max_frames: Stop reading after this many frames.

    Returns:
        (frames, timestamps, fps)
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    if fps <= 0:
        fps = 30.0

    # Pre-compute resize dimensions
    scale = None
    new_w, new_h = 0, 0
    if max_dim is not None:
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if orig_w > 0 and orig_h > 0 and max(orig_w, orig_h) > max_dim:
            scale = max_dim / max(orig_w, orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)

    frames = []
    timestamps = []
    idx = 0

    while True:
        if max_frames and len(frames) >= max_frames:
            break

        ret, frame = cap.read()
        if not ret:
            break

        if scale is not None:
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        frames.append(frame)
        timestamps.append(idx / fps)
        idx += 1

    cap.release()

    if not frames:
        return np.array([]), np.array([]), float(fps)

    return np.array(frames), np.array(timestamps), float(fps)
