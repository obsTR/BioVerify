from __future__ import annotations

from dataclasses import asdict
from typing import List

import numpy as np

from .config import Config
from .types import IngestResult, IngestWindow
from .utils.logging import get_logger, log_params
from .utils.video import read_video


logger = get_logger(__name__)


def _resample_frames(frames: np.ndarray, timestamps: np.ndarray, target_fps: float):
    if len(frames) == 0:
        return frames, timestamps

    duration = timestamps[-1] - timestamps[0]
    if duration <= 0:
        return frames, timestamps

    num_target = int(duration * target_fps)
    if num_target <= 1:
        return frames, timestamps

    new_times = np.linspace(timestamps[0], timestamps[-1], num_target)
    indices = np.clip(
        np.round((new_times - timestamps[0]) / (timestamps[1] - timestamps[0])).astype(
            int
        ),
        0,
        len(frames) - 1,
    )
    return frames[indices], new_times


def _make_windows(
    frames: np.ndarray,
    timestamps: np.ndarray,
    fps: float,
    window_seconds: float,
    overlap_ratio: float,
) -> List[IngestWindow]:
    total_duration = timestamps[-1] - timestamps[0] if len(timestamps) > 0 else 0.0
    if total_duration <= 0:
        return []

    step = window_seconds * (1.0 - overlap_ratio)
    windows: List[IngestWindow] = []
    start = timestamps[0]
    index = 0
    height, width = frames.shape[1:3] if len(frames) else (0, 0)

    while start < timestamps[-1]:
        end = start + window_seconds
        mask = (timestamps >= start) & (timestamps <= end)
        if not np.any(mask):
            start += step
            continue
        ts_w = timestamps[mask]
        duration = ts_w[-1] - ts_w[0]
        window = IngestWindow(
            index=index,
            start_time=float(ts_w[0]),
            end_time=float(ts_w[-1]),
            fps=float(fps),
            resolution={"width": int(width), "height": int(height)},
            duration=float(duration),
            dropped_frames_estimate=0.0,
        )
        windows.append(window)
        index += 1
        start += step

    return windows


def ingest_video(path: str, config: Config) -> IngestResult:
    log_params(logger, "ingest", {"path": path, "ingest": asdict(config.ingest)})

    frames, timestamps, fps = read_video(path)
    if len(frames) == 0:
        return IngestResult(
            windows=[],
            metrics={"error": "no_frames"},
            reasons=["too_short"],
        )

    duration = float(timestamps[-1] - timestamps[0])
    if duration < config.ingest.min_duration_seconds:
        return IngestResult(
            windows=[],
            metrics={"duration": duration},
            reasons=["too_short"],
        )

    frames_r, ts_r = _resample_frames(frames, timestamps, config.ingest.target_fps)

    windows = _make_windows(
        frames_r,
        ts_r,
        config.ingest.target_fps,
        config.ingest.window_seconds,
        config.ingest.overlap_ratio,
    )

    metrics = {
        "num_frames": int(len(frames_r)),
        "duration": duration,
        "source_fps": float(fps),
        "target_fps": float(config.ingest.target_fps),
        "num_windows": len(windows),
    }

    return IngestResult(windows=windows, metrics=metrics, reasons=[])

